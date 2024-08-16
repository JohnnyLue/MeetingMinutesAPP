import os
import json
import datetime

class Record:
    def __init__(self, file_path = None, store_base = os.path.join(os.getcwd(), "records")):
        self.path = file_path
        self.base_dir = store_base
        self.parameters = {}
        self.data = {}
        
        if file_path is not None:
            if self._check_format(file_path):
                print("Record::__init__: Load record file")
                self.load(file_path)
            else:
                raise Exception("Record::__init__: Invalid record file format")
        else:
            self.path = self.__generate_path()
    
    def load(self, file_path):
        with open(file_path, "r") as file:
            json_data = json.load(file)
            self.parameters = json_data["parameters"]
            self.data = json_data["data"]
        self.path = file_path
        
    def set_parameter(self, key, value):
        self.parameters[key] = value
    
    def get_parameter(self, key):
        if key not in self.parameters:
            return None
        return self.parameters[key]
    
    def write_data(self, time_ms, faces, names, statuses):
        self.data[time_ms] = {"faces": faces, "names": names, "statuses": statuses}
        
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
                with open(self.path, "w") as file:
                    json.dump({"parameters": self.parameters, "data": self.data}, file)
            except:
                raise Exception("Record::export: Cannot export record file")
            return self.path
    
    def _check_format(self, file_path: str):
        if not os.path.isfile(file_path) or not file_path.endswith(".json"):
            return False
        try:
            with open(file_path, "r") as file:
                data = json.load(file)
                if "parameters" in data and "data" in data:
                    return True
        except:
            return False
        return False
            
    def __generate_path(self):
        os.makedirs(self.base_dir, exist_ok=True)
        date_str = datetime.datetime.now().strftime("%Y_%m_%d")
        i = 1
        while os.path.exists(os.path.join(self.base_dir, date_str + ".json")):
            date_str = date_str + f" ({i})"
            i += 1
        return os.path.join(self.base_dir, date_str + ".json")