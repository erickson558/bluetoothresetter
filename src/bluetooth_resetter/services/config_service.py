from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from ..i18n.translations import SUPPORTED_LANGUAGES


@dataclass
class AppConfig:
    language: str = "es"
    auto_run: bool = False
    auto_close: bool = False
    auto_close_seconds: int = 60
    geometry: str = "1000x720+120+120"


class ConfigService:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.config = AppConfig()

    def load(self) -> AppConfig:
        if not self.path.exists():
            self.save()
            return self.config

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.save()
            return self.config

        self.config = AppConfig(
            language=self._normalize_language(data.get("language", self.config.language)),
            auto_run=bool(data.get("auto_run", self.config.auto_run)),
            auto_close=bool(data.get("auto_close", self.config.auto_close)),
            auto_close_seconds=self._normalize_seconds(data.get("auto_close_seconds", self.config.auto_close_seconds)),
            geometry=str(data.get("geometry", self.config.geometry)),
        )
        return self.config

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(asdict(self.config), ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self.path)

    def update(self, **kwargs: object) -> AppConfig:
        for key, value in kwargs.items():
            if not hasattr(self.config, key):
                continue

            if key == "language":
                value = self._normalize_language(value)
            elif key == "auto_close_seconds":
                value = self._normalize_seconds(value)
            elif key in {"auto_run", "auto_close"}:
                value = bool(value)
            elif key == "geometry":
                value = str(value)

            setattr(self.config, key, value)

        self.save()
        return self.config

    def _normalize_language(self, language: object) -> str:
        value = str(language or "es").lower()
        if value not in SUPPORTED_LANGUAGES:
            return "es"
        return value

    def _normalize_seconds(self, value: object) -> int:
        try:
            seconds = int(value)
        except (TypeError, ValueError):
            return 60
        return max(5, min(seconds, 3600))
