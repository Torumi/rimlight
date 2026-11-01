"""Roadmap issues and milestones from docs/roadmap.json.

Usage: uv run python scripts/dev_tools/roadmap.py [--dry-run] [owner/repo]

Creates missing milestones and one issue per roadmap item. Issues are found again by a hidden
`<!-- roadmap:ID -->` marker, so re-running is safe: existing issues get their title and
milestone updated and missing roadmap labels added; their body (ticked boxes, edits) and any
labels added by people are left alone. Closed issues stay closed.

Requires an authenticated `gh` with write access to the repository.
"""

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
ROADMAP_JSON = ROOT / "docs" / "roadmap.json"
ROADMAP_MD = ROOT / "docs" / "roadmap.md"
LABELS_JSON = ROOT / ".github" / "labels.json"

MOSCOW = ("Must", "Should", "Could")
MARKER = re.compile(r"<!-- roadmap:(?P<id>[A-Za-z0-9]+) -->")
_MD_ROW = re.compile(
    r"^\|\s*(?P<id>[A-Z]\d+[a-zL]?)\s*\|[^|]*\|\s*(?P<moscow>Must|Should|Could)\s*\|"
    r"\s*(?P<milestone>[0-9.]*)\s*\|",
    re.MULTILINE,
)


@dataclass(frozen=True, slots=True)
class Milestone:
    title: str
    description: str


@dataclass(frozen=True, slots=True)
class Item:
    id: str
    moscow: str
    milestone: str | None
    title: str
    labels: tuple[str, ...]
    summary: str
    done_when: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Roadmap:
    milestones: tuple[Milestone, ...]
    items: tuple[Item, ...]


def load(path: Path = ROADMAP_JSON) -> Roadmap:
    data = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    milestones = tuple(
        Milestone(str(m["title"]), str(m["description"]))
        for m in cast(list[dict[str, Any]], data["milestones"])
    )
    items = tuple(
        Item(
            id=str(i["id"]),
            moscow=str(i["moscow"]),
            milestone=None if i["milestone"] is None else str(i["milestone"]),
            title=str(i["title"]),
            labels=tuple(str(label) for label in cast(list[Any], i["labels"])),
            summary=str(i["summary"]),
            done_when=tuple(str(d) for d in cast(list[Any], i["done_when"])),
        )
        for i in cast(list[dict[str, Any]], data["items"])
    )
    return Roadmap(milestones, items)


def known_labels(path: Path = LABELS_JSON) -> set[str]:
    return {
        str(label["name"]) for label in cast(list[dict[str, Any]], json.loads(path.read_text()))
    }


def issue_labels(item: Item) -> list[str]:
    extra = ["help wanted"] if item.moscow == "Could" else []
    return ["enhancement", *item.labels, *extra]


def issue_body(item: Item) -> str:
    planned = f"milestone {item.milestone}" if item.milestone else "no milestone (help wanted)"
    lines = [
        f"<!-- roadmap:{item.id} -->",
        f"Roadmap item **{item.id}** · **{item.moscow}** for 1.0 · {planned}",
        "",
        item.summary,
        "",
        "### Done when",
        "",
        *(f"- [ ] {d}" for d in item.done_when),
        "",
        "See [docs/roadmap.md](https://github.com/Torumi/rimlight/blob/dev/docs/roadmap.md).",
    ]
    return "\n".join(lines) + "\n"


def validate(roadmap: Roadmap, labels: set[str]) -> list[str]:
    errors: list[str] = []
    titles = {m.title for m in roadmap.milestones}
    seen: set[str] = set()
    for item in roadmap.items:
        if item.id in seen:
            errors.append(f"{item.id}: duplicate id")
        seen.add(item.id)
        if item.moscow not in MOSCOW:
            errors.append(f"{item.id}: MoSCoW must be one of {MOSCOW}, not {item.moscow!r}")
        if (item.moscow == "Could") != (item.milestone is None):
            errors.append(f"{item.id}: Could items have no milestone, others need one")
        if item.milestone is not None and item.milestone not in titles:
            errors.append(f"{item.id}: unknown milestone {item.milestone}")
        errors.extend(
            f"{item.id}: unknown label {label!r}"
            for label in issue_labels(item)
            if label not in labels
        )
        if not item.done_when:
            errors.append(f"{item.id}: no done_when criteria")
    return errors


