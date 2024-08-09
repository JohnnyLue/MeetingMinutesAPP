import cv2
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtCore import QUrl
import sys

from FaceRecognizer import FaceRecognizer
from FaceDatabaseManager import FaceDatabaseManager
from FaceAnalyzer import FaceAnalyzer
from ScriptManager import ScriptManager
from VideoManager import VideoManager
      
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
    errorOccor = QtCore.pyqtSignal(str) # 錯誤訊息
    ProcessFinished = QtCore.pyqtSignal(str) # 任務完成: 紀錄檔位置

class MainWindow(QtWidgets.QWidget):
    def __init__(self, signal_manager: SignalManager):
        super().__init__()
        self.signal_manager = signal_manager
        self.signal_manager.errorOccor.connect(self.open_error_dialog)
        
        self.setObjectName("MainWindow")
        self.setWindowTitle('操作頁面')
        
        self.resize(800, 600)
        self.ui()

    def ui(self):
        layout = QtWidgets.QHBoxLayout(self)

        video_and_progress_layout = QtWidgets.QVBoxLayout()
        # Video Upload Section
        self.video_area = QtWidgets.QVBoxLayout()
        self.video_drop_area = FileDropArea(self)
        self.signal_manager.selectedVideo.connect(self.switch_video_preview)
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
        self.select_database_button.setDefaultAction(QtWidgets.QAction("選擇資料庫", self, triggered=self.select_database_dialog))
        self.add_button = self.new_button("新增")
        self.delete_button = self.new_button("刪除")
        self.move_button = self.new_button("移動")
        self.rename_button = self.new_button("重新命名")
        self.merge_button = self.new_button("合併")
        db_layout.addWidget(self.database_label)
        db_layout.addWidget(self.select_database_button)
        db_layout.addWidget(self.add_button)
        db_layout.addWidget(self.delete_button)
        db_layout.addWidget(self.move_button)
        db_layout.addWidget(self.rename_button)
        db_layout.addWidget(self.merge_button)
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
        self.test_button = self.new_button("測試執行")
        layout.addWidget(self.test_button)
        
        self.signal_manager.requestParams.emit()
        self.signal_manager.requestProgress.emit()

    def new_button(self, text):
        btn = QtWidgets.QToolButton(self)
        btn.setText(text)
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
        self.video_area.removeWidget(self.video_drop_area)
        self.video_preview = QtWidgets.QLabel(self)
        self.video_preview.setFixedSize(640, 360)
        self.video_area.addWidget(self.video_preview)
        self.signal_manager.UpdatePrevewImg.connect(self.update_video_preview)
        self.signal_manager.requestPreviewImg.emit()
        
    @QtCore.pyqtSlot(QtGui.QPixmap)
    def update_video_preview(self, pixmap):
        self.video_preview.setPixmap(pixmap.scaled(640, 360, QtCore.Qt.AspectRatioMode.KeepAspectRatio))
        
    def select_video_dialog(self):
        video_file_dialog = QtWidgets.QFileDialog(self)
        video_file_dialog.setNameFilter("Video File (*.mp4)")
        if video_file_dialog.exec_():
            file_path = video_file_dialog.selectedFiles()[0]
            if file_path:
                self.signal_manager.selectedVideo.emit(file_path)
                
    @QtCore.pyqtSlot(str)
    def open_error_dialog(self, message):
        error_dialog = ErrorDialog(message)
        error_dialog.exec_()
        
class Backend(QtCore.QObject):
    def __init__(self, signal_manager: SignalManager):
        super().__init__()
        self.signal_manager = signal_manager
        
        self.signal_manager.selectedVideo.connect(self.set_video_path)
        self.signal_manager.selectedDatabase.connect(self.set_database_path)
        self.signal_manager.testRun.connect(self.test_run)
        self.signal_manager.startProcess.connect(self.run)
        self.signal_manager.requestPreviewImg.connect(self.update_preview_img)
        self.signal_manager.alterParam.connect(self.alter_param)
        self.signal_manager.requestParams.connect(self.get_params)
        self.signal_manager.requestProgress.connect(self.update_progress)
        
        # parameters
        self.det_size = "480x480"
        self.whisper_model = "small"
        self.language = "zh"
        self.new_member_prefix = "member_"
        self.value_window_size = 20
        
        # create vm first for preview
        self.vm = VideoManager()
        
        self.running = False
    
    @QtCore.pyqtSlot()
    def run(self):
        # check parameters is valid
        if not self.det_size:
            self.signal_manager.errorOccor.emit("Please set the detection size.")
            return
        if not self.whisper_model:
            self.signal_manager.errorOccor.emit("Please set the whisper model.")
            return
        if not self.new_member_prefix:
            self.signal_manager.errorOccor.emit("Please set the new member prefix.")
            return
        if not self.vm.is_ready:
            self.signal_manager.errorOccor.emit("Please select a video.")
            return
        if self.running:
            self.signal_manager.errorOccor.emit("The process is already running.")
            return
        if self.det_size.format(r"\d+x\d+") is None:
            self.signal_manager.errorOccor.emit("Please set the detection size in correct format (format: 123x456).")
            return
        det_size = tuple(map(int, self.det_size.split("x")))
        if det_size[0] < 0 or det_size[1] < 0:
            self.signal_manager.errorOccor.emit("Both value in det_size must be positive integer.")
            
        try:
            self.fr = FaceRecognizer(det_size=det_size)
            self.fdm = FaceDatabaseManager(self.face_database, self.fr, new_member_prefix=self.new_member_prefix)
            self.fa = FaceAnalyzer(value_window_size=self.value_window_size)
            self.sm = ScriptManager(model_name=self.whisper_model, language=self.language)
        except Exception as e:
            self.signal_manager.errorOccor.emit(str(e))
            return
        
        self.running = True
        
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
        self.face_database = database_path
    
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
        self.signal_manager.updateParam.emit("det_size", self.det_size)
        self.signal_manager.updateParam.emit("whisper_model", self.whisper_model)
        self.signal_manager.updateParam.emit("language", self.language)
        self.signal_manager.updateParam.emit("new_member_prefix", self.new_member_prefix)
        self.signal_manager.updateParam.emit("value_window_size", str(self.value_window_size))
    
    def update_progress(self):
        '''
        return current processing section and progress/total using tuple
        '''
        if not self.running:
            self.signal_manager.updateProgress.emit("test", 15, 45)
        else:
            self.signal_manager.updateProgress.emit(self.cur_process, self.cur_progress, self.total_progress)
    
    @QtCore.pyqtSlot(str, str)
    def alter_param(self, param_name, value):
        #self.det_size = "480x480"
        #self.whisper_model = "small"
        #self.language = "zh"
        #self.new_member_prefix = "member_"
        #self.value_window_size = 20
        
        if param_name == "det_size":
            self.det_size = value
        elif param_name == "whisper_model":
            self.whisper_model = value
        elif param_name == "language":
            self.language = value
        elif param_name == "new_member_prefix":
            self.new_member_prefix = value
        elif param_name == "value_window_size":
            self.value_window_size = int(value)
        
    def test_run(self):
        print(f"Run with parameters: {self.det_size}, {self.param2}, {self.param3}")

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
            self.parent().select_video_dialog()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    with open("Incrypt.qss", "r") as f:
        app.setStyleSheet(f.read())
    signal_manager = SignalManager()
    backend = Backend(signal_manager)
    MainWindow = MainWindow(signal_manager)
    MainWindow.show()
    sys.exit(app.exec_())