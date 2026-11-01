# Roadmap

What rimlight should do by 1.0, prioritized with MoSCoW **relative to 1.0**:

- **Must**: 1.0 does not ship without it.
- **Should**: important, planned for a milestone, but 1.0 could ship without it.
- **Could**: welcome, no milestone; done when there is time or a contributor picks it up
  (issues labelled `help wanted`).
- **Won't (before 1.0)**: explicitly out of scope for now.

Each item has an issue (created from [roadmap.json](roadmap.json) by
`scripts/dev_tools/roadmap.py`) and, unless it is a Could, a
[milestone](https://github.com/Torumi/rimlight/milestones). Pull requests reference the issue.

Early versions target Windows first, where the strip is tested on real hardware; Linux follows
in 0.3. The goal for 1.0 is a full replacement for the vendor app, except firmware updates.

## Milestones

| Milestone | Goal |
|-----------|------|
| 0.1 | First useful version on Windows: documented protocol, static color, brightness, **recovery after sleep/resume and replugging**, minimal tray, autostart |
| 0.2 | Screen mirroring on Windows |
| 0.3 | Linux: X11 and Wayland capture, suspend/resume and hotplug, NixOS flake |
| 0.4 | Full settings window and color quality |
| 1.0 | Stabilization: installers, nixpkgs, user documentation |

## Items

Already done: A1 device discovery (`rimlight-cli list`), H1 Windows zip and H3 Linux tarball
builds.

### Device and connection

| ID | Item | MoSCoW | Milestone | Notes |
|----|------|--------|-----------|-------|
| A2 | Initialize the strip as documented in the protocol spec | Must | 0.1 | |
| A3 | Set the whole strip to one color | Must | 0.1 | |
| A4 | Per-LED color frames | Must | 0.2 | needed for mirroring |
| A5 | Brightness control | Must | 0.1 | hardware if the protocol has it, else software |
| A6 | Turn the strip on and off | Must | 0.1 | |
| A7 | Rate-limit writes to the strip | Must | 0.1 | hardware safety |
| A8 | Reconnect after unplugging and replugging (Windows) | Must | 0.1 | |
| A8L | Reconnect after unplugging and replugging (Linux) | Must | 0.3 | |
| A9 | Recover the strip after sleep/resume (Windows) | Must | 0.1 | the reason this project exists |
| A9L | Recover the strip after suspend/resume (Linux) | Must | 0.3 | |
| A10 | Turn the strip off on sleep, shutdown and exit (Windows) | Should | 0.1 | |
| A10L | Turn the strip off on suspend, shutdown and exit (Linux) | Should | 0.3 | |
| A11 | React to screen lock | Could | | |
| A12 | LED count setting | Must | 0.1 | project rule; fallback for A15 |
| A13 | Drive several strips at once | Could | | |
| A14 | Show the firmware version | Could | | only if the protocol reports it |
| A15 | Detect the LED count automatically | Should | 0.1 | only if the protocol allows it; otherwise C2 helps |
| A16a | Device driver abstraction and registry | Must | 0.1 | cheap now, expensive later |
| A16b | Support other Nanoleaf devices | Could | | each device needs its own captures |

### Screen capture

| ID | Item | MoSCoW | Milestone | Notes |
|----|------|--------|-----------|-------|
| B1 | Screen capture on Windows (DXGI) | Must | 0.2 | |
| B2 | Screen capture on Linux X11 | Must | 0.3 | |
| B3 | Screen capture on Linux Wayland | Must | 0.3 | |
| B4 | Choose the monitor to mirror | Must | 0.2 | unusable with two monitors otherwise |
| B5 | Correct colors on HDR monitors | Should | 0.4 | |
| B6 | Ignore letterbox bars | Could | | |
| B7 | Keep CPU and GPU load low while mirroring | Must | 0.2 | runs all the time |

### Zones and color processing

| ID | Item | MoSCoW | Milestone | Notes |
|----|------|--------|-----------|-------|
| C1 | Zone layout: start corner, direction, LEDs per edge | Must | 0.2 | |
| C2 | Calibration wizard | Should | 0.4 | |
| C3 | Configurable zone depth | Should | 0.2 | |
| D1 | Smoothing between frames | Must | 0.2 | flicker otherwise |
| D2 | Gamma, white balance and color temperature | Should | 0.4 | |
| D3 | Saturation boost | Could | | |
| D4 | Threshold for dark scenes | Should | 0.4 | |

### Modes

| ID | Item | MoSCoW | Milestone | Notes |
|----|------|--------|-----------|-------|
| E1 | Static color mode | Must | 0.1 | |
| E2 | Built-in effects | Could | | own designs only, never the vendor's |
| E4 | Schedules: night mode and timed off | Could | | |

### Application

| ID | Item | MoSCoW | Milestone | Notes |
|----|------|--------|-----------|-------|
| F1 | Minimal tray icon | Must | 0.1 | on/off, color, brightness, status |
| F2 | Main settings window | Must | 0.4 | no TOML editing needed |
| F3 | Live LED preview | Should | 0.4 | |
| F4 | Start with Windows | Must | 0.1 | recovery is useless if the app is not running |
| F4L | Start with the desktop session (Linux) | Must | 0.3 | |
| F5 | Persist settings in TOML | Must | 0.1 | |
| F6 | Profiles and presets | Could | | |
| F7 | Global hotkeys | Could | | |
| F8 | Translate the user interface | Could | | English only at first |
| F9 | Notifications on disconnect and recovery | Should | 0.4 | |
| F10 | Allow only one running instance | Must | 0.1 | two instances would fight over the device |

### Integrations, distribution, diagnostics

| ID | Item | MoSCoW | Milestone | Notes |
|----|------|--------|-----------|-------|
| G1 | CLI: set color, on/off, run headless | Must | 0.1 | also the debugging tool |
| G2 | Local API for automation | Could | | |
| G3 | Per-application profiles | Could | | |
| H2 | Windows installer | Should | 1.0 | |
| H4 | Flatpak, AUR and deb packages | Could | | |
| H5 | Check for updates | Could | | |
| H7a | NixOS flake with package and module | Must | 0.3 | PyInstaller builds do not run on NixOS |
| H7b | Package rimlight in nixpkgs | Should | 1.0 | |
| I1 | Log to a file and copy diagnostics | Must | 0.1 | needed to debug sleep/resume reports |
| I2 | Dump sent reports from the CLI | Should | 0.1 | protocol debugging |

## Won't (before 1.0)

| ID | Item | Why |
|----|------|-----|
| E3 | Music-reactive mode | A separate audio-capture subsystem on two operating systems |
| H6 | Code-signed Windows builds | Needs a paid certificate; SmartScreen warnings are documented instead |
| A16c | Devices from other vendors | The driver architecture (A16a) allows it, but the scope stays on one device family until 1.0 |
| — | macOS | Not a target platform |
| — | Firmware updates | Stay with the vendor app (clean-room and hardware safety) |
| — | Cloud features | rimlight works locally |

Changing a priority means editing this file and [roadmap.json](roadmap.json) together (a test
checks they agree) and re-running the script, which updates the issues.
