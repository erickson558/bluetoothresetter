from __future__ import annotations

import ctypes
import subprocess
import sys
from pathlib import Path

from .ui.main_window import BluetoothResetterApp


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> bool:
    if getattr(sys, "frozen", False):
        executable = sys.executable
        arguments = subprocess.list2cmdline([*sys.argv[1:], "--elevated"])
    else:
        executable = sys.executable
        script_path = str(Path(sys.argv[0]).resolve())
        arguments = subprocess.list2cmdline([script_path, *sys.argv[1:], "--elevated"])

    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, arguments, None, 1)
    return result > 32


def main() -> None:
    elevated_flag = "--elevated" in sys.argv[1:]
    has_admin = is_admin()

    if not has_admin and not elevated_flag:
        if relaunch_as_admin():
            return

    app = BluetoothResetterApp(is_elevated=is_admin())
    app.run()
