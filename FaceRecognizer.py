import numpy as np
import os
import random
import cv2
import glob

from insightface.app import FaceAnalysis

MAX_EMBEDDING_NUM = 10

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
        for file in glob.glob(f'{data_path}\*.png'):
            img = cv2.imread(file)
            faces = self.get(img)

            if len(faces) != 1:
                print(f'dataset warning:In {os.path.basename(data_path)}\'s dataset: {file} has {len(faces)} faces!')
                continue

            face = faces[0]
            embeddings.append(face.normed_embedding)
            
        if len(embeddings) == 0:
            print(f'dataset error:No any face detected in {os.path.basename(data_path)}\'s dataset!')
            return None
        if len(embeddings) > MAX_EMBEDDING_NUM:
            embeddings = random.choices(embeddings, k = MAX_EMBEDDING_NUM)

        return np.stack(embeddings, axis=0) # turn into Ndarray

    def get_faces(self, image):
        faces = self.get(image)
        if len(faces) == 0:
            return None
        return faces

    def get_name(self, face, fdm, threshold=0.5):
        '''
        input:
        image: mat_like image
        threshold: float
        fdm: FaceDatabaseManager

        output:
        faces: list[Face] all faces in the image
        pred_names: list[str] predited name for each face
        '''
        pred_name_score = self._search_average(face.normed_embedding, fdm.get_name_embeddings_dict(), threshold)
        if pred_name_score == None:
            print('FaceRecognizer:get_name: No corresponding name found')
            print('creating new person...')
            fdm.add_new_person()
            return
        for i in range(len(pred_results)):
            if pred_results[i] == None:
                face_image = self._crop_face_image(image, faces[i])
                cv2.imwrite(f'test_face_crop_output{i}.png', face_image)
                
        return pred_results
    
    def get_landmarks(self, image):
        faces = self.get(image)
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
        name: str
        None if not found
        '''
        name_scores = []
        for name, embs in name_embedding_dict.items():
            score = np.dot(emb_to_search, embs.T)
            name_scores.append((name, np.average(score)))
            
        idx = np.argmax(name_scores, axis=0)[1] # id of max average score
        score = name_scores[idx][1]
        if score > threshold:
            return name_scores[idx]
        else:
            return None
    
    def _crop_face_image(self, image, face):
        box = face.bbox.astype(int)
        return image[box[1]:box[3], box[0]:box[2]]
    