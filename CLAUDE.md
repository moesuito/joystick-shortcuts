# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common commands

All commands assume the venv at `.venv\` (created on first run of `build.ps1`).

```powershell
# Run from source (dev loop)
.\.venv\Scripts\python.exe main.py

# Headless smoke test — boots full app graph (Qt + tray + poller) for 3s, exits clean
.\.venv\Scripts\python.exe tools\smoke_run.py

# Compile-check every .py without running anything
.\.venv\Scripts\python.exe -c "import py_compile, pathlib; [py_compile.compile(str(p), doraise=True) for p in pathlib.Path('.').rglob('*.py') if '.venv' not in str(p) and 'build' not in str(p) and 'dist' not in str(p)]"

# Build single-file Windows .exe → dist\JoystickShortcuts.exe
.\build.ps1
```

There is **no test suite** and no linter wired up. Verification before shipping is: compile-check → `smoke_run.py` → manual GUI test (plug a controller, bind a button, confirm dispatch).

## Architecture

The app is a **single-purpose Qt event-loop process** that bridges XInput → keyboard. Three layers, connected by Qt signals:

```
XInputPoller (QThread, 120Hz)
    ├── pressed(button: str)      ──┐
    └── released(button: str)     ──┤
                                    ▼
                            Dispatcher (QObject, GUI thread)
                                    │  reads AppConfig.active().bindings
                                    │  manages per-binding hold timers
                                    ▼
                            execute_action(Action)
                                    │
                                    ├── keyboard.send("ctrl+shift+s")
                                    ├── webbrowser.open(...)
                                    └── subprocess.Popen(...)
```

- **`app/xinput_poller.py`** is the only thread-y thing. Loads its own ctypes binding for `XInputGetStateEx` (ordinal 100 in `xinput1_4.dll`, falling back to `1_3` / `9_1_0`) so it can read the Xbox/Guide button (bit `0x0400`) that the documented `XInputGetState` hides. Polls in a tight loop, edge-detects 15 buttons + LT/RT (analog → boolean via `trigger_threshold`), emits Qt signals. When the controller is unplugged it backs off to 1Hz instead of the configured `poll_hz` to save CPU. The `XInput-Python` package is **not** a dependency — we deliberately re-implemented the bindings to add Guide support.
- **`app/actions.py`** has both the stateless `execute_action(Action)` function and the stateful `Dispatcher` class. The dispatcher owns hold-timers (`QTimer` per active hold) so a press → wait → still-held window can fire delayed. It also tracks `self._held: set[str]` of currently-pressed buttons so chord bindings (`Binding.modifier`) can check whether their modifier is held at the moment the trigger button fires. Press/release/hold trigger logic lives entirely in the dispatcher; the poller just emits raw edges.
- **`app/models.py`** dataclasses serialize via explicit `to_dict` / `from_dict`. JSON schema lives at `%APPDATA%\JoystickShortcuts\config.json`. `Binding.modifier: str | None` is the chord field — `None` means "fire on standard press/release/hold of `button`"; a button name means "fire only when that button is held at the moment `button` is pressed". Chord bindings are forced to `trigger="press"` regardless of the saved value.

### Adding a new action type

1. Extend the `ActionType` Literal in `app/models.py`.
2. Add a branch in `execute_action` and `describe_action` in `app/actions.py`.
3. Add a panel in `BindingDialog._build_*_panel` and a stack page in `BindingDialog._build_ui` in `app/gui/binding_dialog.py`.
4. Wire it in `BindingDialog._build_action` and `BindingDialog._load`.

The `Action.payload: dict` is intentionally schema-less — adding a new type requires no migration of existing configs.

## Gotchas

- **`SetPriorityClass` requires explicit ctypes types.** `app/system/priority.py` declares `wintypes.HANDLE` for `GetCurrentProcess.restype` because the default `c_int` truncates the pseudo-handle on x64 Windows and silently fails. If you touch this file, keep the explicit `argtypes` / `restype` setup or priority will quietly stop working.
- **Guide button cannot be suppressed from Steam.** We can read it via `XInputGetStateEx`, but the press still reaches Steam in parallel — there is no user-mode way to consume gamepad input system-wide. So `GUIDE + A` chord bindings will fire your action *and* may pop Steam Big Picture / overlay. This is a known platform limitation, not a bug. If you change the chord behavior, do not promise suppression.
- **PyInstaller `--onefile` produces two processes.** The outer `JoystickShortcuts.exe` is a bootloader that extracts and spawns the real Python app as a child. Priority is set on the child, not the bootloader — `Get-Process` will show one process at Normal (bootloader) and one at High (app).
- **Window close hides to tray.** `MainWindow.closeEvent` calls `event.ignore()` and `self.hide()`. The only path that actually quits is the tray menu's "Quit" → `quit_app()` in `main.py`, which stops the poller before `QApplication.quit()`.
- **Bindings are paused during edit.** `MainWindow._on_add` and `_on_edit_selected` set `config.paused = True` before opening `BindingDialog`, restore on close. This prevents a "press X to capture" gesture from also firing the user's existing X binding.
- **The `keyboard` library does not need admin** for `keyboard.send()`. We never call its global hook APIs (`keyboard.read_event`, `keyboard.hook`), so admin is not required. Key capture in the dialog uses Qt's `keyPressEvent`, not the `keyboard` library.
- **Autostart paths differ between dev and frozen.** `app/system/autostart.py` writes `pythonw.exe main.py --tray` when running from source, and `JoystickShortcuts.exe --tray` when `sys.frozen` is set. If you change the entry point or rename the .exe, this needs updating.

## Conventions

- **UI strings are en_US** in source. The maintainer is Brazilian but the public GitHub project is English-only — keep new strings in English.
- **No `# type: ignore` chains.** If Pyright complains about a Qt API, prefer adding `# noqa: N802` for naming or fixing the call. Qt's `QSystemTrayIcon.MessageIcon`, etc. are fully typed.
- **No background processes spawned outside the Dispatcher.** All side effects (key sends, app launches, registry writes) flow through `execute_action`, autostart helpers, or priority helpers — there's no fire-and-forget thread elsewhere.
- **Commits use `moesuito` identity.** Per the maintainer's global git rules, pass inline `-c user.email=57041838+moesuito@users.noreply.github.com -c user.name="João Alano"` if the local repo has no global identity configured.

## Release flow

The `.exe` is published as a GitHub Release asset, not committed to the repo (see `.gitignore`). To cut a release:

```powershell
.\build.ps1
gh release create vX.Y.Z .\dist\JoystickShortcuts.exe --title "vX.Y.Z" --notes "..."
```

Releases live at https://github.com/moesuito/joystick-shortcuts/releases.
