from pathlib import Path
p=Path(__file__).resolve().parents[1]/'overlay/opt/ashen-installer/main.py'
s=p.read_text()
for forbidden in ('mkfs.', 'pacstrap ', 'grub-install', 'cryptsetup luksFormat', 'parted -s'):
    assert forbidden not in s, forbidden
assert "'efibootmgr','-v'" in s
print('Static read-only checks passed')
