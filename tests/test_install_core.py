"""Pure unit tests; must NEVER make destructive system calls."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'overlay/opt/ashen-installer/install_core.py'
spec = importlib.util.spec_from_file_location('install_core', MODULE)
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)


def disk(path='/dev/vda', serial='ABC', size=32 * 1024**3, mounted=False):
    return {'type': 'disk', 'path': path, 'size': size, 'model': 'Virtual disk',
            'serial': serial, 'rm': False, 'ro': False, 'mountpoints': [],
            'children': [{'type': 'part', 'path': path + '1',
                          'mountpoints': ['/boot'] if mounted else []}]}


def plan(**changes):
    base = dict(disk='/dev/vda', size=32 * 1024**3, serial='ABC',
                hostname='ashen-arch', username='person', locale='es_MX.UTF-8',
                timezone='UTC', desktop='minimal', password='TopSecret123!',
                confirmation='BORRAR /dev/vda')
    base.update(changes)
    return core.Plan(**base)


class DiskSafety(unittest.TestCase):
    def test_mounted_disk_never_available(self):
        self.assertFalse(core.available_disks([disk(mounted=True)], ''))

    def test_ntfs_or_encrypted_disks_never_available(self):
        for filesystem in ('ntfs', 'BitLocker', 'crypto_LUKS', 'linux_raid_member'):
            d = disk()
            d['children'][0]['fstype'] = filesystem
            self.assertFalse(core.available_disks([d], ''), filesystem)

    def test_live_boot_disk_never_available(self):
        self.assertFalse(core.available_disks([disk()], '/dev/vda1'))

    def test_readonly_removable_and_small(self):
        for change in ({'ro': True}, {'size': 12 * 1024**3}):
            d = disk(); d.update(change)
            self.assertFalse(core.available_disks([d], ''))
        d = disk(); d['rm'] = True
        self.assertFalse(core.available_disks([d], ''))
        d = disk(); d['tran'] = 'usb'
        self.assertFalse(core.available_disks([d], ''))

    def test_disk_serial_and_size_must_match(self):
        disks = core.available_disks([disk()], '')
        self.assertRaises(core.InstallError, plan(serial='different').validate, disks)
        self.assertRaises(core.InstallError, plan(size=100).validate, disks)
        self.assertEqual(plan().validate(disks)['serial'], 'ABC')

    def test_fields_validation(self):
        disks = core.available_disks([disk()], '')
        for p in (plan(username='root'), plan(username='space name'),
                  plan(hostname='bad host'), plan(locale='ar_EG.UTF-8'),
                  plan(timezone='../etc/passwd'), plan(password='short'),
                  plan(desktop='surprise'), plan(disk='/dev/../../etc/passwd')):
            with self.subTest(p=p):
                self.assertRaises(core.InstallError, p.validate, disks)

    def test_extra_json_keys_are_rejected(self):
        data = dict(plan().__dict__)
        data['command'] = 'rm -rf /'
        self.assertRaises(core.InstallError, core.Plan.from_dict, data)

    def test_partition_names_sdx_and_nvme(self):
        def pretend(argv):
            if 'nvme' in argv[-1]:
                return '/dev/nvme0n1\n/dev/nvme0n1p1 1\n/dev/nvme0n1p2 2\n'
            return '/dev/sda\n/dev/sda1 1\n/dev/sda2 2\n'
        self.assertEqual(core.partition_paths('/dev/nvme0n1', pretend),
                         ('/dev/nvme0n1p1', '/dev/nvme0n1p2'))
        self.assertEqual(core.partition_paths('/dev/sda', pretend), ('/dev/sda1', '/dev/sda2'))

    def test_no_execute_on_check(self):
        with patch.object(core, 'available_disks', return_value=core.available_disks([disk()], '')), \
             patch.object(core, '_live_source', return_value=''), \
             patch.object(core.Path, 'is_dir', return_value=True):
            self.assertEqual(core.preflight(plan(), root=False)['path'], '/dev/vda')


if __name__ == '__main__':
    unittest.main()
