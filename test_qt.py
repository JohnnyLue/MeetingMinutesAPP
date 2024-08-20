import cv2
from PyQt5 import QtWidgets, QtCore, QtGui
import sys
import threading
import time

from FaceRecognizer import FaceRecognizer
from FaceDatabaseManager import FaceDatabaseManager
from FaceAnalyzer import FaceAnalyzer
from ScriptManager import ScriptManager
from VideoManager import VideoManager
from Record import Record

default_params = {
    "det_size": "480x480",
    "whisper_model": "small",
    "language": "zh",
    "new_member_prefix": "member_",
    "value_window_size": "20"
}

def cv2_to_pixmap(cv2_img):
    cv2_img = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)
    height, width, channel = cv2_img.shape
    bytesPerLine = channel * width
    qImg = QtGui.QImage(cv2_img.data, width, height, bytesPerLine, QtGui.QImage.Format_RGB888)
    return QtGui.QPixmap.fromImage(qImg)
      
class SignalManager(QtCore.QObject):
    # Define signals
    requestImgByName = QtCore.pyqtSignal(str) # 要求照片: 名字
    returnedMemberImg = QtCore.pyqtSignal(str, QtGui.QPixmap) # 回傳名字, 照片

    selectedVideo = QtCore.pyqtSignal(str) # 選擇影片: 檔案位置
    selectedDatabase = QtCore.pyqtSignal(str) # 選擇資料庫: 
    
    requestPreviewImg = QtCore.pyqtSignal() # 要求預覽圖
    UpdatePrevewImg = QtCore.pyqtSignal(QtGui.QPixmap) # 更新影片預覽圖
    
    requestParams = QtCore.pyqtSignal() # 要求參數(全部)
    updateParam = QtCore.pyqtSignal(str, str) # 更新顯示參數: 參數名, 值
    alterParam = QtCore.pyqtSignal(str, str) # 修改參數: 參數名, 值
    
    requestProgress = QtCore.pyqtSignal() # 要求更新進度
    updateProgress = QtCore.pyqtSignal(str, int, int) # 任務, 進度, 總進度
    
    testRun = QtCore.pyqtSignal() # 要求測試執行
    startProcess = QtCore.pyqtSignal() # 要求開始處理
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
        
        self.setObjectName("MainWindow")
        self.setWindowTitle('操作頁面')
        
        self.resize(800, 600)
        self.ui()
        
        self.have_video_preview = False
        
    def ui(self):
        layout = QtWidgets.QHBoxLayout(self)

        video_and_progress_layout = QtWidgets.QVBoxLayout()
        # Video Upload Section
        self.video_area = QtWidgets.QVBoxLayout()
        self.select_video_button = self.new_button()
        self.select_video_button.setDefaultAction(QtWidgets.QAction("選擇影片", self, triggered=self.open_select_video_dialog))
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
        self.select_database_button = self.new_button()
        self.select_database_button.setDefaultAction(QtWidgets.QAction("選擇資料庫", self, triggered=self.select_database_dialog))
        ops = ["新增", "刪除", "移動", "重新命名", "合併"]
        self.db_tabWidget = QtWidgets.QTabWidget(self)
        self.db_tabWidget.setFixedHeight(400)
        self.db_tabWidget.setFixedWidth(450)
        self.db_tabWidget.setFont(MyFont())
        self.add_widget = QtWidgets.QWidget()
        self.delete_widget = QtWidgets.QWidget()
        self.move_widget = QtWidgets.QWidget()
        self.rename_widget = QtWidgets.QWidget()
        self.merge_widget = QtWidgets.QWidget()
        self.db_tabWidget.addTab(self.add_widget, "新增")
        self.db_tabWidget.addTab(self.delete_widget, "刪除")
        self.db_tabWidget.addTab(self.move_widget, "移動")
        self.db_tabWidget.addTab(self.rename_widget, "重新命名")
        self.db_tabWidget.addTab(self.merge_widget, "合併")
        self.add_widget_ui()
        self.delete_widget_ui()
        self.move_widget_ui()
        self.rename_widget_ui()
        self.merge_widget_ui()
        db_layout.addWidget(self.database_label)
        db_layout.addWidget(self.select_database_button)
        db_layout.addWidget(self.db_tabWidget)
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
        self.test_button = self.new_button()# "測試執行"
        layout.addWidget(self.test_button)
        
        self.signal_manager.requestParams.emit()
        self.signal_manager.requestProgress.emit()

    def add_widget_ui(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)
        add_button = self.new_button()
        add_button.setDefaultAction(QtWidgets.QAction("新增", self))
        layout.addWidget(add_button)
        self.add_widget.setLayout(layout)
        
    def delete_widget_ui(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)
        add_button = self.new_button()
        add_button.setDefaultAction(QtWidgets.QAction("adf", self))
        layout.addWidget(add_button)
        self.delete_widget.setLayout(layout)
        
    def move_widget_ui(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)
        add_button = self.new_button()
        add_button.setDefaultAction(QtWidgets.QAction("adsf", self))
        layout.addWidget(add_button)
        self.move_widget.setLayout(layout)
    
    def rename_widget_ui(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)
        add_button = self.new_button()
        add_button.setDefaultAction(QtWidgets.QAction("faaf", self))
        layout.addWidget(add_button)
        self.rename_widget.setLayout(layout)
        
    def merge_widget_ui(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)
        add_button = self.new_button()
        add_button.setDefaultAction(QtWidgets.QAction("eee", self))
        layout.addWidget(add_button)
        self.merge_widget.setLayout(layout)
        
    def new_button(self):
        btn = QtWidgets.QToolButton(self)
        #btn.setText(text)
        btn.setAutoRaise(True)
        btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(40)
        btn.setFixedWidth(150)
        btn.setFont(MyFont())
        return btn
    
    def select_database_dialog(self):
        database_file_dialog = QtWidgets.QFileDialog(self)
        database_file_dialog.setNameFilter("Database Folder (*)")
        database_file_dialog.setFileMode(QtWidgets.QFileDialog.FileMode.Directory)
        if database_file_dialog.exec_():
            file_path = database_file_dialog.selectedFiles()[0]
            if file_path:
                self.signal_manager.selectedDatabase.emit(file_path)
    
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
            self.video_preview.setFixedSize(640, 360)
            self.video_area.addWidget(self.video_preview)
            self.have_video_preview = True
            
            control_layout = QtWidgets.QHBoxLayout()
            control_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.video_rewind_button = self.new_button()
            self.video_rewind_button.setDefaultAction(QtWidgets.QAction("後退", self, triggered=lambda: self.video_preview.rewind(5)))
            self.video_pause_button = self.new_button()
            self.video_pause_button.setDefaultAction(QtWidgets.QAction("播放", self, triggered=lambda: (self.video_preview.pause(), self.video_pause_button.setText("播放") if self.video_preview.is_paused else self.video_pause_button.setText("暫停"))))
            self.video_forward_button = self.new_button()
            self.video_forward_button.setDefaultAction(QtWidgets.QAction("前進", self, triggered=lambda: self.video_preview.forward(5)))
            control_layout.addWidget(self.video_rewind_button)
            control_layout.addWidget(self.video_pause_button)
            control_layout.addWidget(self.video_forward_button)
            self.video_area.addLayout(control_layout)
        self.video_preview.play()
        
        #self.signal_manager.UpdatePrevewImg.connect(self.update_video_preview)
        #self.signal_manager.requestPreviewImg.emit()
        
    @QtCore.pyqtSlot(QtGui.QPixmap)
    def update_video_preview(self, pixmap):
        self.video_preview.setPixmap(pixmap.scaled(640, 360, QtCore.Qt.AspectRatioMode.KeepAspectRatio))
        
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
        self.signal_manager.requestPreviewImg.connect(self.update_preview_img)
        self.signal_manager.alterParam.connect(self.set_param)
        self.signal_manager.requestParams.connect(self.get_params)
        self.signal_manager.requestProgress.connect(self.update_progress)
        self.signal_manager.recordOverwriteConfirmed.connect(self.clear_record_and_run)
        
        # parameters from record, if not recorded, use default
        for key, _ in default_params.items():
            #print(f"Get parameter {key} from record: {record.get_parameter(key)}")
            self.set_param(key, record.get_parameter(key)) # if param is not set in record, get_parameter will return None, and set_param will use default value.
        
        # create ViedoManager first for video preview
        self.vm = VideoManager()
        
        self.running = False
    
    @QtCore.pyqtSlot()
    def run(self):
        if self.record.is_ready:
            self.signal_manager.recordOverwrite.emit()
            return
            
        if not self.vm.is_ready:
            self.signal_manager.errorOccor.emit("Please select a video.")
            return
        if self.running:
            self.signal_manager.errorOccor.emit("The process is already running.")
            return
        if self.params['det_size'].format(r"\d+x\d+") is None:
            self.signal_manager.errorOccor.emit("Please set the detection size in correct format (format: 123x456).")
            return
        
        det_size = self.params['det_size'].format(r"\d+x\d+")
        det_size = tuple(map(int, det_size.split("x")))
        if det_size[0] < 0 or det_size[1] < 0:
            self.signal_manager.errorOccor.emit("Both value in det_size must be positive integer.")
            
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
        self.sm.transcribe(self.vm.get_video_path())
        
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
        
    @QtCore.pyqtSlot()
    def clear_record_and_run(self):
        self.record.clear()
        self.run()
        
    @QtCore.pyqtSlot(str)
    def set_video_path(self, video_path: str):
        print(f"Set video path: {video_path}")
        try:
            self.vm.load_video(video_path)
        except Exception as e:
            self.signal_manager.errorOccor.emit(str(e))
     
    @QtCore.pyqtSlot(str)
    def set_database_path(self, database_path):
        print(f"Set database path: {database_path}")
        self.fdm = FaceDatabaseManager(database_path)
    
    @QtCore.pyqtSlot()
    def update_preview_img(self):
        try:
            frame = self.vm.get_frame()
        except Exception as e:
            self.signal_manager.errorOccor.emit(str(e))
            return
        
        pixmap = cv2_to_pixmap(frame)
        self.signal_manager.UpdatePrevewImg.emit(pixmap)
    
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
        print(f"Run with parameters: {self.det_size}, {self.param2}, {self.param3}")
        
    def save_record(self):
        for key, _ in default_params.items():
            self.record.set_parameter(key, self.params[key])
        self.record.export()

