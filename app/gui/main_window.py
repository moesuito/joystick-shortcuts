"""Main configuration window."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..actions import describe_action
from ..models import AppConfig, Binding, Profile
from ..xinput_poller import XInputPoller
from .binding_dialog import BindingDialog


TRIGGER_LABELS = {
    "press": "On press",
    "release": "On release",
    "hold": "On hold",
}

ACTION_TYPE_LABELS = {
    "key": "Key",
    "key_combo": "Combo",
    "media": "Media",
    "launch": "Launch",
}


class MainWindow(QMainWindow):
    config_changed = Signal()
    pause_toggled = Signal(bool)
    quit_requested = Signal()

    def __init__(
        self,
        config: AppConfig,
        poller: XInputPoller,
        on_save: Callable[[], None],
        app_icon: QIcon | None = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._poller = poller
        self._on_save = on_save
        self._connected = False

        self.setWindowTitle("Joystick Shortcuts")
        self.resize(820, 540)
        if app_icon:
            self.setWindowIcon(app_icon)

        self._build_ui()
        self._refresh_profile_list()
        self._refresh_table()
        self._refresh_status()

        # Live status feedback from the poller.
        self._poller.connection_changed.connect(self._on_connection_changed)

    # ---- UI ----------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        # Top bar: profile selector
        top = QHBoxLayout()
        top.addWidget(QLabel("Profile:"))
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(200)
        self.profile_combo.currentTextChanged.connect(self._on_profile_changed)
        top.addWidget(self.profile_combo)

        self.btn_new_profile = QPushButton("New")
        self.btn_new_profile.clicked.connect(self._on_new_profile)
        top.addWidget(self.btn_new_profile)

        self.btn_rename_profile = QPushButton("Rename")
        self.btn_rename_profile.clicked.connect(self._on_rename_profile)
        top.addWidget(self.btn_rename_profile)

        self.btn_delete_profile = QPushButton("Delete")
        self.btn_delete_profile.clicked.connect(self._on_delete_profile)
        top.addWidget(self.btn_delete_profile)

        top.addStretch(1)

        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #888;")
        top.addWidget(self.status_label)

        root.addLayout(top)

        # Bindings table
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Name", "Button", "Type", "Action", "Trigger", ""]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._on_edit_selected)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.table, 1)

        # Action row under the table
        actions_row = QHBoxLayout()
        self.btn_add = QPushButton("+ Add shortcut")
        self.btn_add.clicked.connect(self._on_add)
        actions_row.addWidget(self.btn_add)

        self.btn_edit = QPushButton("Edit")
        self.btn_edit.clicked.connect(self._on_edit_selected)
        actions_row.addWidget(self.btn_edit)

        self.btn_delete = QPushButton("Delete")
        self.btn_delete.clicked.connect(self._on_delete_selected)
        actions_row.addWidget(self.btn_delete)

        actions_row.addStretch(1)

        self.btn_pause = QPushButton()
        self.btn_pause.setCheckable(True)
        self.btn_pause.setChecked(self._config.paused)
        self._render_pause_button()
        self.btn_pause.toggled.connect(self._on_pause_toggled)
        actions_row.addWidget(self.btn_pause)

        root.addLayout(actions_row)

        # Settings strip
        settings = QHBoxLayout()
        self.chk_autostart = QCheckBox("Start with Windows")
        self.chk_autostart.setChecked(self._config.autostart)
        self.chk_autostart.toggled.connect(self._on_autostart_toggled)
        settings.addWidget(self.chk_autostart)

        self.chk_high_priority = QCheckBox("High priority")
        self.chk_high_priority.setChecked(self._config.high_priority)
        self.chk_high_priority.toggled.connect(self._on_priority_toggled)
        settings.addWidget(self.chk_high_priority)

        self.chk_minimize = QCheckBox("Start minimized")
        self.chk_minimize.setChecked(self._config.minimize_to_tray_on_start)
        self.chk_minimize.toggled.connect(self._on_minimize_toggled)
        settings.addWidget(self.chk_minimize)

        settings.addStretch(1)

        settings.addWidget(QLabel("Polling:"))
        self.poll_spin = QSpinBox()
        self.poll_spin.setRange(30, 500)
        self.poll_spin.setSingleStep(10)
        self.poll_spin.setValue(self._config.poll_hz)
        self.poll_spin.setSuffix(" Hz")
        self.poll_spin.valueChanged.connect(self._on_poll_changed)
        settings.addWidget(self.poll_spin)

        root.addLayout(settings)

        self.setCentralWidget(central)

    # ---- Status ------------------------------------------------------------

    @Slot(bool)
    def _on_connection_changed(self, connected: bool) -> None:
        self._connected = connected
        self._refresh_status()

    def _refresh_status(self) -> None:
        if self._connected:
            self.status_label.setText("● Controller connected")
            self.status_label.setStyleSheet("color: #4caf50;")
        else:
            self.status_label.setText("○ Waiting for controller…")
            self.status_label.setStyleSheet("color: #888;")

    # ---- Profile handlers --------------------------------------------------

    def _refresh_profile_list(self) -> None:
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for name in self._config.profiles:
            self.profile_combo.addItem(name)
        idx = self.profile_combo.findText(self._config.active_profile)
        if idx >= 0:
            self.profile_combo.setCurrentIndex(idx)
        self.profile_combo.blockSignals(False)

    @Slot(str)
    def _on_profile_changed(self, name: str) -> None:
        if not name or name not in self._config.profiles:
            return
        self._config.active_profile = name
        self._refresh_table()
        self._save()

    @Slot()
    def _on_new_profile(self) -> None:
        name, ok = QInputDialog.getText(self, "New profile", "Profile name:")
        name = name.strip()
        if not ok or not name:
            return
        if name in self._config.profiles:
            QMessageBox.warning(self, "Profile exists", f"A profile named '{name}' already exists.")
            return
        self._config.profiles[name] = Profile(name=name)
        self._config.active_profile = name
        self._refresh_profile_list()
        self._refresh_table()
        self._save()

    @Slot()
    def _on_rename_profile(self) -> None:
        old = self._config.active_profile
        if not old:
            return
        new, ok = QInputDialog.getText(self, "Rename profile", "New name:", text=old)
        new = new.strip()
        if not ok or not new or new == old:
            return
        if new in self._config.profiles:
            QMessageBox.warning(self, "Profile exists", f"A profile named '{new}' already exists.")
            return
        # Rebuild dict preserving insertion order, swapping the renamed key.
        rebuilt: dict = {}
        for k, v in self._config.profiles.items():
            if k == old:
                v.name = new
                rebuilt[new] = v
            else:
                rebuilt[k] = v
        self._config.profiles = rebuilt
        self._config.active_profile = new
        self._refresh_profile_list()
        self._save()

    @Slot()
    def _on_delete_profile(self) -> None:
        if len(self._config.profiles) <= 1:
            QMessageBox.information(
                self, "Not allowed", "You must keep at least one profile."
            )
            return
        name = self._config.active_profile
        confirm = QMessageBox.question(
            self,
            "Delete profile",
            f"Delete profile '{name}' and all its shortcuts?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._config.profiles.pop(name, None)
        self._config.active_profile = next(iter(self._config.profiles))
        self._refresh_profile_list()
        self._refresh_table()
        self._save()

    # ---- Bindings table ----------------------------------------------------

    def _refresh_table(self) -> None:
        bindings = self._config.active().bindings
        self.table.setRowCount(len(bindings))
        for row, b in enumerate(bindings):
            self.table.setItem(row, 0, QTableWidgetItem(b.name))
            button_label = f"{b.modifier} + {b.button}" if b.modifier else b.button
            self.table.setItem(row, 1, QTableWidgetItem(button_label))
            self.table.setItem(row, 2, QTableWidgetItem(ACTION_TYPE_LABELS.get(b.action.type, b.action.type)))
            self.table.setItem(row, 3, QTableWidgetItem(describe_action(b.action)))
            if b.modifier:
                trig = "Chord"
            else:
                trig = TRIGGER_LABELS.get(b.trigger, b.trigger)
                if b.trigger == "hold":
                    trig = f"{trig} ({b.hold_ms} ms)"
            self.table.setItem(row, 4, QTableWidgetItem(trig))
            # Store id in the first column item for later lookup.
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, b.id)
            # Empty column 5 reserved for future per-row icon buttons.
            self.table.setItem(row, 5, QTableWidgetItem(""))

    def _selected_binding(self) -> Binding | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if not item:
            return None
        bid = item.data(Qt.ItemDataRole.UserRole)
        for b in self._config.active().bindings:
            if b.id == bid:
                return b
        return None

    @Slot()
    def _on_add(self) -> None:
        was_paused = self._config.paused
        self._config.paused = True
        try:
            dlg = BindingDialog(self._poller, parent=self)
            if dlg.exec() == BindingDialog.DialogCode.Accepted:
                self._config.active().bindings.append(dlg.build_binding())
                self._refresh_table()
                self._save()
        finally:
            self._config.paused = was_paused

    @Slot()
    def _on_edit_selected(self) -> None:
        b = self._selected_binding()
        if not b:
            return
        was_paused = self._config.paused
        self._config.paused = True
        try:
            dlg = BindingDialog(self._poller, binding=b, parent=self)
            if dlg.exec() == BindingDialog.DialogCode.Accepted:
                updated = dlg.build_binding()
                bindings = self._config.active().bindings
                for i, existing in enumerate(bindings):
                    if existing.id == b.id:
                        bindings[i] = updated
                        break
                self._refresh_table()
                self._save()
        finally:
            self._config.paused = was_paused

    @Slot()
    def _on_delete_selected(self) -> None:
        b = self._selected_binding()
        if not b:
            return
        confirm = QMessageBox.question(
            self,
            "Delete shortcut",
            f"Delete shortcut '{b.name}'?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        bindings = self._config.active().bindings
        self._config.active().bindings = [x for x in bindings if x.id != b.id]
        self._refresh_table()
        self._save()

    # ---- Settings handlers -------------------------------------------------

    def _render_pause_button(self) -> None:
        if self._config.paused:
            self.btn_pause.setText("▶ Resume shortcuts")
        else:
            self.btn_pause.setText("⏸ Pause shortcuts")

    @Slot(bool)
    def _on_pause_toggled(self, checked: bool) -> None:
        self._config.paused = checked
        self._render_pause_button()
        self.pause_toggled.emit(checked)
        self._save()

    @Slot(bool)
    def _on_autostart_toggled(self, checked: bool) -> None:
        self._config.autostart = checked
        try:
            from ..system import autostart

            autostart.set_enabled(checked)
        except Exception as exc:
            QMessageBox.warning(self, "Autostart", f"Failed to update autostart: {exc}")
        self._save()

    @Slot(bool)
    def _on_priority_toggled(self, checked: bool) -> None:
        self._config.high_priority = checked
        from ..system import priority

        if checked:
            priority.set_high_priority()
        else:
            priority.set_normal_priority()
        self._save()

    @Slot(bool)
    def _on_minimize_toggled(self, checked: bool) -> None:
        self._config.minimize_to_tray_on_start = checked
        self._save()

    @Slot(int)
    def _on_poll_changed(self, hz: int) -> None:
        self._config.poll_hz = int(hz)
        self._poller.set_poll_hz(int(hz))
        self._save()

    # ---- External control --------------------------------------------------

    def sync_pause_state(self) -> None:
        """Refresh the pause button when toggled from elsewhere (e.g. tray)."""
        self.btn_pause.blockSignals(True)
        self.btn_pause.setChecked(self._config.paused)
        self._render_pause_button()
        self.btn_pause.blockSignals(False)

    def sync_active_profile(self) -> None:
        """Refresh the profile selector when toggled from the tray."""
        self._refresh_profile_list()
        self._refresh_table()

    # ---- Persistence + close behavior --------------------------------------

    def _save(self) -> None:
        self._on_save()
        self.config_changed.emit()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt API)
        # Hide to tray instead of quitting.
        event.ignore()
        self.hide()
