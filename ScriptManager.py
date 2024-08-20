import whisper
import time
import os

class ScriptManager:
    def __init__(self, model_name = 'small', language = 'zh'):
        self.model = whisper.load_model(model_name)
        self.lang = language
        self.result = None
        self.lock = False
    
    def transcribe(self, audio_path:str):
        print("transcribing...")
        start_time = time.time()
        self.lock = True
        _result = whisper.transcribe(self.model, audio_path, language=self.lang, verbose=False)
        print(f"transcribed in {(time.time() - start_time):.2f}s")
        # post process of result (only keeps segments and only the start, end, text)
        _result = _result['segments']
        
        self.result = []
        for s in _result:
            new_s = {'start':round(s['start'], 3), 'end':round(s['end'], 3), 'text':s['text']}
            self.result.append(new_s)

        self.lock = False
    
    def get_result(self):
        '''
        output:
        a list, contains result segments
        segment: script unit containing start, end time and text(mainly)
        '''
        if self.result == None:
            print("ScriptManager::get_result: no result now")
            return None
        if self.lock:
            print("ScriptManager::get_result: result not ready")
            return None
            
        return self.result
    
    def get_script_by_time(self, _time:float):
        '''
        input: [float] time of video.
        output: [str|None] the coresponding line of script or None if no script at the time.
        '''
        if self.result == None:
            print("ScriptManager::get_result: no result now")
            return None
        if self.lock:
            print("ScriptManager::get_result: result not ready")
            return None
        if _time < 0:
            print('ScriptManager::get_script_by_time: time must be positive float.')
            return None
        
        for s in self.result:
            if s['start'] <= _time and s['end'] >= _time:
                return s['text']
        return None
    
    def print_script(self):
        '''
        output: formated print to cmd console, for debug uses
        '''
        if self.result == None:
            print("ScriptManager::print_script: no result now")
            return
        if self.lock:
            print("ScriptManager::print_script: result not ready")
            return
            
        for s in self.result:
            print(f"{s['start']} {s['end']} {s['text']}")
    
    def load_script_file(self, path:str):
        '''
        input: the path to the script file
        output: bool - whether load successfully
        '''
        if not self._check_script_file_format(path):
            print("ScriptManager::load_script_file: script file format error")
            return False
        if self.lock:
            print("ScriptManager::load_script_file: wait for process to end.")
            return False
        
        self.result = []
        with open(path, 'r') as f:
            lines = f.readlines()
        for line in lines:
            s = line.strip().split('_')
            self.result.append({'start':float(s[0]), 'end':float(s[1]), 'text':s[2]})

    def load_script_from_record(self, record):
        result = record.get_script()
        if result == None:
            print("ScriptManager::load_script_from_record: no script in record")
        else:
            self.result = result

    def script_detected_in(self, _from:float, _to:float):
        '''
        input:
        _from: the start time of time range in second
        _to: the end time of thme range in second
        
        output:
        bool: in the time range exist any detected script
        '''
        if self.result == None:
            print("ScriptManager::is_talking: no result now")
            return False
        if self.lock:
            print("ScriptManager::is_talking: result not ready")
            return False
        if _from > _to:
            print("ScriptManager::is_talking: error, start time large then end time")
            return False
        
        for s in self.result:
            if  s['start'] <= _from <= s['end'] or s['start'] <= _to <= s['end']:
                return True
        return False
    
    def save_script_file(self, path:str):
        '''
        input: [str] the path to generate script file
        output: [bool] success or not 
        '''
        lines = []
        try:
            for s in self.result:
                lines.append(f"{s['start']}_{s['end']}_{s['text']}\n")
            with open(path, 'w') as f:
                f.writelines(lines)
        except:
            print('ScriptManager::generate_script_file: encounter error writing file.')
            return False
        
        return True
    
    def append_script_file(self, path:str):
        '''
        input: the path to write the new script file
        output: bool - whether append successfully
        '''
        if not self._check_script_file_format(path):
            print("ScriptManager::append_script_file: script file format error")
            return False
        if self.result == None:
            print("ScriptManager::append_script_file: no result now")
            return False
        if self.lock:
            print("ScriptManager::append_script_file: result not ready")
            return False
        
        with open(path, 'r') as f:
            lines = f.readlines()
        init_time = float(lines[-1].split('_')[1]) # last segment's end time

        lines = []
        try:
            for s in self.result:
                lines.append(f"{round(s['start'] + init_time, 3)}_{round(s['end'] + init_time, 3)}_{s['text']}\n")
            with open(path, 'a') as f:
                f.writelines(lines)
        except:
            print('ScriptManager::append_script_file: encounter error writing file.')
        return True
    
    def _check_script_file_format(self, path:str):
        if not os.path.exists(path):
            print('ScriptManager::check_script_file_format: file path not exist.')
            return False
        
        with open(path, 'r') as f:
            lines = f.readlines()
            
        latest_time = 0.0
        for id, line in enumerate(lines):
            s = line.split('_')
            if len(s) != 3:
                return False
            if s[2] == '':
                return False
            if float(s[0]) > float(s[1]) or float(s[0]) < 0 or float(s[1]) < 0:
                return False
            if float(s[1]) < latest_time:
                return False
            latest_time = float(s[1])
        return True