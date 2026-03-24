from __future__ import annotations

import sys
from pathlib import Path


ICON_NAME = "tools_bluetooth_serial_utility_13004.ico"


def get_bundle_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[3]


def get_app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return get_bundle_root()


def get_icon_path() -> Path:
    return get_bundle_root() / ICON_NAME


def get_powershell_script_path() -> Path:
    return get_bundle_root() / "scripts" / "Fix-AudioBluetooth.ps1"


def get_config_path() -> Path:
    return get_app_root() / "config.json"


def get_log_path() -> Path:
    return get_app_root() / "log.txt"
