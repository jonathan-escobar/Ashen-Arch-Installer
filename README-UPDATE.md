# Ashen Arch Installer — v0.4 Wi-Fi GUI patch

This patch applies on top of the existing `main` branch of `jonathan-escobar/Ashen-Arch-Installer`.

## Changes

- Network panel now scans actual Wi-Fi adapters and available SSIDs via NetworkManager.
- Supports open networks and WPA2-PSK/WPA3-SAE password entry in the PySide6 GUI.
- Wi-Fi credential is not passed on the command line, written into repository files, or printed in logs; activation uses a pipe-backed `nmcli connection up ... passwd-file`.
- Connection and scan run off the UI thread. Ethernet continues via NetworkManager.
- No disk installation actions; this remains a Live Preview ISO.
- Unsupported advanced Wi-Fi auth such as enterprise 802.1X and WEP is reported instead of guessed.

## Apply to a clone

Extract the ZIP contents over the repository root, preserving the `overlay/` and `tests/` directory structure. Do not commit the `README-UPDATE.md` unless you want a separate release note.

```bash
python tests/test_network_backend.py
python tests/test_safety.py
bash scripts/prepare-profile.sh
sudo rm -rf build/work
sudo bash scripts/build-iso.sh
```

**Test caveat:** VirtualBox NAT is Ethernet. Actual Wi-Fi enumeration requires a compatible USB Wi-Fi adapter passed through to the VM or a physical test machine. Do not test a new ISO on production hardware without first validating it in VirtualBox. The ISO requires Internet at build time; it is not a complete offline Arch installer.
