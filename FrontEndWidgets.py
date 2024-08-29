
import cv2
from PyQt5 import QtWidgets, QtCore, QtGui
import threading
import time
from ffpyplayer.player import MediaPlayer

def cv2_to_pixmap(cv2_img):
    cv2_img = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)
    height, width, channel = cv2_img.shape
    bytesPerLine = channel * width
    qImg = QtGui.QImage(cv2_img.data, width, height, bytesPerLine, QtGui.QImage.Format_RGB888)
    return QtGui.QPixmap.fromImage(qImg)

class ErrorDialog(QtWidgets.QDialog):
    def __init__(self, message):
        super().__init__()
        self.setWindowTitle("Error")
        self.setMinimumSize(300, 150)
        
        layout = QtWidgets.QVBoxLayout(self)
        label = QtWidgets.QLabel(message, self)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        label.setFont(MyFont())
        layout.addWidget(label)
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        btn = QtWidgets.QPushButton("確認", self)
        btn.setFixedWidth(100)
        btn.clicked.connect(self.close)
        btn.setFont(MyFont())
        btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

class MyFont(QtGui.QFont):
    def __init__(self):
        super().__init__()
        self.setFamily("微軟正黑體")
        self.setPointSize(12)
        self.setBold(True)
        self.setWeight(70)
        self.setItalic(False)

class FileDropArea(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # 設置區域樣式
        self.setAcceptDrops(True)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(640, 360)
        self.setStyleSheet("border: 2px dashed #aaa;\
                            border-radius: 20px;")
        self.label = QtWidgets.QLabel("拖放檔案至此，或點擊選取檔案", self)
        self.label.setFont(MyFont())
        self.label.setAlignment(QtCore.Qt.AlignCenter)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.label)
        self.setLayout(layout)
    
    def dragEnterEvent(self, event: QtGui.QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QtGui.QDropEvent):
        files = [url.toLocalFile() for url in event.mimeData().urls()]
        if len(files) > 1:
            self.parent().signal_manager.errorOccor.emit("Please only select one video file.")
            return
        self.parent().signal_manager.selectedVideo.emit(files[0])

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.LeftButton:
            self.parent().open_select_video_dialog()

class VideoPlayer(QtWidgets.QLabel):
    def __init__(self, parent=None, video_path=None):
        super().__init__(parent)
        self.is_paused = True
        self.quit_loop = False
        self.cap = None
        self.play_thread = None
        self.buffer_thread = None
        self.video_buffer = []
        self.buf_paused = False
        self.load(video_path)
        self.setFixedSize(640, 360)
    
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.parent().video_pause_button.click()
        
    def update(self, img):
        self.setPixmap(img.scaled(640, 360, QtCore.Qt.AspectRatioMode.KeepAspectRatio))

    def load(self, path):
        self.quit_loop = False
        self.cap = cv2.VideoCapture(path)
        self.update(cv2_to_pixmap(self.cap.read()[1]))
        self.audio = MediaPlayer(path, ff_opts={'vn': 1, 'sn': 1, 'paused': 1})
        self.video_buffer = []
        self.start_buffer()

    def reset(self):
        self.quit_loop = True
        self.play_thread.join()
        self.buffer_thread.join()
        self.cap.release()
        self.buffer_clean()
        self.audio.close_player()

    def pause(self):
        self.is_paused = not self.is_paused
        self.audio.toggle_pause()
        if self.audio.get_pause() == 1:
            self.audio.seek(self.cap.get(cv2.CAP_PROP_POS_MSEC), relative=False)

    def forward(self, seconds):
        ori_state = self.is_paused
        self.is_paused = True
        self.buf_paused = True
        self.audio.set_pause(1)
        time.sleep(0.1)
        self.video_buffer = []
        self.cap.set(cv2.CAP_PROP_POS_MSEC, self.cap.get(cv2.CAP_PROP_POS_MSEC) + seconds*1000)
        self.audio.seek(self.cap.get(cv2.CAP_PROP_POS_MSEC), relative=False)
        _, frame = self.cap.read()
        pFrame = cv2_to_pixmap(frame)
        self.update(pFrame)
        self.is_paused = ori_state
        self.buf_paused = False
        self.audio.set_pause(0)
    
    def rewind(self, seconds):
        ori_state = self.is_paused
        self.is_paused = True
        self.buf_paused = True
        self.audio.set_pause(1)
        time.sleep(0.1)
        self.video_buffer = []
        self.cap.set(cv2.CAP_PROP_POS_MSEC, self.cap.get(cv2.CAP_PROP_POS_MSEC) - seconds*1000)
        self.audio.seek(self.cap.get(cv2.CAP_PROP_POS_MSEC), relative=False)
        _, frame = self.cap.read()
        pFrame = cv2_to_pixmap(frame)
        self.update(pFrame)
        self.is_paused = ori_state
        self.buf_paused = False
        self.audio.set_pause(0)
        
    def set_time(self, seconds):
        self.cap.set(cv2.CAP_PROP_POS_MSEC, seconds*1000)
        
    def get_time(self):
        return self.cap.get(cv2.CAP_PROP_POS_MSEC)/1000
    
    def get_total_time(self):
        return self.cap.get(cv2.CAP_PROP_FRAME_COUNT)/self.cap.get(cv2.CAP_PROP_FPS)
    
    def play(self):
        def func():
            delay = 1.0/self.cap.get(cv2.CAP_PROP_FPS)
            adjust = 0.0
            frame_end = time.monotonic()
            while True:
                if self.quit_loop:
                    break
                if not self.is_paused and frame_end - time.monotonic() < 0 and len(self.video_buffer):
                    frame_end = time.monotonic()
                    print(self.audio.get_pts())
                    print(self.cap.get(cv2.CAP_PROP_POS_MSEC)/1000)
                    print(len(self.video_buffer))
                    #print(f'delay: {t - frame_end}')
                    
                    frame = self.video_buffer.pop(0)
                    #_, val = self.audio.get_frame()
        
                    if self.is_paused:
                        print('paused')
                        continue
                    #elif val == 'eof':
                    #    self.is_paused = True
                    #    continue
                    #elif val == 'paused':
                    #    print('paused')
                    #    continue
                    pFrame = cv2_to_pixmap(frame)
                    self.update(pFrame)
                    adjust = time.monotonic() - frame_end
                    frame_end += delay - adjust
                    
        self.play_thread = threading.Thread(target=func)
        self.play_thread.start()
        
    def start_buffer(self):
        def buffer():
            while True:
                if self.quit_loop:
                    break
                if len(self.video_buffer) < 200 and not self.buf_paused:
                    ret, frame = self.cap.read()
                    if not ret:
                        print('end of video')
                        break
                    self.video_buffer.append(frame)
        self.buffer_thread = threading.Thread(target=buffer)
        self.buffer_thread.start()