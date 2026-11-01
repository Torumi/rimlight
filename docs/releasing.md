# Branching and releases

Maintainer documentation. Contributors only need [CONTRIBUTING.md](../CONTRIBUTING.md).

## Branches

| Branch | Holds | Gets changes from |
|--------|-------|-------------------|
| `dev` (default) | the alpha line: next version's features | `feat/*`, `fix/*` PRs (squash); merge-back PRs from `main` (merge commit) |
| `main` | the beta line (`bN`, `rcN`); after a final, that stable release until the next promotion | promotion PR from `dev` (merge commit); fix PRs and release PRs (squash) |
| `release/X.Y` | the last stable line, only while a beta line occupies `main` | hotfix PRs (squash) |
| `release-prep/*`, `merge-back/*`, `backport/*`, `bump/*` | automation, short-lived | the release App only |

`dev`, `main` and `release/*` accept changes only through PRs with green CI. Nobody force-pushes
or deletes them.

### Changes

Feature and fix PRs follow [CONTRIBUTING.md](../CONTRIBUTING.md): branch off `dev`, sign off,
Conventional Commit PR title, squash merge. Maintainers work the same way, from branches in this
repository instead of a fork.

**Never rebase or force-push automation branches** (`merge-back/*` especially): their merge
commits are what keeps `main` and `dev` history connected. Resolve conflicts there by merging.

A bug found in the beta is fixed with a PR into `main`; merge-back carries it to `dev`.
External PRs that target `dev` but fix a beta bug are re-targeted to `main` by the maintainer.

### Triage

New issues get `needs-triage` from their template. Triage means: reproduce or ask for details
(`needs-repro`), add type, `area:` and `os:` labels, link duplicates, set a milestone if it is
planned, and remove `needs-triage`. Say "no" early (`wontfix`, with a reason) rather than leaving
issues open. Protocol captures attached to issues are reviewed for privacy before any finding
from them goes into `docs/protocol.md`.

## Versions

PEP 440 everywhere: tags `v0.5.0a1`, `v0.5.0b1`, `v0.5.0rc1`, `v0.5.0`, `v0.5.1`. The version
lives statically in `pyproject.toml`:

- on `dev` it is the **next, unreleased** alpha (bumped right after each alpha is tagged), so
  development builds never claim a released version;
- on `main` and `release/X.Y` it is the last release made there.

Before 1.0, a minor release may break compatibility. 1.0 comes when mirroring and sleep/resume
recovery work on both operating systems.

## Release cycle

All releases start from **Actions → Prepare release → Run workflow**, choosing the branch and kind.
The workflow validates the request, bumps the version, regenerates `CHANGELOG.md` and opens a
`release-prep/<version>` PR. Merging that PR tags it; the tag builds and publishes the release.

| Kind | Run on | Result |
|------|--------|--------|
| `alpha` | `dev` | `v0.5.0aN` pre-release; dev moves to `aN+1` |
| `beta` | `dev` | **promotion**: PR `dev → main` as `0.5.0b1` (merge with *Create a merge commit*); dev moves to `0.6.0a1` |
| `beta` | `main` | next beta `0.5.0bN+1` |
| `rc` | `main` | `0.5.0rc1`, `rc2`, ... |
| `final` | `main` | `v0.5.0`, marked latest; old `release/*` branches are deleted |
| `patch` | `main` or `release/X.Y` | hotfix `vX.Y.Z+1` |

Rules enforced by `scripts/release_tools` (both when preparing and again on the tag):

- each kind runs only on the branches above;
- a new version sorts above every existing tag (patches: above every tag of their X.Y line);
- `final` needs an rc of the same version that is at least 7 days old, and only
  `pyproject.toml`, `uv.lock` and `CHANGELOG.md` may differ from that rc;
- `final` and `patch` PRs carry a checklist ([release-checklist.md](release-checklist.md)) that
  must be fully ticked before the PR can be merged.

Pre-releases appear only on GitHub Releases; `CHANGELOG.md` keeps their changes under
"Unreleased" and folds them into the stable release's section.

