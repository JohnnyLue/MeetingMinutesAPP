# reference https://medium.com/@yongsun.yoon/nba-face-recognition-system-345034ffed8c
import cv2
import time

from FaceDatabaseManager import FaceDatabaseManager
from FaceRecognizer import FaceRecognizer
from FaceAnalyzer import FaceAnalyzer
from VideoManager import VideoManager

FPS = 0

if __name__ == '__main__':
    fr = FaceRecognizer(det_size=(320, 320))
    fdm = FaceDatabaseManager('database', fr)
    fa = FaceAnalyzer()
    vm = VideoManager()
    fdm.generate_embeddings()
    cap = cv2.VideoCapture(0)
    start_time = time.time()
    counter = 0
    while cap.isOpened():
        ret, frame = cap.read()
        faces = fr.get_faces(frame)
        name_lmks = []
        for face in faces:
            name_score = fr.get_name(frame, face, fdm, create_new_face=True)
            lmk = fr.get_landmark(face)
            if name_score:
                name_lmks.append((name_score[0], lmk))

        fa.update(name_lmks)
        
        for name, lmk in name_lmks:
            box = face.bbox.astype(int)
            cv2.putText(frame, f'{name}', (box[0], box[1]), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            talking = fa.is_talking(name)
            cv2.putText(frame, f'{talking}', (box[0], box[1]+50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        counter += 1
        if counter == 10:
            end_time = time.time()
            FPS = counter / (end_time - start_time)
            counter = 0
            start_time = time.time()
        cv2.putText(frame, f'FPS: {FPS}', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        
        cv2.imshow('frame', frame)
        if cv2.waitKey(1) == ord('q'):
            break
        if cv2.waitKey(1) == 32: # space to capture image
            cv2.imwrite('saved.png', frame)
            
    cv2.destroyAllWindows()