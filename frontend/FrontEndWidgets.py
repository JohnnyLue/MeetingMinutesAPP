
import cv2
from ffpyplayer.player import MediaPlayer
import glob
import logging
import math
import os
from PyQt5 import QtWidgets, QtCore, QtGui
import threading
import time

logger = logging.getLogger()

def cv2_to_pixmap(cv2_img):
    cv2_img = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)
    height, width, channel = cv2_img.shape
    bytesPerLine = channel * width
    qImg = QtGui.QImage(cv2_img.data, width, height, bytesPerLine, QtGui.QImage.Format_RGB888)
    return QtGui.QPixmap.fromImage(qImg)

def new_button(text=""):
    btn = QtWidgets.QPushButton()
    btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
    btn.setFixedHeight(40)
    btn.setFixedWidth(150)
    btn.setFont(MyFont())
    btn.setText(text)
    return btn

class ErrorDialog(QtWidgets.QDialog):
    def __init__(self, message):
        super().__init__()
        self.setWindowTitle("Error")
        self.setMinimumSize(300, 150)
        
        layout = QtWidgets.QVBoxLayout(self)
        label = QtWidgets.QLabel(message, self)
        label.setWordWrap(True)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        label.setFont(MyFont())
        layout.addWidget(label)
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        btn = new_button("確定")
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
            self.parent().open_error_dialog("Please only select one video file.")
            return
        self.parent().si.send_signal("selectedVideo")
        self.parent().si.send_data(files[0])

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.LeftButton:
            self.parent().open_select_video_dialog()

