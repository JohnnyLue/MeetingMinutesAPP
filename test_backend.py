# reference https://medium.com/@yongsun.yoon/nba-face-recognition-system-345034ffed8c
import cv2

from FaceDatabaseManager import FaceDatabaseManager
from FaceRecognizer import FaceRecognizer
from FaceAnalyzer import FaceAnalyzer

if __name__ == '__main__':
    fr = FaceRecognizer(det_size=(320, 320))
    fdm = FaceDatabaseManager('database', fr)
    fa = FaceAnalyzer()
    fdm.generate_embeddings()
    cap = cv2.VideoCapture(0)
    cv2.namedWindow('frame', cv2.WINDOW_NORMAL)
    while cap.isOpened():
        ret, frame = cap.read()
        lmks = fr.get_landmarks(frame)
        faces = fr.get_faces(frame)
        fr.get_names(faces)
        for lmk in lmks:
            open = fa.mouth_open(lmk)
            print(open)
            cv2.putText(frame, f'{open}', (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.imshow('frame', frame)
        if cv2.waitKey(1) == ord('q'):
            break
        if cv2.waitKey(1) == 32:
            cv2.imwrite('saved.png', frame)
            
    cv2.destroyAllWindows()