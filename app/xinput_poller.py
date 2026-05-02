"""Background thread that polls XInput state and emits press/release signals."""
from __future__ import annotations

import time
from typing import Optional

from PySide6.QtCore import QThread, Signal

from .models import XINPUT_BUTTONS


# Map our normalized button names to the keys returned by XInput-Python.
_LIB_NAME = {
    "A": "A",
    "B": "B",
    "X": "X",
    "Y": "Y",
    "LB": "LEFT_SHOULDER",
    "RB": "RIGHT_SHOULDER",
    "LS": "LEFT_THUMB",
    "RS": "RIGHT_THUMB",
    "BACK": "BACK",
    "START": "START",
    "DPAD_UP": "DPAD_UP",
    "DPAD_DOWN": "DPAD_DOWN",
    "DPAD_LEFT": "DPAD_LEFT",
    "DPAD_RIGHT": "DPAD_RIGHT",
}


class XInputPoller(QThread):
    pressed = Signal(str)
    released = Signal(str)
    connection_changed = Signal(bool)

    def __init__(
        self,
        user_index: int = 0,
        poll_hz: int = 120,
        trigger_threshold: float = 0.5,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._user_index = user_index
        self._poll_hz = poll_hz
        self._trigger_threshold = trigger_threshold
        self._stop = False
        self._connected = False
        self._prev: dict[str, bool] = {b: False for b in XINPUT_BUTTONS}

    def stop(self) -> None:
        self._stop = True

    def set_poll_hz(self, hz: int) -> None:
        self._poll_hz = max(30, min(500, int(hz)))

    def set_trigger_threshold(self, value: float) -> None:
        self._trigger_threshold = max(0.05, min(0.95, float(value)))

    def run(self) -> None:  # noqa: C901 — single-purpose hot loop
        try:
            import XInput  # type: ignore
        except ImportError as exc:
            print(f"[poller] XInput-Python not available: {exc}")
            return

        not_connected_exc = getattr(XInput, "XInputNotConnectedError", Exception)

        while not self._stop:
            sleep_s = 1.0 / max(1, self._poll_hz)
            try:
                state = XInput.get_state(self._user_index)
            except not_connected_exc:
                if self._connected:
                    self._connected = False
                    self.connection_changed.emit(False)
                    # Reset previous state so reconnection doesn't ghost-fire.
                    self._prev = {b: False for b in XINPUT_BUTTONS}
                # Back off so we don't burn CPU when the controller is unplugged.
                time.sleep(1.0)
                continue
            except Exception as exc:  # pragma: no cover — defensive
                print(f"[poller] {type(exc).__name__}: {exc}")
                time.sleep(0.5)
                continue

            if not self._connected:
                self._connected = True
                self.connection_changed.emit(True)

            try:
                lib_buttons = XInput.get_button_values(state)
                lt, rt = XInput.get_trigger_values(state)
            except Exception as exc:  # pragma: no cover
                print(f"[poller] decode error: {exc}")
                time.sleep(sleep_s)
                continue

            current: dict[str, bool] = {}
            for our_name, lib_name in _LIB_NAME.items():
                current[our_name] = bool(lib_buttons.get(lib_name, False))
            current["LT"] = lt > self._trigger_threshold
            current["RT"] = rt > self._trigger_threshold

            for btn, is_pressed in current.items():
                was = self._prev.get(btn, False)
                if is_pressed and not was:
                    self.pressed.emit(btn)
                elif was and not is_pressed:
                    self.released.emit(btn)

            self._prev = current
            time.sleep(sleep_s)
