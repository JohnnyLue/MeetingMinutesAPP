import numpy as np

class FaceAnalyzer:
    def __init__(self, value_window_size = 50):
        self.name_open_value_dict = {}
        self.value_window_size = value_window_size
        pass
    
    def mouth_open(self, face_lmk):
        # there are three pairs of points in lmk that can decide how much the mouse is open, store them
        left_lip_dis = np.linalg.norm(face_lmk[54] - face_lmk[66])
        right_lip_dis = np.linalg.norm(face_lmk[60] - face_lmk[62])
        mid_lip_dis = np.linalg.norm(face_lmk[57] - face_lmk[70])
        return left_lip_dis + right_lip_dis + mid_lip_dis

    def is_talking(self, name, threshold = 0.5):
        if name not in self.name_open_value_dict:
            print(f'FaceAnalyzer:Is_talking: Name {{name}} does not recognized')
            return False
        
        values = self.name_open_value_dict[name]
        
        for value in values:
            # TODO : calculate the value of vibration
            print(value)
        print()
        
    def update(self, face_lmks, names):
        if len(face_lmks) == 0:
            print('FaceRecognizer:Update: No any face lmk passed')
            return
        
        if len(names) == 0:
            print('FaceRecognizer:Update: No any name passed')
            return
        
        if len(names) != len(face_lmks):
            print('FaceRecognizer:Update: The number of names is not equal to the number of lmk')
            return

        for name in names:
            if name not in self.name_open_value_dict:
                print(f'FaceAnalyzer:Update: New name {{name}} ')
                self.name_open_value_dict[name] = []
        
        for name, lmk in zip(names, face_lmks):
            if len(self.name_open_value_dict[name]) > self.value_window_size:
                self.name_open_value_dict[name].pop(0) # pop first value
            self.name_open_value_dict[name].append(self.mouth_open(lmk))
        
        for name in self.name_open_value_dict.keys():
            if name not in names:
                self.name_open_value_dict[name].append(-1) # absent person