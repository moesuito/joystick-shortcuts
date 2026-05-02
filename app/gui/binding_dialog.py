"""Dialog for creating / editing a single Binding."""
from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..models import Action, Binding, XINPUT_BUTTONS
from ..xinput_poller import XInputPoller
from .capture_widgets import ButtonCaptureButton, KeyComboLineEdit


ACTION_TYPES = [
    ("key", "Single key"),
    ("key_combo", "Combo (Ctrl/Shift/Alt/Win)"),
    ("media", "Media & Volume"),
    ("launch", "Launch app / open URL"),
]

TRIGGER_MODES = [
    ("press", "On press"),
    ("release", "On release"),
    ("hold", "On hold"),
]

MEDIA_OPTIONS = [
    ("volume_up", "Volume up"),
    ("volume_down", "Volume down"),
    ("mute", "Mute (toggle)"),
    ("play_pause", "Play / Pause"),
    ("next", "Next track"),
    ("prev", "Previous track"),
]


class BindingDialog(QDialog):
    def __init__(
        self,
        poller: XInputPoller,
        binding: Binding | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._poller = poller
        self._original = binding
        self.setWindowTitle("Edit shortcut" if binding else "New shortcut")
        self.setModal(True)
        self.setMinimumWidth(480)

        self._build_ui()
        if binding:
            self._load(binding)

        # Wire the poller so capture works.
        self._poller.pressed.connect(self._on_controller_pressed)

    # ---- UI construction ---------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Screenshot snip")
        form.addRow("Name:", self.name_edit)

        # Optional modifier (chord). Defaults to no modifier; selecting GUIDE
        # makes this binding fire only when the Xbox button is held.
        self.modifier_combo = QComboBox()
        self.modifier_combo.addItem("(none — single-button)", None)
        for btn in XINPUT_BUTTONS:
            self.modifier_combo.addItem(btn, btn)
        self.modifier_combo.currentIndexChanged.connect(self._on_modifier_changed)
        form.addRow("Hold modifier:", self.modifier_combo)

        self.button_capture = ButtonCaptureButton()
        form.addRow("Button:", self.button_capture)

        self.action_type = QComboBox()
        for value, label in ACTION_TYPES:
            self.action_type.addItem(label, value)
        self.action_type.currentIndexChanged.connect(self._on_action_type_changed)
        form.addRow("Action:", self.action_type)

        # Stacked panels per action type.
        self.action_stack = QStackedWidget()
        self.action_stack.addWidget(self._build_key_panel())          # 0: key
        self.action_stack.addWidget(self._build_combo_panel())        # 1: key_combo
        self.action_stack.addWidget(self._build_media_panel())        # 2: media
        self.action_stack.addWidget(self._build_launch_panel())       # 3: launch
        form.addRow("", self.action_stack)

        # Trigger mode + hold ms.
        trigger_row = QHBoxLayout()
        self.trigger_combo = QComboBox()
        for value, label in TRIGGER_MODES:
            self.trigger_combo.addItem(label, value)
        self.trigger_combo.currentIndexChanged.connect(self._on_trigger_changed)
        self.hold_spin = QSpinBox()
        self.hold_spin.setRange(100, 5000)
        self.hold_spin.setSingleStep(50)
        self.hold_spin.setValue(500)
        self.hold_spin.setSuffix(" ms")
        self.hold_spin.setEnabled(False)
        trigger_row.addWidget(self.trigger_combo, 1)
        trigger_row.addWidget(QLabel("Hold time:"))
        trigger_row.addWidget(self.hold_spin)
        form.addRow("Trigger:", trigger_row)

        root.addLayout(form)

        hint = QLabel(
            "Tip: shortcuts are paused while this dialog is open so they don't fire"
            " while you're capturing buttons/keys."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888;")
        root.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _build_key_panel(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        self.key_single = KeyComboLineEdit(allow_modifiers=False)
        self.key_single.setPlaceholderText("Click here and press a key")
        lay.addWidget(self.key_single)
        return w

    def _build_combo_panel(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        self.key_combo = KeyComboLineEdit(allow_modifiers=True)
        self.key_combo.setPlaceholderText("Click here and press a combination")
        lay.addWidget(self.key_combo)
        return w

    def _build_media_panel(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        self.media_combo = QComboBox()
        for value, label in MEDIA_OPTIONS:
            self.media_combo.addItem(label, value)
        lay.addWidget(self.media_combo)
        return w

    def _build_launch_panel(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)

        target_row = QHBoxLayout()
        self.launch_target = QLineEdit()
        self.launch_target.setPlaceholderText(
            r"C:\path\to\app.exe   or   https://example.com"
        )
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_target)
        target_row.addWidget(self.launch_target, 1)
        target_row.addWidget(browse)
        lay.addLayout(target_row)

        self.launch_args = QLineEdit()
        self.launch_args.setPlaceholderText("Optional arguments")
        lay.addWidget(self.launch_args)

        return w

    # ---- Slots / handlers --------------------------------------------------

    def _browse_target(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose executable")
        if path:
            self.launch_target.setText(path)

    @Slot(int)
    def _on_action_type_changed(self, index: int) -> None:
        self.action_stack.setCurrentIndex(index)

    @Slot(int)
    def _on_trigger_changed(self, index: int) -> None:
        mode = self.trigger_combo.itemData(index)
        self.hold_spin.setEnabled(mode == "hold")

    @Slot(int)
    def _on_modifier_changed(self, index: int) -> None:
        # Chord bindings always fire on press of the secondary button while the
        # modifier is held — disable the trigger picker to avoid silent surprises.
        is_chord = self.modifier_combo.itemData(index) is not None
        if is_chord:
            for i in range(self.trigger_combo.count()):
                if self.trigger_combo.itemData(i) == "press":
                    self.trigger_combo.setCurrentIndex(i)
                    break
        self.trigger_combo.setEnabled(not is_chord)
        self.hold_spin.setEnabled(not is_chord and self.trigger_combo.currentData() == "hold")

    @Slot(str)
    def _on_controller_pressed(self, button: str) -> None:
        if self.button_capture.is_capturing():
            self.button_capture.set_button(button)

    # ---- Load / save ------------------------------------------------------

    def _load(self, b: Binding) -> None:
        self.name_edit.setText(b.name)
        self.button_capture.set_button(b.button)
        # Modifier
        target_index = 0
        if b.modifier:
            for i in range(self.modifier_combo.count()):
                if self.modifier_combo.itemData(i) == b.modifier:
                    target_index = i
                    break
        self.modifier_combo.setCurrentIndex(target_index)
        # Action type
        for i in range(self.action_type.count()):
            if self.action_type.itemData(i) == b.action.type:
                self.action_type.setCurrentIndex(i)
                break
        p = b.action.payload or {}
        if b.action.type == "key":
            key = p.get("key", "")
            if key:
                self.key_single.set_keys([key])
        elif b.action.type == "key_combo":
            self.key_combo.set_keys(p.get("keys") or [])
        elif b.action.type == "media":
            cmd = p.get("command", "volume_up")
            for i in range(self.media_combo.count()):
                if self.media_combo.itemData(i) == cmd:
                    self.media_combo.setCurrentIndex(i)
                    break
        elif b.action.type == "launch":
            self.launch_target.setText(p.get("target", ""))
            self.launch_args.setText(p.get("args", ""))
        # Trigger
        for i in range(self.trigger_combo.count()):
            if self.trigger_combo.itemData(i) == b.trigger:
                self.trigger_combo.setCurrentIndex(i)
                break
        self.hold_spin.setValue(int(b.hold_ms))

    def _build_action(self) -> Action | None:
        kind = self.action_type.currentData()
        if kind == "key":
            keys = self.key_single.keys()
            if not keys:
                return None
            return Action(type="key", payload={"key": keys[0]})
        if kind == "key_combo":
            keys = self.key_combo.keys()
            if not keys:
                return None
            return Action(type="key_combo", payload={"keys": keys})
        if kind == "media":
            return Action(type="media", payload={"command": self.media_combo.currentData()})
        if kind == "launch":
            target = self.launch_target.text().strip()
            if not target:
                return None
            return Action(
                type="launch",
                payload={"target": target, "args": self.launch_args.text().strip()},
            )
        return None

    @Slot()
    def _on_accept(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Name required", "Please give the shortcut a name.")
            return
        button = self.button_capture.captured()
        if not button:
            QMessageBox.warning(self, "Button required", "Capture a controller button.")
            return
        modifier = self.modifier_combo.currentData()
        if modifier and modifier == button:
            QMessageBox.warning(
                self,
                "Invalid chord",
                "The modifier and the trigger button must be different.",
            )
            return
        if modifier == "GUIDE" and not self._poller.supports_guide:
            QMessageBox.warning(
                self,
                "Guide button unavailable",
                "Your XInput runtime does not expose the Xbox/Guide button "
                "(XInputGetStateEx not found). Pick a different modifier.",
            )
            return
        action = self._build_action()
        if action is None:
            QMessageBox.warning(
                self, "Incomplete action", "Fill in the action (key, combo, media, or target)."
            )
            return
        self.accept()

    def build_binding(self) -> Binding:
        action = self._build_action()
        assert action is not None  # guarded by _on_accept
        modifier = self.modifier_combo.currentData()
        kwargs: dict = dict(
            name=self.name_edit.text().strip(),
            button=self.button_capture.captured() or "A",
            action=action,
            trigger="press" if modifier else self.trigger_combo.currentData(),
            hold_ms=self.hold_spin.value(),
            modifier=modifier,
        )
        if self._original is not None:
            kwargs["id"] = self._original.id
        return Binding(**kwargs)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        try:
            self._poller.pressed.disconnect(self._on_controller_pressed)
        except (TypeError, RuntimeError):
            pass
        super().closeEvent(event)
