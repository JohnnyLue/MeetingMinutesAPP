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
            if self._check_format(file_path):
                logger.info(f"Load record file {file_path}")
                self.load(file_path)
            else:
                logger.error("Invalid record file format, record initialization failed")
                return
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
        if self.is_ready:
            logger.debug("Get script from record")
            return self.script
        return None
    
    def get_data(self):
        if self.is_ready:
            logger.debug("Get data from record")
            return self.data
        return None
    
    def write_data(self, time_s, bboxes, names, statuses):
        self.data[time_s] = {"bbox": bboxes, "names": names, "statuses": statuses}
        
    def write_script(self, script_result):
        logger.info("Write script to record")
        self.script = script_result
        
    def export(self, file_path = None):
        if file_path:
            try:
                if os.path.exists(file_path):
                    input_str = input(f"Record::export: File {file_path} already exists. Overwrite? (y/n) ")
                    if input_str.lower() != "y":
                        return None
                with open(file_path, "w") as file:
                    json.dump({"parameters": self.parameters, "data": self.data}, file)
            except:
                raise Exception("Record::export: Cannot export record file")
            return file_path
        else:
            try:
                if os.path.exists(self.path):
                    input_str = input(f"Record::export: File {self.path} already exists. Overwrite? (y/n) ")
                    if input_str.lower() != "y":
                        return None
                if self.parameters and self.data and self.script:
                    with open(self.path, "w") as file:
                        json.dump({"parameters": self.parameters, "data": self.data, "script": self.script}, file)
                else:
                    raise
            except:
                raise Exception("Record::export: Cannot export record file")
            return self.path
    
    def _check_format(self, file_path: str):
        if not os.path.isfile(file_path) or not file_path.endswith(".json"):
            logger.error(f"File not exist or not a json file: {file_path}")
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