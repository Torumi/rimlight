# Changelog

All notable changes to this project are documented here. Pre-releases (alpha, beta, rc)
are listed on the GitHub Releases page; this file collects them into each stable release.

## Unreleased

### Features
- Scaffold project skeleton (phase 0)
- **release:** Add release rules and CLI
- **device:** Add driver abstraction and registry (#71)
- **device:** Implement the strip protocol and driver (#73)
- **device:** Rate-limit frames in the driver base class (#75)
- **config:** Add settings model with TOML persistence (#76)
- Add log file and diagnostics report (#77)
- **device:** Add device manager with recovery (#80)
- **power:** Add Windows sleep and resume events (#81)
- **device:** Restart a hung device through a scheduled task (#82)
- **cli:** Add run and set commands (#83)

### Bug fixes
- **ci:** Install Qt system libraries on Linux runners (#2)
- **cli:** Mask unit identifiers in list --json (#12)
- **device:** Restart the strip when it comes up in its bootloader (#84)

### Refactoring
- **device:** Separate shared code from per-device drivers (#74)
- **config:** Remove the LED count setting (#88)

### Documentation
- Document branching and release process
- Add contributing guide and community files (#6)
- Add MoSCoW roadmap and issue sync script (#13)
- **protocol:** Document framing, color frames and init from captures 00-09 (#72)
- **protocol:** Record that the strip hangs after every S3 sleep (#78)
- **protocol:** Restart the strip through a scheduled task (#79)
- Describe what works in the README (#89)

### Build and CI
- Add release automation workflows and rulesets
- Add git hooks via prek and hooks/pr-title checks (#5)
- Pin actions by SHA, add Dependabot and build smoke test (#7)

### Miscellaneous
- Normalize line endings to LF
- **deps:** Bump the actions group across 1 directory with 5 updates (#8)
- **deps:** Update uv-build requirement (#9)

