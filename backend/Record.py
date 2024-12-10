import datetime
import json
import logging
import os

logger = logging.getLogger()

class Record:
    def __init__(self, base_dir = "records"):
        self.info = {}
        self.parameters = {}
        self.data = {}
        self.script = {}
        self.base_dir = base_dir
        self.file_path = None
    
    def clear(self):
        self.info = {}
        self.parameters = {}
        self.data = {}
        self.script = {}
        self.file_path = None
    
    def load_info(self, file_path):
        # only load info part
        if not self._check_format(file_path):
            logger.error(f"Invalid record file, cannot load: {file_path}")
            return
        try:
            with open(file_path, "r") as file:
                json_data = json.load(file)                
                self.info = json_data["info"]
                if self.info is None:
                    self.info = {}
        except:
            logger.error(f"Cannot load record file: {file_path}")
            self.clear()
            return
        self.file_path = file_path
    
    def load(self, file_path):
        if not self._check_format(file_path):
            logger.error(f"Invalid record file, cannot load: {file_path}")
            return
        try:
            with open(file_path, "r") as file:
                json_data = json.load(file)                
                self.info = json_data["info"]
                if self.info is None:
                    self.info = {}
                self.parameters = json_data["parameters"]
                if self.parameters is None:
                    self.parameters = {}
                self.data = json_data["data"]
                if self.data is None:
                    self.data = {}
                self.script = json_data["script"]
                if self.script is None:
                    self.script = {}
        except:
            logger.error(f"Cannot load record file: {file_path}")
            self.clear()
            return
        self.file_path = file_path
        
    def set_parameter(self, key, value):
        self.parameters[key] = value
        logger.info(f"Set parameter: {key} = {value}")
    
    def get_parameter(self, key):
        if key not in self.parameters:
            return None
        logger.debug(f"Get parameter from record: {key} = {self.parameters[key]}")
        return self.parameters[key]
    
    def get_info(self):
        if "record_name" not in self.info or "create_time" not in self.info or "video_path" not in self.info or "fps" not in self.info or "database_name" not in self.info:
            return None
        return self.info
    
    def get_script(self):
        if len(self.script) == 0:
            logger.warning("No script in record")
            return None
        logger.debug("Get script from record")

        return self.get_script_with_speaker()

    def get_script_with_speaker(self):
        if len(self.script) == 0:
            logger.warning("No script in record")
            return None
        if len(self.data) == 0:
            logger.warning("No data in record")
            return None
        logger.debug("Get script and speaker info from record")

        script_with_speaker = []
        fps = self.info["fps"]
        for i in range(len(self.script)):
            item = self.script[i]
            start_frame = int(item["start"] * fps)
            # search around start_frame
            speaking_counter = {}
            search_frame = start_frame - fps
            for j in range(fps*2):
                index = str(search_frame + j)
                if index in self.data:
                    names = self.data[index]["names"]
                    statuses = self.data[index]["statuses"]
                    logger.debug(f"Frame {search_frame + j}, names: {names}, statuses: {statuses}")
                    assert len(names) == len(statuses)
                    for k in range(len(names)):
                        if statuses[k]:
                            if names[k] not in speaking_counter:
                                speaking_counter[names[k]] = 1
                            speaking_counter[names[k]] += 1
            if len(speaking_counter) == 0:
                speaker = ""
            else:
                max_time = max(speaking_counter.values())
                speaker = ""
                for name in speaking_counter:
                    if speaking_counter[name] == max_time:
                        speaker = name
                        break
            logger.debug(f"Speaker: {speaker}, at frame {start_frame}")
            script_with_speaker.append({"start": item["start"], "end": item["end"], "text": item["text"], "speaker": speaker})

        return script_with_speaker
    
    def get_data(self):
        if len(self.data) == 0:
            logger.warning("No data in record")
            return None
        return self.data
    
    def set_info(self, record_name, create_time, video_path, fps, database_name):
        if not isinstance(create_time, str) or not isinstance(video_path, str) or not isinstance(fps, int) or not isinstance(database_name, str):
            logger.error("Invalid info")
            return
        if record_name is None:
            logger.debug("Generate record name")
            record_name = create_time
        if not isinstance(record_name, str):
            logger.error("Invalid record name")
            return
        self.info = {"record_name": record_name, "create_time": create_time, "video_path": video_path, "fps": fps, "database_name": database_name}
        self.file_path = os.path.join(self.base_dir, record_name + ".json")
        logger.debug(f"Set info: record_name = {record_name}, video_path = {video_path}, fps = {fps}, database_name = {database_name}")
    
    def write_data(self, frame_idx, bboxes, names, statuses):
        self.data[frame_idx] = {"bbox": bboxes, "names": names, "statuses": statuses}
        
    def set_script(self, script_result):
        logger.debug("Write script to record")
        self.script = script_result
        
    def export(self, file_path = None):
        logger.debug(f"Export record, file_path: {file_path}")
        logger.debug(f"info {self.info}, parameters: {self.parameters}, data_len: {len(self.data)}, script: {self.script}")
        if file_path is not None:
            try:
                if not file_path.endswith(".json") and file_path.count(".") == 0:
                    file_path = file_path + ".json"
                    
                with open(os.path.join(self.base_dir, file_path), "w") as file:
                    json.dump({"info": self.info, "parameters": self.parameters, "data": self.data, "script": self.script}, file)
            except:
                logger.error("Cannot export record file")
            return
        else:
            if self.file_path is None:
                logger.error("No file path to export record")
                return
            #try:
            logger.debug(f"Export record to {self.file_path}")
            with open(self.file_path, "w") as file:
                json.dump({"info": self.info, "parameters": self.parameters, "data": self.data, "script": self.script}, file)
            #except:
            #    logger.error("Cannot export record file")
            #    return
        return
    
    def _check_format(self, file_path):
        if not isinstance(file_path, str):
            logger.error(f"Invalid file path: {file_path}")
            return False
        if not file_path.endswith(".json"):
            logger.error(f"File not exist or not a json file: {file_path}")
            return False
        if not os.path.exists(file_path):
            logger.error(f"File not exist: {file_path}")
            return False
        try:
            with open(file_path, "r") as file:
                data = json.load(file)
                if "info" in data and "parameters" in data and "data" in data and "script" in data:
                    return True
        except:
            logger.error(f"Encounter error opening json file: {file_path}")
            return False
        
        logger.error(f"Invalid record file format: {file_path}")
        return False
            
    def __generate_path(self):
        os.makedirs(self.base_dir, exist_ok=True)
        date_str = datetime.datetime.now().strftime("%Y_%m_%d")
        i = 1
        while os.path.exists(os.path.join(self.base_dir, date_str + ".json")):
            date_str = date_str + f" ({i})"
            i += 1
        logger.debug(f"Generate file path: {date_str}")
        return os.path.join(self.base_dir, date_str + ".json")