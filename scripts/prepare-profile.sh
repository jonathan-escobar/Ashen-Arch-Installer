#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="$ROOT/build/profile"
[[ -d /usr/share/archiso/configs/releng ]] || { echo 'Install archiso: sudo pacman -S archiso' >&2; exit 1; }
rm -rf -- "$PROFILE"
mkdir -p -- "$ROOT/build"
cp -a /usr/share/archiso/configs/releng "$PROFILE"
python - "$PROFILE/profiledef.sh" <<'PY'
from pathlib import Path
import re
import sys
p=Path(sys.argv[1]); s=p.read_text()
for key, value in {'iso_name':'ashenarch', 'iso_publisher':'Ashen Arch Project',
                   'iso_application':'Ashen Arch Installer v0.5'}.items():
    s, n = re.subn('^' + key + '=.*$', key + '="' + value + '"', s, flags=re.M)
    if n != 1:
        raise SystemExit('Missing/duplicate ' + key + ' in archiso profiledef.sh')
needle='file_permissions=('
if needle not in s:
    raise SystemExit('profiledef.sh is missing file_permissions array')
permissions = {
    '/usr/local/bin/ashen-create-user': '0:0:755',
    '/usr/local/bin/ashen-install': '0:0:755',
    '/etc/sudoers.d/ashen-installer': '0:0:440',
    '/etc/skel/.xinitrc': '0:0:755',
}
addition='\n' + ''.join(f'  ["{name}"]="{mode}"\n' for name, mode in permissions.items())
s=s.replace(needle, needle+addition, 1)
p.write_text(s)
PY
for pkg in networkmanager python pyside6 xorg-server xorg-xinit xorg-xauth \
           xterm openbox mesa efibootmgr parted dosfstools e2fsprogs \
           arch-install-scripts sudo polkit; do
    grep -Fxq "$pkg" "$PROFILE/packages.x86_64" || echo "$pkg" >> "$PROFILE/packages.x86_64"
done
cp -a "$ROOT/overlay/." "$PROFILE/airootfs/"
# releng enables systemd-networkd and iwd; disable both on this COPY of releng.
for service in iwd.service systemd-networkd.service systemd-networkd-wait-online.service; do
    rm -f "$PROFILE/airootfs/etc/systemd/system/multi-user.target.wants/$service" \
          "$PROFILE/airootfs/etc/systemd/system/network-online.target.wants/$service"
done
mkdir -p "$PROFILE/airootfs/etc/systemd/system/multi-user.target.wants" \
         "$PROFILE/airootfs/etc/systemd/system/getty@tty1.service.d"
ln -sfn /usr/lib/systemd/system/NetworkManager.service \
    "$PROFILE/airootfs/etc/systemd/system/multi-user.target.wants/NetworkManager.service"
ln -sfn /etc/systemd/system/ashen-live-user.service \
    "$PROFILE/airootfs/etc/systemd/system/multi-user.target.wants/ashen-live-user.service"
cat > "$PROFILE/airootfs/etc/systemd/system/getty@tty1.service.d/autologin.conf" <<'EOF'
[Service]
ExecStart=
ExecStart=-/usr/bin/agetty --autologin ashen --noclear %I $TERM
EOF
printf 'Ashen archiso profile ready: %s\n' "$PROFILE"
