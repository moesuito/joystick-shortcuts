"""Load and save AppConfig (with profiles) from %APPDATA%\\JoystickShortcuts\\config.json."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .models import AppConfig, Profile


def config_dir() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / "JoystickShortcuts"
    return Path.home() / ".joystick-shortcuts"


def config_path() -> Path:
    return config_dir() / "config.json"


def load_config() -> AppConfig:
    path = config_path()
    if not path.exists():
        cfg = AppConfig()
        cfg.profiles["Default"] = Profile(name="Default")
        save_config(cfg)
        return cfg
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return AppConfig.from_dict(data)
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        # Corrupted config: back it up and start fresh so the app still launches.
        backup = path.with_suffix(".bak")
        try:
            path.replace(backup)
        except OSError:
            pass
        print(f"[config] could not read {path} ({exc}); starting fresh.")
        cfg = AppConfig()
        cfg.profiles["Default"] = Profile(name="Default")
        save_config(cfg)
        return cfg


def save_config(cfg: AppConfig) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg.to_dict(), indent=2), encoding="utf-8")
    tmp.replace(path)
