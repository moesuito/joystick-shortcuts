"""Boot the full app, run the event loop for ~3 seconds, then quit cleanly.

Used to verify there are no startup crashes (signal connection mistakes, missing
attributes, etc.) without requiring a human to drive the GUI.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the project root importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.profile_manager import load_config, save_config  # noqa: E402
from app.xinput_poller import XInputPoller  # noqa: E402
from app.actions import Dispatcher  # noqa: E402
from app.gui.main_window import MainWindow  # noqa: E402
from app.gui.tray import TrayIcon  # noqa: E402
from PySide6.QtGui import QIcon  # noqa: E402


def main() -> int:
    QApplication.setQuitOnLastWindowClosed(False)
    app = QApplication(sys.argv)

    config = load_config()
    poller = XInputPoller(poll_hz=config.poll_hz)
    dispatcher = Dispatcher(config)
    poller.pressed.connect(dispatcher.on_pressed)
    poller.released.connect(dispatcher.on_released)

    window = MainWindow(config, poller, on_save=lambda: save_config(config))
    tray = TrayIcon(config, QIcon())
    tray.show()
    window.show()
    poller.start()

    print("[smoke] running 3s event loop...")
    QTimer.singleShot(3000, app.quit)

    rc = app.exec()

    poller.stop()
    poller.wait(2000)
    print(f"[smoke] event loop exited rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
