# Joystick Shortcuts

A Windows utility that maps **XInput controller** buttons (Xbox / 8BitDo / GameSir / Razer / Xbox Elite paddles, etc.) to **global keyboard shortcuts**, **media controls**, and **app launchers**. Runs in the system tray and pins itself to **HIGH process priority** so bindings keep firing even while a fullscreen game is hammering the CPU.

## Features

- Unlimited named shortcuts, organized in **switchable profiles** (toggle from the GUI or the tray menu)
- Action types per binding:
  - **Single key** (F1, Print Screen, Insert, …)
  - **Modifier combos** (Ctrl / Shift / Alt / Win + key)
  - **Media & volume** (volume up/down, mute, play/pause, next/prev track)
  - **Launch app or URL** (any `.exe` with optional args, or `http(s)://…`)
- Three trigger modes per binding: **on press**, **on release**, **on hold** (configurable hold time in ms)
- **HIGH priority class** automatic on launch — appears as "High" in Task Manager
- **Auto-start with Windows** (HKCU `Run` registry key)
- **Start minimized to tray** option
- Global **pause toggle** — disable all shortcuts without quitting

Supported buttons: `A`, `B`, `X`, `Y`, `LB`, `RB`, `LT`, `RT`, `BACK`, `START`, `LS` (click), `RS` (click), and the D-Pad (`UP` / `DOWN` / `LEFT` / `RIGHT`).

## Install

Grab the latest **`JoystickShortcuts.exe`** from [Releases](https://github.com/moesuito/joystick-shortcuts/releases). Single file, no installer, no Python runtime required. Double-click and the icon appears in the system tray.

## Run from source

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

The first launch creates `%APPDATA%\JoystickShortcuts\config.json` with an empty "Default" profile. Click **+ Add shortcut** to start binding.

Requires **Python 3.11+** on Windows.

## Build a `.exe`

```powershell
.\build.ps1
```

Produces `dist\JoystickShortcuts.exe` — a single-file, console-less executable. Drop it anywhere on disk and tick **Start with Windows** in the GUI; the registry entry will point to that path.

## Caveats

- **Steam Input / Xbox Game Bar**: XInput is shared-read, so this app's polling does not conflict with games. However, if Steam is remapping your controller to keyboard inputs, both Steam and this app may fire the same action. Disable Steam Input for the affected game if that happens.
- **Guide / Xbox button**: not exposed by the public XInput API; it cannot be bound.
- **Aftermarket controllers with extra buttons**: most paddles/macros (8BitDo Pro 2, Xbox Elite paddles, GameSir, Razer Wolverine, etc.) map their extra buttons onto existing XInput inputs via firmware or a companion app. Configure your back paddle to send, for example, `LB` or `RB`, and bind that here.
- **The `keyboard` library** does not require admin privileges for `keyboard.send()`. We do not hook keyboard events globally — key capture only happens inside the (focused) edit dialog.

## Project layout

```
main.py                       entry point: priority bump → tray + GUI
app/
├─ models.py                  dataclasses (Action, Binding, Profile, AppConfig)
├─ profile_manager.py         load/save JSON in %APPDATA%
├─ xinput_poller.py           QThread polling at 120Hz with edge detection
├─ actions.py                 executor (key / combo / media / launch) + Dispatcher
├─ system/
│  ├─ priority.py             SetPriorityClass via ctypes
│  └─ autostart.py            HKCU Run key
└─ gui/
   ├─ main_window.py          main window: profile selector, table, settings
   ├─ binding_dialog.py       create / edit a single binding
   ├─ capture_widgets.py      controller-button + key-combo capture widgets
   └─ tray.py                 system tray icon + menu
```

## License

[Apache License 2.0](LICENSE) — © 2026 João Alano.