def md_disagreements(roadmap: Roadmap, markdown: str) -> list[str]:
    """Items whose MoSCoW or milestone differ between roadmap.json and roadmap.md."""
    rows = {m["id"]: (m["moscow"], m["milestone"] or None) for m in _MD_ROW.finditer(markdown)}
    errors: list[str] = []
    for item in roadmap.items:
        if item.id not in rows:
            errors.append(f"{item.id}: missing from roadmap.md")
        elif rows[item.id] != (item.moscow, item.milestone):
            errors.append(f"{item.id}: roadmap.md says {rows[item.id]}, roadmap.json says "
                          f"{(item.moscow, item.milestone)}")  # fmt: skip
    errors.extend(
        f"{row}: in roadmap.md but not in roadmap.json"
        for row in rows.keys() - {i.id for i in roadmap.items}
    )
    return errors


def _gh(*args: str, input_text: str | None = None) -> str:
    result = subprocess.run(
        ["gh", *args], input=input_text, check=True, capture_output=True, encoding="utf-8"
    )
    return result.stdout


def _gh_json(*args: str) -> list[dict[str, Any]]:
    pages = cast(list[list[dict[str, Any]]], json.loads(_gh("api", "--paginate", "--slurp", *args)))
    return [entry for page in pages for entry in page]


def apply(repo: str, roadmap: Roadmap, dry_run: bool) -> None:
    existing_ms = {str(m["title"]): m for m in _gh_json(f"repos/{repo}/milestones?state=all")}
    ms_numbers: dict[str, int] = {}
    for ms in roadmap.milestones:
        if ms.title in existing_ms:
            ms_numbers[ms.title] = int(existing_ms[ms.title]["number"])
            print(f"milestone {ms.title}: exists")
            continue
        print(f"milestone {ms.title}: create")
        if not dry_run:
            created = json.loads(
                _gh(
                    "api",
                    f"repos/{repo}/milestones",
                    "-f",
                    f"title={ms.title}",
                    "-f",
                    f"description={ms.description}",
                )
            )
            ms_numbers[ms.title] = int(cast(dict[str, Any], created)["number"])

    issues: dict[str, dict[str, Any]] = {}
    for issue in _gh_json(f"repos/{repo}/issues?state=all&per_page=100"):
        if "pull_request" in issue:
            continue
        match = MARKER.search(str(issue.get("body") or ""))
        if match:
            issues[match["id"]] = issue

    for item in roadmap.items:
        labels = issue_labels(item)
        milestone = ms_numbers.get(item.milestone) if item.milestone else None
        if item.id not in issues:
            print(f"issue {item.id}: create  {item.title}")
            if dry_run:
                continue
            payload: dict[str, Any] = {
                "title": item.title,
                "body": issue_body(item),
                "labels": labels,
            }
            if milestone is not None:
                payload["milestone"] = milestone
            _gh("api", f"repos/{repo}/issues", "--input", "-", input_text=json.dumps(payload))
            continue
        issue = issues[item.id]
        current = {str(label["name"]) for label in cast(list[dict[str, Any]], issue["labels"])}
        current_ms = cast(dict[str, Any] | None, issue.get("milestone"))
        patch: dict[str, Any] = {}
        if issue["title"] != item.title:
            patch["title"] = item.title
        if (None if current_ms is None else int(current_ms["number"])) != milestone:
            patch["milestone"] = milestone
        missing = [label for label in labels if label not in current]
        if missing:
            patch["labels"] = sorted(current | set(missing))
        action = f"update {sorted(patch)}" if patch else "ok"
        print(f"issue {item.id}: #{issue['number']} {action}")
        if patch and not dry_run:
            _gh(
                "api",
                "-X",
                "PATCH",
                f"repos/{repo}/issues/{issue['number']}",
                "--input",
                "-",
                input_text=json.dumps(patch),
            )


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    rest = [a for a in argv if a != "--dry-run"]
    roadmap = load()
    errors = validate(roadmap, known_labels()) + md_disagreements(
        roadmap, ROADMAP_MD.read_text(encoding="utf-8")
    )
    if errors:
        print("roadmap is inconsistent:\n- " + "\n- ".join(errors))
        return 1
    repo = (
        rest[0]
        if rest
        else _gh("repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner")
    )
    apply(repo.strip(), roadmap, dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
