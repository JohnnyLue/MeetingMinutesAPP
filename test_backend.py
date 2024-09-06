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
    def ScriptProcess():
        sm.transcribe(vm.extracted_audio_path)
        sm.save_script_file('test_script.txt')
    script_time = time.monotonic()
    #ScriptProcess()
    script_time = time.monotonic() - script_time
    print(f'script time: {script_time} s')

    #fdm.generate_embeddings(True) # 重新生成臉部特徵
    process_time = time.monotonic() # 計算總處理時間
    start_time = time.monotonic() # 算fps用的
    counter = 0 # 算fps用的
    paused = False
    while not vm.is_end():
        get_frame_time = time.monotonic()
        if not paused:
            frame = vm.next_frame()
        else:
            frame = vm.get_frame() # 暫停時的畫面
        if frame is None:
            break
        
        get_frame_time = time.monotonic() - get_frame_time
        print(f'get frame time: {get_frame_time}s')
        
        # 偵測臉
        detect_time = time.monotonic()
        faces = fr.get_faces(frame)
        name_lmks = []
        for face in faces:
            # 找名字
            name = fr.get_name(frame, face, fdm, create_new_face=True)
            # 臉部標記
            lmk = fr.get_landmark(face)
            if name:
                name_lmks.append((name, lmk))
        detect_time = time.monotonic() - detect_time
        print(f'detect time: {detect_time}s')
        
        draw_face_time = time.monotonic()
        for face in faces:
            # 畫框
            box = face.bbox.astype(int)
            cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), (0, 255, 0), 2)
        draw_face_time = time.monotonic() - draw_face_time
        print(f'draw face time: {draw_face_time}s')
        
        # 更新 臉部(嘴巴)的數據
        update_time = time.monotonic()
        fa.update(name_lmks)
        #os.system('cls')
        update_time = time.monotonic() - update_time
        print(f'update time: {update_time}s')
        
        # 名字和說話狀態
        get_and_draw_talking_info_time = time.monotonic()
        for name_lmk, face in zip(name_lmks, faces):
            name, lmk = name_lmk
            box = face.bbox.astype(int)
            frame = PutText(frame, f'{name}', (box[0], box[1]-50))
            talking = fa.is_talking(name)
            frame = PutText(frame, f'{talking}', (box[0], box[1]-30))
        get_and_draw_talking_info_time = time.monotonic() - get_and_draw_talking_info_time
        print(f'get and draw talking info time: {get_and_draw_talking_info_time}s')
        
        # 字幕 中文需用pillow畫
        draw_script_time = time.monotonic()
        script = sm.get_script_by_time(vm.get_time())
        if script == None:
            script = ''
        frame = PutText(frame, script, (10, 50))
        draw_script_time = time.monotonic() - draw_script_time
        print(f'draw script time: {draw_script_time}s')
        
        # FPS
        counter += 1
        if counter % 10 == 0:
            end_time = time.monotonic()
            FPS = 10.0 / (end_time - start_time)
            start_time = time.monotonic()
            #fdm.smart_merge_faces()
        if counter % 500 == 0:
            store_embeddings_time = time.monotonic()
            fdm.store_embeddings()
            store_embeddings_time = time.monotonic() - store_embeddings_time
            print(f'store embeddings time: {store_embeddings_time}s')
            
        frame = PutText(frame, f'FPS: {FPS}', (10, 10))
        
        cv2.imshow('frame', frame)
        
        print()
        
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
