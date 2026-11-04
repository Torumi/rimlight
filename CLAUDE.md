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

Scope and priorities: `docs/roadmap.md` (MoSCoW for 1.0, milestones 0.1–1.0). It and
`docs/roadmap.json` must agree (tested); the JSON feeds the roadmap issues
(`scripts/dev_tools/roadmap.py`). Work on a roadmap item references its issue.

## Language

- Code, identifiers, comments, docstrings, commit messages, docs, issues: **English**.
- Talk to the user (chat replies, plans, questions): **Russian**.

## Clean-room rules (non-negotiable)

- The only source of protocol knowledge is USB traffic captured by the user or attached to
  "Protocol capture" issues by contributors (Wireshark + USBPcap on Windows, usbmon on Linux),
  and behavior observed on the device.
- Never decompile, disassemble, or read the vendor app's binaries, installers,
  JS bundles, or resources. Never copy vendor code, assets, effect definitions, or strings.
- `docs/protocols/<device>.md` is the spec (rules in `docs/protocols/README.md`). Implementation
  follows the spec only. Every field in the spec cites the capture file(s) it was derived from.
- Firmware updates stay with the vendor app. This project never sends firmware/DFU traffic.

## Hardware safety

- Device: USB HID, `VID 0x37FA`, `PID 0x8202`, vendor usage page `0xFF00`, usage `0x01`.
- Strip ships with 75 LEDs but can be cut; LED count is a user setting, never hard-coded.
- **Only send report types documented in the device's spec.** No fuzzing, no probing of
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
  device/       # shared code only: driver.py (DeviceDriver ABC), transport.py (Transport ABC,
                # HidTransport), discovery.py, rate_limit.py, registry.py (HID interface -> driver),
                # manager.py (open/reopen, hotplug, resume recovery), reset.py (restart a hung device)
    drivers/    # one directory per device; __init__.py holds BUILTIN_DRIVERS
      strip_37fa_8202/  # __init__.py, driver.py, protocol.py (pure encode/decode, no I/O)
      fake/             # __init__.py, driver.py, transport.py: test doubles, not registered
  capture/      # base.py (CaptureBackend protocol), windows_dxgi.py, linux_x11.py, linux_portal.py
  mapping/      # zone layout: LED index -> screen region, corner/edge calibration
  processing/   # averaging, smoothing, gamma, color temperature, brightness
  power/        # platform sleep/resume + lock/unlock listeners -> events
  engine/       # frame loop: capture -> mapping -> processing -> device; modes (mirror, static, effect)
  config/       # settings model + TOML persistence (platformdirs)
  ui/           # PySide6 window, tray, zone editor, live preview
  headless.py   # wires manager, power events and restart together for `rimlight-cli run`
  logs.py       # logging setup: one file per session in logs/, uncaught exceptions
  diagnostics.py # bug report text (identifiers masked)
  cli.py        # debug CLI: list devices, diagnostics, set color, run mirror headless, dump reports
```

Rules:
- Shared `device/` modules know nothing about a specific device; only `registry.py` reaches
  `drivers/`, for `BUILTIN_DRIVERS`. Each device directory has `__init__.py` (exports the driver),
  `driver.py` and `protocol.py`, with spec, fixtures and tests under `docs/protocols/<device>.md`,
  `tests/fixtures/<device>/`, `tests/device/<device>/`. Architecture tests enforce this;
  `docs/adding-a-device.md` is the walkthrough.
- A device's `protocol.py` is pure and fully unit-tested against fixtures from real captures.
- Engine, UI and CLI talk to `DeviceDriver`s only, never to one device's protocol. Drivers
  declare `DeviceCapabilities`; the engine emulates what a device lacks (e.g. brightness).
- Core packages never import PySide6. UI talks to the engine via signals/a thin facade.
- Platform-specific modules are imported lazily behind a factory; the other OS's code must
  import-safely skip in CI.
- Logs and diagnostics may be pasted into public issues: never log serial numbers or other
  unit identifiers, and log device, power and recovery events with `logging.getLogger(__name__)`.
- Resume recovery: on resume or write error → close handle, wait for re-enumeration,
  reopen with backoff, re-send init sequence. Never block the UI thread.

## Commands

```
uv sync                         # install
uv run prek install             # git hooks, once per clone (.pre-commit-config.yaml)
uv run prek run --all-files     # all hooks on the whole repo
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
- Mark tests that take over ~0.5 s on their own with `@pytest.mark.slow`: the pre-commit hook
  skips them (it must stay under ~15 s), CI runs them.
- Protocol tests use byte fixtures in `tests/fixtures/` extracted from captures.
- Raw `.pcapng` captures live in `captures/` (gitignored); only small extracted fixtures are committed.

## Git / CI

Full process: `docs/releasing.md`. Summary:

- GitHub, public repo. Conventional Commits (`feat:`, `fix:`, `docs:`, `ci:`, `refactor:`, `test:`);
  PR titles too, since feature PRs are squash-merged and `CHANGELOG.md` is generated from them.
- Small focused commits; don't commit unless the user asks.
- DCO: every commit is signed off (`git commit -s`). Commits made on the user's command carry
  the user's sign-off; the command to commit is their consent to it. Contributor rules live in
  `CONTRIBUTING.md`.
- Branches: `dev` (default, alpha line), `main` (beta/rc, then the stable release),
  `release/X.Y` (only for hotfixes while a beta is on `main`). Work happens on `feat/*` / `fix/*`
  branches off `dev`, merged by PR; never push directly to `dev`, `main` or `release/*`.
- Never rebase or force-push automation branches (`release-prep/*`, `merge-back/*`, `backport/*`,
  `bump/*`); resolve their conflicts by merging. Rebasing own feature branches is fine.
- Versions: PEP 440 (`0.5.0a1`, `0.5.0b1`, `0.5.0rc1`, `0.5.0`), static in `pyproject.toml`.
  Never bump versions or create `v*` tags by hand: releases go through the
  `prepare-release` workflow; the rules live in `scripts/release_tools` (unit-tested).
- Git hooks (prek, `.pre-commit-config.yaml`): ruff fix/format, pyright, fast tests, file
  hygiene, private keys, large files and captures, `uv lock --check`, actionlint + shellcheck,
  no commits to `dev`/`main`/`release/*`; commit-msg hook checks the DCO sign-off. Don't bypass
  them with `--no-verify`.
- GitHub Actions: `ci.yml` (ruff, format, pyright, pytest on Windows + Ubuntu, plus `hooks` on
  all files), `pr-title.yml` (Conventional Commit PR titles) and `dco.yml` (sign-offs) on PRs;
  `dev-build.yml` (artifacts per dev push); release flow `prepare-release` → `tag-release` →
  `release`; `merge-back` (main → dev); `backport` (release/X.Y → main). Writing workflows
  act as a GitHub App; protection lives in `.github/rulesets/` (applied by `scripts/github/`).
- Never commit secrets, captures, or local config.