class ErrorDialog(QtWidgets.QDialog):
    def __init__(self, message):
        super().__init__()
        self.setWindowTitle("Error")
        self.setFixedSize(300, 100)
        
        layout = QtWidgets.QVBoxLayout(self)
        label = QtWidgets.QLabel(message, self)
        label.setFont(MyFont())
        layout.addWidget(label)
        
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
        #self.setStyleSheet('''
        #    QWidget {
        #        border: 2px dashed #aaa;
        #        border-radius: 20px;
        #        font-size: 16px;
        #        color: #000;
        #        background-color: #FFF;
        #    }
        #''')
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
        self.label.setText(f"已選擇檔案:\n" + "\n".join(files))

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
        self.load(video_path)
        self.setFixedSize(640, 360)
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
    def update(self, img):
        self.setPixmap(img.scaled(640, 360, QtCore.Qt.AspectRatioMode.KeepAspectRatio))

    def load(self, path):
        self.cap = cv2.VideoCapture(path)
        self.update(cv2_to_pixmap(self.cap.read()[1]))

    def reset(self):
        self.quit_loop = True
        self.play_thread.join()
        self.cap.release()

    def pause(self):
        self.is_paused = not self.is_paused

    def forward(self, seconds):
        self.is_paused = True
        time.sleep(0.1)
        self.cap.set(cv2.CAP_PROP_POS_MSEC, self.cap.get(cv2.CAP_PROP_POS_MSEC) + seconds*1000)
        self.is_paused = False
    
    def rewind(self, seconds):
        self.is_paused = True
        time.sleep(0.1)
        self.cap.set(cv2.CAP_PROP_POS_MSEC, self.cap.get(cv2.CAP_PROP_POS_MSEC) - seconds*1000)
        self.is_paused = False
    
    def set_time(self, seconds):
        self.cap.set(cv2.CAP_PROP_POS_MSEC, seconds*1000)
        
    def get_time(self):
        return self.cap.get(cv2.CAP_PROP_POS_MSEC)/1000
    
    def get_total_time(self):
        return self.cap.get(cv2.CAP_PROP_FRAME_COUNT)/self.cap.get(cv2.CAP_PROP_FPS)
    
    def play(self):
        delay = 1.0/self.cap.get(cv2.CAP_PROP_FPS)
        def func():
            while True:
                if self.quit_loop:
                    self.quit_loop = False
                    break
                if not self.is_paused:
                    ret, frame = self.cap.read()
                    if not ret:
                        self.is_paused = True
                        break
                    pFrame = cv2_to_pixmap(frame)
                    self.update(pFrame)
                time.sleep(delay)
        
        self.play_thread = threading.Thread(target=func)
        self.play_thread.start()
        
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    with open("Incrypt.qss", "r") as f:
        app.setStyleSheet(f.read())
    signal_manager = SignalManager()
    record = Record(store_base='records')
    backend = Backend(signal_manager, record)
    MainWindow = MainWindow(signal_manager)
    MainWindow.show()
    sys.exit(app.exec_())