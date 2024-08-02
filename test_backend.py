import cv2
import time

from FaceDatabaseManager import FaceDatabaseManager
from FaceRecognizer import FaceRecognizer
from FaceAnalyzer import FaceAnalyzer
from ScriptManager import ScriptManager
from VideoManager import VideoManager
from Utils import *

FPS = '--'

if __name__ == '__main__':
    import threading
    
    init_time = time.monotonic()
    fr = FaceRecognizer(det_size=(480, 480)) # 偵測不到人臉可以改看看
    fdm = FaceDatabaseManager('database', fr, new_member_prefix='成員_')
    fa = FaceAnalyzer()
    vm = VideoManager(video_path=r'meetingVideo\bianlun.mp4')
    sm = ScriptManager()
    init_time = time.monotonic() - init_time
    print(f'init time: {init_time} s')
    
    
    # 載入字幕
    sm.load_script_file('test_script.txt')
    
    # 生成字幕
    #def ScriptProcess():
    #    sm.transcribe(vm.extracted_audio_path)
    #    sm.save_script_file('test_script.txt')
    #script_time = time.monotonic()
    #t = threading.Thread(target=ScriptProcess)
    #t.start()
    #t.join()
    #script_time = time.monotonic() - script_time
    #print(f'script time: {script_time} s')

    #fdm.generate_embeddings(True) # 重新生成臉部特徵
    process_time = time.monotonic() # 計算總處理時間
    start_time = time.monotonic() # 算fps用的
    counter = 0 # 算fps用的
    paused = False
    while not vm.is_end():
        if not paused:
            frame = vm.next_frame()
        else:
            frame = vm.get_frame() # 暫停時的畫面
        frame = cv2.resize(frame, (1280, 720)) # 16:9
        
        # 偵測臉
        faces = fr.get_faces(frame)
        name_lmks = []
        for face in faces:
            # 找名字
            name_score = fr.get_name(frame, face, fdm, create_new_face=True)
            # 臉部標記
            lmk = fr.get_landmark(face)
            # 畫框 (沒找出名字照畫)
            box = face.bbox.astype(int)
            cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), (0, 255, 0), 2)
            if name_score:
                name_lmks.append((name_score[0], lmk))

        # 更新 臉部(嘴巴)的數據
        fa.update(name_lmks)
        #os.system('cls')
        
        # 名字和說話狀態
        for name_lmk, face in zip(name_lmks, faces):
            name, lmk = name_lmk
            box = face.bbox.astype(int)
            frame = PutText(frame, f'{name}', (box[0], box[1]-50))
            talking = fa.is_talking(name)
            frame = PutText(frame, f'{talking}', (box[0], box[1]-30))

        # 字幕 中文需用pillow畫
        script = sm.get_script_by_time(vm.get_time())
        if script == None:
            script = ''
        frame = PutText(frame, script, (10, 50))
        
                
        # FPS
        counter += 1
        if counter == 10:
            end_time = time.monotonic()
            FPS = counter / (end_time - start_time)
            counter = 0
            start_time = time.monotonic()
            #fdm.smart_merge_faces()
        frame = PutText(frame, f'FPS: {FPS}', (10, 10))
        
        cv2.imshow('frame', frame)
        
        # 輸入操作
        key = cv2.waitKey(1)
        if key == ord('q') or key == 27: # ESC
            break
        elif key == ord('d'):
            vm.forward(100)
        elif key == ord('a'):
            vm.rewind(100)
        elif key == ord('r'): # 重新生成臉部資料
            fdm.generate_embeddings(True)
            fdm.load_data()
        elif key == 32: # space to capture image
            #cv2.imwrite('saved.png', frame)
            paused = not paused
    process_time = time.monotonic() - process_time
    print(f'process time: {process_time} s')
    cv2.destroyAllWindows()
    with open('run_test.txt', 'w') as f:
        f.write(f'init time: {init_time}s\n')
        f.write(f'process_time: {process_time}s\n')