class VideoPlayer(QtWidgets.QLabel):
    def __init__(self, parent=None, video_path=None):
        super().__init__(parent)
        self.is_paused = True
        self.quit_loop = False
        self.cap = None
        self.audio = None
        self.play_thread = None
        self.lock_read = True
        self.total_time = 0
        self.cur_time = 0
        self.load(video_path)
        self.setFixedSize(640, 360)
    
    def mousePressEvent(self, event):
        if self.quit_loop:
            return
        if event.button() == QtCore.Qt.LeftButton:
            self.pause()
        
    def update(self, img):
        self.setPixmap(img.scaled(640, 360, QtCore.Qt.AspectRatioMode.KeepAspectRatio))

    def load(self, path):
        self.quit_loop = False
        self.lock_read = True
        self.cap = cv2.VideoCapture(path)
        self.update(cv2_to_pixmap(self.cap.read()[1]))
        self.audio = MediaPlayer(path, ff_opts={'vn': 1, 'sn': 1, 'paused': 1, 'sync': 'audio'})
        
        logger.debug(f'''Video loaded:
fps:{int(self.cap.get(cv2.CAP_PROP_FPS))}
frame count:{int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))}
video size:{int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}''')
        self.total_time = self.cap.get(cv2.CAP_PROP_FRAME_COUNT)/self.cap.get(cv2.CAP_PROP_FPS)
        def wait_for_audio_load():
            time.sleep(3)
            self.lock_read = False
        threading.Thread(target=wait_for_audio_load).start()

    def close(self):
        self.lock_read = True
        self.quit_loop = True
        self.play_thread.join()
        self.cap.release()
        #self.audio.close_player()
        self.cap = None
        self.audio = None
        logger.debug('Video player closed')

    def pause(self):
        if self.quit_loop:
            return
        if self.lock_read:
            return
        self.lock_read = True
        self.audio.toggle_pause()
        self.is_paused = not self.is_paused
        logger.debug(f'pause: {self.is_paused}')
        self.lock_read = False

    def forward(self, seconds):
        if self.quit_loop:
            return
        if self.lock_read:
            return
        ori_state = self.is_paused
        self.is_paused = True
        self.audio.set_pause(1)
        self.lock_read = True
        time.sleep(0.5) # wait for thread to pause
        
        logger.debug(f'current time: {self.audio.get_pts() * 1000}')
        new_time = (self.audio.get_pts() + seconds) * 1000
        logger.debug(f'new time: {new_time}')
        if new_time < 0:
            new_time = 0
        elif new_time > self.audio.get_metadata()['duration'] * 1000:
            new_time = self.audio.get_metadata()['duration'] * 1000 - 100
            
        self.cap.set(cv2.CAP_PROP_POS_MSEC, new_time)
        self.audio.seek(new_time / 1000, relative=False)
        
        ret, frame = self.cap.read()
        if not ret:
            logger.debug('End of video')
            self.is_paused = True
            self.audio.set_pause(1)
            # update the last frame of the video
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.cap.get(cv2.CAP_PROP_FRAME_COUNT)-1)
            ret, frame = self.cap.read()
            if not ret:
                logger.error('Read frame failed.')
                return
            pFrame = cv2_to_pixmap(frame)
            self.update(pFrame)
            return
        
        pFrame = cv2_to_pixmap(frame)
        self.update(pFrame)
        
        self.is_paused = ori_state
        self.audio.set_pause(1 if ori_state else 0)
        
        logger.debug(f'forward {seconds} seconds')
        self.lock_read = False
    
    def rewind(self, seconds):
        if self.quit_loop:
            return
        if self.lock_read:
            return
        ori_state = self.is_paused
        self.is_paused = True
        self.audio.set_pause(1)
        self.lock_read = True
        time.sleep(0.5) # wait for thread to pause
        
        logger.debug(f'current time: {self.audio.get_pts() * 1000}')
        new_time = (self.audio.get_pts() - seconds) * 1000
        logger.debug(f'new time: {new_time}')
        if new_time < 0:
            new_time = 0
        elif new_time > self.audio.get_metadata()['duration'] * 1000:
            new_time = self.audio.get_metadata()['duration'] * 1000 - 100
        
        self.cap.set(cv2.CAP_PROP_POS_MSEC, new_time)
        self.audio.seek(new_time / 1000, relative=False)
        
        ret, frame = self.cap.read()
        if not ret:
            logger.debug('End of video')
            self.is_paused = True
            self.audio.set_pause(1)
            # update the last frame of the video
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.cap.get(cv2.CAP_PROP_FRAME_COUNT)-1)
            ret, frame = self.cap.read()
            if not ret:
                logger.error('Read frame failed.')
                return
            pFrame = cv2_to_pixmap(frame)
            self.update(pFrame)
            return
        
        pFrame = cv2_to_pixmap(frame)
        self.update(pFrame)
        
        self.is_paused = ori_state
        self.audio.set_pause(1 if ori_state else 0)
        
        logger.debug(f'rewind {seconds} seconds')
        self.lock_read = False

    def set_time(self, new_time):
        if self.quit_loop:
            return
        if self.lock_read:
            return
        if new_time < 0:
            new_time = 0
        elif new_time > self.get_total_time_s():
            new_time = self.get_total_time_s()
            
        ori_state = self.is_paused
        self.is_paused = True
        self.audio.set_pause(1)
        self.lock_read = True
        time.sleep(0.5) # wait for thread to pause
        
        self.cap.set(cv2.CAP_PROP_POS_MSEC, new_time*1000)
        self.audio.seek(new_time, relative=False)
        
        ret, frame = self.cap.read()
        if not ret:
            logger.debug('End of video')
            self.is_paused = True
            self.audio.set_pause(1)
            # update the last frame of the video
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.cap.get(cv2.CAP_PROP_FRAME_COUNT)-1)
            ret, frame = self.cap.read()
            if not ret:
                logger.error('Read frame failed.')
                return
            pFrame = cv2_to_pixmap(frame)
            self.update(pFrame)
            return
        
        pFrame = cv2_to_pixmap(frame)
        self.update(pFrame)
        
        self.is_paused = ori_state
        self.audio.set_pause(1 if ori_state else 0)
        
        logger.debug(f'set time to {new_time} second')
        self.lock_read = False

    def get_time(self):
        if self.quit_loop:
            return -1
        if self.lock_read:
            return -1
        if self.cur_time < 0:
            return -1
        return self.cur_time
    
    def get_total_time_s(self):
        if self.quit_loop:
            return -1
        if self.lock_read:
            return -1
        return self.total_time
    
    def play(self):
        def func():
            delay = 1.0/self.cap.get(cv2.CAP_PROP_FPS)
            while True:
                if self.quit_loop:
                    break
                if not self.is_paused:
                    ret, frame = self.cap.read()
                    if not ret:
                        logger.debug('End of video')
                        self.is_paused = True
                        continue
                    pFrame = cv2_to_pixmap(frame)
                    audio_time = self.audio.get_pts() * 1000  # Get audio time in milliseconds, often crush program
                    cap_time = self.cap.get(cv2.CAP_PROP_POS_MSEC)
                    if abs(audio_time - cap_time) > 100: # Adjust video time to audio time
                        self.cap.set(cv2.CAP_PROP_POS_MSEC, audio_time)
                    self.update(pFrame)
                    self.cur_time = audio_time / 1000
                time.sleep(delay)
            logger.debug('End of play')
        
        self.play_thread = threading.Thread(target=func)
        self.play_thread.start()
        logger.debug('Start playing video')

