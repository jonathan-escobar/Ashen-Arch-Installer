"""NetworkManager Wi-Fi connection without exposing PSKs in process args."""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass


class NetworkError(Exception):
    pass


@dataclass(frozen=True)
class AccessPoint:
    ssid: str
    signal: int
    security: str
    device: str
    in_use: bool = False

    @property
    def protected(self):
        return bool(self.security and self.security != '--')


def run(*args, timeout=30):
    try:
        result = subprocess.run(['nmcli', *args], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        raise NetworkError('NetworkManager is not available or timed out')
    if result.returncode:
        raise NetworkError((result.stderr or result.stdout or 'nmcli failed').strip()[:200])
    return result.stdout.strip()


def split_terse(line):
    result, part, escaped = [], [], False
    for c in line:
        if escaped:
            part.append(c)
            escaped = False
        elif c == '\\':
            escaped = True
        elif c == ':':
            result.append(''.join(part))
            part = []
        else:
            part.append(c)
    result.append(''.join(part))
    return result


def wifi_devices():
    rows = run('-t', '-f', 'DEVICE,TYPE', 'device', 'status')
    return [cells[0] for line in rows.splitlines() if len(cells := split_terse(line)) >= 2 and cells[1] == 'wifi']


def enable_wifi():
    run('radio', 'wifi', 'on')


def scan(device):
    if device not in wifi_devices():
        raise NetworkError('Wi-Fi adapter disappeared')
    try:
        run('device', 'wifi', 'rescan', 'ifname', device)
    except NetworkError:
        pass
    rows = run('-t', '-f', 'IN-USE,SSID,SIGNAL,SECURITY', 'device', 'wifi', 'list',
               'ifname', device, '--rescan', 'no')
    aps = {}
    for row in rows.splitlines():
        fields = split_terse(row)
        if len(fields) != 4 or not fields[1]:
            continue
        try:
            signal = int(fields[2])
        except ValueError:
            continue
        ap = AccessPoint(fields[1], signal, fields[3], device, fields[0] == '*')
        if ap.ssid not in aps or ap.in_use or signal > aps[ap.ssid].signal:
            aps[ap.ssid] = ap
    return sorted(aps.values(), key=lambda x: (-x.in_use, -x.signal, x.ssid))


def internet_check():
    import socket
    try:
        with socket.create_connection(('archlinux.org', 443), timeout=5):
            return True
    except OSError:
        return False


def _activate_with_secret(uuid, password, device):
    """nmcli reads a PSK from an inherited anonymous pipe, not argv or a file."""
    read_fd, write_fd = os.pipe()
    try:
        data = ('802-11-wireless-security.psk:' + password + '\n').encode()
        os.write(write_fd, data)
        os.close(write_fd)
        write_fd = -1
        argv = ['nmcli', '--wait', '45', 'connection', 'up', 'uuid', uuid, 'ifname', device,
                'passwd-file', f'/proc/self/fd/{read_fd}']
        p = subprocess.run(argv, capture_output=True, text=True, pass_fds=(read_fd,), timeout=55)
        if p.returncode:
            raise NetworkError((p.stderr or 'Unable to connect').strip()[:200])
    finally:
        os.close(read_fd)
        if write_fd >= 0:
            os.close(write_fd)


def connect(ap, password=''):
    if ap.device not in wifi_devices():
        raise NetworkError('Adapter not available')
    if not ap.ssid or '\n' in ap.ssid:
        raise NetworkError('Invalid SSID')
    if not ap.protected:
        run('--wait', '45', 'device', 'wifi', 'connect', ap.ssid, 'ifname', ap.device, timeout=55)
        return
    sec = ap.security.upper()
    if any(mode in sec for mode in ('802.1X', 'WEP', 'OWE')):
        raise NetworkError('Enterprise/OWE/WEP not supported. Use nmtui.')
    if not 8 <= len(password) <= 63 or '\n' in password:
        raise NetworkError('WPA password must have 8 to 63 characters')
    key_mgmt = 'sae' if 'WPA3' in sec and 'WPA2' not in sec else 'wpa-psk'
    out = run('connection', 'add', 'type', 'wifi', 'ifname', ap.device,
              'con-name', f'Ashen Wi-Fi - {ap.ssid}', 'ssid', ap.ssid,
              'wifi-sec.key-mgmt', key_mgmt)
    match = re.search(r'\(([0-9a-fA-F-]{36})\)', out)
    if not match:
        raise NetworkError('Could not read connection UUID')
    uuid = match.group(1)
    try:
        _activate_with_secret(uuid, password, ap.device)
    except Exception:
        try:
            run('connection', 'delete', 'uuid', uuid)
        except NetworkError:
            pass
        raise
