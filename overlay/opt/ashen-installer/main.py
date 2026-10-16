"""Ashen Arch Installer v0.4 — Live preview, no disk writes."""
import json
import subprocess
import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QTextEdit, QStackedWidget, QComboBox,
    QFormLayout)
from wifi_panel import WifiPanel


def read_cmd(*cmd):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=12, check=False)
        return p.stdout.strip() if p.returncode == 0 else f'Unavailable: {p.stderr.strip()[:200]}'
    except (OSError, subprocess.TimeoutExpired) as error:
        return f'Unavailable: {error}'


class Installer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Ashen Arch Installer — LIVE DEMO v0.4')
        self.resize(1024, 740)
        host = QWidget()
        self.setCentralWidget(host)
        outer = QVBoxLayout(host)
        heading = QLabel('ASHEN ARCH INSTALLER   ·   LIVE PREVIEW')
        heading.setObjectName('heading')
        outer.addWidget(heading)
        banner = QLabel('DEMO MODE — disks read-only. Wi-Fi configuration is REAL; no Arch installation or formatting.')
        banner.setWordWrap(True)
        banner.setObjectName('banner')
        outer.addWidget(banner)
        self.tabs = QStackedWidget()
        outer.addWidget(self.tabs)
        self.views = []
        for name in ('Welcome', 'Network', 'Disks & EFI', 'Preferences', 'Boot', 'Summary'):
            page = QWidget()
            layout = QVBoxLayout(page)
            title = QLabel(name)
            title.setObjectName('title')
            layout.addWidget(title)
            self.tabs.addWidget(page)
            self.views.append(layout)
        self.views[0].addWidget(QLabel('Explore Arch Linux installation configuration without changing disks.'))
        self.views[0].addWidget(QLabel('NetworkManager supports real Ethernet and Wi-Fi configuration in this preview.'))
        self.views[0].addStretch()

        self.network = QTextEdit()
        self.network.setReadOnly(True)
        self.network.setMaximumHeight(120)
        self.views[1].addWidget(QLabel('Current network interfaces'))
        self.views[1].addWidget(self.network)
        self.wifi = WifiPanel()
        self.views[1].addWidget(self.wifi)
        self.make_button(self.views[1], 'Refresh network status', self.refresh_network)

        self.disk = QTextEdit()
        self.disk.setReadOnly(True)
        self.views[2].addWidget(self.disk)
        self.make_button(self.views[2], 'Refresh disk diagnostics', self.refresh_disks)

        self.mode = QComboBox()
        self.mode.addItems(['Separate disk from Windows', 'Exclusive empty disk',
                            'Alongside Windows (free space only)'])
        self.encryption = QComboBox()
        self.encryption.addItems(['LUKS root + home', 'LUKS root only', 'No encryption'])
        form = QFormLayout()
        form.addRow('Installation scenario (preview)', self.mode)
        form.addRow('Encryption preference', self.encryption)
        self.views[3].addLayout(form)
        self.views[3].addWidget(QLabel('No partitions are changed or created in this preview.'))
        self.views[3].addStretch()

        self.boot = QComboBox()
        self.boot.addItems(['Preserve current UEFI boot order', 'GRUB on dedicated Arch EFI (planned)'])
        self.views[4].addWidget(self.boot)
        self.views[4].addWidget(QLabel('Windows partitions and Windows Boot Manager are never modified.'))
        self.views[4].addStretch()

        self.summary = QTextEdit()
        self.summary.setReadOnly(True)
        self.views[5].addWidget(self.summary)
        self.make_button(self.views[5], 'Refresh preview summary', self.refresh_summary)

        nav = QHBoxLayout()
        outer.addLayout(nav)
        self.prev = QPushButton('← Back')
        self.next = QPushButton('Next →')
        self.prev.clicked.connect(lambda: self.change(-1))
        self.next.clicked.connect(lambda: self.change(1))
        nav.addWidget(self.prev)
        nav.addWidget(self.next)
        self.setStyleSheet('''QWidget {background:#101722;color:#e9f0f6;font:15px Sans;}
        QLabel#heading {font-weight:bold;color:#2dd4bf;font-size:24px;padding:12px;}
        QLabel#title {font-size:20px;font-weight:bold;margin:12px 0;}
        QLabel#banner {color:#fbbf24;padding:9px;border:1px solid #b7791f;}
        QPushButton,QComboBox,QLineEdit {background:#253448;padding:9px;border:1px solid #42546c;border-radius:5px;}
        QPushButton:disabled {color:#9ba8bb;}
        QTextEdit,QListWidget {background:#172233;border:1px solid #42546c;padding:8px;}
        QListWidget::item:selected {background:#167e81;}
        ''')
        self.refresh_network()
        self.refresh_disks()
        self.change(0)

    def make_button(self, layout, label, callback):
        b = QPushButton(label)
        b.clicked.connect(callback)
        layout.addWidget(b)

    def refresh_network(self):
        self.network.setPlainText(read_cmd('nmcli', 'device', 'status'))

    def refresh_disks(self):
        self.disk.setPlainText('BLOCK DEVICES (READ ONLY)\n' +
            read_cmd('lsblk', '-o', 'NAME,SIZE,TYPE,FSTYPE,LABEL,MOUNTPOINTS,MODEL') +
            '\n\nUEFI ENTRIES (READ ONLY)\n' + read_cmd('efibootmgr', '-v') +
            '\n\nNTFS is not conclusive proof of Windows.')

    def refresh_summary(self):
        self.summary.setPlainText(json.dumps({
            'status': 'DEMO — Wi-Fi configuration allowed; disk installation disabled',
            'scenario': self.mode.currentText(),
            'encryption': self.encryption.currentText(),
            'boot': self.boot.currentText(),
            'disk_operations': [], 'efi_writes': [],
        }, indent=2))

    def change(self, delta):
        self.tabs.setCurrentIndex(max(0, min(self.tabs.count()-1, self.tabs.currentIndex()+delta)))
        self.prev.setEnabled(self.tabs.currentIndex() != 0)
        self.next.setEnabled(self.tabs.currentIndex() != self.tabs.count()-1)
        if self.tabs.currentIndex() == 1:
            self.refresh_network()
        if self.tabs.currentIndex() == 5:
            self.refresh_summary()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ui = Installer()
    ui.show()
    sys.exit(app.exec())
