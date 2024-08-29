import cv2
import math
from PyQt5 import QtWidgets, QtCore, QtGui
import sys
import threading

from FaceRecognizer import FaceRecognizer
from FaceDatabaseManager import FaceDatabaseManager
from FaceAnalyzer import FaceAnalyzer
from FrontEndWidgets import *
from ScriptManager import ScriptManager
from VideoManager import VideoManager
from Record import Record
from Utils import *

default_params = {
    "det_size": "480x480",
    "whisper_model": "small",
    "language": "zh",
    "new_member_prefix": "member_",
    "value_window_size": "20"
}
      
class SignalManager(QtCore.QObject):
    # Define signals
    requestImgByName = QtCore.pyqtSignal(str) # 要求照片: 名字
    requestAllMemberImg = QtCore.pyqtSignal() # 要求全部照片
    returnedMemberImg = QtCore.pyqtSignal(str, QtGui.QPixmap) # 回傳名字, 照片

    selectedVideo = QtCore.pyqtSignal(str) # 選擇影片: 檔案位置
    selectedDatabase = QtCore.pyqtSignal(str) # 選擇資料庫: 
    
    requestParams = QtCore.pyqtSignal() # 要求參數(全部)
    updateParam = QtCore.pyqtSignal(str, str) # 更新顯示參數: 參數名, 值
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

