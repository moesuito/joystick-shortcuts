"""System tray icon: open GUI, switch profile, pause, quit."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from ..models import AppConfig


class TrayIcon(QObject):
    open_requested = Signal()
    quit_requested = Signal()
    pause_toggled = Signal(bool)
    profile_selected = Signal(str)

    def __init__(self, config: AppConfig, icon: QIcon, parent=None) -> None:
        super().__init__(parent)
        self._config = config
        self._tray = QSystemTrayIcon(icon, parent=parent)
        self._tray.setToolTip("Joystick Shortcuts")
        self._build_menu()
        self._tray.activated.connect(self._on_activated)

    def show(self) -> None:
        self._tray.show()

    def hide(self) -> None:
        self._tray.hide()

    def _build_menu(self) -> None:
        self._menu = QMenu()

        open_action = QAction("Abrir", self._menu)
        open_action.triggered.connect(self.open_requested.emit)
        self._menu.addAction(open_action)

        # Profile submenu
        self._profile_menu = self._menu.addMenu("Perfil")
        self._profile_group = QActionGroup(self._menu)
        self._profile_group.setExclusive(True)
        self._refresh_profile_menu()

        # Pause toggle
        self._pause_action = QAction("Pausar atalhos", self._menu, checkable=True)
        self._pause_action.setChecked(self._config.paused)
        self._pause_action.toggled.connect(self.pause_toggled.emit)
        self._menu.addAction(self._pause_action)

        self._menu.addSeparator()

        quit_action = QAction("Sair", self._menu)
        quit_action.triggered.connect(self.quit_requested.emit)
        self._menu.addAction(quit_action)

        self._tray.setContextMenu(self._menu)

    def _refresh_profile_menu(self) -> None:
        self._profile_menu.clear()
        # Re-create the action group fresh each time.
        self._profile_group = QActionGroup(self._profile_menu)
        self._profile_group.setExclusive(True)
        for name in self._config.profiles:
            action = QAction(name, self._profile_menu, checkable=True)
            action.setChecked(name == self._config.active_profile)
            action.triggered.connect(lambda _checked=False, n=name: self.profile_selected.emit(n))
            self._profile_group.addAction(action)
            self._profile_menu.addAction(action)

    def refresh(self) -> None:
        """Re-sync menu items with the current config (call after config changes)."""
        self._refresh_profile_menu()
        self._pause_action.blockSignals(True)
        self._pause_action.setChecked(self._config.paused)
        self._pause_action.setText("Retomar atalhos" if self._config.paused else "Pausar atalhos")
        self._pause_action.blockSignals(False)

    def notify(self, title: str, message: str) -> None:
        self._tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 2500)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.open_requested.emit()
