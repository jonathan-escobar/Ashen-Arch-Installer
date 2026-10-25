if [[ -z "${DISPLAY:-}" && "$(tty 2>/dev/null)" == /dev/tty1 ]]; then
    exec startx /home/ashen/.xinitrc -- :0 vt1 -keeptty
fi
