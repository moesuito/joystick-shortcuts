"""Background thread that polls XInput state and emits press/release signals.

Uses the undocumented `XInputGetStateEx` (ordinal 100) when available so the
Xbox/Guide button is exposed alongside the standard 14 buttons. Falls back to
the documented `XInputGetState` if the Ex variant cannot be loaded — in that
case GUIDE is silently unavailable.
"""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from typing import Callable

from PySide6.QtCore import QThread, Signal

from .models import XINPUT_BUTTONS


# Bit masks as documented in XINPUT_GAMEPAD.wButtons.
# 0x0400 (GUIDE) is undocumented and only appears via XInputGetStateEx.
_BUTTON_BITS: dict[str, int] = {
    "DPAD_UP": 0x0001,
    "DPAD_DOWN": 0x0002,
    "DPAD_LEFT": 0x0004,
    "DPAD_RIGHT": 0x0008,
    "START": 0x0010,
    "BACK": 0x0020,
    "LS": 0x0040,
    "RS": 0x0080,
    "LB": 0x0100,
    "RB": 0x0200,
    "GUIDE": 0x0400,
    "A": 0x1000,
    "B": 0x2000,
    "X": 0x4000,
    "Y": 0x8000,
}

ERROR_DEVICE_NOT_CONNECTED = 0x048F


class _XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ("wButtons", wintypes.WORD),
        ("bLeftTrigger", wintypes.BYTE),
        ("bRightTrigger", wintypes.BYTE),
        ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short),
        ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]


class _XINPUT_STATE(ctypes.Structure):
    _fields_ = [
        ("dwPacketNumber", wintypes.DWORD),
        ("Gamepad", _XINPUT_GAMEPAD),
    ]


def _load_get_state() -> tuple[Callable | None, bool]:
    """Try to load XInputGetStateEx (ordinal 100) — returns (func, supports_guide).

    Falls back to documented XInputGetState if the Ex variant is missing.
    Search order matches what Steam / GlosSI use.
    """
    for dll_name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
        try:
            lib = ctypes.WinDLL(dll_name)
        except OSError:
            continue
        # Try undocumented ordinal 100 (XInputGetStateEx) first.
        try:
            func = lib[100]
            func.argtypes = [wintypes.DWORD, ctypes.POINTER(_XINPUT_STATE)]
            func.restype = wintypes.DWORD
            return func, True
        except (AttributeError, OSError):
            pass
        # Fall back to documented XInputGetState.
        try:
            func = lib.XInputGetState
            func.argtypes = [wintypes.DWORD, ctypes.POINTER(_XINPUT_STATE)]
            func.restype = wintypes.DWORD
            return func, False
        except (AttributeError, OSError):
            continue
    return None, False


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
        self._get_state, self._supports_guide = _load_get_state()
        if self._get_state is None:
            print("[poller] no XInput DLL found — controller polling disabled")
        elif not self._supports_guide:
            print("[poller] XInputGetStateEx unavailable — Xbox/Guide button will not be detected")

    @property
    def supports_guide(self) -> bool:
        return self._supports_guide

    def stop(self) -> None:
        self._stop = True

    def set_poll_hz(self, hz: int) -> None:
        self._poll_hz = max(30, min(500, int(hz)))

    def set_trigger_threshold(self, value: float) -> None:
        self._trigger_threshold = max(0.05, min(0.95, float(value)))

    def run(self) -> None:  # noqa: C901 — single-purpose hot loop
        if self._get_state is None:
            return

        state = _XINPUT_STATE()

        while not self._stop:
            sleep_s = 1.0 / max(1, self._poll_hz)
            ret = self._get_state(self._user_index, ctypes.byref(state))

            if ret == ERROR_DEVICE_NOT_CONNECTED:
                if self._connected:
                    self._connected = False
                    self.connection_changed.emit(False)
                    self._prev = {b: False for b in XINPUT_BUTTONS}
                time.sleep(1.0)
                continue

            if ret != 0:
                # Unknown error — log and back off briefly.
                print(f"[poller] XInputGetState returned {ret}")
                time.sleep(0.5)
                continue

            if not self._connected:
                self._connected = True
                self.connection_changed.emit(True)

            wbuttons = state.Gamepad.wButtons
            lt = state.Gamepad.bLeftTrigger / 255.0
            rt = state.Gamepad.bRightTrigger / 255.0

            current: dict[str, bool] = {
                name: bool(wbuttons & bit) for name, bit in _BUTTON_BITS.items()
            }
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
