# Automatically launch the Ashen GUI on the live ISO's tty1 only.
if [[ -z "${DISPLAY:-}" && "$(tty 2>/dev/null)" == /dev/tty1 ]]; then
    exec startx /home/ashen/.xinitrc -- :0 vt1 -keeptty
fi
