"""NetworkManager adapter for Ashen Live; no disk installation operations.

SSID/PSK never appear in shell strings. A PSK is sent to nmcli over an inherited pipe.
"""
from __future__ import annotations
import os
import re
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class AccessPoint:
    ssid: str
    signal: int
    security: str
    device: str
    in_use: bool = False

    @property
    def protected(self) -> bool:
        return bool(self.security and self.security != '--')


class NetworkError(RuntimeError):
    pass


def run(*args: str, timeout: int = 15) -> str:
    try:
        p = subprocess.run(['nmcli', *args], text=True, capture_output=True,
                           timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise NetworkError(f'NetworkManager unavailable: {e}') from e
    if p.returncode:
        raise NetworkError((p.stderr or p.stdout or 'NetworkManager error').strip()[:350])
    return p.stdout.strip()


def unescape_nmcli(value: str) -> str:
    """Undo escaping used by nmcli terse output."""
    chars = []; escaped = False
    for char in value:
        if escaped:
            chars.append(char); escaped = False
        elif char == '\\':
            escaped = True
        else:
            chars.append(char)
    if escaped:
        chars.append('\\')
    return ''.join(chars)


def split_terse(line: str) -> list[str]:
    values = []; current = []; escaped = False
    for char in line:
        if escaped:
            current.append(char); escaped = False
        elif char == '\\':
            escaped = True
        elif char == ':':
            values.append(''.join(current)); current = []
        else:
            current.append(char)
    values.append(''.join(current))
    return values


def wifi_devices() -> list[str]:
    rows = run('-t', '-f', 'DEVICE,TYPE', 'device', 'status')
    result = []
    for line in rows.splitlines():
        columns = split_terse(line)
        if len(columns) >= 2 and columns[1] == 'wifi':
            result.append(columns[0])
    return result


def wifi_enabled() -> bool:
    return run('radio', 'wifi').lower() == 'enabled'


def enable_wifi() -> None:
    run('radio', 'wifi', 'on')


def scan(device: str) -> list[AccessPoint]:
    if device not in wifi_devices():
        raise NetworkError('Wireless adapter not available')
    # A forced scan may be throttled; fall back to cached AP listing.
    try:
        run('device', 'wifi', 'rescan', 'ifname', device, timeout=15)
    except NetworkError:
        pass
    rows = run('-t', '-f', 'IN-USE,SSID,SIGNAL,SECURITY', 'device', 'wifi', 'list',
               'ifname', device, '--rescan', 'no', timeout=20)
    found = {}
    for line in rows.splitlines():
        parts = split_terse(line)
        if len(parts) != 4 or not parts[1]:
            continue
        try:
            strength = max(0, min(100, int(parts[2])))
        except ValueError:
            continue
        ap = AccessPoint(parts[1], strength, parts[3], device, parts[0] == '*')
        existing = found.get(ap.ssid)
        if existing is None or ap.signal > existing.signal or ap.in_use:
            found[ap.ssid] = ap
    return sorted(found.values(), key=lambda a: (-int(a.in_use), -a.signal, a.ssid.casefold()))


def connection_state() -> str:
    return run('-t', '-f', 'DEVICE,TYPE,STATE,CONNECTION', 'device', 'status')


def internet_check() -> bool:
    """Check DNS + TCP/HTTPS reachability without querying secrets."""
    import socket
    try:
        with socket.create_connection(('archlinux.org', 443), timeout=5):
            return True
    except OSError:
        return False


def _activate_with_secret(connection_uuid: str, password: str, device: str) -> None:
    """Use nmcli 'connection up passwd-file' with an in-memory pipe.

    The read fd is inherited by nmcli; password is absent from argv and files.
    """
    read_fd, write_fd = os.pipe()
    try:
        payload = ('802-11-wireless-security.psk:' + password + '\n').encode()
        os.write(write_fd, payload)
        os.close(write_fd); write_fd = -1
        cmd = ['nmcli', '--wait', '45', 'connection', 'up', 'uuid', connection_uuid,
               'ifname', device, 'passwd-file', f'/proc/self/fd/{read_fd}']
        proc = subprocess.run(cmd, pass_fds=(read_fd,), capture_output=True,
                              text=True, timeout=55, check=False)
        if proc.returncode:
            raise NetworkError((proc.stderr or proc.stdout or 'Wi-Fi connection failed').strip()[:350])
    finally:
        os.close(read_fd)
        if write_fd >= 0:
            os.close(write_fd)


def connect(ap: AccessPoint, password: str = '') -> None:
    if ap.device not in wifi_devices():
        raise NetworkError('The selected Wi-Fi adapter is no longer available')
    if not ap.ssid or '\n' in ap.ssid:
        raise NetworkError('Invalid network name')
    if ap.protected:
        security = ap.security.upper()
        if '802.1X' in security or 'WEP' in security or 'OWE' in security:
            raise NetworkError('This security mode is not supported yet. Use nmtui for advanced authentication.')
        if len(password) < 8 or len(password) > 63:
            raise NetworkError('WPA/WPA2 password must contain 8–63 characters')
        key_mgmt = 'sae' if 'WPA3' in security and 'WPA2' not in security else 'wpa-psk'
        name = f'Ashen WiFi — {ap.ssid}'
        # Add a profile without secrets; nmcli returns a UUID.
        output = run('connection', 'add', 'type', 'wifi',
                     'ifname', ap.device, 'con-name', name, 'ssid', ap.ssid,
                     'wifi-sec.key-mgmt', key_mgmt)
        match = re.search(r'\(([0-9a-fA-F-]{36})\)', output)
        if not match:
            raise NetworkError('Created Wi-Fi profile but could not identify its UUID')
        uuid = match.group(1)
        try:
            _activate_with_secret(uuid, password, ap.device)
        except Exception:
            try:
                run('connection', 'delete', 'uuid', uuid)
            except NetworkError:
                pass
            raise
    else:
        run('--wait', '45', 'device', 'wifi', 'connect', ap.ssid,
            'ifname', ap.device, timeout=55)
