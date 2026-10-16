"""Native Wi-Fi selection panel for the Ashen installer."""
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton,
    QComboBox, QListWidget, QListWidgetItem, QLineEdit, QHBoxLayout,
    QCheckBox)
import network_backend as nm


class Task(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, function, *args):
        super().__init__()
        self.function = function
        self.args = args

    def run(self):
        try:
            self.completed.emit(self.function(*self.args))
        except Exception as exc:
            self.failed.emit(str(exc))


class WifiPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.task = None
        self.aps = []
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Wi-Fi connections'))
        self.status = QLabel('Checking wireless adapters…')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        line = QHBoxLayout()
        self.adapters = QComboBox()
        self.enable = QPushButton('Enable Wi-Fi')
        self.refresh = QPushButton('Scan networks')
        line.addWidget(self.adapters)
        line.addWidget(self.enable)
        line.addWidget(self.refresh)
        layout.addLayout(line)
        self.list = QListWidget()
        layout.addWidget(self.list)
        self.password = QLineEdit()
        self.password.setPlaceholderText('Wi-Fi password — protected networks only')
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password)
        self.show_pass = QCheckBox('Show password')
        layout.addWidget(self.show_pass)
        self.join = QPushButton('Connect to selected network')
        layout.addWidget(self.join)
        self.refresh.clicked.connect(self.scan)
        self.enable.clicked.connect(self.enable_wifi)
        self.join.clicked.connect(self.connect)
        self.show_pass.toggled.connect(lambda yes: self.password.setEchoMode(
            QLineEdit.EchoMode.Normal if yes else QLineEdit.EchoMode.Password))
        self.list.currentRowChanged.connect(self.selection_changed)
        self.load_devices()

    def busy(self, active):
        for widget in (self.adapters, self.enable, self.refresh, self.join):
            widget.setEnabled(not active)

    def start(self, function, on_success, *args):
        if self.task is not None and self.task.isRunning():
            return
        self.busy(True)
        task = Task(function, *args)
        self.task = task
        task.completed.connect(on_success)
        task.failed.connect(lambda error: self.status.setText('Error: ' + error))
        task.finished.connect(lambda: self.busy(False))
        task.start()

    def load_devices(self):
        self.start(nm.wifi_devices, self.devices_loaded)

    def devices_loaded(self, devices):
        self.adapters.clear()
        self.adapters.addItems(devices)
        if not devices:
            self.status.setText('No Wi-Fi adapter detected. VirtualBox NAT exposes Ethernet. On a real PC, supported wireless hardware will appear here.')
            self.list.clear()
            return
        self.status.setText('Wireless adapter found. Scanning networks…')
        # Task has emitted completed but may still be finishing; launch shortly through finished event.
        self.task.finished.connect(self.scan)

    def enable_wifi(self):
        self.status.setText('Enabling Wi-Fi…')
        self.start(nm.enable_wifi, lambda _: self.scan())

    def scan(self):
        device = self.adapters.currentText()
        if not device:
            self.status.setText('No wireless adapter available')
            return
        self.status.setText('Scanning…')
        self.start(nm.scan, self.scan_finished, device)

    def scan_finished(self, access_points):
        self.aps = access_points
        self.list.clear()
        for ap in access_points:
            prefix = '✓ ' if ap.in_use else ''
            label = f'{prefix}{ap.ssid}   ·   {ap.signal}%   ·   {ap.security or "Open"}'
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, ap)
            self.list.addItem(item)
        self.status.setText(f'{len(access_points)} networks detected' if access_points else 'No networks found. Try Enable Wi-Fi and Scan networks.')

    def selection_changed(self, _row):
        item = self.list.currentItem()
        ap = item.data(Qt.ItemDataRole.UserRole) if item else None
        self.password.setEnabled(bool(ap and ap.protected))
        self.password.clear()

    def connect(self):
        item = self.list.currentItem()
        if item is None:
            self.status.setText('Select a network first')
            return
        ap = item.data(Qt.ItemDataRole.UserRole)
        password = self.password.text() if ap.protected else ''
        self.password.clear()
        self.status.setText(f'Connecting to {ap.ssid}…')
        self.start(nm.connect, self.connected, ap, password)

    def connected(self, _):
        self.status.setText('Wi-Fi connected. Checking Internet access…')
        self.task.finished.connect(lambda: self.start(nm.internet_check, self.checked))

    def checked(self, online):
        self.status.setText('Connected — Internet reachable' if online else 'Connected to Wi-Fi, but Internet was not verified. Check DNS or captive portal.')
