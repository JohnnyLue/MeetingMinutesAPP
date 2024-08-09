import numpy as np
import os
import random
import cv2
import glob

from insightface.app import FaceAnalysis

MAX_EMBEDDING_NUM = 15
GOOD_FACE_QUALITY = 0.8
LEAST_IMG_SIZE = 80

class FaceRecognizer(FaceAnalysis):
    def __init__(self, 
                 ctx_id = 0, 
                 det_thresh = 0.5, det_size = (320, 320), 
                 name = 'face_lmk', 
                 providers = ['CUDAExecutionProvider'], 
                 allowed_modules = ['detection', 'recognition', 'landmark_2d_106']):
        super().__init__(name = name, providers = providers, allowed_modules = allowed_modules)
        self.prepare(ctx_id, det_thresh, det_size)

    def generate_embedding(self, img):
        if img.shape[0] < LEAST_IMG_SIZE or img.shape[1] < LEAST_IMG_SIZE:
                print(f'FaceRecognizer::generate_embeddings: image is too small.')
                return None
            
        faces = self.get(img)
        if len(faces) != 1:
            print(f'FaceRecognizer::generate_embeddings: The image has {len(faces)} faces.')
            return None
        if faces[0].det_score < GOOD_FACE_QUALITY:
            print(f'FaceRecognizer::generate_embeddings: The image has bad quality face.')
            return None
        embeddings = np.stack([faces[0].normed_embedding], axis=0) # turn into Ndarray
        return embeddings
    
    def generate_embeddings_from_folder(self, image_folder):
        embeddings = []
        files = glob.glob(f'{image_folder}\*.png')
        
        for file in files:
            img = cv2.imread(file)
            if img.shape[0] < LEAST_IMG_SIZE or img.shape[1] < LEAST_IMG_SIZE:
                print(f'FaceRecognizer::generate_embeddings: In {os.path.basename(image_folder)}\'s dataset: {file} picture is too small.')
                continue
            
            faces = self.get(img)
            if len(faces) != 1:
                print(f'FaceRecognizer::generate_embeddings: In {os.path.basename(image_folder)}\'s dataset: {file} has {len(faces)} faces.')
                continue
            if faces[0].det_score < GOOD_FACE_QUALITY:
                print(f'FaceRecognizer::generate_embeddings: In {os.path.basename(image_folder)}\'s dataset: {file} has bad quality face.')
                continue
            
            embeddings.append(faces[0].normed_embedding)
            
        if len(embeddings) == 0:
            print(f'FaceRecognizer::generate_embeddings: No any valid face detected in {os.path.basename(image_folder)}\'s dataset!')
            return None
        if len(embeddings) > MAX_EMBEDDING_NUM:
            embeddings = random.choices(embeddings, k = MAX_EMBEDDING_NUM)
        embeddings = np.stack(embeddings, axis=0) # turn into Ndarray
        print(embeddings.shape, len(embeddings))
        return embeddings

    def get_faces(self, image):
        faces = self.get(image)
        return faces

    def get_name(self, image, face, fdm, create_new_face=False, new_face_threshold = 0.3, search_threshold=0.4):
        '''
        input:
        image: mat_like image
        face: Face to get name
        threshold: float
        fdm: FaceDatabaseManager

        output:
        pred_name_score: [name, score] of predited result
        None if face is not known and creating_new_face is set to false
        '''
        face_emb_dict = fdm.get_name_embeddings_dict()
        if face.det_score < GOOD_FACE_QUALITY: # make sure the quality of face is good
            return None
        
        if create_new_face:
            face_image = self._crop_face_image(image, face)
            if face_image.shape[0] < LEAST_IMG_SIZE or face_image.shape[1] < LEAST_IMG_SIZE: # make sure the quality of picture to add to database
                create_new_face = False
            if self.get(face_image) == []:
                create_new_face = False
            
        if len(face_emb_dict) == 0:
            if create_new_face:
                if self.get(face_image) == []:
                    print('FaceRecognizer::get_name: Just checking, should not be here.')
                    return None
                
                print('FaceRecognizer::get_name: No face in database, creating new face...')
                new_name = fdm.add_new_face(face_image, embedding = face.normed_embedding)
                return new_name
            else:
                return None
            
        pred_name_score = self._search_similar(face.normed_embedding, face_emb_dict)
        if pred_name_score is None:
            return None
        
        if pred_name_score[1] < search_threshold and create_new_face:
            if pred_name_score[1] < new_face_threshold: # create new face in database
                print('FaceRecognizer::get_name: Unrecognized face, creating new face in database...')
                new_name = fdm.add_new_face(face_image, embedding = face.normed_embedding)
                print(f'FaceRecognizer::get_name: New face created: {new_name}')
                return new_name
            else:
                fdm.add_new_face(face_image, name = pred_name_score[0], embedding = face.normed_embedding) # add new face data to this member
                return pred_name_score[0]
            
        if pred_name_score[1] > new_face_threshold: # atleast not a new face
            return pred_name_score[0]
        
        return None
    
    def get_landmark(self, face):
        if len(face.landmark_2d_106) == 106:
            return face.landmark_2d_106
        return None
        ret_lmks = []
        for face in faces:
            lmk = face.landmark_2d_106
            ret_lmks.append(lmk)
            #for i in range(lmk.shape[0]):
                
                #p = (int(lmk[i, 0]), int(lmk[i, 1]))
                #cv2.circle(tim, p, 1, color, 1, cv2.LINE_AA)
                #cv2.putText(tim, f'{i - 52}', p, cv2.FONT_HERSHEY_SIMPLEX, 0.5, color)
        return ret_lmks
        
    def _search_similar(self, emb_to_search, name_embedding_dict):
        '''
        return name with highest similarity score
        input:
        emb_to_search: Face.normed_embedding

        output:
        name_score: [name, score] of founded result
        None if not found
        '''
        if name_embedding_dict is None or len(name_embedding_dict) == 0:
            return None
        
        name_scores = []
        for name, embs in name_embedding_dict.items():
            scores = np.round(np.dot(emb_to_search, embs.T), 3)
            #print(scores, end=' ')
            highest_score = np.max(scores, axis=0)
            name_scores.append((name, highest_score))
        #print()
        name_scores.sort(reverse=True, key=lambda x: x[1])
        #print(name_scores)

        if len(name_scores) == 0:
            return None
        
        return name_scores[0]
    
    def _crop_face_image(self, image, face):
        box = face.bbox.astype(int)
        img_hei = image.shape[0]
        img_wid = image.shape[1]
        # 40% padding
        pedding = 0.4
        img = image[int(max(box[1] * (1.0 + pedding) - box[3] * pedding, 0)):int(min(box[3] * (1.0 + pedding) - box[1] * pedding, img_hei - 1)),
                    int(max(box[0] * (1.0 + pedding) - box[2] * pedding, 0)):int(min(box[2] * (1.0 + pedding) - box[0] * pedding, img_wid - 1))]
        return img
    