class VideoControlPanel(QtWidgets.QWidget):
    def __init__(self, parent=None, video_player=None):
        super().__init__(parent)
        
        if video_player is None:
            logger.error('video_player is None')
            return
        self.video_player = video_player
        self.setFixedWidth(640)
        
        outer_layout = QtWidgets.QVBoxLayout()
        outer_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        btn_time_layout = QtWidgets.QHBoxLayout()
        btn_time_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        btn_time_layout = QtWidgets.QHBoxLayout()
        self.rewind_button = new_button("倒帶")
        self.rewind_button.setFixedWidth(100)
        self.rewind_button.clicked.connect(self.rewind)
        btn_time_layout.addWidget(self.rewind_button)

        self.play_button = new_button("播放")
        self.play_button.setFixedWidth(100)
        self.play_button.clicked.connect(self.play)
        btn_time_layout.addWidget(self.play_button)
        
        self.forward_button = new_button("快進")
        self.forward_button.setFixedWidth(100)
        self.forward_button.clicked.connect(self.forward)
        btn_time_layout.addWidget(self.forward_button)
        
        btn_time_layout.addStretch(1)
                
        self.time_label = QtWidgets.QLabel("00:00:00 / 00:00:00", self)
        self.time_label.setFont(MyFont())
        btn_time_layout.addWidget(self.time_label)
        
        outer_layout.addLayout(btn_time_layout)
        
        self.slider = VideoTimeSlider(self, video_player)
        
        outer_layout.addWidget(self.slider)
        
        self.setLayout(outer_layout)
                
        self.run = True
        
        def update_thread():
            while self.run:
                time.sleep(0.5) # update time every 0.5 second
                self.update_time()
        threading.Thread(target=update_thread).start()
        
    def play(self):
        self.video_player.pause()
        if self.video_player.is_paused:
            self.play_button.setText("播放")
        else:
            self.play_button.setText("暫停")
        
    def close(self):
        self.run = False
        
    def forward(self):
        self.video_player.forward(10)
        
    def rewind(self):
        self.video_player.rewind(10)
        
    def update_time(self):
        cur_time = self.video_player.get_time()
        total_time = self.video_player.get_total_time_s()
        if cur_time == -1 or total_time == -1:
            return
        self.time_label.setText(f'{time.strftime("%H:%M:%S", time.gmtime(cur_time))} / {time.strftime("%H:%M:%S", time.gmtime(total_time))}')
        if not self.slider.is_pressed():
            self.slider.setValue(cur_time)

class VideoTimeSlider(QtWidgets.QSlider):
    def __init__(self, parent=None, video_player=None):
        super().__init__(parent)
        self.video_player = video_player
        self.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.setFixedWidth(640)
        while self.video_player.get_total_time_s() == -1:
            time.sleep(0.5)
        self.setRange(0, int(self.video_player.get_total_time_s()))
        self.setValue(0)
        self.pressed = False
        
    def is_pressed(self):
        return self.pressed
        
    def mousePressEvent(self, event):
        self.pressed = True
        x = event.pos().x()
        value = self.maximum() * x / self.width()
        self.setValue(value)
        self.video_player.set_time(value)
        
    def mouseMoveEvent(self, event):
        x = event.pos().x()
        value = self.maximum() * x / self.width()
        logger.debug(f'value: {value}')
        self.setValue(value)
        self.video_player.set_time(value)
        
    def mouseReleaseEvent(self, event):
        self.pressed = False

class ParamPanel(QtWidgets.QScrollArea):
    '''
    ParamPanel is a widget for setting parameters for the run.
    '''
    def __init__(self, parent=None):
        super().__init__()
        self.scroll_widget = QtWidgets.QWidget(self)
        self.vertical_layout = QtWidgets.QVBoxLayout(self)
        self.scroll_widget.setLayout(self.vertical_layout)
        self.setWidget(self.scroll_widget)
        self.param_widgets = []
        
    def clear(self):
        for widget in self.param_widgets:
            self.vertical_layout.removeWidget(widget)
            widget.deleteLater()
        self.param_widgets = []
        
    def update(self):
        #for _ in range(self.vertical_layout.count()):
        #    self.vertical_layout.takeAt(0).widget().deleteLater()
        #    
        #for widget in self.param_widgets:
        #    self.vertical_layout.addWidget(widget)
        
        
        self.scroll_widget.resize(QtCore.QSize(self.size().width()-25, len(self.param_widgets)*40))
        logger.debug(f'new size: {(self.size().width()-25, len(self.param_widgets)*40)}')
        
    def add_param_widget_custom_value(self, name, default_value):
        '''
        Parameters can be set to custom value by user.
        '''
        widget = QtWidgets.QWidget(self)
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 5, 10, 5)
        label = QtWidgets.QLabel(name)
        label.setFont(MyFont())
        layout.addWidget(label)
        input = QtWidgets.QLineEdit()
        input.setText(str(default_value))
        input.setFont(MyFont())
        input.setFixedWidth(80)
        input.textChanged.connect(lambda: self.on_change(name, input.text()))
        layout.addWidget(input)
        widget.setLayout(layout)
        self.param_widgets.append(widget)
        self.vertical_layout.addWidget(widget)
        
    def add_param_widget_choise_value(self, name, options):
        '''
        parameters can be selected from a list of options.
        '''
        widget = QtWidgets.QWidget(self)
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 5, 10, 5)
        label = QtWidgets.QLabel(name)
        label.setFont(MyFont())
        layout.addWidget(label)
        input = QtWidgets.QComboBox()
        input.addItems(options)
        input.setFont(MyFont())
        input.setFixedWidth(80)
        input.setCurrentIndex(0) # default value
        input.currentIndexChanged.connect(lambda: self.on_change(name, input.currentText()))
        layout.addWidget(input)
        widget.setLayout(layout)
        self.param_widgets.append(widget)
        self.vertical_layout.addWidget(widget)
        
    def on_change(self, name, new_value):
        logger.info(f"{name} change to {new_value}")
        self.parent().alter_param(name, new_value)
        
class MemberDetailWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("詳細資料")
        self.setMinimumSize(600, 600)
        self.name = ''
        self.member_imgs = []
        self.ui()
    
    def ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        info_op_layout = QtWidgets.QHBoxLayout()
        info_op_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignJustify)
        
        name_layout = QtWidgets.QHBoxLayout()
        name_label = QtWidgets.QLabel("名字: ", self)
        name_label.setFont(MyFont())
        self.member_name = QtWidgets.QLabel("", self)
        self.member_name.setFont(MyFont())
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.member_name)
        info_op_layout.addLayout(name_layout)
        
        operator_layout = QtWidgets.QHBoxLayout()
        operator_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.edit_name_btn = new_button("編輯名稱")
        self.edit_name_btn.setFont(MyFont())
        self.edit_name_btn.setFixedWidth(100)
        self.edit_name_btn.clicked.connect(self.edit_name)
        self.add_pic_btn = new_button("新增照片")
        self.add_pic_btn.setFont(MyFont())
        self.add_pic_btn.setFixedWidth(100)
        self.add_pic_btn.clicked.connect(self.add_pic)
        self.delete_btn = new_button("刪除成員")
        self.delete_btn.setFont(MyFont())
        self.delete_btn.setFixedWidth(100)
        self.delete_btn.clicked.connect(self.delete_member)
        operator_layout.addWidget(self.edit_name_btn)
        operator_layout.addWidget(self.add_pic_btn)
        operator_layout.addWidget(self.delete_btn)
        info_op_layout.addLayout(operator_layout)
        layout.addLayout(info_op_layout)
        layout.addSpacing(30)
        
        self.pic_scroll_area = QtWidgets.QScrollArea()
        self.scroll_widget = QtWidgets.QWidget()
        self.pic_grid_layout = QtWidgets.QGridLayout()
        self.pic_grid_layout.setContentsMargins(5, 5, 5, 5)
        self.scroll_widget.setLayout(self.pic_grid_layout)
        self.pic_scroll_area.setWidget(self.scroll_widget)
        layout.addWidget(self.pic_scroll_area)
        
        self.setLayout(layout)
        
    def update(self):
        if self.member_imgs is None:
            return
        if len(self.member_imgs) == 0:
            return
        cols = (self.pic_scroll_area.size().width()-25)//100 #減掉拉桿25px，至少有 20px 的留空 (左右各10px)
        for _ in range(self.pic_grid_layout.count()):
            self.pic_grid_layout.takeAt(0).widget().deleteLater()
        i_row = 0
        i_col = 0
        for img in self.member_imgs:
            member_img = QtWidgets.QLabel()
            member_img.setFixedSize(100, 100)
            member_img.setPixmap(img.scaled(100, 100, QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding))
            member_img.setStyleSheet("border :2px solid #607cff;")
            self.pic_grid_layout.addWidget(member_img, i_row, i_col)
            i_col += 1
            if i_col == cols:
                i_col = 0
                i_row += 1
        for i in range((cols-len(self.member_imgs)%cols)%cols):
            filler = QtWidgets.QLabel()
            filler.setFixedSize(100, 100)
            self.pic_grid_layout.addWidget(filler, i_row, i_col)
            i_col += 1
        hei = 110*math.ceil(len(self.member_imgs)/cols)
        if hei < self.pic_scroll_area.size().height():
            self.scroll_widget.resize(QtCore.QSize(self.pic_scroll_area.size().width()-5, hei))
        else:
            self.scroll_widget.resize(QtCore.QSize(self.pic_scroll_area.size().width()-25, hei))
       
    def resizeEvent(self, event):
        self.update()
        
    def set_name(self, name):
        if name is None:
            return
        name = str(name)
        self.name = name
        self.member_name.setText(name)

    def set_imgs(self, imgs):
        logger.debug(f'"{self.name}" imgs: {len(imgs)}')
        if imgs is None:
            return
        self.member_imgs = imgs
        
    def recieve_pic(self, pixmap):
        pass
        
    def edit_name(self):
        pass
    
    def add_pic(self):
        pass
    
    def delete_member(self):
        pass
    
