"""Ashen Arch Live v0.3: read-only diagnostic and UI prototype."""
import json
import subprocess
import sys
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,
    QPushButton,QTextEdit,QStackedWidget,QComboBox,QLineEdit,QFormLayout,QMessageBox)


def read_cmd(*cmd):
    try:
        p=subprocess.run(cmd, capture_output=True, text=True, timeout=12, check=False)
        return p.stdout.strip() if p.returncode == 0 else f"Unavailable ({p.returncode}): {p.stderr.strip()[:200]}"
    except (OSError,subprocess.TimeoutExpired) as e:
        return f"Unavailable: {e}"


class Installer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Ashen Arch Installer — LIVE DEMO v0.3')
        self.resize(1024,720)
        self.plan={'mode':'Separate disk from Windows', 'encryption':'LUKS optional', 'boot':'Keep existing UEFI boot order'}
        host=QWidget(); self.setCentralWidget(host); outer=QVBoxLayout(host)
        heading=QLabel('ASHEN ARCH INSTALLER    ·    LIVE PREVIEW'); heading.setObjectName('heading');outer.addWidget(heading)
        banner=QLabel('DEMO MODE — read-only disk inspection. NO installation or formatting.');banner.setObjectName('banner');outer.addWidget(banner)
        self.tabs=QStackedWidget();outer.addWidget(self.tabs)
        self.views=[]
        for name in ('Welcome','Network','Disks & EFI','Preferences','Boot','Summary'):
            page=QWidget(); layout=QVBoxLayout(page); title=QLabel(name);title.setObjectName('title');layout.addWidget(title)
            self.tabs.addWidget(page);self.views.append(layout)
        self.views[0].addWidget(QLabel('This preview lets you explore configuration before installing Arch.'))
        self.views[0].addWidget(QLabel('Windows volumes are never mounted or modified by this demo.'))
        self.network=QTextEdit();self.network.setReadOnly(True);self.views[1].addWidget(self.network)
        self.make_button(self.views[1],'Refresh network diagnostics',self.refresh_network)
        self.make_button(self.views[1],'Open NetworkManager TUI (nmtui)',self.open_nmtui)
        self.disk=QTextEdit();self.disk.setReadOnly(True);self.views[2].addWidget(self.disk)
        self.make_button(self.views[2],'Refresh disk diagnostics',self.refresh_disks)
        self.mode=QComboBox();self.mode.addItems(['Separate disk from Windows','Exclusive empty disk','Alongside Windows (free space only)'])
        self.encryption=QComboBox();self.encryption.addItems(['LUKS root + home','LUKS root only','No encryption'])
        form=QFormLayout();form.addRow('Installation scenario (preview)',self.mode);form.addRow('Encryption preference',self.encryption)
        self.views[3].addLayout(form)
        self.views[3].addWidget(QLabel('The preview does not identify a safe target disk or allocate space.'))
        self.boot=QComboBox();self.boot.addItems(['Preserve current UEFI boot order','GRUB on dedicated Arch EFI (planned)'])
        self.views[4].addWidget(self.boot)
        self.views[4].addWidget(QLabel('Windows EFI and Windows Boot Manager remain untouched.'))
        self.summary=QTextEdit();self.summary.setReadOnly(True);self.views[5].addWidget(self.summary)
        self.make_button(self.views[5],'Refresh preview summary',self.refresh_summary)
        nav=QHBoxLayout();outer.addLayout(nav)
        self.prev=QPushButton('← Back');self.next=QPushButton('Next →')
        self.prev.clicked.connect(lambda:self.change(-1));self.next.clicked.connect(lambda:self.change(1))
        nav.addWidget(self.prev);nav.addWidget(self.next)
        self.setStyleSheet("""QWidget {background:#101722;color:#e9f0f6;font:15px Sans;}
        QLabel#heading {font-weight:bold;color:#2dd4bf;font-size:24px;padding:12px;}
        QLabel#title {font-size:20px;font-weight:bold;margin:12px 0;}
        QLabel#banner {color:#fbbf24;padding:9px;border:1px solid #b7791f;}
        QPushButton,QComboBox {background:#253448;padding:12px;border:1px solid #42546c;border-radius:5px;}
        QTextEdit {background:#172233;border:1px solid #42546c;padding:10px;}""")
        self.refresh_network();self.refresh_disks();self.change(0)
    def make_button(self,layout,label,callback):
        b=QPushButton(label);b.clicked.connect(callback);layout.addWidget(b)
    def refresh_network(self):
        self.network.setPlainText('NETWORK DEVICES\n'+read_cmd('nmcli','device','status')+'\n\nWIFI NETWORKS\n'+read_cmd('nmcli','-f','IN-USE,SSID,SIGNAL,SECURITY','device','wifi','list')+'\n\nNOTE: VirtualBox NAT usually shows Ethernet, not Wi-Fi.')
    def open_nmtui(self):
        # NetworkManager CLI configuration in a dedicated user-owned terminal. No privileged disk operations.
        try:subprocess.Popen(['xterm','-e','nmtui'])
        except OSError as e:QMessageBox.warning(self,'Network manager',str(e))
    def refresh_disks(self):
        self.disk.setPlainText('BLOCK DEVICES (READ ONLY)\n'+read_cmd('lsblk','-o','NAME,SIZE,TYPE,FSTYPE,LABEL,MOUNTPOINTS,MODEL')+'\n\nUEFI ENTRIES (READ ONLY)\n'+read_cmd('efibootmgr','-v')+'\n\nNTFS alone does not prove Windows is installed.')
    def refresh_summary(self):
        self.summary.setPlainText(json.dumps({'status':'DEMO — no installation actions', 'scenario':self.mode.currentText(), 'encryption':self.encryption.currentText(), 'boot':self.boot.currentText(), 'disk_operations':[], 'efi_writes':[]},indent=2))
    def change(self, delta):
        self.tabs.setCurrentIndex(max(0,min(self.tabs.count()-1,self.tabs.currentIndex()+delta)))
        self.prev.setEnabled(self.tabs.currentIndex()!=0)
        self.next.setEnabled(self.tabs.currentIndex()!=self.tabs.count()-1)
        if self.tabs.currentIndex()==5:self.refresh_summary()

if __name__=='__main__':
    app=QApplication(sys.argv); ui=Installer();ui.show();sys.exit(app.exec())
