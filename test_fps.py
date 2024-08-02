import cv2
import time

cap = cv2.VideoCapture(r"C:\Users\JohnnyLue\Videos\Overwolf\Insights Capture\VALORANT 05-28-2024_23-39-33-127.mp4")

ori_fps = cap.get(cv2.CAP_PROP_FPS)
new_fps = 50

start_time = time.monotonic()
processing = True
pause = False
cur_time = 0.0
while(processing):
    now_time = time.monotonic()
    if (now_time - start_time) > 1.0/new_fps:
        cap.set(cv2.CAP_PROP_POS_MSEC, cur_time*1000) # 修改取幀的時間點
        if not pause:
            _, frame = cap.read()
            cur_time += 1.0/new_fps
        # process here
        cv2.imshow('frame', frame)
        start_time = now_time
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        processing = False
    if key == ord('p'):
        pause = not pause
        
cap.release()
cv2.destroyAllWindows()