class VideoMenu(QtWidgets.QDialog):
    def __init__(self, root_dir, parent=None):
        super().__init__(parent)
        self.setWindowTitle("選擇影片")
        self.vid_height = 150
        self.vid_width = 150*16//9
        self.setMinimumSize(self.vid_width*2+100, self.vid_height*2+100)
        self.root_dir = root_dir
        self.ui()        
        
    def ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        
        self.curent_dir_label = QtWidgets.QLabel(f'目前根目錄: {self.root_dir}', self)
        self.curent_dir_label.setFont(MyFont())
        layout.addWidget(self.curent_dir_label)
        
        change_dir_btn = new_button("更改根目錄")
        change_dir_btn.clicked.connect(self.open_change_dir_dialog)
        layout.addWidget(change_dir_btn)
        
        self.video_scroll_area = QtWidgets.QScrollArea()
        self.video_scroll_widget = QtWidgets.QWidget()
        self.video_grid_layout = QtWidgets.QGridLayout()
        self.video_scroll_widget.setLayout(self.video_grid_layout)
        self.video_scroll_area.setWidget(self.video_scroll_widget)
        layout.addWidget(self.video_scroll_area)
        
        self.setLayout(layout)
        
    def resizeEvent(self, event):
        self.update()
        
    def update(self):
        # find videos in root_dir and update the grid layout and video widget size
        for _ in range(self.video_grid_layout.count()):
            self.video_grid_layout.takeAt(0).widget().deleteLater()
            
        self.curent_dir_label.setText(f'目前根目錄: {self.root_dir}')
        videos = glob.glob(os.path.join(self.root_dir, '*.mp4'))
        i_row = 0
        i_col = 0
        rols = self.video_scroll_area.size().width()//(self.vid_width+10)
        logger.debug(f'rols: {rols}')
        for video in videos:
            video_cap = cv2.VideoCapture(video)
            if not video_cap.isOpened():
                logger.warning(f'"{video}" is not a valid video file, skiped')
                continue
            success, frame = video_cap.read()
            if not success:
                logger.warning(f'"{video}" is not a valid video file, skiped')
                continue
            video_cap.release()
            pframe = cv2_to_pixmap(frame)
            video_thumb = pframe.scaled(self.vid_width, self.vid_height, QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding)
            video_label = QtWidgets.QLabel()
            video_label.setStyleSheet("border :2px solid #607cff;")
            video_label.setPixmap(video_thumb)
            video_label.setFixedSize(self.vid_width, self.vid_height)
            video_label.mousePressEvent = lambda event, video=video: self.select_video(video)
            self.video_grid_layout.addWidget(video_label, i_row, i_col)
            i_col += 1
            if i_col == rols:
                i_col = 0
                i_row += 1
        self.video_scroll_widget.resize(QtCore.QSize(self.video_scroll_area.size().width()-30, (i_row+1)*(self.vid_height+10)))
        
    def open_change_dir_dialog(self):
        dialog = QtWidgets.QFileDialog(self, "選擇根目錄")
        dialog.setFileMode(QtWidgets.QFileDialog.FileMode.Directory)
        if dialog.exec_():
            logger.debug(f'change root dir to {dialog.selectedFiles()[0]}')
            self.root_dir = dialog.selectedFiles()[0]
            self.update()
        else:
            return
        
    def select_video(self, video_path):
        logger.debug(f'select video: {video_path}')
        self.result = video_path
        self.accept()
        
    def closeEvent(self, event):
        self.result = None
        self.accept()
    
