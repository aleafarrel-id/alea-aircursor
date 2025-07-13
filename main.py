import sys
import os
import cv2
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QTimer, Qt
from ui_main import Ui_MainWindow
from gesture import HandTracker
from tray import SystemTray

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

    def start_tracking(self):
        """Start the hand tracking process"""
        if not self.tracking_active:
            self.capture = cv2.VideoCapture(0)
            if not self.capture.isOpened():
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
            <h3>Alea-AirCursor v1.0.2</h3>
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