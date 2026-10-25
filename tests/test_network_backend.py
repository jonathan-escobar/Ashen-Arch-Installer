import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'overlay/opt/ashen-installer/network_backend.py'
spec = importlib.util.spec_from_file_location('network_backend', MODULE)
network = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = network
spec.loader.exec_module(network)


class NetworkTests(unittest.TestCase):
    def test_parse_escaped_colons(self):
        self.assertEqual(network.split_terse(r'*:Cafe\:Wifi:80:WPA2'),
                         ['*', 'Cafe:Wifi', '80', 'WPA2'])

    def test_scan(self):
        with patch.object(network, 'wifi_devices', return_value=['wlan0']), \
             patch.object(network, 'run', side_effect=['', '*:Home:90:WPA2\n:Guest:60:--']):
            aps = network.scan('wlan0')
        self.assertEqual(aps[0].ssid, 'Home')
        self.assertFalse(aps[1].protected)

    def test_no_password_on_command_line(self):
        class Result:
            returncode = 0
            stdout = 'ok'
            stderr = ''
        with patch.object(network.subprocess, 'run', return_value=Result()) as runner:
            network._activate_with_secret('00000000-0000-0000-0000-000000000001', 'HiddenP@ssw0rd', 'wlan0')
            self.assertNotIn('HiddenP@ssw0rd', str(runner.call_args))


if __name__ == '__main__':
    unittest.main()
