import numpy as np
import os
import shutil
import glob
import cv2

from FaceRecognizer import FaceRecognizer

class FaceDatabaseManager:
    def __init__(self, root, face_recognizer: FaceRecognizer = None, new_member_prefix = 'new_member_'):
        self.database_root = root
        self.face_recognizer = face_recognizer
        if face_recognizer is not None:
            self.have_face_recognizer = True
        else:
            self.have_face_recognizer = False
            print('Warning: FaceDatabaseManager don\'t have a FaceRecognizer, some function will be disabled!')
        self.new_member_prefix = new_member_prefix
        
        if not os.path.exists(self.database_root):
            os.mkdir(self.database_root)
        self.load_data()
        
    def load_data(self):
        names_without_embeddings = []
        self.name_embeddings_dict = {}
        
        self._load_names()
        for name in self.names:
            embaddings_path = os.path.join(self.database_root, name, 'embeddings.npy')
            if not os.path.exists(embaddings_path):
                names_without_embeddings.append(name)
                print(f"Embeddings of {name} does not exist, path:{embaddings_path}")
                continue
            
            # load embeddings
            embaddings = np.load(embaddings_path, allow_pickle=True)
            self.name_embeddings_dict[name] = embaddings
            
        if len(names_without_embeddings) > 0:
            print(f'Names without embeddings: {names_without_embeddings}')
            self.generate_embeddings()
   
    def get_name_list(self):
        if len(self.names) == 0:
            return None
        return self.names
    
    def get_name_embeddings_dict(self):
        return self.name_embeddings_dict
    
    def generate_embeddings(self, regenerate_all = False):
        if not self.have_face_recognizer:
            print('FaceDatabaseManager::generate_embeddings: FaceRecognizer is not set!')
            return

        self._load_names()
        
        if regenerate_all:
            for name in self.names:
                folder_path = os.path.join(self.database_root, name)
                embaddings_path = os.path.join(folder_path, 'embeddings.npy')
                stack = self.face_recognizer.generate_embeddings(folder_path)
                if stack is None:
                    continue
                np.save(embaddings_path, stack)
        else:
            names_without_embeddings = []
            for name in self.names:
                if name not in self.name_embeddings_dict:
                    names_without_embeddings.append(name)
                    
            for name in names_without_embeddings:
                folder_path = os.path.join(self.database_root, name)
                embaddings_path = os.path.join(folder_path, 'embeddings.npy')
                np.save(embaddings_path, self.face_recognizer.generate_embeddings(folder_path))

    def add_new_face(self, image, name = ''):
        if not self.have_face_recognizer:
            print('FaceDatabaseManager::add_new_face: FaceRecognizer is not set!')
            return
        
        self._load_names()
        
        if name in self.names:
            embaddings_path = os.path.join(self.database_root, name, 'embeddings.npy')
            if os.path.exists(embaddings_path):
                os.remove(embaddings_path)
        elif name == '':
            name = self._generate_name() #generate a new name for new face
            os.makedirs(os.path.join(self.database_root, name), exist_ok=True)
        else:
            os.makedirs(os.path.join(self.database_root, name), exist_ok=True)
            
        id = 0
        while os.path.exists(os.path.join(self.database_root, name, f'{id}.png')):
            id += 1
        cv2.imwrite(os.path.join(self.database_root, name, f'{id}.png'), image)
            
        self.generate_embeddings()
        self.load_data()
        
        return name
    
    def smart_merge_faces(self, threshold = 0.3):
        if not self.have_face_recognizer:
            print('FaceDatabaseManager::smart_merge_faces: FaceRecognizer is not set!')
            return
        
        single_emb_names = []
        multi_emb_dict = {}
        for name in self.names:
            if len(self.name_embeddings_dict[name]) == 1:
                single_emb_names.append(name)
            else:
                multi_emb_dict[name] = self.name_embeddings_dict[name]
        
        not_merged_names = []
        for name in single_emb_names:
            embaddings = self.name_embeddings_dict[name][0]
            pred_name_score = self.face_recognizer._search_average(embaddings, multi_emb_dict, threshold)
            if pred_name_score == None:
                not_merged_names.append(name)
                continue
            pred_name = pred_name_score[0]
            self.rename_face(name, pred_name)
        
        not_merged_names.reverse()
        for i in range(len(not_merged_names)):
            emb = self.name_embeddings_dict[not_merged_names[i]][0]
            for j in range(i+1, len(not_merged_names)):
                emb2 = self.name_embeddings_dict[not_merged_names[j]][0]
                score = np.dot(emb, emb2.T)
                if score > threshold:
                    self.rename_face(not_merged_names[i], not_merged_names[j])
                
    def store_embeddings(self):
        for name, embaddings in self.name_embeddings_dict.items():
            embaddings_path = os.path.join(self.database_root, name, 'embeddings.npy')
            np.save(embaddings_path, embaddings)
    
    def rename_face(self, old_name, new_name):
        if old_name == new_name:
            print(f'new name "{new_name}" is the same as old name "{old_name}"')
            return

        self._load_names()
        if old_name not in self.names:
            print(f'Name "{old_name}" does not exist in the database')
            return

        if new_name in self.names:
            print(f'Group "{old_name}" into "{new_name}"')
            for file in glob.glob(os.path.join(self.database_root, old_name, '*.png')):
                new_file_path = os.path.join(self.database_root, new_name, os.path.basename(file))
                i = 0
                while os.path.exists(new_file_path):
                    new_file_path = os.path.join(self.database_root, new_name, f'{i}.png')
                    i+=1
                shutil.move(file, new_file_path)
                
            shutil.rmtree(os.path.join(self.database_root, old_name))
            folder_path = os.path.join(self.database_root, new_name)
            embaddings_path = os.path.join(folder_path, 'embeddings.npy')
            np.save(embaddings_path, self.face_recognizer.generate_embeddings(folder_path))
            self.load_data()
        else:
            os.rename(os.path.join(self.database_root, old_name), os.path.join(self.database_root, new_name))
            print(f'{old_name} renamed to {new_name}')
            self.load_data()
                
    def delete_face(self, name):
        if name not in self.names:
            print(f'Name "{name}" does not exist in the database')
            return

        shutil.rmtree(os.path.join(self.database_root, name))
        self.load_data()
    
    def _load_names(self):
        # load all names in database into self.names
        if not os.path.exists(self.database_root):
            os.mkdir(self.database_root)
        names = os.listdir(self.database_root)
        self.names = [name for name in names if os.path.isdir(os.path.join(self.database_root, name))] # filter out non-folder
        
    def _generate_name(self):
        self._load_names()
        i = 0
        while True:
            name = f'{self.new_member_prefix}{i}'
            if name not in self.names:
                return name
            i += 1
     