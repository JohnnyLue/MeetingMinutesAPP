import datetime
import json
import logging
import os

logger = logging.getLogger()

class Record:
    def __init__(self):
        self.info = {}
        self.parameters = {}
        self.data = {}
        self.script = {}
        self.file_path = None
    
    def clear(self):
        self.info = {}
        self.parameters = {}
        self.data = {}
        self.script = {}
        self.file_path = None
    
    def load(self, file_path):
        if not self._check_format(file_path):
            logger.error(f"Invalid record file, cannot load: {file_path}")
            return
        with open(file_path, "r") as file:
            json_data = json.load(file)
            self.info = json_data["info"]
            self.parameters = json_data["parameters"]
            self.data = json_data["data"]
            self.script = json_data["script"]
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
        if "record_name" not in self.info or "create_time" not in self.info or "video_path" not in self.info or "database_name" not in self.info:
            return None
        return self.info
    
    def get_script(self):
        if len(self.script) == 0:
            logger.warning("No script in record")
            return None
        return self.script
    
    def get_data(self):
        if len(self.data) == 0:
            logger.warning("No data in record")
            return None
        return self.data
    
    def set_info(self, record_name, create_time, video_path, database_name):
        if not isinstance(create_time, str) or not isinstance(video_path, str) or not isinstance(database_name, str):
            logger.error("Invalid info")
            return
        if record_name is None:
            logger.debug("Generate record name")
            record_name = create_time
        if not isinstance(record_name, str):
            logger.error("Invalid record name")
            return
        self.info = {"record_name": record_name, "create_time": create_time, "video_path": video_path, "database_name": database_name}
        self.file_path = record_name + ".json"
        logger.debug(f"Set info: record_name = {record_name}, video_path = {video_path}, database_name = {database_name}")
    
    def write_data(self, frame_idx, bboxes, names, statuses):
        self.data[frame_idx] = {"bbox": bboxes, "names": names, "statuses": statuses}
        
    def set_script(self, script_result):
        logger.debug("Write script to record")
        self.script = script_result
        
    def export(self, file_path = None):
        if file_path is not None:
            try:
                with open(file_path, "w") as file:
                    json.dump({"info": self.info, "parameters": self.parameters, "data": self.data, "script": self.script}, file_path)
            except:
                logger.error("Cannot export record file")
            return
        else:
            if self.file_path is None:
                logger.error("No file path to export record")
                return
            try:
                with open(self.file_path, "w") as file:
                    json.dump({"info": self.info, "parameters": self.parameters, "data": self.data, "script": self.script}, self.file_path)
            except:
                logger.error("Cannot export record file")
                return
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