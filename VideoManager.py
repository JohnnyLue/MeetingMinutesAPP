import cv2
import os
import subprocess
import shutil
import tempfile
import tqdm

supported_format = ['mp4']

class VideoManager:
    def __init__(self, video_path = 0):
        self.is_ready = False
        self.writing = False
        self.using_cam = False
        self.tempdir = tempfile.mkdtemp()
        if not video_path == 0:
            if not os.path.exists(video_path):
                print('VideoManager::__init__: video not exist.')
                return
            for fmt in supported_format:
                if video_path.endswith(fmt):
                    self.video_path = video_path
                    break
                print('VideoManager::__init__: video format not supported.')
                return
            self.video_path = video_path
        else:
            self.video_path = 0
            self.using_cam = True

        self.cap = cv2.VideoCapture(self.video_path)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        print(f'total frames: {self.total_frames}')
        
        # get video info
        if self.video_path == 0:
            self.file_name = self._generate_file_name()
        else:
            self.file_name = os.path.basename(self.video_path)
        self.codec = "mp4v"
        self.fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        self.print_info()
        
        self.is_ready = True
        
        # extract audio and video
        self.extracted_audio_path = self.extract_audio()
        self.extracted_video_path = self.extract_video()
        if not self.extracted_audio_path or not self.extracted_video_path:
            print('VideoManager::__init__: extract audio or video failed.')
            return
        
    def extract_audio(self):
        '''
        extract audio from video, stored in wav
        output: [str] the path of extracted audio
        '''
        if not self.is_ready:
            print('VideoManager::extract_audio: initialization is not done.')
            return
        
        path = os.path.join(self.tempdir, 'extracted.wav')
        self.writing = True
        p = subprocess.Popen(['ffmpeg', '-y', '-i', self.video_path, path])
        p.wait()
        
        return path
    
    def extract_video(self):
        '''
        extract soundless video from video, stored in mp4
        output: [str] the path of extracted video
        '''
        if not self.is_ready:
            print('VideoManager::extract_video: initialization is not done.')
            return
        
        path = os.path.join(self.tempdir, 'extracted.mp4')
        self.out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*self.codec), self.fps, (self.width, self.height))
        for i in tqdm.tqdm(range(self.total_frames), desc='extracting video'):
            ret, frame = self.cap.read()
            if ret:
                self.out.write(frame)
            else:
                break
        self.out.release()
        
        return path
    
    def print_info(self):
        print(f'Name:{self.file_name}, codec:{self.codec}, fps:{self.fps}, height:{self.height}, width:{self.width}')
    
    def record_cam(self, seconds = 5):
        if not self.is_ready:
            print('VideoManager::record_cam: initialization is not done.')
            return
        if self.writing:
            print('VideoManager::record_cam: recording is already in progress.')
            return
        if not self.using_cam:
            print('VideoManager::record_cam: Not using camera.')
            return
        
        self.writing = True
        self.out = cv2.VideoWriter(self.file_name, cv2.VideoWriter_fourcc(*'mp4v'), self.fps, (self.width, self.height))
        total_frames = self.fps * seconds
        frame_cnt = 0
        while True:
            ret, frame = self.cap.read()
            if ret:
                self.out.write(frame)
            else:
                break
            frame_cnt += 1
            if frame_cnt >= total_frames:
                break
        self.out.release()
    
    def save_video(self, path = ''):
        if not self.is_ready:
            print('VideoManager::save_video: initialization is not done.')
            return
        if path == '':
            path = self._generate_file_name()
            
        p = subprocess.Popen(['ffmpeg', '-y', '-i', self.extracted_video_path, '-i', self.extracted_audio_path, path])
        p.wait()
        
    def _generate_file_name(self):
        import time
        timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        fname = timestamp+'.mp4'
        i = 1
        while os.path.exists(fname):
            fname = timestamp + f' ({i})' +'.mp4'
            i+=1
        return fname
    
    def __del__(self):
        if self.is_ready:
            self.cap.release()
        if self.writing:
            self.out.release()
        shutil.rmtree(self.tempdir, ignore_errors=True)

if __name__ == '__main__':
    vm = VideoManager(r"C:\Users\JohnnyLue\Videos\Overwolf\Insights Capture\VALORANT 05-24-2024_14-05-07-489.mp4")
    #vm.print_info()
    vm.save_video('test.mp4')
