"""Executor + dispatcher for bindings (key, combo, media, launch)."""
from __future__ import annotations

import os
import shlex
import subprocess
import webbrowser
from typing import Callable

from PySide6.QtCore import QObject, QTimer, Slot

from .models import Action, AppConfig


MEDIA_MAP = {
    "volume_up": "volume up",
    "volume_down": "volume down",
    "mute": "volume mute",
    "play_pause": "play/pause media",
    "next": "next track",
    "prev": "previous track",
}

MEDIA_LABELS = {
    "volume_up": "Volume up",
    "volume_down": "Volume down",
    "mute": "Mute",
    "play_pause": "Play / Pause",
    "next": "Next track",
    "prev": "Previous track",
}


def _send(combo: str) -> None:
    """Send a key combination via the keyboard library."""
    import keyboard  # imported lazily so import errors are visible only when triggered

    keyboard.send(combo)


def execute_action(action: Action) -> None:
    t = action.type
    p = action.payload or {}
    try:
        if t == "key":
            key = (p.get("key") or "").strip()
            if key:
                _send(key)
        elif t == "key_combo":
            keys = [k for k in (p.get("keys") or []) if k]
            if keys:
                _send("+".join(keys))
        elif t == "media":
            cmd = p.get("command")
            mapping = MEDIA_MAP.get(cmd)
            if mapping:
                _send(mapping)
        elif t == "launch":
            target = (p.get("target") or "").strip()
            if not target:
                return
            args = p.get("args") or ""
            if target.startswith(("http://", "https://", "mailto:")):
                webbrowser.open(target)
            elif os.path.isfile(target):
                cmd_args = shlex.split(args) if args else []
                subprocess.Popen([target, *cmd_args], close_fds=True)
            else:
                # Could be an installed app key like "calc" or a folder path.
                try:
                    os.startfile(target)  # type: ignore[attr-defined]
                except OSError as exc:
                    print(f"[action] launch failed for '{target}': {exc}")
    except Exception as exc:
        print(f"[action] {type(exc).__name__}: {exc}")


def describe_action(action: Action) -> str:
    p = action.payload or {}
    if action.type == "key":
        return p.get("key", "—") or "—"
    if action.type == "key_combo":
        keys = p.get("keys") or []
        return " + ".join(k.upper() for k in keys) if keys else "—"
    if action.type == "media":
        return MEDIA_LABELS.get(p.get("command", ""), p.get("command", "—"))
    if action.type == "launch":
        target = p.get("target", "—") or "—"
        args = p.get("args")
        return f"{target} {args}".strip() if args else target
    return "—"


class Dispatcher(QObject):
    """Routes pressed/released events from the poller to the active profile's bindings."""

    def __init__(self, config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self._config = config
        self._hold_timers: dict[str, QTimer] = {}
        self._executor: Callable[[Action], None] = execute_action

    def set_config(self, config: AppConfig) -> None:
        self._config = config
        self.cancel_all_holds()

    def set_executor(self, fn: Callable[[Action], None]) -> None:
        """Override action execution (used by the binding dialog to capture buttons silently)."""
        self._executor = fn

    def reset_executor(self) -> None:
        self._executor = execute_action

    def cancel_all_holds(self) -> None:
        for t in self._hold_timers.values():
            t.stop()
        self._hold_timers.clear()

    @Slot(str)
    def on_pressed(self, button: str) -> None:
        if self._config.paused:
            return
        for b in self._config.active().bindings:
            if b.button != button:
                continue
            if b.trigger == "press":
                self._executor(b.action)
            elif b.trigger == "hold":
                key = f"{button}:{b.id}"
                timer = QTimer(self)
                timer.setSingleShot(True)
                timer.setInterval(max(50, int(b.hold_ms)))
                action = b.action
                timer.timeout.connect(lambda a=action, k=key: self._fire_hold(k, a))
                self._hold_timers[key] = timer
                timer.start()

    @Slot(str)
    def on_released(self, button: str) -> None:
        # Cancel any pending hold timers for this button regardless of paused state.
        for key in list(self._hold_timers):
            if key.startswith(f"{button}:"):
                self._hold_timers[key].stop()
                del self._hold_timers[key]
        if self._config.paused:
            return
        for b in self._config.active().bindings:
            if b.button == button and b.trigger == "release":
                self._executor(b.action)

    def _fire_hold(self, key: str, action: Action) -> None:
        self._hold_timers.pop(key, None)
        if not self._config.paused:
            self._executor(action)
