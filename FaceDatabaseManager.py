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
        
    def set_face_recognizer(self, face_recognizer: FaceRecognizer):
        self.face_recognizer = face_recognizer
        self.have_face_recognizer = True
        
    def set_new_member_prefix(self, new_member_prefix):
        self.new_member_prefix = new_member_prefix
        
    def load_data(self, generate_all = False, retry = True):
        '''
        Load data from database, including names and embeddings.
        if generate_all is True, generate embeddings for all faces in the database.
        if retry is True, regenerate embeddings for faces that failed to load once.
        '''
        unprocessed_names = []
        self.name_embeddings_dict = {}
        
        if generate_all:
            self.generate_database_embeddings()
        
        self._load_names()
        for name in self.names:
            embaddings_path = os.path.join(self.database_root, name, 'embeddings.npy')
            if not os.path.exists(embaddings_path):
                unprocessed_names.append(name)
                continue
            
            # load embeddings
            try:
                embaddings = np.load(embaddings_path, allow_pickle=True)
            except Exception as e:
                print(f'FaceDatabaseManager::load_data: Failed to load embeddings for {name}, error: {e}')
                unprocessed_names.append(name)
                continue
            
            self.name_embeddings_dict[name] = embaddings
            
        if len(unprocessed_names) > 0 and retry:
            print(f'FaceDatabaseManager::load_data: Try to generate embeddings for: {unprocessed_names}')
            self.generate_database_embeddings(unprocessed_names)
            self.load_data(retry = False)
   
    def get_name_list(self):
        if len(self.names) == 0:
            return None
        return self.names
    
    def get_name_embeddings_dict(self):
        return self.name_embeddings_dict
    
    def generate_database_embeddings(self, names_to_process = None):
        '''
        Generate embeddings files for faces in the database, if not assign names_to_process, generate all
        '''
        if not self.have_face_recognizer:
            print('FaceDatabaseManager::generate_embeddings: FaceRecognizer is not set!')
            return

        self._load_names()
        
        if names_to_process is None: # generate all
            for name in self.names:
                folder_path = os.path.join(self.database_root, name)
                embaddings_path = os.path.join(folder_path, 'embeddings.npy')
                stack = self.face_recognizer.generate_embeddings_from_folder(folder_path)
                if stack is None:
                    continue
                np.save(embaddings_path, stack)
        else:
            namesToProcess = []
            for name in names_to_process:
                if name not in self.names:
                    print(f'FaceDatabaseManager::generate_database_embeddings: Name "{name}" does not exist in the database')
                    continue
                namesToProcess.append(name)

            for name in namesToProcess:
                folder_path = os.path.join(self.database_root, name)
                embaddings_path = os.path.join(folder_path, 'embeddings.npy')
                stack = self.face_recognizer.generate_embeddings_from_folder(folder_path)
                if stack is None:
                    continue
                np.save(embaddings_path, stack)

    def add_new_face(self, image, name = None, embedding = None):
        '''
        add new face to current processing session, and save image to database, but not embeddings, return the name of the new face.
        To save embeddings to database, call store_embeddings()
        '''
        if not self.have_face_recognizer:
            print('FaceDatabaseManager::add_new_face: FaceRecognizer is not set!')
            return None
            
        if name is None:
            name = self._generate_name() #generate a new name for new face
        os.makedirs(os.path.join(self.database_root, name), exist_ok=True)
            
        id = 0
        while os.path.exists(os.path.join(self.database_root, name, f'{id}.png')):
            id += 1
        cv2.imwrite(os.path.join(self.database_root, name, f'{id}.png'), image)
            
        self.add_embedding(name, embedding)
        
        return name
    
    def add_embedding(self, name, embedding):
        if embedding is None:
            return
        
        if embedding.shape[-1] != 512:
            print('FaceDatabaseManager::add_embedding: embedding should be shape (512,)')
            return
        
        if name not in self.name_embeddings_dict.keys():
            self.name_embeddings_dict[name] = np.reshape(embedding, (1, 512))
        else:
            self.name_embeddings_dict[name] = np.append(self.name_embeddings_dict[name], np.reshape(embedding, (1, 512)), axis = 0)
        
        # for debug
        for item in self.name_embeddings_dict.items():
            print(item[0], item[1].shape, len(item[1]))
    
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
            pred_name_score = self.face_recognizer._search_similar(embaddings, multi_emb_dict, threshold)
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
                print(emb.shape, emb2.shape)
                score = np.dot(emb, emb2)
                if score > threshold:
                    self.rename_face(not_merged_names[i], not_merged_names[j])
                
    def store_embeddings(self):
        if self.name_embeddings_dict is None or len(self.name_embeddings_dict) == 0:
            return
        
        print('FaceDatabaseManager::store_embeddings: Storing embeddings...')
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
            stack = self.face_recognizer.generate_embeddings_from_folder(folder_path)
            if stack is None:
                return
            else:
                np.save(embaddings_path, stack)
                self.name_embeddings_dict[new_name] = stack
                self.name_embeddings_dict.pop(old_name)
        else:
            os.rename(os.path.join(self.database_root, old_name), os.path.join(self.database_root, new_name))
            print(f'{old_name} renamed to {new_name}')
            self.name_embeddings_dict[new_name] = self.name_embeddings_dict[old_name]
            self.name_embeddings_dict.pop(old_name)
                
    def delete_face(self, name):
        self._load_names()
        if name not in self.names:
            print(f'Name "{name}" does not exist in the database')
            return

        shutil.rmtree(os.path.join(self.database_root, name))
        self.name_embeddings_dict.pop(name)
    
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