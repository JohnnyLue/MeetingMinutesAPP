
import cv2
import math
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

class ParamPanel(QtWidgets.QScrollArea):
    '''
    ParamPanel is a widget for setting parameters for the run.
    '''
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scroll_widget = QtWidgets.QWidget(self)
        self.grid_layout = QtWidgets.QGridLayout(self)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_widget.setLayout(self.grid_layout)
        self.setWidget(self.scroll_widget)
        self.param_widgets = []
        
    def update(self):
        i, j = 0, 0
        for widget in self.param_widgets:
            self.grid_layout.addWidget(widget, i, j)
            j+=1
            if j == 1:
                i+=1
                j=0
        self.scroll_widget.resize(self.grid_layout.sizeHint())
        
    def add_param_widget_custom_value(self, name, default_value):
        '''
        Parameters can be set to custom value by user.
        '''
        widget = QtWidgets.QWidget(self)
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(0, 5, 10, 5)
        label = QtWidgets.QLabel(name, widget)
        label.setFont(MyFont())
        layout.addWidget(label)
        input = QtWidgets.QLineEdit(widget)
        input.setText(str(default_value))
        input.setFont(MyFont())
        input.setFixedWidth(80)
        input.textChanged.connect(lambda: self.on_change(name, input.text()))
        layout.addWidget(input)
        widget.setLayout(layout)
        self.param_widgets.append(widget)
        
    def add_param_widget_choise_value(self, name, options):
        '''
        parameters can be selected from a list of options.
        '''
        widget = QtWidgets.QWidget(self)
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(0, 5, 10, 5)
        label = QtWidgets.QLabel(name, widget)
        label.setFont(MyFont())
        layout.addWidget(label)
        input = QtWidgets.QComboBox(widget)
        input.addItems(options)
        input.setFont(MyFont())
        input.setFixedWidth(80)
        input.setCurrentIndex(0) # default value
        input.currentIndexChanged.connect(lambda: self.on_change(name, input.currentText()))
        layout.addWidget(input)
        widget.setLayout(layout)
        self.param_widgets.append(widget)
        
    def on_change(self, name, new_value):
        print(f"{name} change to {new_value}")
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
        cols = (self.pic_scroll_area.size().width()-25)//120 #減掉拉桿25px，至少有 20px 的留空 (左右各10px)
        for _ in range(self.pic_grid_layout.count()):
            self.pic_grid_layout.takeAt(0).widget().deleteLater()
        i_row = 0
        i_col = 0
        for img in self.member_imgs:
            print('add img')
            member_img = QtWidgets.QLabel()
            member_img.setPixmap(img.scaled(100, 100, QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding))
            member_img.setStyleSheet("border :4px solid #607cff;")
            member_img.setFixedSize(100, 100)
            self.pic_grid_layout.addWidget(member_img, i_row, i_col)
            i_col += 1
            if i_col == cols:
                i_col = 0
                i_row += 1
        for i in range(len(self.member_imgs)%cols):
            self.pic_grid_layout.addWidget(QtWidgets.QLabel(), i_row, i_col)
            i_col += 1
        hei = 110*math.ceil(len(self.member_imgs)/cols)
        if hei < self.pic_scroll_area.size().height():
            self.scroll_widget.resize(QtCore.QSize(self.pic_scroll_area.size().width()-5, hei))
        else:
            self.scroll_widget.resize(QtCore.QSize(self.pic_scroll_area.size().width()-25, hei))
       
    def resizeEvent(self, event):
        print('resize')
        self.update()
        
    def set_name(self, name):
        if name is None:
            return
        name = str(name)
        self.name = name
        self.member_name.setText(name)

    def set_member_imgs(self, imgs):
        print(f'set member imgs {len(imgs)}')
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
    