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
    returnedDatabaseMenu = QtCore.pyqtSignal(str, str, QtGui.QPixmap) # 回傳資料庫: 資料庫名, 人員名, 照片

    requestParams = QtCore.pyqtSignal() # 要求參數(全部)
    updateParam = QtCore.pyqtSignal(str, list) # 更新顯示參數: 參數名, 值 (可能是list)
    alterParam = QtCore.pyqtSignal(str, str) # 修改參數: 參數名, 值

    requestProgress = QtCore.pyqtSignal() # 要求更新進度
    updateProgress = QtCore.pyqtSignal(str, int, int) # 任務, 進度, 總進度

    testRun = QtCore.pyqtSignal() # 要求測試執行
    startProcess = QtCore.pyqtSignal() # 要求開始處理
    terminateProcess = QtCore.pyqtSignal() # 要求終止處理
    
    updateRuntimeImg = QtCore.pyqtSignal(QtGui.QPixmap) # 接收即時照片
    
    recordOverwrite = QtCore.pyqtSignal() # 要求確認是否覆蓋紀錄
    recordOverwriteConfirmed = QtCore.pyqtSignal() # 確認覆蓋紀錄

    errorOccor = QtCore.pyqtSignal(str) # 錯誤訊息
    ProcessFinished = QtCore.pyqtSignal(str) # 任務完成: 紀錄檔位置
    
    returnedRecordMenu = QtCore.pyqtSignal(str, str, str) # 接收紀錄: 紀錄名, 影片位置, 資料庫名

signals = SignalTable()
####################################################################################
                    
