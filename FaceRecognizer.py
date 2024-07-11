import numpy as np
import os
import random
import cv2
import glob

from insightface.app import FaceAnalysis

MAX_EMBEDDING_NUM = 15

class FaceRecognizer(FaceAnalysis):
    def __init__(self, 
                 ctx_id = 0, 
                 det_thresh = 0.5, det_size = (320, 320), 
                 name = 'face_lmk', 
                 providers = ['CUDAExecutionProvider'], 
                 allowed_modules = ['detection', 'recognition', 'landmark_2d_106']):
        super().__init__(name = name, providers = providers, allowed_modules = allowed_modules)
        self.prepare(ctx_id, det_thresh, det_size)

    def generate_embeddings(self, data_path):
        embeddings = []
        files = glob.glob(f'{data_path}\*.png')
        
        for file in files:
            img = cv2.imread(file)
            faces = self.get(img)

            if len(faces) != 1:
                print(f'FaceRecognizer::generate_embeddings: In {os.path.basename(data_path)}\'s dataset: {file} has {len(faces)} faces!')
                continue

            face = faces[0]
            embeddings.append(face.normed_embedding)
            
        if len(embeddings) == 0:
            print(f'FaceRecognizer::generate_embeddings: No any face detected in {os.path.basename(data_path)}\'s dataset!')
            return None
        if len(embeddings) > MAX_EMBEDDING_NUM:
            embeddings = random.choices(embeddings, k = MAX_EMBEDDING_NUM)

        return np.stack(embeddings, axis=0) # turn into Ndarray

    def get_faces(self, image):
        faces = self.get(image)
        return faces

    def get_name(self, image, face, fdm, create_new_face=False, face_quality = 0.7, search_threshold=0.3):
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
        if face.det_score < face_quality: # make sure the quality of face is good
            return None
        pred_name_score = self._search_average(face.normed_embedding, fdm.get_name_embeddings_dict(), search_threshold)
        if pred_name_score == None and create_new_face:
            face_image = self._crop_face_image(image, face)
            if self.get(face_image) == []:
                return None
            
            print('FaceRecognizer:get_name: No corresponding name found')
            print('FaceRecognizer:get_name: Creating new person...')
            new_name = fdm.add_new_face(face_image) # add a new face to database and let fdm decide the name
            print(f'FaceRecognizer:get_name: new person name: {new_name}')
            return (new_name, 1)
                  
        return pred_name_score
    
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
        
    def _search_average(self, emb_to_search, name_embedding_dict, threshold):
        '''
        input:
        emb_to_search: Face.normed_embedding
        threshold: float

        output:
        name_score: [name, score] of founded result
        None if not found
        '''
        name_scores = []
        for name, embs in name_embedding_dict.items():
            score = np.dot(emb_to_search, embs.T)
            name_scores.append((name, np.average(score)))

        if len(name_scores) == 0:
            return None
        
        idx = np.argmax(name_scores, axis=0)[1] # id of max average score
        score = name_scores[idx][1]
        if score > threshold:
            return name_scores[idx]
        else:
            return None
    
    def _crop_face_image(self, image, face):
        box = face.bbox.astype(int)
        return image[box[1]:box[3], box[0]:box[2]]
    