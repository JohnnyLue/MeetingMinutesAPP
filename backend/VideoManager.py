import cv2
import logging
import os
import subprocess
import shutil
import tempfile

logger = logging.getLogger()

supported_format = ['mp4']

class VideoManager:
    def __init__(self, video_path = 0):
        self.is_ready = False
        self.writing = False
        self.tempdir = tempfile.mkdtemp()
        
        # load video
        if video_path != 0:
            self.load_video(video_path)
        
        self.cur_frame_idx = 0
        logger.info('VideoManager initialized.')

    def load_video(self, video_path):
        self.video_path = 0
        if self.is_ready:
            self.frame = None
            self.cap.release()
        self.is_ready = False
        self.cur_time = 0.0
        self.total_frames = 0
        self.total_time = 0.0
        self.file_name = ''
        self.codec = ''
        self.fps = 0
        self.width = 0
        self.height = 0
        self.cur_frame_idx = 0
        
        if not os.path.exists(video_path):
            logger.warning('Video not exist.')
            return
        for fmt in supported_format:
            if video_path.endswith(fmt):
                self.video_path = video_path
                break
        if self.video_path == 0:
            logger.warning('Video format not supported.')
            return
        
        self.cap = cv2.VideoCapture(self.video_path)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.total_time = self.total_frames/self.cap.get(cv2.CAP_PROP_FPS)
        logger.debug(f'total frames: {self.total_frames}')
        logger.debug(f'time: {self.total_time}')
        
        # get video info
        self.file_name = os.path.basename(self.video_path)
        self.codec = "mp4v"
        self.fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        self.is_ready = True
        
        self.next_frame()

    def get_video_path(self):
        if not self.is_ready:
            logger.warning('Initialization is not done.')
            return None
        return self.video_path

    def print_info(self):
        logger.info(f'Name:{self.file_name}, codec:{self.codec}, fps:{self.fps}, height:{self.height}, width:{self.width}')

    def next_frame(self):
        if not self.is_ready:
            logger.warning('Initialization is not done.')
            return None
        
        ret, self.frame = self.cap.read()
        if not ret or self.frame is None:
            logger.warning('Read frame failed.')
            return None
        
        self.cur_frame_idx += 1
        
        return self.frame

    def get_cur_frame_idx(self):
        return self.cur_frame_idx

    def get_frame(self):
        '''
        get the current frame by time, won't update current time
        '''
        if not self.is_ready:
            logger.warning('Initialization is not done.')
            return
        if self.frame is None:
            logger.warning('Read frame failed.')
            return None
        
        return self.frame

    def forward(self, seconds):
        '''
        input: [float] seconds to forward
        '''
        if not self.is_ready:
            logger.warning('Initialization is not done.')
            return
        if seconds <= 0:
            logger.warning('Seconds must be positive float.')
            return
        cur_time_ms = self.cap.get(cv2.CAP_PROP_POS_MSEC)
        new_time_ms = min(cur_time_ms + seconds * 1000, self.total_time * 1000)
        self.cap.set(cv2.CAP_PROP_POS_MSEC, new_time_ms)
        self.frame = self.cap.read()[1]
        self.cur_frame_idx = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
        logger.debug(f'forward {new_time_ms} ms')

    def rewind(self, seconds):
        if not self.is_ready:
            logger.warning('Initialization is not done.')
            return
        if seconds <= 0:
            logger.warning('Seconds must be positive float.')
            return
        
        cur_time_ms = self.cap.get(cv2.CAP_PROP_POS_MSEC)
        new_time_ms = max(cur_time_ms - seconds * 1000, 0)
        self.cap.set(cv2.CAP_PROP_POS_MSEC, new_time_ms)
        self.frame = self.cap.read()[1]
        self.cur_frame_idx = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
        logger.debug(f'rewind {new_time_ms} ms')

    def is_end(self):
        if not self.is_ready:
            logger.warning('Initialization is not done.')
            return False
        
        return abs(self.cur_frame_idx - self.total_frames) < 10

    def get_time(self):
        if not self.is_ready:
            logger.warning('Initialization is not done.')
            return 0
        
        return round(self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000, 1)

    def get_total_frame(self):
        if not self.is_ready:
            logger.warning('Initialization is not done.')
            return 0
        
        return self.total_frames

    def _generate_file_path(self, dir):
        import time
        timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        fname = timestamp+'.mp4'
        fpath = os.path.join(dir, fname)
        i = 1
        while os.path.exists(fpath):
            fname = timestamp + f' ({i})' +'.mp4'
            fpath = os.path.join(dir, fname)
            i+=1
        logger.debug(f'Generated file path: {fpath}')
        return fpath

    def __del__(self):
        if self.is_ready:
            self.cap.release()
        if self.writing:
            self.out.release()
        shutil.rmtree(self.tempdir, ignore_errors=True)
        logger.debug('VideoManager deleted.')