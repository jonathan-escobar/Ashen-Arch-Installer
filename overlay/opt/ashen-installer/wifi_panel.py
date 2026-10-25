"""Live Wi-Fi GUI; tasks execute off the UI thread."""
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QComboBox,
                                QListWidget, QListWidgetItem, QLineEdit, QHBoxLayout)
import network_backend as nm


class Job(QThread):
    success = Signal(object)
    error = Signal(str)

    def __init__(self, function, *args):
        super().__init__()
        self.function = function
        self.args = args

    def run(self):
        try:
            self.success.emit(self.function(*self.args))
        except Exception as exc:
            self.error.emit(str(exc))


class WifiPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.job = None
        self.access_points = []
        layout = QVBoxLayout(self)
        self.status = QLabel('Buscando adaptadores Wi-Fi…')
        layout.addWidget(self.status)
        row = QHBoxLayout()
        self.adapters = QComboBox()
        self.scan_button = QPushButton('Buscar redes')
        self.enable_button = QPushButton('Activar Wi-Fi')
        for item in (self.adapters, self.scan_button, self.enable_button):
            row.addWidget(item)
        layout.addLayout(row)
        self.networks = QListWidget()
        layout.addWidget(self.networks)
        self.password = QLineEdit()
        self.password.setPlaceholderText('Contraseña de la red')
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password)
        self.join = QPushButton('Conectar')
        layout.addWidget(self.join)
        self.scan_button.clicked.connect(self.scan)
        self.enable_button.clicked.connect(lambda: self.start(nm.enable_wifi, lambda _: self.scan()))
        self.join.clicked.connect(self.connect)
        self.networks.currentRowChanged.connect(self.selection_changed)
        self.start(nm.wifi_devices, self.loaded)

    def start(self, fun, callback, *args):
        if self.job and self.job.isRunning():
            return
        self.job = Job(fun, *args)
        for widget in (self.adapters, self.scan_button, self.enable_button, self.join):
            widget.setEnabled(False)
        self.job.success.connect(callback)
        self.job.error.connect(lambda error: self.status.setText('Error: ' + error))
        self.job.finished.connect(self.finished)
        self.job.start()

    def finished(self):
        for widget in (self.adapters, self.scan_button, self.enable_button, self.join):
            widget.setEnabled(True)

    def loaded(self, devices):
        self.adapters.addItems(devices)
        if devices:
            self.status.setText('Adaptador detectado. Selecciona Buscar redes.')
        else:
            self.status.setText('No se encontró Wi-Fi. VirtualBox NAT aparece como Ethernet; USB passthrough para Wi-Fi real.')

    def scan(self):
        device = self.adapters.currentText()
        if device:
            self.status.setText('Buscando redes…')
            # Release completed worker before starting the new worker.
            if self.job and self.job.isRunning():
                self.job.finished.connect(lambda: self.start(nm.scan, self.scanned, device))
            else:
                self.start(nm.scan, self.scanned, device)

    def scanned(self, aps):
        self.access_points = aps
        self.networks.clear()
        for ap in aps:
            item = QListWidgetItem(f'{"✓ " if ap.in_use else ""}{ap.ssid} · {ap.signal}% · {ap.security}')
            item.setData(Qt.ItemDataRole.UserRole, ap)
            self.networks.addItem(item)
        self.status.setText(f'{len(aps)} redes disponibles')

    def selection_changed(self, _):
        self.password.clear()
        item = self.networks.currentItem()
        ap = item.data(Qt.ItemDataRole.UserRole) if item else None
        self.password.setEnabled(bool(ap and ap.protected))

    def connect(self):
        item = self.networks.currentItem()
        if not item:
            self.status.setText('Selecciona una red')
            return
        ap = item.data(Qt.ItemDataRole.UserRole)
        password = self.password.text() if ap.protected else ''
        self.password.clear()
        self.status.setText('Conectando…')
        self.start(nm.connect, lambda _: self.status.setText('Conexión establecida'), ap, password)
