import numpy as np
import logging

logger = logging.getLogger()

class FaceAnalyzer:
    def __init__(self, value_window_size = 20):
        self.name_open_value_dict = {}
        self.value_window_size = value_window_size
        logger.info("FaceAnalyzer initialized")
    
    def mouth_open(self, face_lmk):
        # there are three pairs of points in lmk that can decide how much the mouse is open, store them
        left_lip_dis = np.linalg.norm(face_lmk[54] - face_lmk[66])
        right_lip_dis = np.linalg.norm(face_lmk[60] - face_lmk[62])
        mid_lip_dis = np.linalg.norm(face_lmk[57] - face_lmk[70])
        base_ref = (np.linalg.norm(face_lmk[66] - face_lmk[70]) + np.linalg.norm(face_lmk[54] - face_lmk[57])) / 2
        # logger.debug(f"points: {face_lmk[54]}, {face_lmk[66]}, {face_lmk[60]}, {face_lmk[62]}, {face_lmk[57]}, {face_lmk[70]}")
        #logger.debug(f"left_lip_dis: {left_lip_dis}, right_lip_dis: {right_lip_dis}, mid_lip_dis: {mid_lip_dis}, base_ref: {base_ref}")
        return float((left_lip_dis + right_lip_dis + mid_lip_dis) / base_ref)

    def is_talking(self, name, threshold = 0.7):
        if name is None:
            return False
            
        if name not in self.name_open_value_dict.keys():
            logger.warning(f"Name \"{name}\" does not exist")
            return False
        
        values = self.name_open_value_dict[name]
        values = [value for value in values if value != -1] # remove absent data
        # med = np.median(values)
        max = np.max(values)
        min = np.min(values)
        logger.debug(f"Name \"{name}\", max: {max}, min: {min}, max-min: {max-min}")
        # logger.debug(f"values: {values}")
        if (max - min) > threshold:
            return True
        if min < 0.08 and max > 0.2:
            return True
        else:
            return False
        #elif min > 0.04 and max > min * threshold:
        #    return True
        # ## visualize in cmd
        # for name in self.name_open_value_dict.keys():
        #     for value in self.name_open_value_dict[name]:
        #         print(f'{value:04.2f} ', end='')
        #         for i in range(int(value)):
        #             if i < med:
        #                 print('-', end='')
        #             else:
        #                 print('*', end='')
        #         print('', end='\n')
            
        # cross_zero = 0
        # for i in range(len(values)-1):
        #     if (values[i] - med)*(values[i+1] - med) < 0:
        #         cross_zero += 1
            
        # logger.debug(f"Name \"{name}\" cross midian {cross_zero} times (in {len(values)} frames)")
        # return cross_zero > len(values)*threshold
        
    def update(self, name_lmks):
        for name in self.name_open_value_dict.keys():
            while len(self.name_open_value_dict[name]) >= self.value_window_size:
                self.name_open_value_dict[name].pop(0) # pop first value
                
        names = []
        for name, lmk in name_lmks:
            if name not in self.name_open_value_dict.keys():
                self.name_open_value_dict[name] = []
            self.name_open_value_dict[name].append(self.mouth_open(lmk))
            names.append(name)
            
        for name in self.name_open_value_dict.keys():
            if name not in names:
                self.name_open_value_dict[name].append(-1) # absent person
