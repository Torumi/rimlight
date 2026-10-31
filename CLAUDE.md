# CLAUDE.md

## Project

Open-source, clean-room desktop app that drives a USB monitor-backlight LED strip
(the "Nanoleaf PC Screen Mirror Lightstrip") without the vendor's software:
screen mirroring, static colors/effects, and **reliable recovery after sleep/resume**
(the vendor app loses the device after resume — Windows shows the HID node with Code 28
until the device is restarted).

Working name: `rimlight` (package `rimlight`). Do not use the vendor's name or logo in the
app name, icon, or UI; mention it only as "compatible with" in README.

Platforms: Windows 10/11 and Linux (Wayland + X11). License: MIT.

## Language

- Code, identifiers, comments, docstrings, commit messages, docs, issues: **English**.
- Talk to the user (chat replies, plans, questions): **Russian**.

## Clean-room rules (non-negotiable)

- The only source of protocol knowledge is USB traffic captured by the user
  (Wireshark + USBPcap on Windows, usbmon on Linux) and behavior observed on the device.
- Never decompile, disassemble, or read the vendor app's binaries, installers,
  JS bundles, or resources. Never copy vendor code, assets, effect definitions, or strings.
- `docs/protocol.md` is the spec. Implementation follows the spec only.
  Every field in the spec cites the capture file(s) it was derived from.
- Firmware updates stay with the vendor app. This project never sends firmware/DFU traffic.

## Hardware safety

- Device: USB HID, `VID 0x37FA`, `PID 0x8202`, vendor usage page `0xFF00`, usage `0x01`.
- Strip ships with 75 LEDs but can be cut; LED count is a user setting, never hard-coded.
- **Only send report types documented in `docs/protocol.md`.** No fuzzing, no probing of
  unknown command bytes, no "let's see what this does". Unknown/unsure → ask the user.
- Rate-limit writes (default cap 60 fps). Always close the device handle cleanly.
- Code that talks to real hardware must be behind the `Transport` interface so everything
  else runs against `FakeTransport` in tests.

## Stack

- Python 3.12, managed with **uv** (`pyproject.toml` + `uv.lock`, src layout).
- Lint/format: **ruff** (`ruff check`, `ruff format`). Types: **pyright** in strict mode.
- Tests: **pytest** (+ `pytest-qt` for UI).
- HID: `hidapi` (cython-hidapi). Arrays: `numpy`.
- UI: **PySide6**, full main window (zone editor, live preview, settings) plus tray icon.
- Screen capture backends:
  - Windows: DXGI Desktop Duplication (`dxcam` or `windows-capture`).
  - Linux X11: XShm (`mss`).
  - Linux Wayland: xdg-desktop-portal ScreenCast + PipeWire stream.
- Power/sleep events:
  - Windows: `RegisterSuspendResumeNotification` / `WM_POWERBROADCAST`, plus device-arrival notifications.
  - Linux: logind `PrepareForSleep` D-Bus signal, plus udev/hidraw hotplug.
- Packaging: PyInstaller (Windows zip, Linux tarball); udev rule shipped in `packaging/linux/`.

## Architecture

```
src/rimlight/
  device/       # protocol.py (pure encode/decode, no I/O), transport.py (Transport ABC,
                # HidTransport, FakeTransport), manager.py (open/reopen, hotplug, resume recovery)
  capture/      # base.py (CaptureBackend protocol), windows_dxgi.py, linux_x11.py, linux_portal.py
  mapping/      # zone layout: LED index -> screen region, corner/edge calibration
  processing/   # averaging, smoothing, gamma, color temperature, brightness
  power/        # platform sleep/resume + lock/unlock listeners -> events
  engine/       # frame loop: capture -> mapping -> processing -> device; modes (mirror, static, effect)
  config/       # settings model + TOML persistence (platformdirs)
  ui/           # PySide6 window, tray, zone editor, live preview
  cli.py        # debug CLI: list devices, set color, run mirror headless, dump reports
```

Rules:
- `device/protocol.py` is pure and fully unit-tested against fixtures from real captures.
- Core packages never import PySide6. UI talks to the engine via signals/a thin facade.
- Platform-specific modules are imported lazily behind a factory; the other OS's code must
  import-safely skip in CI.
- Resume recovery: on resume or write error → close handle, wait for re-enumeration,
  reopen with backoff, re-send init sequence. Never block the UI thread.

## Commands

```
uv sync                         # install
uv run ruff check . && uv run ruff format --check .
uv run pyright
uv run pytest                   # hardware tests are skipped by default
uv run pytest -m hardware       # only with the strip plugged in, run by the user
uv run rimlight-cli --help
uv run rimlight                 # GUI
```

Before saying a task is done: ruff, pyright and pytest all pass.

## Tests

- Mark tests needing the real strip with `@pytest.mark.hardware`; CI never runs them.
- Protocol tests use byte fixtures in `tests/fixtures/` extracted from captures.
- Raw `.pcapng` captures live in `captures/` (gitignored); only small extracted fixtures are committed.

## Git / CI

- GitHub, public repo. Conventional Commits (`feat:`, `fix:`, `docs:`, `ci:`, `refactor:`, `test:`).
- Small focused commits; don't commit unless the user asks.
- GitHub Actions:
  - `ci.yml` on push/PR: matrix `windows-latest` + `ubuntu-latest`: ruff, ruff format check, pyright, pytest.
  - `release.yml` on tag `v*`: PyInstaller builds for Windows and Linux, attached to a GitHub Release.
- Never commit secrets, captures, or local config.