class DatabaseMenu(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("資料庫")
        self.setFixedSize(650, 600)
        self.ui()
        
        self.database_preview_items = {}
        self.create_new_button = None
    
    def ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        
        self.member_scroll_area = QtWidgets.QScrollArea()
        self.member_scroll_widget = QtWidgets.QWidget()
        self.member_vbox_layout = QtWidgets.QVBoxLayout()
        self.member_vbox_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.member_scroll_widget.setLayout(self.member_vbox_layout)
        self.member_scroll_area.setWidget(self.member_scroll_widget)
        layout.addWidget(self.member_scroll_area)
        
        self.setLayout(layout)
        
    def add_database_item(self, name):
        if not isinstance(name, str):
            return
        
        self.database_preview_items[name] = DatabaseMenuItem(name, self) # initialization
        self.member_vbox_layout.addWidget(self.database_preview_items[name])
        
    def add_create_new_button(self):
        self.create_new_button = new_button("新增")
        self.create_new_button.clicked.connect(self.create_new_database)
        self.member_vbox_layout.addWidget(self.create_new_button)    
    
    def addPreview_img(self, database_name, member_name, preview_img):
        if not isinstance(database_name, str):
            return
        if not isinstance(member_name, str):
            return
        if not isinstance(preview_img, QtGui.QPixmap):
            return
        if database_name not in self.database_preview_items.keys():
            self.add_database_item(database_name)
        if member_name in self.database_preview_items[database_name].get_names():
            logger.waring(f'"{member_name}" in "{database_name}" already have preview picture')
            return
        
        logger.debug(f'add preview image of "{member_name}" in "{database_name}"')
        self.database_preview_items[database_name].add_member(member_name, preview_img)
        
    def update(self):
        if self.create_new_button is None:
            self.add_create_new_button()
        else:
            self.member_vbox_layout.removeWidget(self.create_new_button)
            self.create_new_button.deleteLater()
            self.add_create_new_button()
        for database_name in self.database_preview_items.keys():
            self.database_preview_items[database_name].update()
        self.member_scroll_widget.resize(QtCore.QSize(600, len(self.database_preview_items)*220))
        logger.debug(f'new size: {(600, len(self.database_preview_items)*250)}')

    def create_new_database(self):
        self.open_new_database_dialog()
        
    def confirm_new_database(self, database_name):
        self.parent().si.send_signal("createDatabase")
        self.parent().si.send_data(database_name)
        
    def open_new_database_dialog(self):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("新增資料庫")
        dialog.setMinimumSize(300, 150)
        layout = QtWidgets.QVBoxLayout(dialog)
        label = QtWidgets.QLabel("輸入資料庫名稱:", dialog)
        label.setFont(MyFont())
        layout.addWidget(label)
        input = QtWidgets.QLineEdit(dialog)
        input.setFont(MyFont())
        id = 1
        while ("database_"+str(id)) in [k.lower() for k in self.database_preview_items.keys()]:
            id += 1
        default_name = "Database_" + str(id)
        input.setPlaceholderText(default_name)
        layout.addWidget(input)
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        confirm_btn = new_button("確定")
        def confirm_and_close():
            if input.text() in self.database_preview_items.keys():
                self.parent().open_error_dialog("資料庫名稱重複!")
                return
            if input.text() == '':
                self.confirm_new_database(default_name)
                dialog.close()
                return
            self.confirm_new_database(input.text())
            dialog.close()
        confirm_btn.clicked.connect(confirm_and_close)
        confirm_btn.setFont(MyFont())
        cancel_btn = new_button("取消")
        cancel_btn.clicked.connect(dialog.close)
        cancel_btn.setFont(MyFont())
        btn_layout.addWidget(confirm_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        dialog.setLayout(layout)
        dialog.exec()
        
    def select_database(self, database_name):
        self.result = database_name
        self.accept()
        
    def delete_database(self, database_name):
        self.open_confirm_dialog(f'{database_name}')
        
    def confirm_delete_database(self, database_name):
        self.parent().si.send_signal("deleteDatabase")
        self.parent().si.send_data(database_name)
        self.member_vbox_layout.removeWidget(self.database_preview_items[database_name])
        self.database_preview_items.pop(database_name)
        self.update()
        
    def open_confirm_dialog(self, database_name):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("確認刪除")
        dialog.setMinimumSize(300, 150)
        layout = QtWidgets.QVBoxLayout(dialog)
        label = QtWidgets.QLabel(f'確定要刪除"{database_name}"嗎?', dialog)
        label.setFont(MyFont())
        layout.addWidget(label)
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        confirm_btn = new_button("確定")
        def confirm_and_close():
            self.confirm_delete_database(database_name)
            dialog.close()
        confirm_btn.clicked.connect(confirm_and_close)
        confirm_btn.setFont(MyFont())
        cancel_btn = new_button("取消")
        cancel_btn.clicked.connect(dialog.close)
        cancel_btn.setFont(MyFont())
        btn_layout.addWidget(confirm_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        dialog.setLayout(layout)
        dialog.exec()
        
    def closeEvent(self, event):
        self.result = None
        self.accept()
        
class DatabaseMenuItem(QtWidgets.QWidget):
    def __init__(self, database_name, menu, parent=None):
        super().__init__(parent)
        self.setFixedSize(600, 200)
        self.database_name = database_name
        self.name_list = []
        self.preview_imgs = []
        self.preview_img_num = 0
        self.menu = menu
        self.ui()
    
    def ui(self):
        frame = QtWidgets.QFrame(self)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        
        name_label = QtWidgets.QLabel(self.database_name)
        name_label.setFont(MyFont())
        name_label.setAutoFillBackground(True)
        name_label.setFixedWidth(100)
        layout.addWidget(name_label)
        
        op_layout = QtWidgets.QHBoxLayout()
        op_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        select_button = new_button("Select")
        del_button = new_button("Delete")
        select_button.setFixedSize(100, 30)
        del_button.setFixedSize(100, 30)
        select_button.clicked.connect(self.select_database)
        del_button.clicked.connect(self.delete_database)
        op_layout.addWidget(select_button)
        op_layout.addWidget(del_button)
        layout.addLayout(op_layout)
        
        pic_layout = QtWidgets.QHBoxLayout()
        pic_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        for i in range(5): # at most 5 preview images
            img_label = QtWidgets.QLabel(self)
            self.preview_imgs.append(img_label)
            pic_layout.addWidget(self.preview_imgs[i])
            #if i != 4:
            #    pic_layout.addStretch(1)
        layout.addLayout(pic_layout)
        
        frame.setLayout(layout)
        frame.setObjectName("frame")
        frame.setStyleSheet("#frame {border :2px solid #607cff;}")
        _layout = QtWidgets.QHBoxLayout(self)
        _layout.addWidget(frame)
        self.setLayout(_layout)
        
    def select_database(self):
        self.menu.select_database(self.database_name)
        
    def delete_database(self):
        self.menu.delete_database(self.database_name)
        
    def get_names(self):
        return self.name_list
    
    def update(self):
        self.setToolTip(f'{self.database_name}\n{", ".join(self.name_list)}')
        
    def add_member(self, member_name, pixmap):
        if not isinstance(member_name, str):
            return
        if not isinstance(pixmap, QtGui.QPixmap):
            return
        self.name_list.append(member_name)
        logger.debug(f'add member "{member_name}" in "{self.database_name}, {len(self.name_list)}, {self.preview_img_num}"')
        if self.preview_img_num < 5:
            self.preview_imgs[self.preview_img_num].setPixmap(pixmap.scaled(100, 100, QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding))
            self.preview_img_num += 1
            
class SubtitleArea(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(400)
        self.time_subtitle = {}
        self.ui()
        
    def ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        
        subtitle_label = QtWidgets.QLabel("字幕區域", self)
        subtitle_label.setFont(MyFont())
        layout.addWidget(subtitle_label)
        
        self.subtitle_scroll_area = QtWidgets.QScrollArea()
        self.subtitle_scroll_widget = QtWidgets.QWidget()
        self.subtitle_vbox_layout = QtWidgets.QVBoxLayout()
        self.subtitle_scroll_widget.setLayout(self.subtitle_vbox_layout)
        self.subtitle_scroll_area.setWidget(self.subtitle_scroll_widget)
        layout.addWidget(self.subtitle_scroll_area)
        
        self.setLayout(layout)
        
    def update(self):
        for _ in range(self.subtitle_vbox_layout.count()):
            self.subtitle_vbox_layout.takeAt(0).widget().deleteLater()
            
        total_height = 0
        for _time, subtitle in self.time_subtitle.items():
            time_str = time.strftime("%H:%M:%S", time.gmtime(float(_time)))
            subtitle_item = SubtitleItem(time_str, subtitle, self)
            self.subtitle_vbox_layout.addWidget(subtitle_item)
            logger.debug(f'subtitle height:{subtitle_item.sizeHint().height()}')
            total_height += subtitle_item.sizeHint().height() + 20
        self.subtitle_scroll_widget.resize(QtCore.QSize(360, total_height+50))
        
    def set_subtitle_data(self, subtitle_data):
        self.time_subtitle = {} # clear data
        for d in subtitle_data:
            start_time = d['start']
            subtitle = d['text']
            
            self.time_subtitle[start_time] = subtitle
            logger.debug(f'add subtitle: {d}')
        self.update()
            
class SubtitleItem(QtWidgets.QWidget):
    def __init__(self, time, subtitle, parent=None):
        super().__init__(parent)
        self.setFixedWidth(360)
        self.setMinimumHeight(50)
        self.time = time
        self.subtitle = subtitle
        self.ui()
        
    def ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        
        time_label = QtWidgets.QLabel(f'{self.time}: ', self)
        time_label.setFont(MyFont())
        layout.addWidget(time_label)
        
        subtitle_label = QtWidgets.QLabel(self.subtitle, self)
        subtitle_label.setFont(MyFont())
        subtitle_label.setWordWrap(True)
        layout.addWidget(subtitle_label)
        
        self.setLayout(layout)
            
class RecordMenu(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("選擇紀錄檔")
        self.setFixedSize(550, 500)
        self.ui()
        self.update()
        self.record_widgets = {}
        
    def ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        
        self.record_scroll_area = QtWidgets.QScrollArea()
        self.record_scroll_widget = QtWidgets.QWidget()
        self.record_vbox_layout = QtWidgets.QVBoxLayout()
        self.record_scroll_widget.setLayout(self.record_vbox_layout)
        self.record_scroll_area.setWidget(self.record_scroll_widget)
        layout.addWidget(self.record_scroll_area)
        
        self.setLayout(layout)
        
    def add_record_item(self, record_name, create_time, video_path, database_name):
        if not isinstance(video_path, str) or not isinstance(database_name, str) or not isinstance(create_time, str):
            return
        if not isinstance(record_name, str):
            return
        
        record_item = RecordMenuItem(record_name, create_time, video_path, database_name, self)
        self.record_vbox_layout.addWidget(record_item)
        self.record_widgets[record_name] = record_item
        self.update()
    
    def clear(self):
        for widget in self.record_widgets.values():
            self.record_vbox_layout.removeWidget(widget)
            widget.deleteLater()
        self.record_widgets = {}
        self.update()
        
    def update(self):
        self.record_scroll_widget.resize(QtCore.QSize(500, self.record_vbox_layout.count()*200))
        
    def select_record(self, record_name):
        self.result = record_name
        self.accept()
        
    def delete_record(self, record_name):
        self.parent().si.send_signal("deleteRecord")
        self.parent().si.send_data(record_name)
        self.record_vbox_layout.removeWidget(self.record_widgets[record_name])
        self.record_widgets.pop(record_name)
        self.update()
        
    def closeEvent(self, event):
        self.result = None
        self.accept()

class RecordMenuItem(QtWidgets.QWidget):
    def __init__(self, record_name, create_time, video_path, database_name, menu, parent=None):
        super().__init__(parent)
        self.record_name = record_name
        self.create_time = create_time
        self.video_path = video_path
        self.database_name = database_name
        self.menu = menu
        logger.debug(f'create record item: {record_name} {create_time} {video_path} {database_name}')
        self.ui()
        
    def ui(self):
        frame = QtWidgets.QFrame(self)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        
        info_layout = QtWidgets.QHBoxLayout()
        info_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        name_label = QtWidgets.QLabel(f'{self.record_name}', self)
        name_label.setFont(MyFont())
        create_time_label = QtWidgets.QLabel(f'建立時間: {self.time_format(self.create_time)}', self)
        create_time_label.setFont(MyFont())
        info_layout.addWidget(name_label)
        info_layout.addWidget(create_time_label)
        layout.addLayout(info_layout)
        
        info_layout2 = QtWidgets.QVBoxLayout()
        info_layout2.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        
        #video_path_label = QtWidgets.QLabel(f'檔案路徑: {self.video_path}', self)
        #video_path_label.setWordWrap(True)
        #video_path_label.setFont(MyFont())
        database_name_label = QtWidgets.QLabel(f'資料庫: {self.database_name}', self)
        database_name_label.setWordWrap(True)
        database_name_label.setFont(MyFont())
        info_layout2.addWidget(database_name_label)
        layout.addLayout(info_layout2)
        
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.select_btn = new_button("選擇")
        self.select_btn.clicked.connect(self.select_record)
        self.select_btn.setFixedWidth(100)
        video_path_btn = new_button("開啟影片位置")
        video_path_btn.clicked.connect(lambda: os.system(f'explorer /select,{self.video_path}'))
        self.delete_btn = new_button("刪除")
        self.delete_btn.clicked.connect(self.delete_record)
        self.delete_btn.setFixedWidth(100)
        button_layout.addWidget(self.select_btn)
        button_layout.addStretch(1)
        button_layout.addWidget(video_path_btn)
        button_layout.addWidget(self.delete_btn)
        layout.addLayout(button_layout)
                
        frame.setLayout(layout)
        frame.setObjectName("frame")
        frame.setStyleSheet("#frame {border :2px solid #607cff;}")
        _layout = QtWidgets.QHBoxLayout(self)
        _layout.addWidget(frame)
        self.setLayout(_layout)
        
    def delete_record(self):
        self.open_confirm_dialog(self.record_name)
        
    def confirm_delete_record(self, record_name):
        self.menu.delete_record(record_name)
        
    def open_confirm_dialog(self, record_name):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("確認刪除")
        dialog.setMinimumSize(300, 150)
        layout = QtWidgets.QVBoxLayout(dialog)
        label = QtWidgets.QLabel(f'確定要刪除"{record_name}"嗎?', dialog)
        label.setFont(MyFont())
        layout.addWidget(label)
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        confirm_btn = new_button("確定")
        def confirm_and_close():
            self.confirm_delete_record(record_name)
            dialog.close()
        confirm_btn.clicked.connect(confirm_and_close)
        confirm_btn.setFont(MyFont())
        cancel_btn = new_button("取消")
        cancel_btn.clicked.connect(dialog.close)
        cancel_btn.setFont(MyFont())
        btn_layout.addWidget(confirm_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        dialog.setLayout(layout)
        dialog.exec()
        
    def time_format(self, time_str:str):
        # time_str format: "YYYY_MM_DD_HH_MM_SS"
        # after: "YYYY/MM/DD HH:MM:SS"
        time_str = time_str.replace('_', '/', 2)
        time_str = time_str.replace('_', ' ', 1)
        time_str = time_str.replace('_', ':', 2)
        
        return time_str
        
    def select_record(self):
        self.menu.select_record(self.record_name)

