from PyQt5 import QtWidgets, QtGui

class SystemTray(QtWidgets.QSystemTrayIcon):
    def __init__(self, parent=None, icon_path=None):
        super().__init__(parent)
        self.parent = parent
        
        # Set up the system tray icon
        if icon_path:
            self.setIcon(QtGui.QIcon(icon_path))

        # Setup menu
        self.menu = QtWidgets.QMenu()
        
        # Action for restore
        self.restore_action = QtWidgets.QAction("Restore")
        self.restore_action.triggered.connect(self.restore_app)
        self.menu.addAction(self.restore_action)
        
        # Action for exit
        self.exit_action = QtWidgets.QAction("Exit")
        self.exit_action.triggered.connect(self.exit_app)
        self.menu.addAction(self.exit_action)
        
        self.setContextMenu(self.menu)
        self.activated.connect(self.on_tray_activated)

    def on_tray_activated(self, reason):
        if reason == self.Trigger:
            self.restore_app()

    def restore_app(self):
        self.parent.show()
        self.parent.activateWindow()

    def exit_app(self):
        self.parent.close()