class MainWindow(QtWidgets.QWidget):
    def __init__(self, signal_manager: SignalManager):
        super().__init__()
        self.signal_manager = signal_manager
        self.signal_manager.errorOccor.connect(self.open_error_dialog)
        self.signal_manager.recordOverwrite.connect(self.open_check_overwrite_dialog)
        self.signal_manager.selectedVideo.connect(self.switch_video_preview)
        self.signal_manager.returnedMemberImg.connect(self.update_database_member_img)
        
        self.setObjectName("MainWindow")
        self.setWindowTitle('操作頁面')
        
        self.resize(1100, 600)
        self.ui()
        
        self.have_video_preview = False
        self.member_name_imgs = {}
        
    def ui(self):
        layout = QtWidgets.QHBoxLayout(self)

        video_and_progress_layout = QtWidgets.QVBoxLayout()
        # Video Upload Section
        self.video_area = QtWidgets.QVBoxLayout()
        self.select_video_button = self.new_button("選擇影片")
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
        self.signal_manager.updateProgress.connect(self.update_progress_bar)
        video_and_progress_layout.addLayout(progress_bar_layout)
        layout.addLayout(video_and_progress_layout)

        # database control and parameter section
        db_and_parm_layout = QtWidgets.QVBoxLayout()
        db_and_parm_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        # Database Operations
        db_layout = QtWidgets.QVBoxLayout()
        db_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        db_layout.setSpacing(10)
        self.database_label = QtWidgets.QLabel("資料庫操作:", self)
        self.database_label.setFont(MyFont())
        self.select_database_button = self.new_button("選擇資料庫")
        self.select_database_button.clicked.connect(self.select_database_dialog)
        
        # Database Operation Gui
        self.db_grid_layout = QtWidgets.QGridLayout()
        self.db_scroll_widget = QtWidgets.QWidget()
        self.db_scroll_area = QtWidgets.QScrollArea()
        self.db_scroll_area.setObjectName("DatabaseScrollArea")
        self.db_scroll_area.setStyleSheet(r"#DatabaseScrollArea {border: 2px solid #aaa;}")
        self.db_scroll_widget.setLayout(self.db_grid_layout)
        self.db_scroll_area.setWidget(self.db_scroll_widget)
        #self.db_scroll_area.setWidgetResizable(True)
        self.db_scroll_widget.hide()
        db_layout.addWidget(self.database_label)
        db_layout.addWidget(self.select_database_button)
        db_layout.addWidget(self.db_scroll_area)
        db_and_parm_layout.addLayout(db_layout)
        db_and_parm_layout.addSpacing(30)

        # Parameter Adjustment Section
        param_layout = QtWidgets.QVBoxLayout()
        param_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignBottom)
        
        self.param_label = QtWidgets.QLabel("參數調整:")
        self.param_label.setFont(MyFont())
        
        # Create a combo box for selecting parameters to adjust
        self.param_combo = QtWidgets.QComboBox()
        self.param_combo.setFont(MyFont())
        
        self.param_input = QtWidgets.QLineEdit()
        self.param_input.setFont(MyFont())
        self.param_input.setFixedWidth(160)
        self.param_input.setPlaceholderText("")
        
        # Connect the signal of combo box to input box
        self.param_combo.currentTextChanged.connect(self.alter_param)
        self.signal_manager.updateParam.connect(self.update_param_value)
        
        param_layout.addWidget(self.param_label)
        param_layout.addWidget(self.param_combo)
        param_layout.addWidget(self.param_input)
        db_and_parm_layout.addLayout(param_layout)
        
        layout.addLayout(db_and_parm_layout)

        # Test Execution Section
        execution_layout = QtWidgets.QVBoxLayout()
        execution_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.test_button = self.new_button("測試執行")
        self.test_button.clicked.connect(self.signal_manager.testRun.emit)
        self.run_button = self.new_button("確認執行")
        self.run_button.clicked.connect(self.signal_manager.startProcess.emit)
        execution_layout.addWidget(self.test_button)
        execution_layout.addSpacing(20)
        execution_layout.addWidget(self.run_button)
        layout.addLayout(execution_layout)
        
        self.signal_manager.requestParams.emit()
        self.signal_manager.requestProgress.emit()

    def new_button(self, text=""):
        btn = QtWidgets.QPushButton(self)
        btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(40)
        btn.setFixedWidth(150)
        btn.setFont(MyFont())
        btn.setText(text)
        return btn
    
    def resizeEvent(self, event):
        self.resize_database_widget()
    
    @QtCore.pyqtSlot(str, QtGui.QPixmap)
    def update_database_member_img(self, name, pixmap):
        if name == "": # all images are sent
            self.resize_database_widget()
            self.db_scroll_widget.show()
            return
        
        print(f"Update database member img: {name}")
        if name not in self.member_name_imgs:
            self.member_name_imgs[name] = []
            self.member_name_imgs[name].append(pixmap)
        else:
            self.member_name_imgs[name].append(pixmap)
        
    def resize_database_widget(self):
        cols = (self.db_scroll_area.size().width()-25)//120 #減掉拉桿25px，至少有 20px 的留空 (左右各10px)
        for _ in range(self.db_grid_layout.count()):
            self.db_grid_layout.takeAt(0).widget().deleteLater()
        i_row = 0
        i_col = 0
        for name, imgs in self.member_name_imgs.items():
            member_img = QtWidgets.QLabel()
            member_img.setPixmap(imgs[0].scaled(100, 100, QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding))
            member_img.setStyleSheet("border :4px solid #607cff;")
            member_img.setFixedSize(100, 100)
            member_img.setToolTip(name)
            self.db_grid_layout.addWidget(member_img, i_row, i_col)
            i_col += 1
            if i_col == cols:
                i_col = 0
                i_row += 1
        
        hei = 110*math.ceil(len(self.member_name_imgs)/cols)
        if hei < self.db_scroll_area.size().height():
            self.db_scroll_widget.resize(QtCore.QSize(self.db_scroll_area.size().width()-5, hei))
        else:
            self.db_scroll_widget.resize(QtCore.QSize(self.db_scroll_area.size().width()-25, hei))
        
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
                self.signal_manager.selectedDatabase.emit(file_path)
                self.signal_manager.requestAllMemberImg.emit()
    
    def alter_param(self):
        name = self.param_combo.currentText()
        value = self.param_combo.itemData(self.param_combo.currentIndex())
        self.param_input.setText(value)
        self.signal_manager.alterParam.emit(name, value)
    
    @QtCore.pyqtSlot(str, int, int)
    def update_progress_bar(self, task, progress, total):
        if task == "" or total == 0:
            self.progress_task.setText("目前沒有任務")
            self.progress_bar.setValue(0)
            self.progress_percent.setText("")
            return
        
        self.progress_task.setText(task)
        self.progress_bar.setValue(int(progress/total*100))
        self.progress_percent.setText(f"{progress}/{total}")
        
    @QtCore.pyqtSlot(str, str)
    def update_param_value(self, name, value):
        self.param_combo.addItem(name)
        self.param_combo.setItemData(self.param_combo.count()-1, value)

    @QtCore.pyqtSlot(str)
    def switch_video_preview(self, file_path: str):
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
            self.video_rewind_button = self.new_button("後退")
            self.video_rewind_button.clicked.connect(lambda: self.video_preview.rewind(5))
            self.video_pause_button = self.new_button("播放")
            self.video_pause_button.clicked.connect(lambda: (self.video_preview.pause(), self.video_pause_button.setText("播放") if self.video_preview.is_paused else self.video_pause_button.setText("暫停")))
            self.video_forward_button = self.new_button("前進")
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
                self.signal_manager.selectedVideo.emit(file_path)
    
    @QtCore.pyqtSlot()
    def open_check_overwrite_dialog(self):
        check_dialog = QtWidgets.QMessageBox(self)
        check_dialog.setWindowTitle("確認")
        check_dialog.setText("紀錄已存在，是否覆蓋？")
        check_dialog.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
        if check_dialog.exec_() == QtWidgets.QMessageBox.StandardButton.Yes:
            self.signal_manager.recordOverwriteConfirmed.emit()
       
    @QtCore.pyqtSlot(str)
    def open_error_dialog(self, message):
        error_dialog = ErrorDialog(message)
        error_dialog.exec_()
        
    def closeEvent(self, event):
        self.signal_manager.terminateProcess.emit()
        if self.have_video_preview:
            self.video_preview.reset()
        event.accept()
        
