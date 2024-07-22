import cv2
import os
import subprocess
import shutil
import tempfile
import tqdm

supported_format = ['mp4']

class VideoManager:
    def __init__(self, video_path = 0, store_dir = './'):
        self.is_ready = False
        self.writing = False
        self.tempdir = tempfile.mkdtemp()
        if not os.path.exists(store_dir):
            try:
                os.mkdir(store_dir)
            except:
                print('VideoManager::__init__: store dir not exist and cannot create.')
                
        self.store_dir = store_dir
        
        # load video
        if video_path != 0:
            self.load_video(video_path)
                            
        # extract audio and video
        if self.is_ready:
            self.extracted_audio_path = self.extract_audio()
            #self.extracted_video_path = self.extract_video()
            if not self.extracted_audio_path:
                print('VideoManager::__init__: extract audio failed.')
                return
        
    def load_video(self, video_path):
        self.video_path = 0
        if self.is_ready:
            self.frame = None
            self.cap.release()
        self.is_ready = False
        self.cur_time = 0.0
        
        if not os.path.exists(video_path):
            print('VideoManager::load_video: video not exist.')
            return
        for fmt in supported_format:
            if video_path.endswith(fmt):
                self.video_path = video_path
                break
        if self.video_path == 0:
            print('VideoManager::load_video: video format not supported.')
            return
        
        self.cap = cv2.VideoCapture(self.video_path)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        print(f'total frames: {self.total_frames}')
        print(f'time: {self.total_frames/self.cap.get(cv2.CAP_PROP_FPS)}')
        
        # get video info
        self.file_name = os.path.basename(self.video_path)
        self.codec = "mp4v"
        self.fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        self.process_fps = self.fps # default process fps
        
        ret, self.frame = self.cap.read()
        if not ret or self.frame is None:
            print('VideoManager::load_video: load video failed.')
            return
        
        self.is_ready = True
    
    def extract_audio(self):
        '''
        extract audio from video, stored in wav
        output: [str] the path of extracted audio
        '''
        if not self.is_ready:
            print('VideoManager::extract_audio: initialization is not done.')
            return
        
        path = os.path.join(self.tempdir, 'extracted.wav')

        p = subprocess.Popen(['ffmpeg', '-y', '-i', self.video_path, path])
        p.wait()
        
        return path
    
    def print_info(self):
        print(f'Name:{self.file_name}, codec:{self.codec}, fps:{self.fps}, height:{self.height}, width:{self.width}')
    
    def set_fps(self, fps):
        if not self.is_ready:
            print('VideoManager::set_fps: initialization is not done.')
            return
        if fps <= 0:
            print('VideoManager::set_fps: fps must be greater than 0.')
            return
        self.process_fps = fps
    
    def get_fps(self):
        if not self.is_ready:
            print('VideoManager::set_fps: initialization is not done.')
            return
        return self.process_fps
    
    def next_frame(self):
        if not self.is_ready:
            print('VideoManager::next_frame: initialization is not done.')
            return
        self.cur_time = (self.cur_time + 1.0/self.process_fps)
        self.cap.set(cv2.CAP_PROP_POS_MSEC, self.cur_time * 1000)
        ret, self.frame = self.cap.read()
        if not ret or self.frame is None:
            print('VideoManager::next_frame: read frame failed.')
            return None
        
        return self.frame
    
    def get_time(self):
        if not self.is_ready:
            print('VideoManager::get_time: initialization is not done.')
            return 0
        return round(self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000, 1)
    
    def set_process_fps(self, fps):
        if not self.is_ready:
            print('VideoManager::set_fps: initialization is not done.')
            return
        self.fps = fps
        self.cap.set(cv2.CAP_PROP_FPS, fps)
    
    def save_video(self, path = ''):
        if not self.is_ready:
            print('VideoManager::save_video: initialization is not done.')
            return
        if path == '':
            path = self._generate_file_name()
            
        p = subprocess.Popen(['ffmpeg', '-y', '-i', self.video_path, '-i', self.extracted_audio_path, path])
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
    import time
    vm = VideoManager(video_path=r"C:\Users\JohnnyLue\Videos\Overwolf\Insights Capture\VALORANT 05-31-2024_23-13-03-895.mp4")
    vm.set_fps(20)
    vm.print_info()
    print(vm.get_fps())
    
    start_time = time.monotonic()
    processing = True
    pause = False
    fps = 20
    while(processing):
        now_time = time.monotonic()
        if (now_time - start_time) > 1.0/fps:
            if not pause:
                try:
                    frame = vm.next_frame()
                except:
                    break
            cv2.imshow('frame', frame)
            start_time = now_time
            
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            processing = False
        if key == ord('p'):
            pause = not pause
    cv2.destroyAllWindows()
    
    #vm.save_video('test.mp4')
