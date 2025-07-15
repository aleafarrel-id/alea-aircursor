import sys
import os
import cv2
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QTimer, Qt
from ui_main import Ui_MainWindow
from gesture import HandTracker
from tray import SystemTray
import platform
import subprocess

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        
        # Set up main window properties
        self.setWindowTitle("AirCursor")
        icon_path = resource_path("assets/icon.png")
        self.setWindowIcon(QtGui.QIcon(icon_path))
        
        # Initialize hand tracker
        self.hand_tracker = HandTracker(
            click_radius=20,
            hover_radius=25,
            right_click_radius=50,
            right_hover_radius=60,
            hold_click_radius=30,
            hold_hover_radius=35,
            scroll_radius=25,
            scroll_hover_radius=30,
            scroll_speed=60
        )
        self.capture = None
        self.tracking_active = False
        self.show_camera = True
        
        # Setup system tray
        self.tray = SystemTray(self)
        self.tray.setIcon(QtGui.QIcon(icon_path))
        
        # Connect buttons to their respective functions
        self.startButton.clicked.connect(self.start_tracking)
        self.stopButton.clicked.connect(self.stop_tracking)
        self.showButton.clicked.connect(self.toggle_camera_display)
        self.minimizeButton.clicked.connect(self.minimize_to_tray)
        
        # Connect about menu actions
        self.actionAbout.triggered.connect(self.show_about_dialog)
        
        # Setup timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        
        # Disable stop button initially
        self.stopButton.setEnabled(False)
        
        # Set initial camera display
        self.clear_camera_display("Camera ready")

        # Camera selection setup
        self.available_cameras = self.detect_available_cameras()
        self.selected_camera_index = 0  # Default camera index
        
        # Connect camera selection button
        self.selectCameraButton.clicked.connect(self.select_camera)
        
        # Populate camera combo box
        self.populate_camera_combo()

    def detect_available_cameras(self):
        """
        Detect available cameras with descriptive names
        Returns list of tuples (index, name)
        """
        available = []
        os_name = platform.system()
        
        # Windows: Use DirectShow to get camera names
        if os_name == "Windows":
            try:
                from pygrabber.dshow_graph import FilterGraph
                graph = FilterGraph()
                devices = graph.get_input_devices()
                
                for index, name in enumerate(devices):
                    # Try to open the camera to verify it works
                    cap = cv2.VideoCapture(index)
                    if cap.isOpened():
                        available.append((index, name))
                        cap.release()
            except ImportError:
                # Fallback if pygrabber is not available
                print("pygrabber not installed, using basic camera detection")
                for i in range(10):
                    cap = cv2.VideoCapture(i)
                    if cap.isOpened():
                        available.append((i, f"Camera {i+1}"))
                        cap.release()
            except Exception as e:
                print(f"Error in Windows camera detection: {e}")
                for i in range(10):
                    cap = cv2.VideoCapture(i)
                    if cap.isOpened():
                        available.append((i, f"Camera {i+1}"))
                        cap.release()
        
        # Linux: Use v4l2-ctl to get camera names
        elif os_name == "Linux":
            try:
                result = subprocess.run(
                    ['v4l2-ctl', '--list-devices'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                if result.returncode == 0:
                    output = result.stdout
                    devices = output.strip().split('\n\n')
                    
                    for device_block in devices:
                        if not device_block:
                            continue
                            
                        lines = device_block.split('\n')
                        camera_name = lines[0].split('(')[0].strip()
                        
                        # Video device path is usually the second line
                        for line in lines[1:]:
                            if '/dev/video' in line:
                                dev_path = line.strip().split()[0]
                                index = int(dev_path.split('/dev/video')[-1])
                                
                                # Check if the camera can be opened
                                cap = cv2.VideoCapture(index)
                                if cap.isOpened():
                                    available.append((index, camera_name))
                                    cap.release()
                else:
                    # If v4l2-ctl command fails, fallback to basic detection
                    raise Exception("v4l2-ctl command failed")
            except Exception as e:
                print(f"Error in Linux camera detection: {e}")
                # Fallback to basic detection
                for i in range(10):
                    cap = cv2.VideoCapture(i)
                    if cap.isOpened():
                        available.append((i, f"Camera {i+1}"))
                        cap.release()
        
        # Fallback for other OS or if above methods fail
        if not available:
            for i in range(10):
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    available.append((i, f"Camera {i+1}"))
                    cap.release()
        
        return available

    def populate_camera_combo(self):
        """Populate the camera combo box with available cameras"""
        self.cameraComboBox.clear()
        
        if not self.available_cameras:
            self.cameraComboBox.addItem("No cameras detected", -1)
            self.selectCameraButton.setEnabled(False)
            return
        
        for idx, name in self.available_cameras:
            self.cameraComboBox.addItem(name, idx)
        
        # Set default selection to first available camera
        if self.available_cameras:
            self.cameraComboBox.setCurrentIndex(0)
            self.selected_camera_index = self.available_cameras[0][0]

    def select_camera(self):
        """Handle camera selection from combo box"""
        selected_data = self.cameraComboBox.currentData()
        
        if selected_data == -1:
            QtWidgets.QMessageBox.warning(
                self, "No Camera", "No cameras available for selection"
            )
            return
        
        self.selected_camera_index = selected_data
        self.statusbar.showMessage(f"Selected {self.cameraComboBox.currentText()}")

    def start_tracking(self):
        """Start the hand tracking process"""
        if not self.tracking_active:
             # Disable camera selection if tracking is active
            self.cameraComboBox.setEnabled(False)
            self.selectCameraButton.setEnabled(False)

            # Use the selected camera
            self.capture = cv2.VideoCapture(self.selected_camera_index)
            if not self.capture.isOpened():
                # Enable camera selection if camera cannot be opened
                self.cameraComboBox.setEnabled(True)
                self.selectCameraButton.setEnabled(True)

                QtWidgets.QMessageBox.critical(
                    self, "Error",
                    "Could not open camera. Please check your camera connection.")
                return
            
            self.clear_camera_display()
            
            self.tracking_active = True
            self.timer.start(10)
            self.startButton.setEnabled(False)
            self.stopButton.setEnabled(True)
            self.statusbar.showMessage("Active tracking...")

    def stop_tracking(self):
        """Stop the hand tracking process"""
        if self.tracking_active:
            self.timer.stop()
            self.tracking_active = False
            if self.capture:
                self.capture.release()
            self.capture = None
            self.startButton.setEnabled(True)
            self.stopButton.setEnabled(False)
            self.statusbar.showMessage("Tracking stopped.")
            self.clear_camera_display("Camera stopped.")

            # Re-enable camera selection
            self.cameraComboBox.setEnabled(True)
            self.selectCameraButton.setEnabled(True)

        # Set initial button text for showButton
        self.update_show_button_text()
    
    def update_show_button_text(self):
        """Update the show button text based on current state"""
        if self.show_camera:
            self.showButton.setText("Hide Camera")
        else:
            self.showButton.setText("Show Camera")

    def toggle_camera_display(self):
        """Toggle the visibility of the camera feed"""
        self.show_camera = not self.show_camera
        if not self.show_camera:
            if self.tracking_active:
                self.clear_camera_display("Camera feed hidden")
            else:
                self.clear_camera_display("Camera feed hidden")
        elif not self.tracking_active:
            self.clear_camera_display("Camera ready")

        self.update_show_button_text()

    def minimize_to_tray(self):
        """Minimize the application to the system tray"""
        self.hide()
        self.tray.show()
        icon_path = resource_path("assets/icon.png")
        self.tray.showMessage(
            "AirCursor",
            "Alea-AirCursor is minimized to the tray.",
            QtGui.QIcon(icon_path),  # Perbarui ini
            2000
        )

    def clear_camera_display(self, message=""):
        """Clear the camera feed display and set a message"""
        self.cameraFeedLabel.clear()
        if message:
            self.cameraFeedLabel.setText(message)
            self.cameraFeedLabel.setAlignment(QtCore.Qt.AlignCenter)
            font = self.cameraFeedLabel.font()
            font.setPointSize(14)
            self.cameraFeedLabel.setFont(font)

    def update_frame(self):
        """Update the camera feed with the processed frame"""
        if not self.capture or not self.capture.isOpened():
            return
            
        ret, frame = self.capture.read()
        if ret:
            processed_frame = self.hand_tracker.process_frame(frame)
            
            if self.show_camera:
                rgb_image = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w
                qt_image = QtGui.QImage(
                    rgb_image.data, w, h, bytes_per_line, 
                    QtGui.QImage.Format_RGB888
                )
                pixmap = QtGui.QPixmap.fromImage(qt_image)
                self.cameraFeedLabel.setPixmap(
                    pixmap.scaled(
                        self.cameraFeedLabel.width(),
                        self.cameraFeedLabel.height(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                )

    def show_about_dialog(self):
        """Show the about dialog with application information"""
        about_text = """
        <center>
            <h3>Alea-AirCursor v1.0.3</h3>
            <hr>
            <p>Experience the future of touchless interaction</p>
            <p>Transform your hand gestures to control your computer.</p>
            <p>Designed for intuitive control and seamless navigation.</p>
            <hr>
            <p><i>Innovation at your fingertips</i></p>
        </center>
        """
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setWindowTitle("About")
        msg_box.setTextFormat(QtCore.Qt.RichText)
        msg_box.setText(about_text)
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg_box.exec_()

    def closeEvent(self, event):
        """Handler for the close event to stop tracking and hide the tray icon"""
        self.stop_tracking()
        self.hand_tracker.release()
        self.tray.hide()
        event.accept()

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())