class Backend(QtCore.QObject):
    def __init__(self, signal_manager: SignalManager, record: Record):
        super().__init__()
        self.signal_manager = signal_manager
        self.record = record
        self.params = {}
        
        # connect signals
        self.signal_manager.selectedVideo.connect(self.set_video_path)
        self.signal_manager.selectedDatabase.connect(self.set_database_path)
        self.signal_manager.testRun.connect(self.test_run)
        self.signal_manager.startProcess.connect(self.run)
        self.signal_manager.terminateProcess.connect(self.terminateProcess)
        self.signal_manager.alterParam.connect(self.set_param)
        self.signal_manager.requestParams.connect(self.get_params)
        self.signal_manager.requestProgress.connect(self.update_progress)
        self.signal_manager.recordOverwriteConfirmed.connect(self.clear_record_and_run)
        self.signal_manager.requestAllMemberImg.connect(self.get_all_member_img)
        
        # parameters from record, if not recorded, use default
        for key, _ in default_params.items():
            #print(f"Get parameter {key} from record: {record.get_parameter(key)}")
            self.set_param(key, record.get_parameter(key)) # if param is not set in record, get_parameter will return None, and set_param will use default value.
        
        # create ViedoManager first for video preview
        self.vm = VideoManager()
        
        self.running = False
        self.test_running = False
        self.have_face_database = False
        self.transcribe_thread = None
        self.main_thread = None
        self.test_run_thread = None
        
        self.cur_process = ""
        self.cur_progress = 0
        self.total_progress = 100
    
    @QtCore.pyqtSlot()
    def run(self):
        if not self.vm.is_ready:
            self.signal_manager.errorOccor.emit("Please select a video.")
            return
        if self.running:
            self.signal_manager.errorOccor.emit("Running process is already running.")
            return
        if self.test_running:
            self.signal_manager.errorOccor.emit("正在測試執行，請終止之後再試。")
            return
        if self.params['det_size'].format(r"\d+x\d+") is None:
            self.signal_manager.errorOccor.emit("Please set the detection size in correct format (format: 123x456).")
            return
        det_size = self.params['det_size'].format(r"\d+x\d+")
        det_size = tuple(map(int, det_size.split("x")))
        if det_size[0] < 0 or det_size[1] < 0:
            self.signal_manager.errorOccor.emit("Both value in det_size must be positive integer.")
        if not self.have_face_database:
            self.signal_manager.errorOccor.emit("Please select a database.")
            return
        if self.record.is_ready:
            self.signal_manager.recordOverwrite.emit()
            return
        
        try:
            self.fr = FaceRecognizer(det_size=det_size)
            self.fdm.set_face_recognizer(self.fr)
            self.fdm.set_new_member_prefix(self.params['new_member_prefix'])
            self.fa = FaceAnalyzer(value_window_size=int(self.params['value_window_size']))
            self.sm = ScriptManager(model_name=self.params['whisper_model'], language=self.params['language'])
        except Exception as e:
            self.signal_manager.errorOccor.emit(str(e))
            return
        
        self.running = True
        
        self.cur_process = "Transcribing"
        self.cur_progress = 0
        self.total_progress = 100
        self.update_progress()
        self.transcribe_thread = threading.Thread(target=lambda: self.sm.transcribe(self.vm.get_video_path()))
        self.transcribe_thread.start()
        
        def main_run():
            while self.running:
                try:
                    frame = self.vm.next_frame()
                except Exception as e:
                    self.signal_manager.errorOccor.emit(str(e))
                    self.running = False
                    break
                faces = self.fr.get(frame)
                bboxes = []
                for i in range(len(faces)):
                    bbox = faces[i].bbox.astype(int).tolist()
                    bboxes.append(bbox)
                names = []
                for i in range(len(faces)):
                    name = self.fr.get_name(frame, faces[i], self.fdm, create_new_face=True)
                    names.append(name)
                    
                self.fa.update(zip(names, [self.fr.get_landmark(x) for x in faces]))
                statuses = []
                for i in range(len(faces)):
                    status = self.fa.is_talking(names[i])
                    statuses.append(status)
                    
                time_s = self.vm.get_time()
                
                self.record.write_data(time_s, bboxes, names, statuses)
                #print(f"Recorded at {time_s} s")
                #print(f"bboxes: {bboxes}")
                #print(f"Names: {names}")
                #print(f"Statuses: {statuses}")
                
            self.running = False
            self.save_record()
        
        self.main_thread = threading.Thread(target=main_run)
        self.main_thread.start()
        
    @QtCore.pyqtSlot()
    def clear_record_and_run(self):
        self.record.clear()
        self.run()
        
    @QtCore.pyqtSlot(str)
    def set_video_path(self, video_path: str):
        print(f"Set video path: {video_path}")
        def func():
            try:
                self.vm.load_video(video_path)
            except Exception as e:
                self.signal_manager.errorOccor.emit(str(e))
        threading.Thread(target=func).start()
     
    @QtCore.pyqtSlot(str)
    def set_database_path(self, database_path):
        self.fdm = FaceDatabaseManager(database_path)
        self.have_face_database = True
        print(f"Set database path: {database_path}")
    
    @QtCore.pyqtSlot()
    def get_all_member_img(self):
        if not self.have_face_database:
            self.signal_manager.errorOccor.emit("Please select a database.")
            return
        
        names = self.fdm.get_name_list()
        for name in names:
            imgs = self.fdm.get_images_by_name(name)
            for img in imgs:
                self.signal_manager.returnedMemberImg.emit(name, cv2_to_pixmap(img))
        self.signal_manager.returnedMemberImg.emit("", QtGui.QPixmap()) # send a signal to tell all images are sent
    
    def get_params(self):
        for key, _ in default_params.items():
            try:
                self.signal_manager.updateParam.emit(key, self.params[key])
            except:
                self.signal_manager.updateParam.emit(key, default_params[key])
    
    def update_progress(self):
        '''
        return current processing section and progress/total using tuple
        '''
        if not self.running:
            self.signal_manager.updateProgress.emit("test", 15, 45)
        else:
            self.signal_manager.updateProgress.emit(self.cur_process, self.cur_progress, self.total_progress)
    
    @QtCore.pyqtSlot(str, str)
    def set_param(self, param_name, value):
        change_to_default = False
        if value is None:
            change_to_default = True
        
        if change_to_default:
            self.params[param_name] = default_params[param_name]
        else:
            self.params[param_name] = value
        
    def test_run(self):
        if not self.vm.is_ready:
            self.signal_manager.errorOccor.emit("Please select a video.")
            return
        if self.running:
            self.signal_manager.errorOccor.emit("Running process is already running.")
            return
        if self.test_running:
            self.signal_manager.errorOccor.emit("Test running process is already running.")
            return
        if not self.have_face_database:
            self.signal_manager.errorOccor.emit("Please select a database.")
            return
        if self.params['det_size'].format(r"\d+x\d+") is None:
            self.signal_manager.errorOccor.emit("Please set the detection size in correct format (format: 123x456).")
            return
        
        det_size = self.params['det_size'].format(r"\d+x\d+")
        det_size = tuple(map(int, det_size.split("x")))
        if det_size[0] < 0 or det_size[1] < 0:
            self.signal_manager.errorOccor.emit("Both value in det_size must be positive integer.")
            return
            
        print(f"Test running with parameters: {self.params}")
        try:
            self.fr = FaceRecognizer(det_size=det_size)
            self.fdm.set_face_recognizer(self.fr)
            self.fdm.set_new_member_prefix(self.params['new_member_prefix'])
            self.fa = FaceAnalyzer(value_window_size=int(self.params['value_window_size']))
            self.sm = ScriptManager(model_name=self.params['whisper_model'], language=self.params['language'])
        except Exception as e:
            self.signal_manager.errorOccor.emit(str(e))
            return
        
        self.test_running = True
        
        #self.cur_process = "Transcribing"
        #self.cur_progress = 0
        #self.total_progress = 100
        #self.update_progress()
        #self.transcribe_thread = threading.Thread(target=lambda: self.sm.transcribe(self.vm.get_video_path()))
        #self.transcribe_thread.start()
        
        def test_run():
            while self.test_running:
                try:
                    frame = self.vm.next_frame()
                except Exception as e:
                    self.signal_manager.errorOccor.emit(str(e))
                    self.test_running = False
                    break
                
                frame = cv2.resize(frame, (1280, 720)) # 16:9
                faces = self.fr.get(frame)
                bboxes = []
                for i in range(len(faces)):
                    bbox = faces[i].bbox.astype(int).tolist()
                    bboxes.append(bbox)
                names = []
                for i in range(len(faces)):
                    name = self.fr.get_name(frame, faces[i], self.fdm, create_new_face=False)
                    names.append(name)
                self.fa.update(zip(names, [self.fr.get_landmark(x) for x in faces]))
                statuses = []
                for i in range(len(faces)):
                    status = self.fa.is_talking(names[i])
                    statuses.append(status)
                    
                time_s = self.vm.get_time()
                
                #print(f"Recorded at {time_s} s")
                #print(f"bboxes: {bboxes}")
                #print(f"Names: {names}")
                #print(f"Statuses: {statuses}")
                
                # putting informations on the frame using cv2
                for i in range(len(faces)):
                    cv2.rectangle(frame, tuple(bboxes[i][:2]), tuple(bboxes[i][2:]), (0, 255, 0), 2)
                    frame = PutText(frame, "Not Found" if not names[i] else names[i], (bboxes[i][0], bboxes[i][1]-10))
                    frame = PutText(frame, "Talking" if statuses[i] else "Slient", (bboxes[i][0], bboxes[i][3]+20))
                cv2.imshow("Test Running", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                
            self.test_running = False
        
        self.test_run_thread = threading.Thread(target=test_run)
        self.test_run_thread.start()
        
    @QtCore.pyqtSlot()
    def terminateProcess(self):
        self.running = False
        self.test_running = False
        if self.test_run_thread:
            self.test_run_thread.join()
        if self.transcribe_thread:
            self.transcribe_thread.join()
        if self.main_thread:
            self.main_thread.join()
        
    def save_record(self):
        for key, _ in default_params.items():
            self.record.set_parameter(key, self.params[key])
        self.record.export()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    with open("Darkeum.qss", "r") as f:
        app.setStyleSheet(f.read())
    signal_manager = SignalManager()
    record = Record(store_base='records')
    backend = Backend(signal_manager, record)
    main = MainWindow(signal_manager)
    main.show()
    sys.exit(app.exec_())