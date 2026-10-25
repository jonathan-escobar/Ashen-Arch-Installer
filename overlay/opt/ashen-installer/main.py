"""Ashen Arch graphical installer. Disk writes only via validated root helper."""
import json
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, Qt
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QTextEdit, QStackedWidget, QComboBox,
    QFormLayout, QLineEdit, QMessageBox)

import install_core as engine
from wifi_panel import WifiPanel


class Installer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Ashen Arch Installer — v0.5')
        self.resize(1024, 760)
        self.proc = None
        self.disks = []
        host = QWidget()
        self.setCentralWidget(host)
        outer = QVBoxLayout(host)
        header = QLabel('ASHEN ARCH INSTALLER')
        header.setObjectName('heading')
        outer.addWidget(header)
        warning = QLabel('Instalación REAL: el disco seleccionado se borrará completamente. '
                         'NO selecciones un disco que contenga Windows u otros datos. '
                         'Solo UEFI, disco dedicado y conexión a Internet.')
        warning.setWordWrap(True)
        warning.setObjectName('warning')
        outer.addWidget(warning)
        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)
        self.pages = []
        for name in ('Bienvenida', 'Red', 'Disco de destino', 'Cuenta y sistema', 'Confirmación'):
            page = QWidget()
            layout = QVBoxLayout(page)
            title = QLabel(name)
            title.setObjectName('title')
            layout.addWidget(title)
            self.stack.addWidget(page)
            self.pages.append(layout)

        self.pages[0].addWidget(QLabel('Instala Arch Linux con partición EFI (1 GiB), raíz ext4 y systemd-boot.'))
        self.pages[0].addWidget(QLabel('Se instala el Arch disponible en los repositorios al momento de ejecutar pacstrap.'))
        self.pages[0].addWidget(QLabel('Windows solo se conserva si está en OTRO disco que no selecciones.'))
        self.pages[0].addStretch()
        self.wifi = WifiPanel()
        self.pages[1].addWidget(self.wifi)
        self.network_info = QLabel('Conecta Ethernet o Wi-Fi antes de continuar.')
        self.pages[1].addWidget(self.network_info)
        refresh_n = QPushButton('Verificar conexión')
        refresh_n.clicked.connect(self.network_status)
        self.pages[1].addWidget(refresh_n)

        self.disk_choice = QComboBox()
        self.pages[2].addWidget(QLabel('Solo se muestran discos de al menos 16 GiB que no están montados.'))
        self.pages[2].addWidget(self.disk_choice)
        self.disk_details = QTextEdit()
        self.disk_details.setReadOnly(True)
        self.pages[2].addWidget(self.disk_details)
        self.disk_choice.currentIndexChanged.connect(self.disk_detail)
        refresh = QPushButton('Actualizar discos')
        refresh.clicked.connect(self.load_disks)
        self.pages[2].addWidget(refresh)

        self.hostname = QLineEdit('ashen-arch')
        self.username = QLineEdit('ashenuser')
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password2 = QLineEdit()
        self.password2.setEchoMode(QLineEdit.EchoMode.Password)
        self.locale = QComboBox()
        self.locale.addItems(['es_MX.UTF-8', 'en_US.UTF-8'])
        self.timezone = QComboBox()
        self.timezone.setEditable(True)
        self.timezone.addItems(['America/Mexico_City', 'America/Monterrey', 'America/Tijuana', 'UTC'])
        self.desktop = QComboBox()
        self.desktop.addItem('Minimal (terminal)', 'minimal')
        self.desktop.addItem('KDE Plasma (escritorio)', 'plasma')
        form = QFormLayout()
        for label, widget in (('Hostname', self.hostname), ('Usuario', self.username),
                              ('Contraseña (min 8 caracteres)', self.password),
                              ('Repetir contraseña', self.password2),
                              ('Idioma', self.locale), ('Zona horaria', self.timezone),
                              ('Entorno', self.desktop)):
            form.addRow(label, widget)
        self.pages[3].addLayout(form)
        self.pages[3].addWidget(QLabel('La cuenta root quedará bloqueada; tu usuario podrá usar sudo.'))
        self.pages[3].addStretch()

        self.summary = QTextEdit()
        self.summary.setReadOnly(True)
        self.pages[4].addWidget(self.summary)
        self.confirm = QLineEdit()
        self.confirm.setPlaceholderText('Escribe BORRAR /dev/… exactamente como aparece arriba')
        self.pages[4].addWidget(self.confirm)
        self.start_install = QPushButton('INSTALAR Y BORRAR EL DISCO SELECCIONADO')
        self.start_install.clicked.connect(self.install)
        self.pages[4].addWidget(self.start_install)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.pages[4].addWidget(self.log)

        nav = QHBoxLayout()
        self.previous = QPushButton('← Atrás')
        self.next = QPushButton('Siguiente →')
        self.previous.clicked.connect(lambda: self.change(-1))
        self.next.clicked.connect(lambda: self.change(1))
        nav.addWidget(self.previous)
        nav.addWidget(self.next)
        outer.addLayout(nav)
        self.setStyleSheet('''QWidget{background:#101722;color:#e9f0f6;font:15px Sans;}
          QLabel#heading{color:#2dd4bf;font-weight:bold;font-size:25px;padding:12px;}
          QLabel#title{font-size:20px;font-weight:bold;padding:8px 0;}
          QLabel#warning{color:#ffd19e;background:#382719;padding:12px;}
          QPushButton,QComboBox,QLineEdit{background:#253448;padding:9px;border:1px solid #42546c;border-radius:5px;}
          QTextEdit,QListWidget{background:#172233;border:1px solid #42546c;padding:8px;}
          QPushButton:disabled{color:#7e8799;}''')
        self.load_disks()
        self.change(0)

    def load_disks(self):
        self.disk_choice.clear()
        try:
            self.disks = engine.available_disks()
            for disk in self.disks:
                size = disk['size'] / 1024**3
                self.disk_choice.addItem(f"{disk['path']} — {size:.1f} GiB — {disk['model']}")
        except Exception as exc:
            self.disks = []
            self.disk_details.setPlainText(f'No se pudieron listar discos: {exc}')
        self.disk_detail()

    def disk_detail(self, *_):
        i = self.disk_choice.currentIndex()
        if 0 <= i < len(self.disks):
            disk = self.disks[i]
            self.disk_details.setPlainText(json.dumps(disk, indent=2, ensure_ascii=False) +
                '\n\nATENCIÓN: SE DESTRUIRÁN TODAS LAS PARTICIONES Y LOS DATOS DE ESTE DISCO.')
        else:
            self.disk_details.setPlainText('No hay discos válidos. No se puede instalar.')

    def network_status(self):
        import network_backend as nm
        try:
            output = subprocess.run(['nmcli', 'device', 'status'], capture_output=True,
                                    text=True, timeout=8, check=False).stdout
            self.network_info.setText(output + ('\nInternet alcanzable' if nm.internet_check() else '\nSin acceso comprobado a Internet'))
        except (OSError, subprocess.TimeoutExpired):
            self.network_info.setText('NetworkManager no responde')

    def make_plan(self):
        index = self.disk_choice.currentIndex()
        if index < 0 or index >= len(self.disks):
            raise engine.InstallError('Selecciona un disco disponible')
        if self.password.text() != self.password2.text():
            raise engine.InstallError('Las contraseñas no coinciden')
        disk = self.disks[index]
        return engine.Plan(disk=disk['path'], size=disk['size'], serial=disk['serial'],
                           hostname=self.hostname.text().strip(), username=self.username.text().strip(),
                           password=self.password.text(), locale=self.locale.currentText(),
                           timezone=self.timezone.currentText().strip(),
                           desktop=self.desktop.currentData(), confirmation=self.confirm.text().strip())

    def preview(self):
        try:
            plan = self.make_plan()
            plan.validate(engine.available_disks())
            self.summary.setPlainText(
                f'DISCO A BORRAR: {plan.disk}\nIdentificador: {plan.serial or "sin serial"}\n'
                f'Tamaño: {plan.size / 1024**3:.1f} GiB\n\n'
                'Operaciones: crear GPT, EFI FAT32 de 1 GiB, raíz ext4 (resto del disco), '\
                'descargar Arch con pacstrap, habilitar NetworkManager, configurar systemd-boot.\n\n'
                f'Host: {plan.hostname}\nUsuario: {plan.username}\n'
                f'Locale: {plan.locale}\nZona: {plan.timezone}\nEntorno: {plan.desktop}\n\n'
                f'Para instalar escribe: BORRAR {plan.disk}\n\n'
                'NO HAY DESHACER. Haz backup antes de instalar.')
            return True
        except Exception as exc:
            QMessageBox.warning(self, 'Plan inválido', str(exc))
            return False

    def change(self, delta):
        next_index = max(0, min(self.stack.count() - 1, self.stack.currentIndex() + delta))
        if next_index == 4 and delta > 0 and not self.preview():
            return
        self.stack.setCurrentIndex(next_index)
        self.previous.setEnabled(next_index > 0)
        self.next.setEnabled(next_index < 4)

    def install(self):
        try:
            plan = self.make_plan()
            plan.validate(engine.available_disks())
            if self.confirm.text().strip() != f'BORRAR {plan.disk}':
                raise engine.InstallError(f'Debes escribir BORRAR {plan.disk} exactamente')
        except Exception as exc:
            QMessageBox.warning(self, 'Instalación bloqueada', str(exc))
            return
        answer = QMessageBox.warning(self, 'ÚLTIMA CONFIRMACIÓN',
            f'Se BORRARÁN todos los datos en {plan.disk}. ¿Continuar con la instalación real?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        if self.proc and self.proc.state() != QProcess.ProcessState.NotRunning:
            return
        self.start_install.setEnabled(False)
        self.previous.setEnabled(False)
        self.next.setEnabled(False)
        self.log.clear()
        self.log.append('Solicitando instalación privilegiada…')
        self.proc = QProcess(self)
        self.proc.setProgram('/usr/bin/sudo')
        self.proc.setArguments(['-n', '/usr/local/bin/ashen-install', '--execute'])
        self.proc.readyReadStandardOutput.connect(self.read_output)
        self.proc.readyReadStandardError.connect(self.read_error)
        self.proc.finished.connect(self.completed)
        self.proc.errorOccurred.connect(lambda err: self.log.append(f'No se pudo iniciar el instalador: {err}'))
        self.proc.start()
        if not self.proc.waitForStarted(5000):
            self.log.append('ERROR: el servicio privilegiado no inició.')
            self.start_install.setEnabled(True)
            return
        self.proc.write(json.dumps(plan.__dict__).encode('utf-8'))
        self.proc.closeWriteChannel()
        self.password.clear()
        self.password2.clear()

    def read_output(self):
        for line in bytes(self.proc.readAllStandardOutput()).decode('utf-8', 'replace').splitlines():
            try:
                obj = json.loads(line)
                self.log.append(obj.get('step') or ('ERROR: ' + obj['error'] if 'error' in obj else line))
            except (ValueError, KeyError):
                self.log.append(line)

    def read_error(self):
        # Sanitized output from the helper, not from arbitrary executed commands.
        content = bytes(self.proc.readAllStandardError()).decode('utf-8', 'replace')
        if content.strip():
            self.log.append('ERROR del ejecutor: ' + content[:300])

    def completed(self, exit_code, _status):
        if exit_code == 0:
            self.log.append('LISTO: sistema instalado. Retira el medio Live y reinicia.')
            QMessageBox.information(self, 'Ashen instalado', 'Instalación terminada. Retira la ISO antes del siguiente arranque.')
        else:
            self.log.append('INSTALACIÓN FALLIDA: no reinicies sin revisar el sistema. Consulta la consola.')
            self.start_install.setEnabled(True)
        self.previous.setEnabled(True)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    screen = Installer()
    screen.show()
    sys.exit(app.exec())
