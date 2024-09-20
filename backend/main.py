import argparse
import configparser
import cv2
import logging
import socket
import time
import threading

from FaceAnalyzer import FaceAnalyzer
from FaceDatabaseManager import FaceDatabaseManager
from FaceRecognizer import FaceRecognizer
from Record import Record
from ScriptManager import ScriptManager
from VideoManager import VideoManager
from Utils import *
from SocketInterface import SocketInterface

config = configparser.ConfigParser()
config.read("config.ini")
default_params = config['DEFAULT']
param_aliases = config['ALIASES']

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

class Backend():
    def __init__(self, record: Record):
        super().__init__()
        self.si = SocketInterface()
        self.si.imServer()
                
        self.record = record
        self.params = {}
        
        # connect signals
        self.si.connect_signal("selectedVideo", self.set_video_path, True)
        self.si.connect_signal("selectedDatabase", self.set_database_path, True)
        self.si.connect_signal("testRun", self.test_run, False)
        self.si.connect_signal("startProcess", self.run, False)
        self.si.connect_signal("terminateProcess", self.terminateProcess, False)
        self.si.connect_signal("alterParam", self.set_param, True)
        self.si.connect_signal("requestParams", self.get_params, False)
        self.si.connect_signal("requestProgress", self.update_progress, False)
        self.si.connect_signal("recordOverwriteConfirmed", self.clear_record_and_run, False)
        self.si.connect_signal("requestAllMemberImg", self.get_all_member_img, False)
        
        # parameters from record, if not recorded, use default
        for key, _ in default_params.items():
            #print(f"Get parameter {key} from record: {record.get_parameter(key)}")
            self.set_param((key, record.get_parameter(key))) # if param is not set in record, get_parameter will return None, and set_param will use default value.
        
        # create ViedoManager first for video preview
        self.vm = VideoManager()
        
        self.running = False
        self.test_running = False
        self.have_face_database = False
        self.transcribe_thread = None
        self.main_thread = None
        self.test_run_thread = None
        
        self.cur_process = ""
        self.cur_progress = 0
        self.total_progress = 100
        
        def recv_loop():
            while True:
                type, data = self.si.receive()
                if type is None:
                    logger.error("Error occurred, exit.")
                    self.terminateProcess()
                    self.si.close()
                    break
                if type == "SIG" and data == "END_PROGRAM":
                    self.terminateProcess()
                    self.si.close()
                    break
                    
        threading.Thread(target=recv_loop).start()
    
    def run(self):
        if not self.vm.is_ready:
            self.raise_error("Please select a video.")
            return
        if self.running:
            self.raise_error("Running process is already running.")
            return
        if self.test_running:
            self.raise_error("Test running process is already running.")
            return
        if self.params['det_size'].format(r"\d+x\d+") is None:
            self.raise_error("Please set the detection size in correct format (format: 123x456).")
            return
        det_size = self.params['det_size'].format(r"\d+x\d+")
        det_size = tuple(map(int, det_size.split("x")))
        if det_size[0] < 0 or det_size[1] < 0:
            self.raise_error("Both value in det_size must be positive integer.")
        if not self.have_face_database:
            self.raise_error("Please select a database.")
            return
        if self.record.is_ready:
            self.si.send_signal("recordOverwrite")
            return
        
        try:
            self.fr = FaceRecognizer(det_size=det_size)
            self.fdm.set_face_recognizer(self.fr)
            self.fdm.set_new_member_prefix(self.params['new_member_prefix'])
            self.fa = FaceAnalyzer()
            self.sm = ScriptManager(model_name=self.params['whisper_model'], language=self.params['language'])
        except Exception as e:
            self.raise_error("Error occurred when setting up: " + str(e))
            return
        
        self.running = True
        
        self.cur_process = "Transcribing"
        self.cur_progress = 0
        self.total_progress = 100
        self.update_progress()
        self.transcribe_thread = threading.Thread(target=lambda: self.sm.transcribe(self.vm.get_video_path()))
        self.transcribe_thread.start()
        
        def main_run():
            while self.running:
                try:
                    frame = self.vm.next_frame()
                except:
                    self.raise_error("Failed to get frame")
                    logger.warning("Failed to get frame")
                    self.running = False
                    break
                faces = self.fr.get(frame)
                bboxes = []
                for i in range(len(faces)):
                    bbox = faces[i].bbox.astype(int).tolist()
                    bboxes.append(bbox)
                names = []
                for i in range(len(faces)):
                    name = self.fr.get_name(frame, faces[i], self.fdm, create_new_face=True)
                    names.append(name)
                    
                self.fa.update(zip(names, [self.fr.get_landmark(x) for x in faces]))
                statuses = []
                for i in range(len(faces)):
                    status = self.fa.is_talking(names[i])
                    statuses.append(status)
                    
                time_s = self.vm.get_time()
                
                self.record.write_data(time_s, bboxes, names, statuses)
                #print(f"Recorded at {time_s} s")
                #print(f"bboxes: {bboxes}")
                #print(f"Names: {names}")
                #print(f"Statuses: {statuses}")
                
            self.running = False
            self.save_record()
        
        self.main_thread = threading.Thread(target=main_run)
        self.main_thread.start()
        
    def clear_record_and_run(self):
        self.record.clear()
        self.run()
        
    def set_video_path(self, video_path: str):
        logger.info(f"Set video path: {video_path}")
        def func():
            try:
                self.vm.load_video(video_path)
            except:
                self.raise_error("Failed to load video.")
        threading.Thread(target=func).start()
     
    def set_database_path(self, database_path):
        self.fdm = FaceDatabaseManager(database_path)
        self.have_face_database = True
        logger.info(f"Set database path: {database_path}")
    
    def get_all_member_img(self):
        if not self.have_face_database:
            self.raise_error("Please select a database.")
            return
        
        names = self.fdm.get_name_list()
        for name in names:
            imgs = self.fdm.get_images_by_name(name)
            for img in imgs:
                self.si.send_signal("returnedMemberImg")
                self.si.send_data(name)
                self.si.send_image(img)
        self.si.send_signal("returnedMemberImg")
        self.si.send_data("EOF") # end of data
        self.si.send_image(np.zeros((1, 1, 3), dtype=np.uint8))
         
    def get_params(self):
        logger.debug("Request parameters")
        for key, _ in default_params.items():
            _key = key
            if _key in param_aliases:
                _key = param_aliases[key]
            if default_params[key].count(",") > 0:
                value_list = default_params[key].split(",")
                if key in self.params:
                    if self.params[key] in value_list:
                        value_list.remove(self.params[key])
                        value_list.insert(0, self.params[key]) # insert it to the first element (show on screen)
                value_list = [param_aliases[x] if x in param_aliases else x for x in value_list]
                self.si.send_signal("updateParam")
                self.si.send_data(_key)
                self.si.send_data(value_list)
            else:
                if key in self.params:
                    _value = self.params[key]
                else:
                    _value = default_params[key]
                _value = param_aliases[_value] if _value in param_aliases else _value
                self.si.send_signal("updateParam")
                self.si.send_data(_key)
                self.si.send_data([_value])
    
    def update_progress(self):
        '''
        return current processing section and progress/total using tuple
        '''
        if not self.running:
            self.si.send_signal("updateProgress")
            self.si.send_data("Idle")
            self.si.send_data(0)
            self.si.send_data(0)
        else:
            self.si.send_signal("updateProgress")
            self.si.send_data(self.cur_process)
            self.si.send_data(self.cur_progress)
            self.si.send_data(self.total_progress)
    
    def set_param(self, name_value):
        param_name, value = name_value
        inv_aliases = {v: k for k, v in param_aliases.items()}
        name = inv_aliases[param_name] if param_name in inv_aliases else param_name
        if value is None:
            if default_params[name].count(",") > 0:
                self.params[name] = default_params[name].split(",")[0]
                logger.info(f"Set parameter: {name} = {self.params[name]}")
            else:
                self.params[name] = default_params[name]
                logger.info(f"Set parameter: {name} = {default_params[name]}")
        else:
            value = inv_aliases[value] if value in inv_aliases else value
            self.params[name] = value
            logger.info(f"Set parameter: {name} = {value}")
        
    def test_run(self):
        #check_time = time.monotonic()
        #if not self.vm.is_ready:
        #    self.signal_manager.errorOccor.emit("Please select a video.")
        #    return
        #if self.running:
        #    self.signal_manager.errorOccor.emit("Running process is already running.")
        #    return
        #if self.test_running:
        #    self.signal_manager.errorOccor.emit("Test running process is already running.")
        #    return
        #if not self.have_face_database:
        #    self.signal_manager.errorOccor.emit("Please select a database.")
        #    return
        #if self.params['det_size'].format(r"\d+x\d+") is None:
        #    self.signal_manager.errorOccor.emit("Please set the detection size in correct format (format: 123x456).")
        #    return
        #
        #det_size = self.params['det_size'].format(r"\d+x\d+")
        #det_size = tuple(map(int, det_size.split("x")))
        #if det_size[0] < 0 or det_size[1] < 0:
        #    self.signal_manager.errorOccor.emit("Both value in det_size must be positive integer.")
        #    return
        #
        #print(f"Check time: {time.monotonic()-check_time} s")
        #
        #print(f"Test running with parameters: {self.params}")
        #
        #def test_run():
        #    build_time = time.monotonic()
        #    try:
        #        self.fr = FaceRecognizer(det_size=det_size)
        #        self.fdm.set_face_recognizer(self.fr)
        #        self.fdm.set_new_member_prefix(self.params['new_member_prefix'])
        #        self.fa = FaceAnalyzer()
        #        self.sm = ScriptManager(model_name=self.params['whisper_model'], language=self.params['language'])
        #    except Exception as e:
        #        self.signal_manager.errorOccor.emit(str(e))
        #        return
        #    
        #    print(f"Build time: {time.monotonic()-build_time} s")
        #    
        #    self.test_running = True
        #    
        #    transcribe_time = time.monotonic()
        #    self.cur_process = "Transcribing"
        #    self.cur_progress = 0
        #    self.total_progress = 100
        #    self.update_progress()
        #    self.sm.transcribe(self.vm.get_video_path())
        #    
        #    print(f"Transcribe time: {time.monotonic()-transcribe_time} s")
        #    
        #    while self.test_running:
        #        get_frame_time = time.monotonic()
        #        try:
        #            frame = self.vm.next_frame()
        #        except Exception as e:
        #            self.signal_manager.errorOccor.emit(str(e))
        #            self.test_running = False
        #            break
        #        
        #        print(f"Get frame time: {time.monotonic()-get_frame_time} s")
        #        
        #        resize_time = time.monotonic()
        #        frame = cv2.resize(frame, (1280, 720)) # 16:9
        #        print(f"Resize time: {time.monotonic()-resize_time} s")
        #        recon_time = time.monotonic()
        #        faces = self.fr.get(frame)
        #        print(f"Recognition time: {time.monotonic()-recon_time} s")
        #        process_time = time.monotonic()
        #        bboxes = []
        #        for i in range(len(faces)):
        #            bbox = faces[i].bbox.astype(int).tolist()
        #            bboxes.append(bbox)
        #        names = []
        #        for i in range(len(faces)):
        #            name = self.fr.get_name(frame, faces[i], self.fdm, create_new_face=False)
        #            names.append(name)
        #        self.fa.update(zip(names, [self.fr.get_landmark(x) for x in faces]))
        #        statuses = []
        #        for i in range(len(faces)):
        #            status = self.fa.is_talking(names[i])
        #            statuses.append(status)
        #        print(f"Process time: {time.monotonic()-process_time} s")
        #        #time_s = self.vm.get_time()
        #        
        #        draw_time = time.monotonic()
        #        # putting informations on the frame using cv2
        #        for i in range(len(faces)):
        #            cv2.rectangle(frame, tuple(bboxes[i][:2]), tuple(bboxes[i][2:]), (0, 255, 0), 2)
        #            frame = PutText(frame, "Not Found" if not names[i] else names[i], (bboxes[i][0], bboxes[i][1]-10))
        #            frame = PutText(frame, "Talking" if statuses[i] else "Slient", (bboxes[i][0], bboxes[i][3]+20))
        #        print(f"Draw time: {time.monotonic()-draw_time} s")
        #        cv2.imshow("Test Running", frame)
        #        if cv2.waitKey(1) & 0xFF == ord('q'):
        #            break
        #        
        #    self.test_running = False
        #
        #print(self.vm.get_video_path(), 'script.txt', self.fdm.database_root, 'records', None, self.params['whisper_model'], self.params['language'], self.params['new_member_prefix'], self.params['det_size'])
        #test_run_p.run(video_path=self.vm.get_video_path(), script_path='script.txt', database_dir=self.fdm.database_root, output_dir='records', record_path=None, model_name=self.params['whisper_model'], language=self.params['language'], prefix=self.params['new_member_prefix'], resolution=self.params['det_size'])
        run(self.vm.get_video_path(), 'script.txt', self.fdm.database_root, 'records', None, self.params['whisper_model'], self.params['language'], self.params['new_member_prefix'], self.params['det_size'])
        #self.test_run_thread = threading.Thread(target=test_run)
        #self.test_run_thread.start()
        
    def raise_error(self, error_message):
        self.si.send_signal("errorOccor")
        self.si.send_data(error_message)
        
    def terminateProcess(self):
        self.running = False
        self.test_running = False
        if self.test_run_thread:
            self.test_run_thread.join()
        if self.transcribe_thread:
            self.transcribe_thread.join()
        if self.main_thread:
            self.main_thread.join()
        
    def save_record(self):
        for key, _ in default_params.items():
            self.record.set_parameter(key, self.params[key])
        self.record.export()

if __name__ == '__main__':
    Backend(Record())