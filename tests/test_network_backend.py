import importlib.util
from pathlib import Path
from unittest.mock import patch

P = Path(__file__).resolve().parents[1] / 'overlay/opt/ashen-installer/network_backend.py'
spec = importlib.util.spec_from_file_location('network_backend', P)
mod = importlib.util.module_from_spec(spec)
import sys
sys.modules['network_backend'] = mod
spec.loader.exec_module(mod)


def test_terse_parser():
    assert mod.split_terse(r'*:Cafe\:Wifi:88:WPA2') == ['*', 'Cafe:Wifi', '88', 'WPA2']
    assert mod.split_terse(r':My\\Net:70:--') == ['', 'My\\Net', '70', '--']


def test_scan_and_no_wifi():
    with patch.object(mod, 'wifi_devices', return_value=['wlan0']), patch.object(mod, 'run', side_effect=['', '*:Home:92:WPA2\n:Guest:60:--']):
        aps = mod.scan('wlan0')
        assert aps[0].ssid == 'Home' and aps[0].in_use
        assert aps[1].protected is False
    with patch.object(mod, 'wifi_devices', return_value=[]):
        try:
            mod.scan('wlan0')
            assert False
        except mod.NetworkError:
            pass


def test_password_never_in_argv():
    class Result:
        returncode = 0
        stdout = 'success'
        stderr = ''
    with patch('subprocess.run', return_value=Result()) as runner:
        mod._activate_with_secret('00000000-0000-0000-0000-000000000001', 'TopSecretPassword123', 'wlan0')
        assert 'TopSecretPassword123' not in repr(runner.call_args)

if __name__ == '__main__':
    test_terse_parser()
    test_scan_and_no_wifi()
    test_password_never_in_argv()
    print('Network tests passed')
