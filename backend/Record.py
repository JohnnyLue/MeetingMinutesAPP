import datetime
import json
import logging
import os

logger = logging.getLogger()

class Record:
    def __init__(self, file_path = None, store_base = os.path.join(os.getcwd(), "records")):
        self.path = file_path
        self.base_dir = store_base
        self.parameters = {}
        self.data = {}
        self.script = {}
        self.is_ready = False
        
        if file_path is not None:
            if os.path.exists(file_path):
                if self._check_format(file_path):
                    if not os.path.exists(file_path):
                        logger.info("Create new record")
                        self.path = self.__generate_path()
                    logger.info(f"Load record file {file_path}")
                    self.load(file_path)
                else:
                    logger.error("Invalid record file format, record initialization failed")
                    return
            elif file_path.endswith(".json"):
                self.path = file_path
        else:
            logger.info("Create new record")
            self.path = self.__generate_path()
            
        logger.info(f"Record initialized, record file: {self.path}")
    
    def clear(self):
        self.parameters = {}
        self.data = {}
        self.script = {}
        self.is_ready = False
    
    def load(self, file_path):
        if not self._check_format(file_path):
            logger.error(f"Invalid record file, cannot load: {file_path}")
            return
        with open(file_path, "r") as file:
            json_data = json.load(file)
            self.parameters = json_data["parameters"]
            self.data = json_data["data"]
            self.script = json_data["script"]
        self.is_ready = True
        self.path = file_path
        
    def set_parameter(self, key, value):
        self.parameters[key] = value
        logger.info(f"Set parameter: {key} = {value}")
    
    def get_parameter(self, key):
        if key not in self.parameters:
            return None
        logger.debug(f"Get parameter: {key} = {self.parameters[key]}")
        return self.parameters[key]
    
    def get_script(self):
        return self.script
    
    def get_data(self):
        return self.data
    
    def write_data(self, time_s, bboxes, names, statuses):
        self.data[time_s] = {"bbox": bboxes, "names": names, "statuses": statuses}
        
    def write_script(self, script_result):
        logger.info("Write script to record")
        self.script = script_result
        
    def export(self, file_path = None):
        if not self.is_ready:
            logger.error("Record is not ready")
            return
        if file_path is not None:
            try:
                if len(self.parameters) > 0 and len(self.data) > 1 and len(self.script) > 1:
                    with open(self.path, "w") as file:
                        json.dump({"parameters": self.parameters, "data": self.data, "script": self.script}, file)
            except:
                raise Exception("Record::export: Cannot export record file")
            return
        else:
            try:
                if len(self.parameters) > 0 and len(self.data) > 1 and len(self.script) > 1:
                    with open(self.path, "w") as file:
                        json.dump({"parameters": self.parameters, "data": self.data, "script": self.script}, file)
            except:
                logger.error("Cannot export record file")
                return
        return
    
    def _check_format(self, file_path: str):
        if not file_path.endswith(".json"):
            logger.error(f"File not exist or not a json file: {file_path}")
            return False
        if not os.path.exists(file_path):
            logger.error(f"File not exist: {file_path}")
            return False
        try:
            with open(file_path, "r") as file:
                data = json.load(file)
                if "parameters" in data and "data" in data and "script" in data:
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