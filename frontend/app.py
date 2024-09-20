import cv2
import logging
import math
import sys
import configparser
import os

from PyQt5 import QtWidgets, QtCore, QtGui
from FrontEndWidgets import *
from SocketInterface import SocketInterface


#################################################################################
# Set up logger

logger = logging.getLogger()
logger.handlers.clear()
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
	'[%(levelname)-7s %(asctime)s] %(name)s:%(module)s:%(funcName)s:%(lineno)d: %(message)s',
	'%H:%M:%S')
fileLogger = logging.FileHandler('log.txt', mode='w')
fileLogger.setLevel(logging.DEBUG)
fileLogger.setFormatter(formatter)
streamLogger = logging.StreamHandler()
streamLogger.setLevel(logging.DEBUG)
streamLogger.setFormatter(formatter)
logger.addHandler(fileLogger)
logger.addHandler(streamLogger)

#################################################################################
# Define signals
class SignalTable(QtCore.QObject):
    requestImgByName = QtCore.pyqtSignal(str) # 要求照片: 名字
    requestAllMemberImg = QtCore.pyqtSignal() # 要求全部照片
    returnedMemberImg = QtCore.pyqtSignal(str, QtGui.QPixmap) # 回傳名字, 照片

    selectedVideo = QtCore.pyqtSignal(str) # 選擇影片: 檔案位置
    selectedDatabase = QtCore.pyqtSignal(str) # 選擇資料庫: 

    requestParams = QtCore.pyqtSignal() # 要求參數(全部)
    updateParam = QtCore.pyqtSignal(str, list) # 更新顯示參數: 參數名, 值 (可能是list)
    alterParam = QtCore.pyqtSignal(str, str) # 修改參數: 參數名, 值

    requestProgress = QtCore.pyqtSignal() # 要求更新進度
    updateProgress = QtCore.pyqtSignal(str, int, int) # 任務, 進度, 總進度

    testRun = QtCore.pyqtSignal() # 要求測試執行
    startProcess = QtCore.pyqtSignal() # 要求開始處理
    terminateProcess = QtCore.pyqtSignal() # 要求終止處理
    recordOverwrite = QtCore.pyqtSignal() # 要求確認是否覆蓋紀錄
    recordOverwriteConfirmed = QtCore.pyqtSignal() # 確認覆蓋紀錄

    errorOccor = QtCore.pyqtSignal(str) # 錯誤訊息
    ProcessFinished = QtCore.pyqtSignal(str) # 任務完成: 紀錄檔位置

signals = SignalTable()
####################################################################################

class loopThread(QtCore.QThread):
    def __init__(self, si, parent=None):
        super(loopThread, self).__init__(parent)
        self.si = si
        self.signals_pairs = {
            "errorOccor": signals.errorOccor,
            "recordOverwrite": self.recordOverwrite,
            "selectedVideo": self.selectedVideo,
            "returnedMemberImg": self.returnedMemberImg,
            "updateParam": self.updateParam,
            "updateProgress": self.updateProgress
        }
        self.require_data_count = {
            "errorOccor": 1,
            "recordOverwrite": 0,
            "selectedVideo": 1,
            "returnedMemberImg": 1,
            "updateParam": 2,
            "updateProgress": 3
        }
        
    def run(self):
        while True:
            type, signal_name = self.si.receive() # if not buged, this will only receive signal type
            if type != "SIG":
                logger.error("Error, expected signal")
                logger.debug(f"Recieve type: {type}, signal: {signal_name}")
                self.si.close()
                break
            elif signal_name == "END_PROGRAM":
                logger.info("Program terminated")
                self.si.close()
                break
            else:
                if self.signals_pairs[signal_name] is None:
                    logger.error(f"Signal {signal_name} not defined")
                    continue
                
                data = []
                for _ in range(self.require_data_count[signal_name]):
                    type, d = self.si.receive()
                    if type != "DAT":
                        logger.error("Error, expected data")
                        self.si.close()
                        break
                    data.append(d)
                logger.debug(f"Recieve signal: {signal_name}, data: {data}")
                self.signals_pairs[signal_name].emit(*data)
                    
