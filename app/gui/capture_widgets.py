"""Reusable widgets to capture controller buttons and keyboard combos."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import QLineEdit, QPushButton


_QT_MOD_FLAGS = [
    (Qt.KeyboardModifier.ControlModifier, "ctrl"),
    (Qt.KeyboardModifier.AltModifier, "alt"),
    (Qt.KeyboardModifier.ShiftModifier, "shift"),
    (Qt.KeyboardModifier.MetaModifier, "windows"),
]


_NAMED_KEYS = {
    Qt.Key.Key_Escape: "esc",
    Qt.Key.Key_Tab: "tab",
    Qt.Key.Key_Backspace: "backspace",
    Qt.Key.Key_Return: "enter",
    Qt.Key.Key_Enter: "enter",
    Qt.Key.Key_Insert: "insert",
    Qt.Key.Key_Delete: "delete",
    Qt.Key.Key_Pause: "pause",
    Qt.Key.Key_Print: "print screen",
    Qt.Key.Key_SysReq: "print screen",
    Qt.Key.Key_Home: "home",
    Qt.Key.Key_End: "end",
    Qt.Key.Key_Left: "left",
    Qt.Key.Key_Up: "up",
    Qt.Key.Key_Right: "right",
    Qt.Key.Key_Down: "down",
    Qt.Key.Key_PageUp: "page up",
    Qt.Key.Key_PageDown: "page down",
    Qt.Key.Key_CapsLock: "caps lock",
    Qt.Key.Key_NumLock: "num lock",
    Qt.Key.Key_ScrollLock: "scroll lock",
    Qt.Key.Key_Space: "space",
}


def _is_modifier_key(qkey: int) -> bool:
    return qkey in (
        Qt.Key.Key_Control,
        Qt.Key.Key_Shift,
        Qt.Key.Key_Alt,
        Qt.Key.Key_AltGr,
        Qt.Key.Key_Meta,
        Qt.Key.Key_Super_L,
        Qt.Key.Key_Super_R,
    )


def _qt_modifiers_to_names(mods: Qt.KeyboardModifier) -> list[str]:
    names = []
    for flag, name in _QT_MOD_FLAGS:
        if mods & flag:
            names.append(name)
    return names


def _qt_key_to_name(qkey: int) -> str | None:
    if qkey in _NAMED_KEYS:
        return _NAMED_KEYS[qkey]
    if Qt.Key.Key_F1 <= qkey <= Qt.Key.Key_F35:
        return f"f{qkey - Qt.Key.Key_F1 + 1}"
    text = QKeySequence(qkey).toString()
    if text:
        return text.lower()
    return None


class ButtonCaptureButton(QPushButton):
    """Click to capture, then displays the captured controller button."""

    capture_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._captured: str | None = None
        self._capturing = False
        self._render()
        self.clicked.connect(self._toggle_capture)

    def _toggle_capture(self) -> None:
        if self._capturing:
            self._capturing = False
            self._render()
            return
        self._capturing = True
        self._render()
        self.capture_requested.emit()

    def cancel_capture(self) -> None:
        if self._capturing:
            self._capturing = False
            self._render()

    def is_capturing(self) -> bool:
        return self._capturing

    def set_button(self, name: str | None) -> None:
        self._captured = name
        self._capturing = False
        self._render()

    def captured(self) -> str | None:
        return self._captured

    def _render(self) -> None:
        if self._capturing:
            self.setText("Press a controller button… (click to cancel)")
        elif self._captured:
            self.setText(f"Button: {self._captured}   (click to change)")
        else:
            self.setText("Capture controller button")


class KeyComboLineEdit(QLineEdit):
    """A line edit that captures key combinations into a normalized string.

    Format: comma-less plus-joined like "ctrl+shift+s".
    Reading via `keys()` returns the list of token names suitable for the `keyboard` lib.
    """

    captured = Signal(list)

    def __init__(self, parent=None, allow_modifiers: bool = True) -> None:
        super().__init__(parent)
        self._allow_modifiers = allow_modifiers
        self._keys: list[str] = []
        self.setReadOnly(True)
        self.setPlaceholderText("Click and press the key combination")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def keys(self) -> list[str]:
        return list(self._keys)

    def set_keys(self, keys: list[str]) -> None:
        self._keys = [k for k in keys if k]
        self.setText("+".join(self._keys))

    def clear_keys(self) -> None:
        self._keys = []
        self.setText("")

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (Qt API)
        # Backspace clears (only if it's the lone key with no modifiers we want to record).
        if event.key() == Qt.Key.Key_Backspace and not event.modifiers():
            self.clear_keys()
            return

        if _is_modifier_key(event.key()):
            # Show partial state while user holds modifiers.
            mods = _qt_modifiers_to_names(event.modifiers())
            self.setText("+".join(mods + ["…"]) if mods else "…")
            return

        name = _qt_key_to_name(event.key())
        if not name:
            return

        if self._allow_modifiers:
            mods = _qt_modifiers_to_names(event.modifiers())
            tokens = mods + [name]
        else:
            tokens = [name]
        self._keys = tokens
        self.setText("+".join(tokens))
        self.captured.emit(tokens)
