#!/usr/bin/env bash
# Apply the repository settings the release flow relies on (see docs/releasing.md).
#
# Usage: scripts/github/configure-repo.sh [owner/repo]
set -euo pipefail

repo="${1:-$(gh repo view --json nameWithOwner --jq .nameWithOwner)}"

# dev is the default branch: PRs target it and visitors land on the alpha line.
# Squash for feature PRs, merge commits for promotion and merge-back; rebase merges would
# rewrite history the merge-back flow depends on. Automation branches are deleted by the App
# (cleanup-branches.yml), not by GitHub, because rulesets protect them from deletion.
gh repo edit "$repo" \
  --default-branch dev \
  --enable-squash-merge \
  --enable-merge-commit \
  --enable-rebase-merge=false \
  --enable-auto-merge \
  --delete-branch-on-merge=false

echo "configured $repo"
