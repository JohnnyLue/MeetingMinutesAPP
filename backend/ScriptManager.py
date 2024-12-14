import logging
import os
import time
import whisper

logger = logging.getLogger()

class ScriptManager:
    def __init__(self, model_name = 'small', language = 'zh'):
        self.model = whisper.load_model(model_name)
        self.lang = language
        self.result = None
        self.lock = False
        logger.info("ScriptManager initialized")
    
    def transcribe(self, audio_path:str):
        logger.info("Start transcription")
        start_time = time.time()
        self.lock = True
        _result = whisper.transcribe(self.model, audio_path, language=self.lang, verbose=False)
        logger.debug(f"transcribed in {(time.time() - start_time):.2f}s")
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
            logger.warning("No result now")
            return None
        if self.lock:
            logger.warning("Result not ready")
            return None
        
        logger.debug("Get transcribe result")
        return self.result
    
    def get_script_by_time(self, _time:float):
        '''
        input: [float] time of video.
        output: [str|None] the coresponding line of script or None if no script at the time.
        '''
        if self.result == None:
            logger.warning("No result now")
            return ''
        if self.lock:
            logger.warning("Result not ready")
            return ''
        if _time < 0:
            logger.warning('Time must be positive float.')
            return ''
        
        for s in self.result:
            if s['start'] <= _time and s['end'] >= _time:
                return s['text'] if s['text'] else ''
        return ''
    
    def print_script(self):
        '''
        output: formated logger.warning to cmd console, for debug uses
        '''
        if self.result == None:
            logger.warning("No result now")
            return
        if self.lock:
            logger.warning("Result not ready")
            return
            
        for s in self.result:
            logger.debug(f"{s['start']} {s['end']} {s['text']}")
    
    def load_script_file(self, path):
        '''
        input: the path to the script file
        output: bool - whether load successfully
        '''
        if path is None:
            return 
        if not self._check_script_file_format(path):
            logger.warning("Script file format error")
            return 
        if self.lock:
            logger.warning("Wait until process ended.")
            return 
        logger.debug(f"Loading script file: {path}")
        self.result = []
        with open(path, 'r') as f:
            lines = f.readlines()
        for line in lines:
            s = line.strip().split('_')
            self.result.append({'start':float(s[0]), 'end':float(s[1]), 'text':s[2]})
        logger.info(f"Script file loaded: {path}")

    def load_script_from_record(self, record):
        result = record.get_script()
        if result == None:
            logger.warning("No script in record")
        else:
            self.result = result
            logger.info("Loaded from record")

    def script_detected_in(self, _from:float, _to:float):
        '''
        input:
        _from: the start time of time range in second
        _to: the end time of thme range in second
        
        output:
        bool: in the time range exist any detected script
        '''
        if self.result == None:
            logger.warning("No result now")
            return False
        if self.lock:
            logger.warning("Result not ready")
            return False
        if _from > _to:
            logger.warning("Start time large then end time")
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
            logger.warning('Encounter error writing file.')
            return False
        
        return True
    
    def append_script_file(self, path:str):
        '''
        input: the path to write the new script file
        output: bool - whether append successfully
        '''
        if not self._check_script_file_format(path):
            logger.warning("Script file format error")
            return False
        if self.result == None:
            logger.warning("No result now")
            return False
        if self.lock:
            logger.warning("Result not ready")
            return False
        
        try:
            with open(path, 'r') as f:
                lines = f.readlines()
        except:
            logger.error('Encounter error reading file.')
            return False
        init_time = float(lines[-1].split('_')[1]) # last segment's end time

        lines = []
        try:
            for s in self.result:
                lines.append(f"{round(s['start'] + init_time, 3)}_{round(s['end'] + init_time, 3)}_{s['text']}\n")
            with open(path, 'a') as f:
                f.writelines(lines)
        except:
            logger.error('Encounter error writing file.')
            return False
        return True
    
    def _check_script_file_format(self, path:str):
        if not os.path.exists(path):
            logger.warning(f'File path {path} not exist.')
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