import argparse
import cv2
import logging
import socket
import time

from FaceAnalyzer import FaceAnalyzer
from FaceDatabaseManager import FaceDatabaseManager
from FaceRecognizer import FaceRecognizer
from Record import Record
from ScriptManager import ScriptManager
from VideoManager import VideoManager
from Utils import *

logger = logging.getLogger()
logger.handlers.clear()
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
	'[%(levelname)-7s %(asctime)s] %(name)s:%(module)s:%(funcName)s:%(lineno)d: %(message)s',
	'%H:%M:%S')

fileLogger = logging.FileHandler('log.txt', mode='w')
fileLogger.setLevel(logging.DEBUG)
fileLogger.setFormatter(formatter)

streamLogger = logging.StreamHandler()
streamLogger.setLevel(logging.DEBUG)
streamLogger.setFormatter(formatter)

logger.addHandler(fileLogger)
logger.addHandler(streamLogger)

def run(video_path, script_path, database_dir, output_dir, record_path, model_name, language, prefix, resolution):
    init_time = time.monotonic()
    det_size = resolution.split('x')
    record = Record(record_path, output_dir)
    fr = FaceRecognizer(det_size=(int(det_size[0]), int(det_size[1]))) # 偵測不到人臉可以改看看
    fdm = FaceDatabaseManager(database_dir, fr, new_member_prefix=prefix)
    fa = FaceAnalyzer()
    vm = VideoManager(video_path=video_path)
    sm = ScriptManager(model_name, language)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    init_time = time.monotonic() - init_time
    logger.debug(f'init time: {init_time} s')
    
    if script_path is not None:
        try:
            # 載入字幕
            sm.load_script_file(script_path)
        except:
            # 生成字幕
            script_time = time.monotonic()
            sm.transcribe(vm.get_video_path())
            sm.save_script_file('script.txt')
            script_time = time.monotonic() - script_time
            logger.debug(f'script time: {script_time} s')
    else:
        # 生成字幕
        script_time = time.monotonic()
        sm.transcribe(vm.get_video_path())
        sm.save_script_file('script.txt')
        script_time = time.monotonic() - script_time
        logger.debug(f'script time: {script_time} s')

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
        frame = cv2.resize(frame, (1280, 720)) # 16:9
        get_frame_time = time.monotonic() - get_frame_time
        #logger.debug(f'get frame time: {get_frame_time}s')
        
        # 偵測、分析臉部
        detect_time = time.monotonic()
        faces = fr.get_faces(frame)
        bboxes = []
        for i in range(len(faces)):
            bbox = faces[i].bbox.astype(int).tolist()
            bboxes.append(bbox)
        names = []
        for i in range(len(faces)):
            name = fr.get_name(frame, faces[i], fdm, create_new_face=True)
            names.append(name)
        logger.debug(f'Found names: {names}')
        name_lmk = zip(names, [fr.get_landmark(x) for x in faces])
        name_lmk = [x for x in name_lmk if x[0] is not None]
        fa.update(name_lmk)
        statuses = []
        for i in range(len(faces)):
            status = fa.is_talking(names[i])
            statuses.append(status)
        logger.debug(f'Statuses: {statuses}')
        detect_time = time.monotonic() - detect_time
        #logger.debug(f'detect time: {detect_time}s')
        
        # 顯示
        show_time = time.monotonic()
        for i in range(len(faces)):
            cv2.rectangle(frame, tuple(bboxes[i][:2]), tuple(bboxes[i][2:]), (0, 255, 0), 2)
            frame = PutText(frame, "Not Found" if not names[i] else names[i], (bboxes[i][0], bboxes[i][1]-10))
            frame = PutText(frame, "Talking" if statuses[i] else "Slient", (bboxes[i][0], bboxes[i][3]+20))
            frame = PutText(frame, sm.get_script_by_time(vm.get_time()), (0, 0))
            #'time_s': vm.get_time(), 'bbox': bboxes, 'name': names, 'status': statuses
            #requests.post('http://localhost:5000/frame', json={'frame': frame.tolist()})
            #s.bind(('localhost', 12345))
        cv2.imshow('frame', frame)
        show_time = time.monotonic() - show_time
        #logger.debug(f'show time: {show_time}s')
        
        # 計算fps
        counter += 1
        if counter % 30 == 0:
            now_time = time.monotonic()
            fps = 30 / (now_time - start_time)
            start_time = now_time
            logger.debug(f'fps: {fps}')
        
        logger.debug(' ')
        
        # 暫停
        if cv2.waitKey(1) & 0xFF == ord(' '):
            paused = not paused
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        if cv2.waitKey(1) & 0xFF == ord('d'):
            vm.forward(120)
        if cv2.waitKey(1) & 0xFF == ord('a'):
            vm.rewind(120)
    cv2.destroyAllWindows()

if __name__ == '__main__':
    arg = argparse.ArgumentParser()
    arg.add_argument("-v", "--video", required=True, help="path to video file")
    arg.add_argument("-s", "--script", required=False, help="path to script file", default=None)
    arg.add_argument("-d", "--database", required=False, help="path to database folder", default='database')
    arg.add_argument("-o", "--output", required=False, help="path to folder storing output record", default='records')
    arg.add_argument("-i", "--record", required=False, help="path to record file", default=None)
    
    arg.add_argument("-m", "--model", required=True, help="Name of the Whisper model")
    arg.add_argument("-l", "--language", required=True, help="language of the script")
    arg.add_argument("-p", "--prefix", required=True, help="prefix of new member")
    arg.add_argument("-r", "--resolution", required=True, help="resolution of face detection") # format: WIDTHxHEIGHT
    args = arg.parse_args()
    run(args.video, args.script, args.database, args.output, args.record, args.model, args.language, args.prefix, args.resolution)