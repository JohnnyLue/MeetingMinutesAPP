import numpy as np
import os
import shutil
import glob

from FaceRecognizer import FaceRecognizer

class FaceDatabaseManager:
    def __init__(self, root, face_recognizer: FaceRecognizer):
        self.database_root = root
        self.face_recognizer = face_recognizer
        self.load_data()
        
    def load_data(self):
        names_without_embeddings = []
        self.name_embeddings_dict = {}
        
        self._load_names()
        for name in self.names:
            embaddings_path = os.path.join(self.database_root, name, 'embeddings.npy')
            if not os.path.exists(embaddings_path):
                names_without_embeddings.append(name)
                continue
            
            # load embeddings
            embaddings = np.load(embaddings_path, allow_pickle=True)
            self.name_embeddings_dict[name] = embaddings
            
        if len(names_without_embeddings) > 0:
            print(f'Names without embeddings: {names_without_embeddings}')
            print('Please generate them manually')
   
    def get_name_list(self):
        if len(self.names) == 0:
            return None
        return self.names
    
    def get_name_embeddings_dict(self):
        return self.name_embeddings_dict
    
    def generate_embeddings(self, regenerate_all = False):
        self._load_names()
        
        if regenerate_all:
            for name in self.names:
                folder_path = os.path.join(self.database_root, name)
                embaddings_path = os.path.join(folder_path, 'embeddings.npy')
                np.save(embaddings_path, self.face_recognizer.generate_embeddings(folder_path))
        else:
            names_without_embeddings = []
            for name in self.names:
                if name not in self.name_embeddings_dict:
                    names_without_embeddings.append(name)
                    
            for name in names_without_embeddings:
                folder_path = os.path.join(self.database_root, name)
                embaddings_path = os.path.join(folder_path, 'embeddings.npy')
                np.save(embaddings_path, self.face_recognizer.generate_embeddings(folder_path))

        self.load_data()

    def add_new_face(self, images, name = ''):
        if name in self.names:
            print(f"Name {{name}} already exists in the database")
            return
        
        if name == '':
            name = self._generate_name() #generate a new name for new face
            self.names.append(name)
        
        os.makedirs(os.path.join(self.database_root, name), exist_ok=True)
        for i, img in enumerate(images):
            id = i
            while os.path.exists(os.path.join(self.database_root, name, f'{id}.png')):
                id += 1
            cv2.imwrite(os.path.join(self.database_root, name, f'{id}.png'), img)
            
        self.generate_embeddings()
        self.load_data()
        
        return name
    
    def store_embeddings(self):
        for name, embaddings in self.name_embeddings_dict.items():
            embaddings_path = os.path.join(self.database_root, name, 'embeddings.npy')
            np.save(embaddings_path, embaddings)
    
    def rename_face(self, old_name, new_name):
        if old_name == new_name:
            print(f'new name {{new_name}} is the same as old name {{old_name}}')
            return

        self._load_names()
        if old_name not in self.names:
            print(f'Name {{old_name}} does not exist in the database')
            return

        if new_name in self.names:
            print(f"Group {{old_name}} into {{new_name}}")
            for file in glob.glob(os.path.join(self.database_root, old_name, '*.png')):
                new_file_path = os.path.join(self.database_root, new_name, os.path.basename(file))
                i = 0
                while os.path.exists(new_file_path):
                    new_file_path = os.path.join(self.database_root, new_name, f'{i}.png')
                    i+=1
                shutil.move(file, new_file_path)
                
            shutil.rmtree(os.path.join(self.database_root, old_name))
            self.load_data()
            return

        os.rename(os.path.join(self.database_root, old_name), os.path.join(self.database_root, new_name))
        print(f'{old_name} renamed to {new_name}')
        self.load_data()
                
    def delete_face(self, name):
        if name not in self.names:
            print(f'Name {{name}} does not exist in the database')
            return

        shutil.rmtree(os.path.join(self.database_root, name))
        self.load_data()
    
    def _load_names(self):
        # load all names in database into self.names
        names = os.listdir(self.database_root)
        self.names = [name for name in names if os.path.isdir(os.path.join(self.database_root, name))] # filter out non-folder
        
    def _generate_name(self):
        self._load_names()
        i = 0
        while True:
            name = f'Unknown member {i}'
            if name not in self.names:
                return name
            i += 1
     