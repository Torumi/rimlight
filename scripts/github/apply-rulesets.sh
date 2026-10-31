#!/usr/bin/env bash
# Create or update the repository rulesets from .github/rulesets/*.json.
#
# Usage: scripts/github/apply-rulesets.sh <app-id> [owner/repo]
#   app-id      numeric ID of the release GitHub App (App settings page, "App ID")
#   owner/repo  defaults to the repository of the current checkout
#
# Rulesets are matched by name: existing ones are replaced, missing ones are created.
# Requires an authenticated `gh` with admin rights on the repository.
set -euo pipefail

app_id="${1:?usage: $0 <app-id> [owner/repo]}"
repo="${2:-$(gh repo view --json nameWithOwner --jq .nameWithOwner)}"
dir="$(cd "$(dirname "$0")/../../.github/rulesets" && pwd)"

if ! [[ "$app_id" =~ ^[0-9]+$ ]]; then
  echo "app-id must be numeric, got: $app_id" >&2
  exit 1
fi

existing="$(gh api "repos/$repo/rulesets" --paginate --jq '.[] | "\(.name)\t\(.id)"')"

for file in "$dir"/*.json; do
  body="$(sed "s/\"__APP_ID__\"/$app_id/g" "$file")"
  name="$(basename "$file" .json)" # file name == ruleset "name"
  id="$(awk -F'\t' -v n="$name" '$1 == n {print $2}' <<<"$existing")"
  if [ -n "$id" ]; then
    echo "update  $name (#$id)"
    gh api -X PUT "repos/$repo/rulesets/$id" --input - <<<"$body" >/dev/null
  else
    echo "create  $name"
    gh api -X POST "repos/$repo/rulesets" --input - <<<"$body" >/dev/null
  fi
done
