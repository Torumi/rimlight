<!--
Title: a Conventional Commit, e.g. "fix(device): reopen after resume". It becomes the
squash commit and the changelog entry. See CONTRIBUTING.md.
-->

Closes #<!-- issue number; anything beyond a typo needs an agreed issue first -->

## What and why

## How it was tested

<!-- Tests added or run; real hardware (OS, X11/Wayland, strip length) or FakeTransport only. -->

## Checklist

- [ ] I followed the [clean-room rules](https://github.com/Torumi/rimlight/blob/dev/CONTRIBUTING.md#clean-room-rules): no knowledge from the vendor app's binaries or resources, also not via AI tools.
- [ ] Every commit is signed off (`git commit -s`, Developer Certificate of Origin).
- [ ] New behavior has tests; hardware is only touched through `Transport`.
- [ ] I mentioned substantial AI assistance above, if any.
