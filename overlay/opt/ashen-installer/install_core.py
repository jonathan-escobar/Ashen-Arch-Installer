"""Ashen Arch installation engine (UEFI, dedicated disk, ext4).

The executable is *intentionally destructive*. It is only launched by the
Live ISO's restricted sudo rule after a separate preview and typed consent.
No generic shell invocation is used; user strings never become shell code.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Callable

MIN_DISK_SIZE = 16 * 1024 ** 3
DISK_PATH_RE = re.compile(r"^/dev/[A-Za-z0-9_./-]+$")
USER_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
HOST_RE = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$")
SUPPORTED_LOCALES = {"en_US.UTF-8", "es_MX.UTF-8"}
SUPPORTED_DESKTOPS = {"minimal", "plasma"}
PACKAGES = ["base", "linux", "linux-firmware", "networkmanager", "sudo", "nano", "efibootmgr"]
PLASMA_PACKAGES = ["plasma-desktop", "plasma-nm", "plasma-pa", "sddm", "konsole", "dolphin", "mesa", "xorg-xwayland", "noto-fonts", "noto-fonts-emoji", "pipewire", "pipewire-pulse", "pipewire-alsa", "wireplumber"]


class InstallError(Exception):
    """A preflight or installation step failed."""


def command(argv: list[str], *, input_text: str | None = None, timeout: int = 1800) -> str:
    """Execute a command with arguments only (never through a shell)."""
    try:
        p = subprocess.run(argv, input=input_text, capture_output=True,
                           text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InstallError(f"Could not execute {argv[0]}: {type(exc).__name__}") from exc
    if p.returncode:
        # stderr from chpasswd or external commands may be sensitive; do NOT print it.
        raise InstallError(f"Command {Path(argv[0]).name} failed (exit {p.returncode}); see the live system journal")
    return p.stdout


def lsblk_tree() -> list[dict]:
    output = command(["lsblk", "--json", "--bytes", "--output",
                      "NAME,PATH,TYPE,SIZE,MODEL,SERIAL,RM,RO,TRAN,MOUNTPOINTS,FSTYPE"])
    return json.loads(output).get("blockdevices", [])


def _has_active_mount(node: dict) -> bool:
    if any(p for p in (node.get("mountpoints") or [])):
        return True
    return any(_has_active_mount(c) for c in node.get("children", []))


PROTECTED_FILESYSTEMS = {"ntfs", "ntfs3", "bitlocker", "crypto_luks", "linux_raid_member", "lvm2_member"}


def _has_protected_fs(node: dict) -> bool:
    if (node.get("fstype") or "").casefold() in PROTECTED_FILESYSTEMS:
        return True
    return any(_has_protected_fs(c) for c in node.get("children", []))


def _all_paths(node: dict) -> set[str]:
    return {node.get("path", "")} | set().union(*(_all_paths(c) for c in node.get("children", [])))


def _live_source() -> str:
    try:
        return command(["findmnt", "--noheadings", "--output", "SOURCE", "--mountpoint", "/run/archiso/bootmnt"]).strip().split("[")[0]
    except InstallError:
        return ""


def available_disks(tree: list[dict] | None = None, live_source: str | None = None) -> list[dict]:
    if tree is None:
        tree = lsblk_tree()
    if live_source is None:
        live_source = _live_source()
    result = []
    for node in tree:
        if node.get("type") != "disk" or not node.get("path"):
            continue
        if (node.get("ro") in (True, "1", 1)
                or int(node.get("size") or 0) < MIN_DISK_SIZE
                or bool(int(node.get("rm") or 0))
                or (node.get("tran") or "").lower() == "usb"):
            continue
        paths = _all_paths(node)
        if _has_active_mount(node) or _has_protected_fs(node) or (live_source and live_source in paths):
            continue
        result.append({"path": node["path"], "size": int(node["size"]),
                       "model": (node.get("model") or "Unknown").strip(),
                       "serial": (node.get("serial") or "").strip(),
                       "transport": node.get("tran") or "",
                       "removable": bool(int(node.get("rm") or 0))})
    return result


@dataclass(frozen=True)
class Plan:
    disk: str
    size: int
    serial: str
    hostname: str
    username: str
    locale: str
    timezone: str
    desktop: str
    # Passphrase is not stored in files or arguments and is never printed.
    password: str
    confirmation: str

    @classmethod
    def from_dict(cls, data: dict) -> "Plan":
        if set(data) != set(cls.__dataclass_fields__):
            raise InstallError("Plan fields are missing or unexpected")
        if type(data["size"]) is not int:
            raise InstallError("Invalid disk size")
        if not all(isinstance(v, str) for k, v in data.items() if k != "size"):
            raise InstallError("Plan contains invalid values")
        return cls(**data)

    def validate(self, disks: list[dict], *, check_password: bool = True) -> dict:
        if not DISK_PATH_RE.fullmatch(self.disk) or ".." in self.disk:
            raise InstallError("Invalid target disk")
        found = next((d for d in disks if d["path"] == self.disk), None)
        if not found:
            raise InstallError("Target disk is not available, is mounted, or is too small")
        if self.size != found["size"] or self.serial != found["serial"]:
            raise InstallError("Disk identity changed. Refresh the target selection")
        if found["removable"]:
            raise InstallError("Removable drives are not supported as installation targets")
        if not HOST_RE.fullmatch(self.hostname) or len(self.hostname) > 63:
            raise InstallError("Invalid hostname")
        if not USER_RE.fullmatch(self.username) or self.username in {"root", "ashen", "nobody"}:
            raise InstallError("Invalid username")
        if self.locale not in SUPPORTED_LOCALES:
            raise InstallError("Unsupported locale")
        if self.desktop not in SUPPORTED_DESKTOPS:
            raise InstallError("Unsupported desktop")
        if not re.fullmatch(r"[A-Za-z0-9_+./-]{1,100}", self.timezone) or ".." in self.timezone:
            raise InstallError("Invalid timezone")
        zone = (Path("/usr/share/zoneinfo") / self.timezone)
        if not zone.is_file() or not zone.resolve().is_relative_to(Path("/usr/share/zoneinfo").resolve()):
            raise InstallError("Timezone not found")
        if check_password and (len(self.password) < 8 or len(self.password) > 128 or any(c in self.password for c in "\r\n\0")):
            raise InstallError("User password must be 8–128 characters without control newlines")
        return found


def preflight(plan: Plan, *, root: bool = False) -> dict:
    if root and os.geteuid() != 0:
        raise InstallError("Installer must run as root")
    if not Path("/sys/firmware/efi/efivars").is_dir():
        raise InstallError("Boot this ISO in UEFI mode (Legacy BIOS is not supported)")
    if not Path("/run/archiso").is_dir():
        raise InstallError("Run only from the Ashen Arch live ISO")
    disk = plan.validate(available_disks())
    if root:
        st = os.stat(plan.disk)
        if not stat.S_ISBLK(st.st_mode):
            raise InstallError("Target is not a block device")
        # Guard against aliases and unexpected disk substitutions.
        if os.path.realpath(plan.disk) != plan.disk:
            raise InstallError("Use the canonical /dev disk path")
    return disk


def partition_paths(disk: str, runner: Callable = command) -> tuple[str, str]:
    """Resolve actual kernel partition names, including NVMe and MMC devices."""
    rows = runner(["lsblk", "-nrpo", "PATH,PARTN", disk]).splitlines()
    by_number = {}
    for row in rows:
        col = row.split()
        if len(col) == 2 and col[1].isdigit():
            by_number[int(col[1])] = col[0]
    if 1 not in by_number or 2 not in by_number:
        raise InstallError("Partitions did not appear after partitioning")
    return by_number[1], by_number[2]


def step(message: str) -> None:
    # Plain text status, never contain credentials.
    print(json.dumps({"step": message}, ensure_ascii=False), flush=True)


def install(plan: Plan, runner: Callable = command) -> None:
    """Destructive implementation: never call from preview/tests."""
    disk = preflight(plan, root=True)
    if plan.confirmation != f"BORRAR {plan.disk}":
        raise InstallError("Explicit erase confirmation is required")
    for name in ("parted", "wipefs", "partprobe", "mkfs.fat", "mkfs.ext4", "pacstrap", "arch-chroot", "genfstab", "bootctl"):
        if not any((Path(directory) / name).is_file() for directory in os.environ.get("PATH", "").split(":")):
            raise InstallError(f"Required live-ISO command missing: {name}")

    target = Path(tempfile.mkdtemp(prefix="ashen-target-", dir="/mnt"))
    mounted_root = mounted_esp = False
    try:
        # Recheck immediately before destroying any data.
        if plan.validate(available_disks()) != disk:
            raise InstallError("Disk changed during preparation")
        step("Borrando la tabla de particiones del disco elegido")
        runner(["wipefs", "--all", plan.disk])
        runner(["parted", "--script", "--align", "optimal", plan.disk,
                "mklabel", "gpt", "mkpart", "ESP", "fat32", "1MiB", "1025MiB",
                "set", "1", "esp", "on", "mkpart", "ASHEN_ROOT", "ext4", "1025MiB", "100%"])
        runner(["partprobe", plan.disk])
        runner(["udevadm", "settle"])
        esp, root = partition_paths(plan.disk, runner)
        step("Formateando EFI (FAT32) y raíz (ext4)")
        runner(["mkfs.fat", "-F", "32", "-n", "ASHEN_EFI", esp])
        runner(["mkfs.ext4", "-F", "-L", "ASHEN_ROOT", root])
        runner(["mount", root, str(target)])
        mounted_root = True
        (target / "boot").mkdir()
        runner(["mount", esp, str(target / "boot")])
        mounted_esp = True

        step("Descargando e instalando paquetes de Arch Linux (requiere Internet)")
        packages = list(PACKAGES)
        cpu = Path("/proc/cpuinfo").read_text(errors="replace")
        if "GenuineIntel" in cpu:
            packages.append("intel-ucode")
        elif "AuthenticAMD" in cpu:
            packages.append("amd-ucode")
        if plan.desktop == "plasma":
            packages.extend(PLASMA_PACKAGES)
        runner(["pacstrap", "-K", str(target), *packages], timeout=7200)

        step("Configurando sistema, idioma, cuenta y red")
        fstab = runner(["genfstab", "-U", str(target)])
        mountpoints = {fields[1] for line in fstab.splitlines()
                       if (fields := line.split()) and not line.startswith('#') and len(fields) >= 2}
        if not {'/', '/boot'} <= mountpoints:
            raise InstallError("Generated fstab is missing root or EFI entry")
        (target / "etc/fstab").write_text(fstab)
        (target / "etc/hostname").write_text(plan.hostname + "\n")
        (target / "etc/hosts").write_text(
            f"127.0.0.1 localhost\n::1 localhost\n127.0.1.1 {plan.hostname}.localdomain {plan.hostname}\n")
        (target / "etc/locale.conf").write_text(f"LANG={plan.locale}\n")
        (target / "etc/vconsole.conf").write_text("KEYMAP=us\n")
        locale_gen = target / "etc/locale.gen"
        lines = locale_gen.read_text().splitlines()
        target_code = plan.locale + " UTF-8"
        lines = [target_code if ln.lstrip("# ") == target_code else ln for ln in lines]
        locale_gen.write_text("\n".join(lines) + "\n")
        if target_code not in lines:
            raise InstallError("Requested locale not available in target")
        runner(["arch-chroot", str(target), "ln", "-sf", "/usr/share/zoneinfo/" + plan.timezone, "/etc/localtime"])
        runner(["arch-chroot", str(target), "locale-gen"])
        runner(["arch-chroot", str(target), "useradd", "-m", "-G", "wheel", "-s", "/bin/bash", plan.username])
        runner(["arch-chroot", str(target), "chpasswd"], input_text=f"{plan.username}:{plan.password}\n")
        runner(["arch-chroot", str(target), "passwd", "-l", "root"])
        sudoers = target / "etc/sudoers.d/10-ashen-wheel"
        sudoers.write_text("%wheel ALL=(ALL:ALL) ALL\n")
        sudoers.chmod(0o440)
        runner(["arch-chroot", str(target), "systemctl", "enable", "NetworkManager"])
        if plan.desktop == "plasma":
            runner(["arch-chroot", str(target), "systemctl", "enable", "sddm"])
        runner(["arch-chroot", str(target), "mkinitcpio", "-P"])

        step("Instalando systemd-boot en la EFI del disco elegido")
        root_uuid = runner(["blkid", "-s", "UUID", "-o", "value", root]).strip()
        if not re.fullmatch(r"[0-9a-fA-F-]{16,40}", root_uuid):
            raise InstallError("Cannot determine root UUID")
        (target / "boot/loader/entries").mkdir(parents=True, exist_ok=True)
        (target / "boot/loader/loader.conf").write_text("default ashen.conf\ntimeout 4\neditor no\n")
        (target / "boot/loader/entries/ashen.conf").write_text(
            f"title Ashen Arch Linux\nlinux /vmlinuz-linux\ninitrd /initramfs-linux.img\noptions root=UUID={root_uuid} rw\n")
        runner(["bootctl", "--esp-path=" + str(target / "boot"), "install"])
        step("Instalación completada. Apaga, retira la ISO y arranca desde el disco instalado")
    finally:
        if mounted_esp:
            try:
                runner(["umount", str(target / "boot")])
            except InstallError:
                step("Aviso: no se pudo desmontar EFI; revisa el montaje manualmente")
        if mounted_root:
            try:
                runner(["umount", str(target)])
            except InstallError:
                step("Aviso: no se pudo desmontar la raíz; revisa el montaje manualmente")
        try:
            target.rmdir()
        except OSError:
            pass
