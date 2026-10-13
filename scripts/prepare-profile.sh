#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="$ROOT/build/profile"
if [[ ! -d /usr/share/archiso/configs/releng ]]; then echo 'Instala archiso (sudo pacman -S archiso)' >&2; exit 1; fi
rm -rf "$PROFILE"
mkdir -p "$ROOT/build"
cp -a /usr/share/archiso/configs/releng "$PROFILE"
python - "$PROFILE/profiledef.sh" <<'PY2'
import pathlib,sys,re
p=pathlib.Path(sys.argv[1]); s=p.read_text()
for key,value in {'iso_name':'ashenarch','iso_publisher':'Ashen Arch Project','iso_application':'Ashen Arch Live Preview'}.items():
    s,n=re.subn(r'^'+key+r'=.*$',key+'="'+value+'"',s,flags=re.M)
    if not n: raise SystemExit('Falta '+key+' en profiledef.sh')
p.write_text(s)
PY2
for pkg in networkmanager python pyside6 xorg-server xorg-xinit xorg-xauth xterm openbox mesa efibootmgr; do
  grep -Fxq "$pkg" "$PROFILE/packages.x86_64" || printf '%s\n' "$pkg" >> "$PROFILE/packages.x86_64"
done
cp -a "$ROOT/overlay/." "$PROFILE/airootfs/"
# releng usa networkd+iwd: inhabilitarlos en la copia del perfil, dejando sus herramientas instaladas.
for name in iwd.service systemd-networkd.service systemd-networkd-wait-online.service; do
  rm -f "$PROFILE/airootfs/etc/systemd/system/multi-user.target.wants/$name" \
        "$PROFILE/airootfs/etc/systemd/system/network-online.target.wants/$name"
done
mkdir -p "$PROFILE/airootfs/etc/systemd/system/multi-user.target.wants"
ln -sfn /usr/lib/systemd/system/NetworkManager.service "$PROFILE/airootfs/etc/systemd/system/multi-user.target.wants/NetworkManager.service"
ln -sfn /etc/systemd/system/ashen-live-user.service "$PROFILE/airootfs/etc/systemd/system/multi-user.target.wants/ashen-live-user.service"
mkdir -p "$PROFILE/airootfs/etc/systemd/system/getty@tty1.service.d"
cat > "$PROFILE/airootfs/etc/systemd/system/getty@tty1.service.d/autologin.conf" <<'EOF'
[Service]
ExecStart=
ExecStart=-/usr/bin/agetty --autologin ashen --noclear %I $TERM
EOF
chmod +x "$PROFILE/airootfs/usr/local/bin/ashen-create-user"
# archiso stores default files with explicit permissions in profiledef; allow executable initializer.
python - "$PROFILE/profiledef.sh" <<'PY2'
import pathlib,sys
p=pathlib.Path(sys.argv[1]);s=p.read_text()
needle='file_permissions=('; insert='  ["/usr/local/bin/ashen-create-user"]="0:0:755"\n'
if needle not in s: raise SystemExit('No file_permissions found')
s=s.replace(needle,needle+'\n'+insert,1);p.write_text(s)
PY2
printf 'Perfil preparado: %s\n' "$PROFILE"
