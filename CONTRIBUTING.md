# Contributing to rimlight

Thanks for helping! rimlight is a small project maintained in spare time, and it is
**pre-alpha**: the device protocol is still being documented and the architecture still moves.
Reports from real hardware are as valuable as code.

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md). Security issues go through
[SECURITY.md](SECURITY.md), never public issues.

## Ways to help

- **Report bugs** and **test on your setup**: Windows version, X11 or Wayland (and which
  compositor), strip length. Use the issue forms; they ask for what we need.
- **Capture USB traffic** for the protocol work. See [Protocol captures](#protocol-captures).
- **Answer questions** and share working setups in
  [Discussions](https://github.com/Torumi/rimlight/discussions).
- **Code and docs.** Look for `good first issue` and `help wanted`.

English is the project language, but an issue in another language or a machine translation is
fine: we will translate.

**Response times:** issues and PRs usually get an answer within one to two weeks. If it has been
longer, a polite ping is welcome.

## Clean-room rules

rimlight is a clean-room implementation. Its legality rests on these rules, so they apply to
every contribution and are not negotiable:

- Protocol knowledge comes **only** from USB traffic captured on your own device and from the
  device's observed behavior.
- **Never** decompile, disassemble, or read the vendor app's binaries, installers, scripts, or
  resources, and never feed them to AI tools. Never copy vendor code, assets, effect definitions,
  or strings.
- Firmware updates are out of scope; rimlight never sends firmware traffic.

If you have studied the vendor app's internals, please do not contribute protocol code or
protocol documentation. You can still help with everything else.

## Before you start

**Open or comment on an issue first** for anything beyond a typo or a small doc fix, and wait
for a maintainer to agree on the approach. The code changes quickly before 1.0, and this saves
you from writing a PR that cannot be merged.

## Development setup

You need [uv](https://docs.astral.sh/uv/) and git. Fork the repository on GitHub, then:

```
git clone https://github.com/<you>/rimlight.git
cd rimlight
git remote add upstream https://github.com/Torumi/rimlight.git
uv sync
uv run prek install
```

`prek install` sets up the git hooks (`.pre-commit-config.yaml`): ruff fixes and formatting,
pyright, the fast tests, file hygiene, blocking of secrets, large files and USB captures, a
`uv.lock` check, workflow linting, and the DCO sign-off check. A commit touching Python files
takes about 5 seconds. CI runs the same hooks, so skipping them only moves failures to the PR.

On Linux, install the udev rule from the README to access the strip without root.

Useful commands:

```
uv run pytest                    # all tests except hardware ones
uv run pytest -m hardware        # with the strip plugged in
uv run pyright
uv run prek run --all-files      # every hook on the whole repository
uv run rimlight-cli list         # find the strip (read-only)
```

## Making a change

1. Sync and branch off `dev` (the default branch):
   ```
   git fetch upstream
   git switch -c feat/<topic> upstream/dev     # or fix/<topic>, docs/<topic>
   ```
2. Commit with a sign-off (see [DCO](#developer-certificate-of-origin)):
   ```
   git commit -s
   ```
3. Push to your fork and open a pull request **into `dev`**. Fill in the template.
4. Rebasing your branch on `upstream/dev` and `git push --force-with-lease` is fine.

### Pull request rules

- **Title**: a [Conventional Commit](https://www.conventionalcommits.org/), for example
  `feat(device): reopen after resume` or `fix: crash with 30-LED strips`. Types: `feat`, `fix`,
  `perf`, `refactor`, `docs`, `test`, `ci`, `build`, `chore`. PRs are squash-merged, so the
  title becomes the commit message and the changelog entry. The `pr-title` check enforces it.
- **Required checks**: `check` (ruff, pyright, tests on Windows and Linux), `hooks`, `pr-title`
  and `dco`. A maintainer approves the CI run for your first PR.
- **Keep it focused**: one topic per PR.
- **Tests**: new behavior comes with tests. Hardware access goes through the `Transport`
  interface, so tests run against `FakeTransport`. Mark tests that need the real strip with
  `@pytest.mark.hardware`, and tests that take over ~0.5 s on their own with
  `@pytest.mark.slow`.
- **Hardware safety**: only send reports documented in `docs/protocol.md`. No probing or fuzzing
  of unknown commands.
- Say in the PR how you tested it, especially whether on real hardware.

### Developer Certificate of Origin

Every commit must be signed off, certifying the
[Developer Certificate of Origin](https://developercertificate.org/): that you wrote the change
or otherwise have the right to submit it under the project's MIT license. `git commit -s` adds
the line, which must match your commit's author email:

```
Signed-off-by: Jane Doe <jane@example.org>
```

The commit-msg hook and the `dco` check enforce this. To fix a branch:

```
git commit --amend --no-edit -s          # last commit
git rebase --signoff upstream/dev        # every commit on the branch
git push --force-with-lease
```

### AI-assisted contributions

Using AI tools is fine. You are responsible for every line as if you wrote it yourself, and you
mention substantial AI use in the PR. The clean-room rules apply to AI tools too: never give them
vendor code, binaries, or resources.

## Protocol captures

USB captures from more devices and firmware versions speed up the protocol work.

1. Follow [docs/capture-guide.md](docs/capture-guide.md) and capture one scenario per file.
2. **Filter to the strip's traffic only** before sharing (in Wireshark:
   `usb.device_address == N`, then *File → Export Specified Packets → Displayed*). A raw capture
   can contain other USB devices, including your keyboard.
3. Open a **Protocol capture** issue and attach the file.

Raw captures never go into the repository. Findings go into `docs/protocol.md` with a reference
to the issue, and small extracted byte fixtures go into `tests/fixtures/` through a PR.

## Releases

Maintainers handle releases; see [docs/releasing.md](docs/releasing.md). Contributors never
bump versions or create tags.
