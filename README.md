# rimlight

Open-source desktop app for USB monitor-backlight LED strips: static colors and reliable
recovery after sleep/resume today, screen mirroring and effects later. Windows 10/11 first, then
Linux (Wayland and X11).

Compatible with the Nanoleaf PC Screen Mirror Lightstrip (USB HID, `37FA:8202`).

> **Status: alpha, Windows only, command line only.** rimlight holds a static color and
> brightness, and brings the strip back after sleep and after replugging. So far this has been
> tested on one PC. There is no tray icon, autostart or screen mirroring yet, and on Linux nothing
> beyond `rimlight-cli list` has been tested.

## Why

The vendor app loses the strip after the PC wakes from sleep (on Windows the HID node shows
Code 28 until the device is restarted). rimlight drives the strip directly and recovers by
itself after resume.

## Clean-room disclaimer

rimlight is an independent, clean-room implementation. The protocol is documented only from
USB traffic captured on our own hardware and from observed device behavior
([docs/protocols/](docs/protocols/README.md), [docs/capture-guide.md](docs/capture-guide.md)).
No vendor software is decompiled, disassembled or copied, and rimlight never sends firmware
updates; use the vendor app for those.

rimlight is not affiliated with, endorsed by, or supported by Nanoleaf. Product names are
used only to describe compatibility.

## Install (from source)

Requires [uv](https://docs.astral.sh/uv/).

```
git clone https://github.com/Torumi/rimlight.git
cd rimlight
uv sync
uv run rimlight-cli list
```

### Linux: device permissions

To access the strip without root, install the udev rule:

```
sudo cp packaging/linux/99-rimlight.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Then unplug and replug the strip.

## Usage

Close the vendor app first, so that only one program talks to the strip.

```
uv run rimlight-cli set --color "#ff8800" --brightness 50   # save the light
uv run rimlight-cli set --off                               # or --on; the color is kept
uv run rimlight-cli run                                     # show it and keep it up (Ctrl+C stops)
```

`set` only saves the settings: a running `run` picks them up when it is restarted.

Other commands:

```
uv run rimlight-cli list          # HID interfaces with the vendor usage page (0xFF00)
uv run rimlight-cli list --all    # every interface of the strip
uv run rimlight-cli list --json
uv run rimlight-cli diagnostics   # report for bug reports, with identifiers masked
uv run rimlight                   # GUI (placeholder for now)
```

### Automatic restart (Windows)

After sleep the strip stops answering, and after replugging it can come up in its bootloader
(USB ID `4348:55E0`, Code 28). Only restarting the device brings it back, and that needs
administrator rights, so rimlight can set up a scheduled task once and then start it as a normal
user:

```
uv run rimlight-cli recovery enable    # asks for administrator rights once
uv run rimlight-cli recovery status
uv run rimlight-cli recovery disable   # turn it off, keep the task
uv run rimlight-cli recovery remove    # turn it off, remove the task
```

The task runs as SYSTEM and only restarts the USB devices with the strip's two IDs. rimlight
never writes to the bootloader. Its ID looks like the chip maker's, so while the strip is missing,
another device with that ID would be restarted too.

## Development

```
uv sync
uv run prek install               # git hooks (lint, format, types, fast tests, hygiene)
uv run ruff check . && uv run ruff format --check .
uv run pyright
uv run pytest                     # hardware tests are skipped
uv run pytest -m hardware         # with the strip plugged in
```

## Roadmap

| Milestone | Goal |
|-----------|------|
| 0.1 | Windows: documented protocol, static color, recovery after sleep/resume and replugging, tray |
| 0.2 | Screen mirroring on Windows |
| 0.3 | Linux (X11, Wayland) and NixOS |
| 0.4 | Full settings window and color quality |
| 1.0 | Stabilization, installers |

Every feature with its priority is in [docs/roadmap.md](docs/roadmap.md); progress is tracked in
[milestones](https://github.com/Torumi/rimlight/milestones).

## Contributing

Bug reports, setup reports, USB captures, and code are all welcome. Read
[CONTRIBUTING.md](CONTRIBUTING.md) first, especially the clean-room rules, and open an issue
before larger changes. Questions and ideas go to
[Discussions](https://github.com/Torumi/rimlight/discussions); security issues to
[SECURITY.md](SECURITY.md). This project follows the [Code of Conduct](CODE_OF_CONDUCT.md).

### Branches and releases

`dev` (the default branch) is the alpha line, `main` is the beta line; stable versions are
tagged releases. Download builds from [Releases](../../releases); see
[docs/releasing.md](docs/releasing.md) for the full flow. PRs go into `dev`.

## License

[MIT](LICENSE)
