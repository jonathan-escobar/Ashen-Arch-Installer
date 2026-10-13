# Ashen Arch Installer — v0.3 Live Preview

ISO Live basada en Arch Linux para **demostrar** un instalador gráfico seguro. **No instala Arch, no formatea, no modifica GRUB/UEFI ni escribe particiones.**

## Construir desde Arch Linux (no Windows)

```bash
sudo pacman -Syu --needed archiso git
unzip ashen-arch-installer-v0.3.zip # si recibiste el ZIP; también puedes clonar el repo
cd ashen-arch-installer-v0.3
bash scripts/prepare-profile.sh
sudo bash scripts/build-iso.sh
```

ISO resultante en `out/`. Se requiere Internet durante la construcción para obtener paquetes. Recomendamos 35 GiB libres, 4 GiB RAM y UEFI en VirtualBox.

## Qué probar

- Arranque gráfico con Openbox y PySide6 en usuario Live `ashen` (sin sudo).
- Pantallas de bienvenida, conectividad, discos/EFI, preferencias y resumen.
- Diagnóstico con `lsblk` y `efibootmgr` (lectura); redes vía `nmcli` en lectura.
- Abrir configuración de red con `nmtui` en terminal, sin enviar contraseñas a la app.
- Exportar plan **solo a memoria del proceso** (no genera acciones de instalación).

## Limitaciones

- **Solo DEMO**. Detección Windows heurística (NTFS / EFI != prueba de Windows).
- VirtualBox NAT presenta Ethernet virtual; para probar Wi-Fi hay que pasar un adaptador USB compatible a la VM.
- La VM de construcción y la VM de prueba deben ser distintas; usar snapshots.
- No verificada aún en una ISO arrancada real. Si falla el arranque gráfico, entrar por otra TTY y revisar `journalctl -u ashen-live-user` y `journalctl -b`.
- Releng contiene sus propias configuraciones; el script prepara una copia fresca y configura NetworkManager para evitar dos gestores de red.

## Repo GitHub

```bash
git init
git add .
git commit -m "feat: add Ashen Arch graphical live ISO preview"
git branch -M develop
git remote add origin https://github.com/TU_USUARIO/TU_REPO.git
git push -u origin develop
```

Si ya existe el repo, haz primero un `git clone` y copia ahí los archivos. **No uses `git init` ni `remote add` dentro de un clon existente.**

## Seguridad

El modo gráfico no contiene llamadas de escritura a dispositivos, `mkfs`, `parted`, `cryptsetup`, `pacstrap`, GRUB ni `efibootmgr` de modificación. El script de construcción se ejecuta como root solo dentro del entorno Builder para fabricar la ISO.
