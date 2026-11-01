# rimlight

Open-source desktop app for USB monitor-backlight LED strips: screen mirroring, static colors
and effects, and reliable recovery after sleep/resume. Windows 10/11 and Linux (Wayland and X11).

Compatible with the Nanoleaf PC Screen Mirror Lightstrip (USB HID, `37FA:8202`).

> **Status: pre-alpha.** The device protocol is not documented yet, so rimlight cannot
> control the strip. What works today: `rimlight-cli list`, which finds the strip's HID
> interfaces without sending anything to it.

## Why

The vendor app loses the strip after the PC wakes from sleep (on Windows the HID node shows
Code 28 until the device is restarted). rimlight aims to drive the strip directly and recover
by itself after resume.

## Clean-room disclaimer

rimlight is an independent, clean-room implementation. The protocol is documented only from
USB traffic captured on our own hardware and from observed device behavior
([docs/protocol.md](docs/protocol.md), [docs/capture-guide.md](docs/capture-guide.md)).
No vendor software is decompiled, disassembled or copied, and rimlight never sends firmware
updates; use the vendor app for those.

rimlight is not affiliated with, endorsed by, or supported by Nanoleaf. Product names are
used only to describe compatibility.

## Install (from source)

Requires [uv](https://docs.astral.sh/uv/).

```
git clone <repo-url> rimlight
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

```
uv run rimlight-cli list          # HID interfaces with the vendor usage page (0xFF00)
uv run rimlight-cli list --all    # every interface of the strip
uv run rimlight-cli list --json
uv run rimlight                   # GUI (placeholder for now)
```

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
