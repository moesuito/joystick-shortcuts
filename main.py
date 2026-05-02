"""Joystick Shortcuts — entry point.

Runs:
1. Bumps process priority to HIGH (so input keeps firing under game load).
2. Loads config from %APPDATA%\\JoystickShortcuts\\config.json.
3. Boots Qt app with main window + system tray + XInput polling thread.
4. Routes controller events through the dispatcher to fire keyboard/system actions.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from app import APP_DISPLAY_NAME, APP_NAME
from app.actions import Dispatcher
from app.gui.main_window import MainWindow
from app.gui.tray import TrayIcon
from app.profile_manager import load_config, save_config
from app.system import autostart, priority
from app.xinput_poller import XInputPoller


def _build_icon() -> QIcon:
    """Use bundled .ico if present, else draw a simple gamepad-ish glyph."""
    here = Path(__file__).resolve().parent
    candidates = [
        here / "assets" / "tray_icon.ico",
        here / "_internal" / "assets" / "tray_icon.ico",  # PyInstaller onedir
    ]
    for p in candidates:
        if p.is_file():
            return QIcon(str(p))

    # Programmatic fallback: a simple rounded square with "JS".
    pix = QPixmap(64, 64)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#3a82f7"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(2, 2, 60, 60, 12, 12)
    painter.setPen(QColor("white"))
    font = painter.font()
    font.setPointSize(22)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "JS")
    painter.end()
    return QIcon(pix)


def main() -> int:
    QApplication.setApplicationName(APP_NAME)
    QApplication.setApplicationDisplayName(APP_DISPLAY_NAME)
    QApplication.setOrganizationName("JoystickShortcuts")
    QApplication.setQuitOnLastWindowClosed(False)  # tray keeps the app alive

    app = QApplication(sys.argv)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(
            None,
            APP_DISPLAY_NAME,
            "Bandeja do sistema não disponível neste ambiente.",
        )
        return 1

    config = load_config()

    # Apply priority class.
    if config.high_priority:
        priority.set_high_priority()

    # Sync autostart registry with the saved preference (in case the .exe was moved).
    if config.autostart:
        try:
            autostart.set_enabled(True)
        except Exception as exc:
            print(f"[main] autostart sync failed: {exc}")

    icon = _build_icon()

    poller = XInputPoller(
        user_index=0,
        poll_hz=config.poll_hz,
        trigger_threshold=config.trigger_threshold,
    )

    dispatcher = Dispatcher(config)
    poller.pressed.connect(dispatcher.on_pressed)
    poller.released.connect(dispatcher.on_released)

    def persist() -> None:
        save_config(config)
        dispatcher.set_config(config)

    window = MainWindow(config, poller, on_save=persist, app_icon=icon)

    tray = TrayIcon(config, icon)
    tray.show()

    def open_window() -> None:
        window.showNormal()
        window.raise_()
        window.activateWindow()

    def quit_app() -> None:
        poller.stop()
        poller.wait(2000)
        save_config(config)
        QApplication.quit()

    def on_tray_pause(checked: bool) -> None:
        config.paused = checked
        window.sync_pause_state()
        tray.refresh()
        save_config(config)

    def on_tray_profile(name: str) -> None:
        if name in config.profiles:
            config.active_profile = name
            window.sync_active_profile()
            tray.refresh()
            save_config(config)
            tray.notify(APP_DISPLAY_NAME, f"Perfil ativo: {name}")

    def on_window_pause(checked: bool) -> None:
        tray.refresh()

    def on_config_changed() -> None:
        tray.refresh()
        dispatcher.set_config(config)

    tray.open_requested.connect(open_window)
    tray.quit_requested.connect(quit_app)
    tray.pause_toggled.connect(on_tray_pause)
    tray.profile_selected.connect(on_tray_profile)
    window.pause_toggled.connect(on_window_pause)
    window.config_changed.connect(on_config_changed)

    # Decide whether to show the window or stay in the tray.
    start_in_tray = config.minimize_to_tray_on_start or "--tray" in sys.argv
    if not start_in_tray:
        window.show()

    poller.start()

    try:
        return app.exec()
    finally:
        poller.stop()
        poller.wait(2000)
        save_config(config)


if __name__ == "__main__":
    sys.exit(main())
