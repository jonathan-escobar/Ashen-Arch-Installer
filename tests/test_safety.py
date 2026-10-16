from pathlib import Path
root = Path(__file__).resolve().parents[1]
installer = (root / 'overlay/opt/ashen-installer/main.py').read_text()
backend = (root / 'overlay/opt/ashen-installer/network_backend.py').read_text()
for command in ('mkfs.', 'pacstrap ', 'grub-install', 'cryptsetup luksFormat', 'parted -s'):
    assert command not in installer, command
    assert command not in backend, command
assert "read_cmd('efibootmgr', '-v')" in installer
assert 'pass_fds=' in backend
assert 'wifi-sec.key-mgmt' in backend
print('Static disk-safety checks passed')
