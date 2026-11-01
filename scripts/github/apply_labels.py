"""Create or update the repository's issue labels from .github/labels.json.

Usage: uv run python scripts/github/apply_labels.py [--prune] [owner/repo]
  --prune     also delete labels that are not in labels.json (asks no questions; review first)
  owner/repo  defaults to the repository of the current checkout

Requires an authenticated `gh` with write access to the repository.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

LABELS_FILE = Path(__file__).resolve().parents[2] / ".github" / "labels.json"


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def main(argv: list[str]) -> int:
    prune = "--prune" in argv
    rest = [a for a in argv if a != "--prune"]
    repo = (
        rest[0] if rest else gh("repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner")
    )
    repo = repo.strip()

    wanted = cast(list[dict[str, str]], json.loads(LABELS_FILE.read_text(encoding="utf-8")))
    existing = cast(
        list[dict[str, Any]],
        json.loads(gh("label", "list", "--repo", repo, "--limit", "500", "--json", "name")),
    )
    existing_names = {str(label["name"]) for label in existing}

    for label in wanted:
        name = label["name"]
        gh(
            "label", "create", name, "--repo", repo, "--force",
            "--color", label["color"], "--description", label["description"],
        )  # fmt: skip
        print(f"{'update' if name in existing_names else 'create'}  {name}")

    extra = sorted(existing_names - {label["name"] for label in wanted})
    for name in extra:
        if prune:
            gh("label", "delete", name, "--repo", repo, "--yes")
            print(f"delete  {name}")
        else:
            print(f"extra   {name}  (not in labels.json; --prune deletes it)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
