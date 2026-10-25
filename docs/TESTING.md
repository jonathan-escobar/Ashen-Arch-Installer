# Pruebas de integración pendientes (v0.5)

Ninguna de estas pruebas se debe hacer en discos físicos de producción.

## 1. Validación estática (puede hacerse en cualquier Linux con Python (no requiere Arch))

```bash
python -m compileall -q overlay tests
python -m unittest discover -s tests -p 'test_*.py' -v
bash -n scripts/*.sh overlay/usr/local/bin/ashen-create-user
```

## 2. Build en Arch Linux

1. `sudo pacman -Syu --needed archiso git`.
2. `bash scripts/prepare-profile.sh`.
3. Comprobar disponibilidad de paquetes del perfil con
   `comm -23 <(sort -u build/profile/packages.x86_64) <(pacman -Slq | sort -u)`;
   resultado vacío esperado. (La lista de repositorios debe haberse actualizado).
4. `sudo bash scripts/build-iso.sh`.
5. Confirmar `out/ashenarch-*.iso` y que el sistema arranca en UEFI.

## 3. Prueba segura en VM

- Firmware EFI, Secure Boot apagado, 4 GiB RAM, 2 CPU, NAT, disco vacío de 32 GiB.
- Validar GUI Live y detección Ethernet.
- Validar que el disco del medio Live y cualquier disco montado no aparezcan como destino.
- Confirmar que un error de validación o la cancelación no modifica particiones.
- Seleccionar `/dev/vda`, confirmar con `BORRAR /dev/vda`, instalar mínimo.
- Apagar, retirar ISO, verificar arranque systemd-boot, login, `sudo`, DHCP e idioma.
- Repetir la prueba con el disco de VM **NVMe** (`/dev/nvme0n1`) y KDE Plasma.
- Confirmar que `bootctl` crea una entrada en firmware y carga el sistema instalado.
- Repetir el arranque con y sin red durante la instalación (sin red debe fallar explícitamente).
- Interrumpir `pacstrap` en VM y confirmar que el instalador notifica fallo; no presumir rollback.

## 4. Criterios de salida antes de usar hardware real

- ISO compilada correctamente con Arch actualizado.
- Al menos una instalación real en VM UEFI con cada modo (minimal y KDE).
- Test de disco equivocado y confirmación negativa.
- Test del primer arranque y reconexión de red.
- Test de errores y recuperación desde el LiveISO.
- Actualización de la documentación con evidencia de resultados.

**Sin la ejecución de estos escenarios la release permanece EXPERIMENTAL.**