class MainWindow(QtWidgets.QWidget):
    def __init__(self, host = 'localhost', port = 8080, buffer_size = 1024):
        super().__init__()
        # create socket interface instance
        self.si = SocketInterface(host, port, buffer_size)
        self.si.imClient()
        
        # set up signal pairs and data info
        self.signals_pairs = {
            "errorOccor": signals.errorOccor,
            "recordOverwrite": signals.recordOverwrite,
            "selectedVideo": signals.selectedVideo,
            "returnedMemberImg": signals.returnedMemberImg,
            "updateParam": signals.updateParam,
            "updateProgress": signals.updateProgress,
            "updateRuntimeImg": signals.updateRuntimeImg,
            "returnedDatabaseMenu": signals.returnedDatabaseMenu,
            "returnedRecordMenu": signals.returnedRecordMenu
        }
        self.require_data_count = {
            "errorOccor": 1,
            "recordOverwrite": 0,
            "selectedVideo": 1,
            "returnedMemberImg": 2,
            "updateParam": 2,
            "updateProgress": 3,
            "updateRuntimeImg": 1,
            "returnedDatabaseMenu": 3,
            "returnedRecordMenu": 3
        }
        
        # bind signals
        signals.errorOccor.connect(self.open_error_dialog)
        signals.recordOverwrite.connect(self.open_check_overwrite_dialog)
        signals.selectedVideo.connect(self.switch_video_preview)
        signals.returnedMemberImg.connect(self.update_database_member_img)
        signals.updateParam.connect(self.received_param_value)
        signals.updateProgress.connect(self.update_progress_bar)
        signals.updateRuntimeImg.connect(self.update_runtime_img)
        signals.returnedDatabaseMenu.connect(self.recieve_database_menu)
        signals.returnedRecordMenu.connect(self.received_record_menu)
        
        # set up window title and size
        self.setWindowTitle('操作頁面')
        self.resize(1100, 600)
        
        # create ui
        self.ui()
        
        # initialize some status var and image storage
        self.have_video_preview = False
        self.have_runtime_preview = False
        self.member_name_imgs = {}
        self.database_menu = None
        self.record_menu = None
        
        # start receiving loop
        threading.Thread(target=self.receiving_loop).start()

        # send signals for initialization
        self.si.send_signal("requestParams")
        self.si.send_signal("requestProgress")
        
    def receiving_loop(self):
        if not self.si.inited:
            logger.warning("socket connection not created")
        while True:
            type, signal_name = self.si.receive() # if not buged, this will only receive signal type
            if type != "SIG":
                logger.error(f'Error, expect to receive signal, not "{type}"')
                self.si.close()
                break
            elif signal_name == "END_PROGRAM":
                logger.info("Recvive terminate signal")
                self.si.close()
                break
            else: # signal type is "signal" and signal_name is not "END_PROGRAM"
                if self.signals_pairs[signal_name] is None:
                    logger.warning(f"Signal {signal_name} not defined, ignored")
                    continue
                
                data = []
                for _ in range(self.require_data_count[signal_name]):
                    type, d = self.si.receive()
                    if type == "SIG":
                        logger.error("Expected data or image")
                        self.si.close()
                        break
                    elif type == "IMG": # receive image
                        pixmap = cv2_to_pixmap(d)
                        data.append(pixmap)
                    else:
                        data.append(d) # receive data
                self.signals_pairs[signal_name].emit(*data) # emit qt signal with data
        
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
        self.progress_text = QtWidgets.QLabel("", self)
        self.progress_text.setFixedWidth(640)
        self.progress_text.setFixedHeight(40)
        self.progress_text.setFont(MyFont())
        self.progress_text.setAlignment(QtCore.Qt.AlignCenter)
        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setFixedWidth(640)
        self.progress_bar.setFixedHeight(20)
        self.progress_bar.setTextVisible(False)
        progress_bar_layout.addWidget(self.progress_text)
        progress_bar_layout.addWidget(self.progress_bar)
        video_and_progress_layout.addLayout(progress_bar_layout)
        layout.addLayout(video_and_progress_layout)
        
        # Subtitle Display Section
        subtitle_layout = SubtitleArea(self)
        layout.addWidget(subtitle_layout)

        # database control and parameter section
        db_and_parm_layout = QtWidgets.QVBoxLayout()
        db_and_parm_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        # Database Operations
        db_layout = QtWidgets.QVBoxLayout()
        db_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        db_layout.setSpacing(10)
        self.select_database_button = new_button("選擇資料庫")
        self.select_database_button.clicked.connect(self.request_database_menu)
        
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
        self.terminate_button = new_button("終止處理")
        self.terminate_button.clicked.connect(self.terminate_process)
        # Select Record
        select_record_btn = new_button("選擇紀錄")
        select_record_btn.clicked.connect(self.open_select_record_dialog)
        execution_layout.addWidget(select_record_btn)
        execution_layout.addSpacing(20)
        execution_layout.addWidget(self.test_button)
        execution_layout.addSpacing(20)
        execution_layout.addWidget(self.run_button)
        execution_layout.addSpacing(20)
        execution_layout.addWidget(self.terminate_button)
        layout.addLayout(execution_layout)
    
    def resizeEvent(self, event):
        self.resize_database_widget()
    
    def update_database_member_img(self, name, pixmap):
        if name == "EOF": # all images are sent
            self.resize_database_widget()
            self.db_scroll_widget.show()
            logger.debug("All member images received")
            return
        
        if name not in self.member_name_imgs:
            self.member_name_imgs[name] = []
            self.member_name_imgs[name].append(pixmap)
        else:
            self.member_name_imgs[name].append(pixmap)
        logger.debug(f'Receive member "{name}"\'s img')
        
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
        self.member_detail_window.set_imgs(self.member_name_imgs[name])
        self.member_detail_window.exec_()
        
    def request_database_menu(self):
        logger.debug("open database menu")
        self.database_menu = DatabaseMenu(self)
        self.si.send_signal("requestDatabaseMenu")
        self.database_menu.exec_()
        if self.database_menu.result is None:
            logger.debug("No database selected")
            self.database_menu = None
            return
        else:
            logger.info(f"Selected database: {self.database_menu.result}")
            self.member_name_imgs = {}
            self.si.send_signal("selectedDatabase")
            self.si.send_data(self.database_menu.result)
            self.si.send_signal("requestAllMemberImg")
            self.database_menu = None
    
    def recieve_database_menu(self, database_name, member_name, pic):
        if self.database_menu is None:
            logger.warning("Database menu page is not opened")
            return
        if database_name == 'EOF':
            self.database_menu.update()
            return
        self.database_menu.addPreview_img(database_name, member_name, pic)
    
    def alter_param(self, name, value):
        self.si.send_signal("alterParam")
        self.si.send_data((name, value))
    
    def update_progress_bar(self, task, progress, total):
        logger.debug(f"update progress bar: {task}, {progress}, {total}")
        if self.progress_bar is None or self.progress_text is None:
            logger.warning("Progress bar not initialized")
            return
        
        if task == "":
            self.progress_text.setText(f"目前沒有任務")
            self.progress_bar.setValue(0)
            return
        
        if total == 0:
            self.progress_text.setText(task)
            self.progress_bar.setValue(0)
            return
        
        self.progress_text.setText(f"{task} ({str(progress)}/{str(total)})")
        self.progress_bar.setValue(int((progress/total)*100))
        
    def received_param_value(self, name, values):
        #name, values = name_values
        logger.debug(f"Receive param: {name}, values: {values}")
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
        
        if file_path == "": # switch to runtime image mode
            if self.have_runtime_preview:
                logger.debug("already have runtime preview")
                return
            
            if self.have_video_preview:
                logger.debug("remove video preview")
                self.video_preview.close()
                self.video_control.close()
                self.video_area.takeAt(1).widget().deleteLater()
                self.video_area.takeAt(1).widget().deleteLater()
                self.have_video_preview = False
            self.runtime_preview = QtWidgets.QLabel()
            self.runtime_preview.setFixedSize(640, 360)
            self.video_area.addWidget(self.runtime_preview)
            self.have_runtime_preview = True
            logger.debug("Created runtime preview")
            return
        
        if not os.path.exists(file_path):
            logger.warning("File not found")
            self.open_error_dialog("File not found")
            return
        
        if self.have_video_preview:
            logger.debug("Reset video preview")
            self.video_preview.close()
            self.video_control.close()
            self.video_area.takeAt(1).widget().deleteLater()
            self.video_area.takeAt(1).widget().deleteLater()
            
            self.video_preview = VideoPlayer(self, file_path)
            self.video_area.addWidget(self.video_preview)
            
            self.video_control = VideoControlPanel(self, self.video_preview)
            self.video_area.addWidget(self.video_control)
        else:
            self.video_area.takeAt(1).widget().deleteLater()
            self.video_preview = VideoPlayer(self, file_path)
            self.video_area.addWidget(self.video_preview)
            self.have_video_preview = True
            
            self.video_control = VideoControlPanel(self, self.video_preview)
            self.video_area.addWidget(self.video_control)
        self.video_preview.play()
        
    def update_runtime_img(self, pixmap):
        if pixmap is None:
            logger.warning("Receive None pixmap")
            return
        if not self.have_runtime_preview:
            logger.warning("No runtime preview")
            self.switch_video_preview("") # switch to runtime image mode
            
        self.runtime_preview.setPixmap(pixmap)
        
    def open_select_video_dialog(self):
        video_file_dialog = VideoMenu(os.path.join(os.getcwd(), 'meetingVideo'), self)
        video_file_dialog.exec_()
        if video_file_dialog.result is not None:
            logger.debug(f"Selected video: {video_file_dialog.result}")
            file_path = video_file_dialog.result
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
       
    def open_select_record_dialog(self):
        self.record_menu = RecordMenu(self)
        self.si.send_signal("requestRecordMenu")
        self.record_menu.exec_()
        if self.record_menu.result is not None:
            logger.debug(f"Selected record: {self.record_menu.result}")
            self.si.send_signal("selectedRecord")
            self.si.send_data(self.record_menu.result)
            self.record_menu = None
       
    def received_record_menu(self, record_name, video_path, database_name):
        if self.record_menu is None:
            logger.warning("Record menu page is not opened")
            return
        self.record_menu.addRecord(record_name, video_path, database_name)
        logger.debug(f"Receive record: {record_name}, {video_path}, {database_name}")
       
    def open_error_dialog(self, message):
        logger.error(f"Error occur: {message}")
        if not isinstance(message, str) or message is None:
            logger.warning("Invalid error message")
            return
        error_dialog = ErrorDialog(message)
        error_dialog.exec_()
        
    def terminate_process(self):
        logger.info("Terminate process")
        self.si.send_signal("terminateProcess")
        
    def closeEvent(self, event):
        logger.info("Close window and terminate process")
        self.si.send_signal("terminateProcess")
        self.si.close()
        if self.have_video_preview:
            self.video_preview.close()
        event.accept()
        
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    with open("Darkeum.qss", "r") as f:
        app.setStyleSheet(f.read())    
    main = MainWindow()
    main.show()
    sys.exit(app.exec_())