class MainWindow(QtWidgets.QWidget):
    def __init__(self, host = 'localhost', port = 8080, buffer_size = 1024):
        super().__init__()
        self.si = SocketInterface(host, port, buffer_size)
        self.si.imClient()
        self.signals_pairs = {
            "errorOccor": signals.errorOccor,
            "recordOverwrite": signals.recordOverwrite,
            "selectedVideo": signals.selectedVideo,
            "returnedMemberImg": signals.returnedMemberImg,
            "updateParam": signals.updateParam,
            "updateProgress": signals.updateProgress
        }
        self.require_data_count = {
            "errorOccor": 1,
            "recordOverwrite": 0,
            "selectedVideo": 1,
            "returnedMemberImg": 2,
            "updateParam": 2,
            "updateProgress": 3
        }
        
        signals.errorOccor.connect(self.open_error_dialog)
        signals.recordOverwrite.connect(self.open_check_overwrite_dialog)
        signals.selectedVideo.connect(self.switch_video_preview)
        signals.returnedMemberImg.connect(self.update_database_member_img)
        signals.updateParam.connect(self.recieved_param_value)
        
        #self.loop_thread = loopThread(self.si)
        #self.loop_thread.errorOccor.connect(self.open_error_dialog)
        #self.loop_thread.recordOverwrite.connect(self.open_check_overwrite_dialog)
        #self.loop_thread.selectedVideo.connect(self.switch_video_preview)
        #self.loop_thread.returnedMemberImg.connect(self.update_database_member_img)
        #self.loop_thread.updateParam.connect(self.recieved_param_value)
        #self.loop_thread.start()
        
        #self.si.connect_signal("errorOccor", self.open_error_dialog, True)
        #self.si.connect_signal("recordOverwrite", self.open_check_overwrite_dialog, False)
        #self.si.connect_signal("selectedVideo", self.switch_video_preview, True)
        #self.si.connect_signal("returnedMemberImg", self.update_database_member_img, True)
        #self.si.connect_signal("updateParam", self.recieved_param_value, True)
        
        self.setObjectName("MainWindow")
        self.setWindowTitle('操作頁面')
        
        self.resize(1100, 600)
        self.ui()
        
        self.have_video_preview = False
        self.member_name_imgs = {}
                
        threading.Thread(target=self.recv_loop).start()
        self.si.send_signal("requestParams")
        logger.debug("Requesting all parameters")
        self.si.send_signal("requestProgress")
        
        
    def recv_loop(self):
        if not self.si.inited:
            logger.warning("socket connection not created")
        while True:
            type, signal_name = self.si.receive() # if not buged, this will only receive signal type
            if type != "SIG":
                logger.error("Error, expected signal")
                logger.debug(f"Recieve type: {type}, signal: {signal_name}")
                self.si.close()
                break
            elif signal_name == "END_PROGRAM":
                logger.info("Program terminated")
                self.si.close()
                break
            else:
                if self.signals_pairs[signal_name] is None:
                    logger.error(f"Signal {signal_name} not defined")
                    continue
                
                data = []
                for _ in range(self.require_data_count[signal_name]):
                    type, d = self.si.receive()
                    if type == "SIG":
                        logger.error("Expected data or image")
                        self.si.close()
                        break
                    elif type == "IMG":
                        logger.debug(f"Recieve image")
                        pixmap = cv2_to_pixmap(d)
                        data.append(pixmap)
                    else:
                        data.append(d)
                logger.debug(f"Recieve signal: {signal_name}, data: {data}")
                self.signals_pairs[signal_name].emit(*data)
                #self.signals_pairs["errorOccor"].emit(signal_name)
        
    def ui(self):
        layout = QtWidgets.QHBoxLayout(self)

        video_and_progress_layout = QtWidgets.QVBoxLayout()
        # Video Upload Section
        self.video_area = QtWidgets.QVBoxLayout()
        self.select_video_button = new_button("選擇影片")
        self.select_video_button.clicked.connect(self.open_select_video_dialog)
        self.video_drop_area = FileDropArea(self)
        self.video_area.addWidget(self.select_video_button)
        self.video_area.addWidget(self.video_drop_area)
        video_and_progress_layout.addLayout(self.video_area)
                
        # Progress Bar for Visualization
        progress_bar_layout = QtWidgets.QVBoxLayout()
        self.progress_task = QtWidgets.QLabel("", self)
        self.progress_task.setFixedWidth(640)
        self.progress_task.setFixedHeight(20)
        self.progress_task.setFont(MyFont())
        self.progress_task.setAlignment(QtCore.Qt.AlignCenter)
        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setFixedWidth(640)
        self.progress_bar.setFixedHeight(20)
        self.progress_bar.setTextVisible(False)
        self.progress_percent = QtWidgets.QLabel("", self.progress_bar)
        self.progress_percent.setFixedWidth(640)
        self.progress_percent.setFixedHeight(20)
        self.progress_percent.setAlignment(QtCore.Qt.AlignCenter)
        self.progress_percent.setFont(MyFont())
        progress_bar_layout.addWidget(self.progress_task)
        progress_bar_layout.addWidget(self.progress_bar)
        signals.updateProgress.connect(self.update_progress_bar)
        video_and_progress_layout.addLayout(progress_bar_layout)
        layout.addLayout(video_and_progress_layout)

        # database control and parameter section
        db_and_parm_layout = QtWidgets.QVBoxLayout()
        db_and_parm_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        # Database Operations
        db_layout = QtWidgets.QVBoxLayout()
        db_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        db_layout.setSpacing(10)
        self.select_database_button = new_button("選擇資料庫")
        self.select_database_button.clicked.connect(self.select_database_dialog)
        
        self.db_grid_layout = QtWidgets.QGridLayout()
        self.db_scroll_widget = QtWidgets.QWidget()
        self.db_scroll_area = QtWidgets.QScrollArea()
        self.db_scroll_area.setObjectName("DatabaseScrollArea")
        self.db_scroll_area.setStyleSheet(r"#DatabaseScrollArea {border: 2px solid #aaa;}")
        self.db_scroll_widget.setLayout(self.db_grid_layout)
        self.db_scroll_area.setWidget(self.db_scroll_widget)
        self.db_scroll_widget.hide()
        
        self.merge_button = new_button("合併人員")
        #self.merge_button.clicked.connect()
        
        db_layout.addWidget(self.select_database_button)
        db_layout.addWidget(self.db_scroll_area)
        db_layout.addWidget(self.merge_button)
        db_and_parm_layout.addLayout(db_layout)
        db_and_parm_layout.addSpacing(30)

        # Parameter Adjustment Section
        param_layout = QtWidgets.QVBoxLayout()
        param_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        param_label = QtWidgets.QLabel("參數調整:", self)
        param_label.setFont(MyFont())
        param_layout.addWidget(param_label)
        self.param_panel = ParamPanel(self)
        param_layout.addWidget(self.param_panel)
        
        db_and_parm_layout.addLayout(param_layout)
        
        layout.addLayout(db_and_parm_layout)

        # Test Execution Section
        execution_layout = QtWidgets.QVBoxLayout()
        execution_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.test_button = new_button("測試執行")
        self.test_button.clicked.connect(lambda: self.si.send_signal("testRun"))
        self.run_button = new_button("確認執行")
        self.run_button.clicked.connect(lambda: self.si.send_signal("startProcess"))
        execution_layout.addWidget(self.test_button)
        execution_layout.addSpacing(20)
        execution_layout.addWidget(self.run_button)
        layout.addLayout(execution_layout)
    
    def resizeEvent(self, event):
        self.resize_database_widget()
    
    def update_database_member_img(self, name, pixmap):
        if name == "EOF": # all images are sent
            self.resize_database_widget()
            self.db_scroll_widget.show()
            logger.debug("All member images recieved")
            return
        
        if name not in self.member_name_imgs:
            self.member_name_imgs[name] = []
            self.member_name_imgs[name].append(pixmap)
        else:
            self.member_name_imgs[name].append(pixmap)
        logger.debug(f'Recieve member "{name}"\'s img')
        
    def resize_database_widget(self):
        cols = (self.db_scroll_area.size().width()-25)//120 #減掉拉桿25px，至少有 20px 的留空 (左右各10px)
        for _ in range(self.db_grid_layout.count()):
            self.db_grid_layout.takeAt(0).widget().deleteLater()
        i_row = 0
        i_col = 0
        for name, imgs in self.member_name_imgs.items():
            member_img = QtWidgets.QLabel()
            member_img.setObjectName('member_img')
            member_img.setPixmap(imgs[0].scaled(100, 100, QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding))
            member_img.setStyleSheet("#member_img {border :4px solid #607cff;}")
            member_img.setFixedSize(100, 100)
            member_img.setToolTip(name)
            member_img.mousePressEvent = lambda event, name=name: self.pop_member_detail_window(name)
            self.db_grid_layout.addWidget(member_img, i_row, i_col)
            i_col += 1
            if i_col == cols:
                i_col = 0
                i_row += 1
        
        hei = 110*math.ceil(len(self.member_name_imgs)/cols)
        if hei < self.db_scroll_area.size().height():
            self.db_scroll_widget.resize(QtCore.QSize(self.db_scroll_area.size().width()-5, hei))
            logger.debug(f"Resize db_scroll_widget to {(self.db_scroll_area.size().width()-5, hei)}")
        else:
            self.db_scroll_widget.resize(QtCore.QSize(self.db_scroll_area.size().width()-25, hei))
            logger.debug(f"Resize db_scroll_widget to {(self.db_scroll_area.size().width()-25, hei)}")
            
    def pop_member_detail_window(self, name):
        self.member_detail_window = MemberDetailWindow(self)
        self.member_detail_window.set_name(name)
        self.member_detail_window.set_member_imgs(self.member_name_imgs[name])
        self.member_detail_window.exec_()
        
    def select_database_dialog(self):
        database_file_dialog = QtWidgets.QFileDialog(self)
        database_file_dialog.setNameFilter("Database Folder (*)")
        database_file_dialog.setFileMode(QtWidgets.QFileDialog.FileMode.Directory)
        if database_file_dialog.exec_():
            file_path = database_file_dialog.selectedFiles()[0]
            if file_path:
                for _ in range(len(self.member_name_imgs)):
                    self.db_grid_layout.takeAt(0).widget().deleteLater()
                self.member_name_imgs = {}
                self.si.send_signal("selectedDatabase")
                self.si.send_data(file_path)
                self.si.send_signal("requestAllMemberImg")
    
    def alter_param(self, name, value):
        self.si.send_signal("alterParam")
        self.si.send_data((name, value))
    
    def update_progress_bar(self, task, progress, total):
        #task, progress, total = task_progress_total
        if task == "" or total == 0:
            self.progress_task.setText("目前沒有任務")
            self.progress_bar.setValue(0)
            self.progress_percent.setText("")
            return
        
        self.progress_task.setText(task)
        self.progress_bar.setValue(int(progress/total*100))
        self.progress_percent.setText(f"{progress}/{total}")
        
    def recieved_param_value(self, name, values):
        #name, values = name_values
        logger.debug(f"Recieve param: {name}, values: {values}")
        if name is None or values is None:
            return
        if len(values) == 0:
            return
        if len(values)>1:
            self.param_panel.add_param_widget_choise_value(name, values)
        else:
            self.param_panel.add_param_widget_custom_value(name, values[0])
        self.param_panel.update()

    def switch_video_preview(self, file_path: str):
        if not isinstance(file_path, str) or file_path is None:
            logger.warning("File path is not string")
            return
        if not os.path.exists(file_path):
            logger.warning("File not found")
            self.open_error_dialog("File not found")
            return
        
        if self.have_video_preview:
            self.video_preview.reset()
            self.video_preview.load(file_path)
        else:
            self.video_area.takeAt(1).widget().deleteLater()
            self.video_preview = VideoPlayer(self, file_path)
            self.video_area.addWidget(self.video_preview)
            self.have_video_preview = True
            
            control_layout = QtWidgets.QHBoxLayout()
            control_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.video_rewind_button = new_button("後退")
            self.video_rewind_button.clicked.connect(lambda: self.video_preview.rewind(5))
            self.video_pause_button = new_button("播放")
            self.video_pause_button.clicked.connect(lambda: (self.video_preview.pause(), self.video_pause_button.setText("播放") if self.video_preview.is_paused else self.video_pause_button.setText("暫停")))
            self.video_forward_button = new_button("前進")
            self.video_forward_button.clicked.connect(lambda: self.video_preview.forward(5))
            control_layout.addWidget(self.video_rewind_button)
            control_layout.addWidget(self.video_pause_button)
            control_layout.addWidget(self.video_forward_button)
            self.video_area.addLayout(control_layout)
        self.video_preview.play()
        
    def open_select_video_dialog(self):
        video_file_dialog = QtWidgets.QFileDialog(self)
        video_file_dialog.setNameFilter("Video File (*.mp4)")
        if video_file_dialog.exec_():
            file_path = video_file_dialog.selectedFiles()[0]
            if file_path:
                self.si.send_signal("selectedVideo")
                self.si.send_data(file_path)
    
    def open_check_overwrite_dialog(self):
        check_dialog = QtWidgets.QMessageBox(self)
        check_dialog.setWindowTitle("確認")
        check_dialog.setText("紀錄已存在，是否覆蓋？")
        check_dialog.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
        if check_dialog.exec_() == QtWidgets.QMessageBox.StandardButton.Yes:
            self.si.send_signal("recordOverwriteConfirmed")
       
    def open_error_dialog(self, message):
        if not isinstance(message, str) or message is None:
            logger.warning("Invalid error message")
            return
        error_dialog = ErrorDialog(message)
        error_dialog.exec_()
        
    def closeEvent(self, event):
        self.si.send_signal("terminateProcess")
        self.si.close()
        if self.have_video_preview:
            self.video_preview.reset()
        event.accept()
        
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    with open("Darkeum.qss", "r") as f:
        app.setStyleSheet(f.read())    
    main = MainWindow()
    main.show()
    sys.exit(app.exec_())