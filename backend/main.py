import argparse
import configparser
import cv2
import glob
import logging
import time
import os
import shutil
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
        self.si.connect_signal("deleteDatabase", self.delete_database, True)
        self.si.connect_signal("createDatabase", self.create_database, True)
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
        self.si.connect_signal("deleteRecord", self.delete_record, True)
        self.si.connect_signal("alterName", self.alter_name, True)
        self.si.connect_signal("addMemberImg", self.add_member_img, True)
        self.si.connect_signal("mergeMembers", self.merge_members, True)
        
        # create ViedoManager first for video preview
        self.vm = VideoManager()
        self.record = None
        self.fdm = None
        
        self.running = False
        self.database_name = None
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

    def run(self, test):
        if self.running:
            return
        
        self.si.send_signal("processStarted")
        if not test and self.record is None:
            logger.warning("No record file, create a new one.")
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
        if not os.path.exists(os.path.join(config['STORE_DIR']['DATABASE_ROOT'], self.database_name)):
            self.raise_error("Database not found.")
            return
        self.cur_progress+=1
        self.update_progress()
        
        self.cur_process = "Setting up..."
        self.cur_progress = 0
        self.total_progress = 5
        self.update_progress()
        try:
            self.vm = VideoManager(self.vm.get_video_path())
            self.cur_progress+=1
            self.update_progress()
            
            self.fr = FaceRecognizer(det_size=det_size)
            self.cur_progress+=1
            self.update_progress()
            
            self.fdm.set_face_recognizer(self.fr)
            self.fdm.set_new_member_prefix(self.params['new_member_prefix'])
            self.fdm.load_data(generate_all=True)
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
            self.record.set_info(None, time.strftime(r"%Y_%m_%d_%H_%M_%S"), self.vm.get_video_path(), self.vm.fps, self.database_name)
            # parameters
            for key, _ in default_params.items():
                self.record.set_parameter(key, self.params[key])
        
        if not test: # no trinscribing in test mode
            self.cur_process = "Transcribing..."
            self.cur_progress = 0
            self.total_progress = 0
            self.update_progress()
            
            logger.debug("Start transcribing")
            self.sm.transcribe(self.vm.get_video_path())
        
        def main_run(test):
            start_time = time.time()
            self.cur_process = "Running..."
            self.total_progress = self.vm.get_total_frame()
            self.cur_progress = 0
            self.update_progress()
            end_safly = False
            # to deside wether to get name this round, if bboxes are not change too much (position, amount), use last round's name
            last_round_face_boxes = []
            last_round_names = []
            nochange_counter = 0
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
                
                face_boxes = sorted(list(zip(faces, bboxes)), key=lambda x: x[1][0])
        
                need_to_get_name = True
                if len(last_round_face_boxes) == len(face_boxes):
                    closest = 1
                    for i in range(len(face_boxes)-1):
                        dis = face_boxes[i+1][1][0] - face_boxes[i][1][0]
                        closest = min(closest, dis)
                    logger.debug(f"closest face dis: {closest}")
                    if closest > 0.1: # no face too close to each other
                        for i in range(len(face_boxes)):
                            # diff = [dx1, dy1, dx2, dy2]
                            diff = np.array(face_boxes[i][1]) - np.array(last_round_face_boxes[i][1])
                            dis1 = np.sqrt(diff[0]**2 + diff[1]**2)
                            dis2 = np.sqrt(diff[2]**2 + diff[3]**2)
                            dis = (dis1 + dis2) / 2
                            logger.debug(f"bbox diff: {dis}")
                            if dis > 0.1:
                                break
                    need_to_get_name = False
                
                names = []
                valid_faces_bboxes = []
                if need_to_get_name or nochange_counter >= 150:
                    nochange_counter = 0
                    for i in range(len(face_boxes)):
                        name, is_new = self.fr.get_name(frame, face_boxes[i][0], self.fdm, create_new_face=True)
                        if name is None:
                            continue
                        if is_new:
                            self.si.send_signal("newMemberImage")
                            self.si.send_data(name)
                            self.si.send_image(self.fdm.get_images_by_name(name)[0])
                            
                        names.append(name)
                        valid_faces_bboxes.append(face_boxes[i])
                    logger.debug(f"Names: {names}")
                    last_round_face_boxes = valid_faces_bboxes
                    last_round_names = names
                else:
                    nochange_counter+=1
                    valid_faces_bboxes = face_boxes
                    last_round_face_boxes = face_boxes                        
                    names = last_round_names
                    logger.debug(f"use last Names: {names}")
                        
                valid_faces = [x[0] for x in valid_faces_bboxes]
                valid_bboxes = [x[1] for x in valid_faces_bboxes]
                
                self.fa.update(zip(names, [self.fr.get_landmark(x) for x in valid_faces]))
                
                statuses = []
                for i in range(len(valid_faces)):
                    status = self.fa.is_talking(names[i])
                    statuses.append(status)
                    
                frame_idx = self.vm.get_cur_frame_idx()
                
                if not test:
                    self.record.write_data(frame_idx, valid_bboxes, names, statuses)
                    
                #draw on frame
                if not test:
                    for i in range(len(valid_faces)):
                        x1, y1, x2, y2 = valid_bboxes[i]
                        cv2.rectangle(frame, (int(x1*self.vm.width), int(y1*self.vm.height)), (int(x2*self.vm.width), int(y2*self.vm.height)), (0, 255, 0) if statuses[i] else (225, 0, 0), 5)
                        frame = PutText(frame, names[i], (int(x1*self.vm.width), int(y1*self.vm.height)-20), fontScale=50)
                        #frame = PutText(frame, self.sm.get_script_by_time(time_s), (0, 0), fontScale=50)
                else:
                    for i in range(len(valid_faces)):
                        x1, y1, x2, y2 = valid_bboxes[i]
                        frame = PutText(frame, "Not Found" if not names[i] else names[i], (int(x1*self.vm.width), int(y1*self.vm.height)-20), fontScale=50)
                        cv2.rectangle(frame, (int(x1*self.vm.width), int(y1*self.vm.height)), (int(x2*self.vm.width), int(y2*self.vm.height)), (0, 255, 0) if statuses[i] else (225, 0, 0), 5)
                
                self.si.send_signal("updateRuntimeImg")
                self.si.send_image(cv2.resize(frame, (640, 360))) # 640*360
                
                self.cur_progress+=1
                self.update_progress()
                
            self.cur_process = "Done"
            self.cur_progress = 0
            self.total_progress = 0
            self.update_progress()
            
            self.running = False
            if not test and end_safly:
                self.save_record()
                self.set_record_file(self.record.get_info()['record_name'])
            self.si.send_signal("processFinished")
            logger.info(f"Process finished/terminated in {time.time() - start_time} seconds")
            
        self.run_thread = threading.Thread(target=main_run, args=(test,))
        self.run_thread.start()

    def get_record_menu(self):
        files = glob.glob(os.path.join(config['STORE_DIR']['RECORD'], '*.json'))
        logger.debug(files)
        self.si.send_signal("returnedRecordMenu")
        self.si.send_data("CLEAR_RECORDS")
        self.si.send_data("")
        self.si.send_data("")
        self.si.send_data("")
        
        for file in files:
            record = Record()
            logger.debug(f"Loading record: {file}")
            record.load_info(file)
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

    def delete_record(self, record_name):
        if not isinstance(record_name, str):
            self.raise_error("Invalid record name.")
            return
        
        record_path = os.path.join(config['STORE_DIR']['RECORD'], record_name + ".json")
        if os.path.exists(record_path):
            logger.info(f"Delete record: {record_name}")
            os.remove(record_path)
            self.get_record_menu()
        else:
            self.raise_error("Record not found.")

    def set_record_file(self, record_name):
        self.record = Record()
        logger.info(f"Set record file: {record_name}")
        self.record.load(os.path.join(config['STORE_DIR']['RECORD'], record_name + ".json"))
        if self.record.get_info() is None:
            self.raise_error("Failed to load record file.")
            self.record = None
            return
        logger.debug(self.record.get_info())
        self.set_video_path(self.record.get_info()['video_path'])
        self.set_database_path(self.record.get_info()['database_name'])
        for key, _ in default_params.items():
            self.set_param((key, self.record.get_parameter(key)))
        self.get_params()
        self.get_all_member_img()
        self.get_script()
        self.get_record_content()

    def get_record_content(self):
        if self.record is None:
            self.raise_error("Please select a record.")
            return
        logger.debug("Get record content")
        self.si.send_signal("updateRecordContent")
        self.si.send_data(self.record.get_data())

    def get_script(self):
        if self.record is None:
            self.raise_error("Please select a record.")
            return
        logger.debug("Request script")
        script = self.record.get_script()
        if script is None:
            self.raise_error("No script in this record.")
            return
        self.si.send_signal("updateScript")
        self.si.send_data(script)

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
        self.database_name = None
        if not isinstance(database_name, str):
            self.raise_error("Invalid database name.")
            return
        
        if not os.path.exists(os.path.join(config['STORE_DIR']['DATABASE_ROOT'], database_name)):
            self.raise_error("Database not found.")
            return
        
        self.fdm = FaceDatabaseManager(os.path.join(config['STORE_DIR']['DATABASE_ROOT'], database_name))
        self.database_name = database_name
        logger.info(f"Set database path:\"{database_name}\"")

    def create_database(self, database_name):
        if not isinstance(database_name, str):
            self.raise_error("Invalid database name.")
            return
        if database_name == "":
            self.raise_error("Invalid database name.")
            return
        if os.path.exists(os.path.join(config['STORE_DIR']['DATABASE_ROOT'], database_name)):
            self.raise_error("Database already exists.")
            return
        
        logger.info(f"Create new database: {database_name}")
        new_dir = os.path.join(config['STORE_DIR']['DATABASE_ROOT'], database_name)
        os.makedirs(new_dir)
        
        self.si.send_signal("returnedDatabaseMenu")
        self.si.send_data(database_name)
        self.si.send_data("")
        no_member_img = cv2.imread("no_member.png")
        self.si.send_image(no_member_img)
        
        self.si.send_signal("returnedDatabaseMenu")
        self.si.send_data('EOF')
        self.si.send_data('')
        self.si.send_image(np.zeros((1, 1, 3), dtype=np.uint8))

    def delete_database(self, database_name):
        if not isinstance(database_name, str):
            return
        if os.path.exists(os.path.join(config['STORE_DIR']['DATABASE_ROOT'], database_name)):
            try:
                shutil.rmtree(os.path.join(config['STORE_DIR']['DATABASE_ROOT'], database_name))
                if self.database_name == database_name:
                    self.database_name = None
                    self.si.send_signal("returnedMemberImg")
                    self.si.send_data("CLEAR_IMGS") # start of data
                    self.si.send_image(np.zeros((1, 1, 3), dtype=np.uint8))
            except:
                self.raise_error("Failed to delete database.")
        else:
            self.raise_error("Database not found.")

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
                    logger.warning(f"No image in {name}")
                    img = cv2.imread("no_member.png")
                else:
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
        if self.fdm is None:
            self.raise_error("Please select a database.")
            return
        if self.database_name is None:
            self.raise_error("Please select a database.")
            return
        
        self.si.send_signal("returnedMemberImg")
        self.si.send_data("CLEAR_IMGS") # start of data
        self.si.send_image(np.zeros((1, 1, 3), dtype=np.uint8))
        
        names = self.fdm.get_name_list()
        logger.debug(f"names: {names}")
        for name in names:
            imgs = self.fdm.get_images_by_name(name)
            for img in imgs:
                self.si.send_signal("returnedMemberImg")
                self.si.send_data(name)
                self.si.send_image(img)
            if len(imgs) == 0:
                self.si.send_signal("returnedMemberImg")
                self.si.send_data(name)
                self.si.send_image(cv2.imread("no_member.png"))
        if len(names) == 0:
            self.si.send_signal("returnedMemberImg")
            self.si.send_data("")
            self.si.send_image(cv2.imread("no_member.png"))
        self.si.send_signal("returnedMemberImg")
        self.si.send_data("EOF") # end of data
        self.si.send_image(np.zeros((1, 1, 3), dtype=np.uint8))

    def add_member_img(self, name_imgs):
        name, img_paths = name_imgs
        if self.fdm is None:
            self.raise_error("Please select a database.")
            return
        if self.database_name is None:
            self.raise_error("Please select a database.")
            return
        if not isinstance(name, str):
            self.raise_error("Invalid name.")
            return
        if name == "":
            self.raise_error("Invalid name.")
            return
        
        logger.info(f"Add member image: {name}")
        for img_path in img_paths:
            if not os.path.exists(img_path):
                self.raise_error(f"Image not found: {img_path}")
                return
            img = cv2.imread(img_path)
            if img is None:
                self.raise_error(f"Failed to load image: {img_path}")
                return
            id = 0
            while os.path.exists(os.path.join(config["STORE_DIR"]["DATABASE_ROOT"], self.database_name, name, f"{id}.png")):
                id+=1
                
            cv2.imwrite(os.path.join(config['STORE_DIR']['DATABASE_ROOT'], self.database_name, name, f"{id}.png"), img)
            
        # refresh member images
        self.get_all_member_img()

    def alter_name(self, old_new_name):
        old_name, new_name = old_new_name
        if self.fdm is None:
            self.raise_error("Please select a database.")
            return
        if self.database_name is None:
            self.raise_error("Please select a database.")
            return
        if not isinstance(old_name, str) or not isinstance(new_name, str):
            self.raise_error("Invalid name.")
            return
        if new_name == "":
            self.raise_error("Invalid name.")
            return
        if old_name == new_name:
            self.raise_error("New name is the same as old name.")
            return
        
        self.fdm.rename_face(old_name, new_name)
        logger.info(f"Alter name in {self.database_name}: {old_name} -> {new_name}")
        
        # refresh member images
        self.get_all_member_img()

    def merge_members(self, members):
        if members is None:
            return
        if len(members) < 2:
            return
        if self.fdm is None:
            self.raise_error("Please select a database.")
            return
        
        new_name = members[0]
        for i in range(len(members)-1):
            logging.info(f"renaming {members[i+1]} to {new_name}")
            self.fdm.rename_face(members[i+1], new_name)
        self.get_all_member_img()

    def get_params(self):
        logger.debug("Request parameters")
        
        # tell frontend to clear all parameters
        self.si.send_signal("updateParam")
        self.si.send_data("CLEAR_PARAMS")
        self.si.send_data([""])
        
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
                
        self.si.send_signal("updateParam")
        self.si.send_data("EOF")
        self.si.send_data([""])

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
        self.si.send_signal("processFinished")
        self.cur_process = "Idle"
        self.cur_progress = 0
        self.total_progress = 0
        self.update_progress()

    def terminateProcess(self):
        self.running = False
        
        
        time.sleep(1)
        if self.run_thread is not None:
            self.run_thread.join()
            self.run_thread = None
            
        self.update_progress_lock = False
        self.cur_process = "Idle"
        self.cur_progress = 0
        self.total_progress = 0
        self.update_progress()

    def save_record(self):
        if self.record is None:
            logger.warning("No record to save")
            return
        
        script_result = self.sm.get_result()
        if script_result is None:
            self.record.set_script(script_result)
            self.raise_error("沒有正常完成轉錄, 取消操作")
            return
        
        self.record.set_script(self.sm.get_result())
        
        self.record.export()

if __name__ == '__main__':
    Backend()
