from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable


CREATE_NO_WINDOW = 0x08000000


class BluetoothFixRunner:
    def __init__(self, script_path: Path, log_path: Path) -> None:
        self.script_path = script_path
        self.log_path = log_path

    def execute(self, on_output: Callable[[str], None]) -> int:
        if not self.script_path.exists():
            raise FileNotFoundError(str(self.script_path))

        command = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(self.script_path),
            "-LogPath",
            str(self.log_path),
        ]

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=CREATE_NO_WINDOW,
        )

        assert process.stdout is not None

        for line in process.stdout:
            clean_line = line.rstrip()
            if clean_line:
                on_output(clean_line)

        return process.wait()
