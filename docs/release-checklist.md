# Release checklist

`prepare-release` copies the matching section into the release PR. The `checklist` status check
blocks the merge until every box is ticked. If an item does not apply yet (for example, mirroring
before it exists), tick it and write "N/A" after it.

## Stable release

- [ ] CI is green on the release PR
- [ ] The rc builds from GitHub Releases start on Windows and Linux
- [ ] `uv run pytest -m hardware` passes with the strip plugged in, on Windows
- [ ] `uv run pytest -m hardware` passes with the strip plugged in, on Linux
- [ ] Sleep/resume on Windows: the strip recovers by itself after waking from sleep
- [ ] Suspend/resume on Linux: the strip recovers by itself after resume
- [ ] Unplug/replug while running: the strip recovers by itself
- [ ] Screen mirroring works on Windows, Linux X11 and Linux Wayland
- [ ] Static color and brightness changes apply
- [ ] CHANGELOG.md in this PR reads correctly

## Hotfix

- [ ] CI is green on the release PR
- [ ] The fix is verified on the strip, in the scenario it fixes
- [ ] `uv run pytest -m hardware` passes on the affected OS
- [ ] Sleep/resume still recovers on the affected OS
- [ ] CHANGELOG.md in this PR reads correctly
