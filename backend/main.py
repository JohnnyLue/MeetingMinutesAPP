import argparse
import configparser
import cv2
import glob
import logging
import time
import os
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

class Backend():
    def __init__(self):
        super().__init__()
        self.si = SocketInterface()
        self.si.imServer()
                
        self.params = {}
        
        # connect signals
        self.si.connect_signal("selectedVideo", self.set_video_path, True)
        self.si.connect_signal("selectedDatabase", self.set_database_path, True)
        self.si.connect_signal("selectedRecord", self.set_record_file, True)
        self.si.connect_signal("testRun", lambda: self.run(True), False)
        self.si.connect_signal("startProcess", lambda: self.run(False), False)
        self.si.connect_signal("terminateProcess", self.terminateProcess, False)
        self.si.connect_signal("alterParam", self.set_param, True)
        self.si.connect_signal("requestParams", self.get_params, False)
        self.si.connect_signal("requestProgress", self.update_progress, False)
        #self.si.connect_signal("recordOverwriteConfirmed", self.clear_record_and_run, False)
        self.si.connect_signal("requestAllMemberImg", self.get_all_member_img, False)
        self.si.connect_signal("requestDatabaseMenu", self.get_database_menu, False)
        self.si.connect_signal("requestRecordMenu", self.get_record_menu, False)
        
        # create ViedoManager first for video preview
        self.vm = VideoManager()
        self.record = None
        
        self.running = False
        self.test_running = False
        self.database_name = None
        self.transcribe_thread = None
        self.run_thread = None
        
        self.cur_process = ""
        self.cur_progress = 0
        self.total_progress = 100
        self.update_progress_lock = False
        
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
    
    def run(self, test=False):
        if self.running:
            self.raise_error("Running process is already running.")
            return
        if self.test_running:
            self.raise_error("Test running process is already running.")
            return
        
        if not test and self.record is None:
            self.create_empty_record()
        
        self.cur_process = "Checking parameters..."
        self.cur_progress = 0
        self.total_progress = 4
        self.update_progress()
        if not self.vm.is_ready:
            self.raise_error("Please select a video.")
            return
        self.cur_progress+=1
        self.update_progress()
        if self.params['det_size'].format(r"\d+x\d+") is None:
            self.raise_error("Please set the detection size in correct format (format: 123x456).")
            return
        self.cur_progress+=1
        self.update_progress()
        det_size = self.params['det_size'].format(r"\d+x\d+")
        det_size = tuple(map(int, det_size.split("x")))
        if det_size[0] < 0 or det_size[1] < 0:
            self.raise_error("Both value in det_size must be positive integer.")
            return
        self.cur_progress+=1
        self.update_progress()
        if self.database_name is None:
            self.raise_error("Please select a database.")
            return
        self.cur_progress+=1
        self.update_progress()
        
        self.cur_process = "Setting up..."
        self.cur_progress = 0
        self.total_progress = 6
        self.update_progress()
        try:
            self.vm = VideoManager(self.vm.get_video_path())
            self.cur_progress+=1
            self.update_progress()
            
            self.fr = FaceRecognizer(det_size=det_size)
            self.cur_progress+=1
            self.update_progress()
            
            self.fdm.set_face_recognizer(self.fr)
            self.cur_progress+=1
            self.update_progress()
            
            self.fdm.set_new_member_prefix(self.params['new_member_prefix'])
            self.cur_progress+=1
            self.update_progress()
            
            self.fa = FaceAnalyzer()
            self.cur_progress+=1
            self.update_progress()
            
            self.sm = ScriptManager(model_name=self.params['whisper_model'], language=self.params['language'])
            self.cur_progress+=1
            self.update_progress()
        except Exception as e:
            self.raise_error("Error occurred when setting up: " + str(e))
            self.cur_process = "Idle"
            self.cur_progress = 0
            self.total_progress = 0
            self.update_progress()
            return
        
        self.running = True
        
        if not test:
            # info
            self.record.set_info(None, time.strftime(r"%Y_%m_%d_%H_%M_%S"), self.vm.get_video_path(), self.database_name)
            # parameters
            for key, _ in default_params.items():
                self.record.set_parameter(key, self.params[key])
        
        if not test: # no trinscribing in test mode
            self.cur_process = "Transcribing..."
            self.cur_progress = 0
            self.total_progress = 0
            self.update_progress()
            
            #self.sm.transcribe(self.vm.get_video_path())
            #self.transcribe_thread = threading.Thread(target=lambda: self.sm.transcribe(self.vm.get_video_path()))
            self.sm.load_script_file('script.txt') # for test
            #self.transcribe_thread.start()
        
        def main_run(test):
            self.cur_process = "Running..."
            self.total_progress = self.vm.get_total_frame()
            self.cur_progress = 0
            self.update_progress()
            end_safly = False
            while self.running:                
                for i in range(10):
                    frame = self.vm.next_frame()
                    if frame is not None:
                        break
                if frame is None:
                    if self.vm.is_end():
                        logger.info("End of video")
                        self.running = False
                        end_safly = True
                        break
                    self.raise_error("Failed to get frame")
                    logger.warning("Failed to get frame")
                    self.running = False
                    end_safly = False
                    break
                
                faces = self.fr.get_faces(frame)
                bboxes = []
                for i in range(len(faces)):
                    bbox = faces[i].bbox.astype(int).tolist()
                    logger.debug(f"{bbox}")
                    bbox[0] /= self.vm.width
                    bbox[1] /= self.vm.height

                    bbox[2] /= self.vm.width
                    bbox[3] /= self.vm.height
                    bboxes.append(bbox)
                names = []
                valid_faces = []
                valid_bboxes = []
                for i in range(len(faces)):
                    name = self.fr.get_name(frame, faces[i], self.fdm, create_new_face=False if test else True)
                    if name is None:
                        continue
                    names.append(name)
                    valid_faces.append(faces[i])
                    valid_bboxes.append(bboxes[i])
                    
                self.fa.update(zip(names, [self.fr.get_landmark(x) for x in valid_faces]))
                
                statuses = []
                for i in range(len(valid_faces)):
                    status = self.fa.is_talking(names[i])
                    statuses.append(status)
                    
                time_s = self.vm.get_time()
                frame_idx = self.vm.get_cur_frame_idx()
                
                if not test:
                    self.record.write_data(frame_idx, valid_bboxes, names, statuses)
                    
                #draw on frame
                if not test:
                    for i in range(len(valid_faces)):
                        x1, y1, x2, y2 = valid_bboxes[i]
                        cv2.rectangle(frame, (int(x1*self.vm.width), int(y1*self.vm.height)), (int(x2*self.vm.width), int(y2*self.vm.height)), (0, 255, 0) if statuses[i] else (225, 0, 0), 5)
                        frame = PutText(frame, "Not Found" if not names[i] else names[i], (int(x1*self.vm.width), int(y1*self.vm.height)-20), fontScale=50)
                        #frame = PutText(frame, self.sm.get_script_by_time(time_s), (0, 0), fontScale=50)
                else:
                    for i in range(len(valid_faces)):
                        x1, y1, x2, y2 = valid_bboxes[i]
                        frame = PutText(frame, "Not Found" if not names[i] else names[i], (int(x1*self.vm.width), int(y1*self.vm.height)-20), fontScale=50)
                    for i in range(len(faces)):
                        x1, y1, x2, y2 = bboxes[i]
                        cv2.rectangle(frame, (int(x1*self.vm.width), int(y1*self.vm.height)), (int(x2*self.vm.width), int(y2*self.vm.height)), (0, 255, 0), 5)
                
                self.si.send_signal("updateRuntimeImg")
                self.si.send_image(cv2.resize(frame, (640, 360))) # 640*360
                
                cv2.waitKey(10)
                self.cur_progress+=1
                self.update_progress()
                
            self.cur_process = "Done"
            self.cur_progress = 0
            self.total_progress = 0
            self.update_progress()
            
            self.running = False
            if not test and end_safly:
                self.save_record()
        
        self.run_thread = threading.Thread(target=main_run, args=(test,))
        self.run_thread.start()
        
    def get_record_menu(self):
        files = glob.glob(os.path.join(config['STORE_DIR']['RECORD'], '*.json'))
        logger.debug(files)
        for file in files:
            record = Record()
            logger.debug(f"Loading record: {file}")
            record.load(file)
            info = record.get_info()
            logger.debug(info)
            if info is None:
                continue
            self.si.send_signal("returnedRecordMenu")
            self.si.send_data(info['record_name'])
            self.si.send_data(info['create_time'])
            self.si.send_data(info['video_path'])
            self.si.send_data(info['database_name'])
        
    def create_empty_record(self):
        self.record = Record()
        
    def set_record_file(self, record_name):
        self.record = Record()
        logger.info(f"Set record file: {record_name}")
        self.record.load(os.path.join(config['STORE_DIR']['RECORD'], record_name + ".json"))
        if self.record.get_info() is None:
            self.raise_error("Failed to load record file.")
            self.record = None
            return
        self.set_video_path(self.record.get_info()['video_path'])
        self.set_database_path(self.record.get_info()['database_name'])
        self.get_all_member_img()
        for key, _ in default_params.items():
            self.set_param((key, self.record.get_parameter(key)))
        self.get_params()
        
    def set_video_path(self, video_path: str):
        logger.info(f"Set video path:\n\"{video_path}\"")
        self.cur_process = f"Selected video: \"{os.path.basename(video_path)}\""
        self.cur_progress = 0
        self.total_progress = 0
        self.update_progress()
        try:
            self.vm.load_video(video_path)
            # echo back to the sender
            self.si.send_signal("selectedVideo")
            self.si.send_data(video_path)
        except:
            self.raise_error("Failed to load video.")
            self.cur_process = "Idle"
            self.cur_progress = 0
            self.total_progress = 0
            self.update_progress()
     
    def set_database_path(self, database_name):
        if database_name ==  "": # create new database
            new_name = "Database"
            i = 1
            while os.path.exists(os.path.join(config['STORE_DIR']['DATABASE_ROOT'], new_name)):
                new_name = f"Database_{i}"
                i+=1
            logger.debug(f"Create new database: {new_name}")
            database_name = new_name
            new_dir = os.path.join(config['STORE_DIR']['DATABASE_ROOT'], new_name)
            os.makedirs(new_dir)
        if not isinstance(database_name, str):
            self.raise_error("Invalid database name.")
            return
        
        self.fdm = FaceDatabaseManager(os.path.join(config['STORE_DIR']['DATABASE_ROOT'], database_name))
        self.database_name = database_name
        logger.info(f"Set database path:\"{database_name}\"")
    
    def get_database_menu(self):
        databasees_list = glob.glob(os.path.join(config['STORE_DIR']['DATABASE_ROOT'], '*'))
        logger.debug(databasees_list)
        
        for database in databasees_list:
            logger.debug(os.path.basename(database))
            names = glob.glob(os.path.join(database, '*'))
            logger.debug(names)
            preview_imgs = []
            name_list = []
            for name in names: # pick one picture of each person
                img_paths = glob.glob(os.path.join(name, '*.png'))
                logger.debug(img_paths)
                if len(img_paths) == 0:
                    logger.warning(f"No image found in {name}, skiped")
                    continue
                img = cv2.imread(img_paths[0])
                preview_imgs.append(img)
                name_list.append(os.path.basename(name))
                
            for i in range(len(name_list)): # send data
                self.si.send_signal("returnedDatabaseMenu")
                self.si.send_data(os.path.basename(database))
                self.si.send_data(name_list[i])
                self.si.send_image(preview_imgs[i])
                
            if len(name_list) == 0: # no member in this database
                self.si.send_signal("returnedDatabaseMenu")
                self.si.send_data(os.path.basename(database))
                self.si.send_data("")
                no_member_img = cv2.imread("no_member.png")
                self.si.send_image(no_member_img)
                
        self.si.send_signal("returnedDatabaseMenu")
        self.si.send_data('EOF')
        self.si.send_data('')
        self.si.send_image(np.zeros((1, 1, 3), dtype=np.uint8))
        
    def get_all_member_img(self):
        if self.database_name is None:
            self.raise_error("Please select a database.")
            return
        
        names = self.fdm.get_name_list()
        for name in names:
            imgs = self.fdm.get_images_by_name(name)
            for img in imgs:
                self.si.send_signal("returnedMemberImg")
                self.si.send_data(name)
                self.si.send_image(img)
        if len(names) == 0:
            self.si.send_signal("returnedMemberImg")
            self.si.send_data("")
            self.si.send_image(cv2.imread("no_member.png"))
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
                self.params[key] = value_list[0]
                value_list = [param_aliases[x] if x in param_aliases else x for x in value_list]
                self.si.send_signal("updateParam")
                self.si.send_data(_key)
                self.si.send_data(value_list)
            else:
                if key in self.params:
                    _value = self.params[key]
                else:
                    _value = default_params[key]
                self.params[key] = _value
                _value = param_aliases[_value] if _value in param_aliases else _value
                self.si.send_signal("updateParam")
                self.si.send_data(_key)
                self.si.send_data([_value])
    
    def update_progress(self):
        '''
        return current processing section and progress/total using tuple
        '''
        if self.update_progress_lock:
            return
        logger.debug(f"Update progress: {str(self.cur_process)} {str(self.cur_progress)}/{str(self.total_progress)}")
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
        
    def raise_error(self, error_message):
        self.si.send_signal("errorOccor")
        self.si.send_data(error_message)
        
    def terminateProcess(self):
        self.running = False
        self.test_running = False
        
        self.cur_process = "Terminating process..."
        self.cur_progress = 0
        self.total_progress = 0
        self.update_progress()
        self.update_progress_lock = True
        
        if self.transcribe_thread is not None:
            self.transcribe_thread.join()
            self.transcribe_thread = None
        if self.run_thread is not None:
            self.run_thread.join()
            self.run_thread = None
            
        self.update_progress_lock = False
        self.cur_process = "Idle"
        self.cur_progress = 0
        self.total_progress = 0
        self.update_progress()
        
    def save_record(self):
        if self.transcribe_thread is not None:
            self.cur_process = "Waiting for transcribing..."
            self.cur_progress = 0
            self.total_progress = 0
            self.update_progress()
            self.transcribe_thread.join()
        if self.run_thread is not None: # basically it shouldn't be None
            self.run_thread.join()
            
        if self.record is None:
            logger.warning("No record to save")
            return
        
        self.record.set_script(self.sm.get_result())
        
        self.record.export()

if __name__ == '__main__':
    Backend()