Every push to `dev` also produces downloadable builds (Actions → Dev build → artifacts, kept 14
days). PRs and `main` only run checks.

## Hotfixes

Only the latest stable line gets hotfixes. A hotfix skips the rc and uses the short "Hotfix"
checklist.

**No beta in progress** (`main` holds the stable release): PR the fix into `main`, then run
`patch` on `main`. Merge-back carries it to `dev`.

**A beta is in progress on `main`**: create the stable line's branch from its last tag, once:

```
gh api repos/{owner}/{repo}/git/refs -f ref=refs/heads/release/0.4 -f sha="$(git rev-parse v0.4.0^{commit})"
```

PR the fix into `release/0.4`, then run `patch` on `release/0.4`. Backport opens a PR that
cherry-picks the fix into `main` (or an issue, if it conflicts). `release/0.4` is deleted
automatically when `0.5.0` is released.

## Automation

| Workflow | Trigger | Does |
|----------|---------|------|
| `ci.yml` | PRs; pushes to `dev`, `main`, `release/**` | ruff, format check, pyright, pytest on Windows and Ubuntu; `hooks`: the git hooks on all files |
| `pr-title.yml` | PR opened/edited | required `pr-title` check: Conventional Commit title |
| `dco.yml` | PR opened/updated | required `dco` check: every commit signed off (automation branches skipped) |
| `release-checklist.yml` | release-prep PR opened/edited | required `checklist` check |
| `dev-build.yml` | push to `dev` | PyInstaller builds as artifacts |
| `prepare-release.yml` | manual | validates, bumps, changelog, opens the release PR |
| `tag-release.yml` | release-prep PR merged | tags; opens the dev bump PR (auto-merge); retires old `release/*` |
| `release.yml` | `v*` tag | validates the tag, builds, publishes the GitHub (pre-)release |
| `merge-back.yml` | push to `main` | PR `main → dev`; auto-resolves version-only conflicts and auto-merges |
| `backport.yml` | PR merged into `release/**` | cherry-pick PR into `main`, or an issue on conflict |
| `cleanup-branches.yml` | automation PR closed | deletes its branch |

Workflows that write act as a dedicated GitHub App: pushes and PRs made with the default
`GITHUB_TOKEN` would not trigger CI, and the App is the only actor allowed past the tag and
automation-branch rulesets.

### Merge-back conflicts

Merging `main` into `dev` always "conflicts" on the version line; the workflow keeps dev's
version, takes dev's `uv.lock` (then re-locks) and dev's `CHANGELOG.md` (it is regenerated at
every release anyway), and auto-merges. Any other conflict is left to you; the PR description
shows the commands. Merge, never rebase, and merge the PR with *Create a merge commit*.

## One-time setup

### 1. GitHub App

Settings → Developer settings → GitHub Apps → **New GitHub App**:

- Name: e.g. `rimlight-release`; Homepage URL: the repository URL.
- Webhook: untick **Active**.
- Repository permissions: **Contents**: read and write, **Pull requests**: read and write,
  **Issues**: read and write, **Workflows**: read and write (merge-back and backport push
  commits that may touch `.github/workflows/`). Everything else: no access.
- Where can this App be installed: **Only on this account**.

After creating it:

1. Note the **App ID** (for rulesets) and the **Client ID**.
2. **Generate a private key** (downloads a `.pem`).
3. **Install App** → only the `rimlight` repository.
4. In the repository: Settings → Secrets and variables → Actions:
   variable `APP_CLIENT_ID` = Client ID; secret `APP_PRIVATE_KEY` = contents of the `.pem`.
   Then delete the local `.pem` or keep it in a password manager.

### 2. Repository settings and rulesets

With an authenticated `gh` (admin on the repository):

```
bash scripts/github/configure-repo.sh
bash scripts/github/apply-rulesets.sh <app-id>
```

`configure-repo.sh` makes `dev` the default branch, allows squash and merge commits (no rebase
merges) and enables auto-merge. `apply-rulesets.sh` creates or updates the rulesets in
`.github/rulesets/`; edit those files and re-run it to change protection.
