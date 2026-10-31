"""Gate rules that are not plain version arithmetic."""

import re
from collections.abc import Iterable
from datetime import datetime, timedelta

from packaging.version import Version

from release_tools.versions import ReleaseError, kind_of

RC_MIN_AGE = timedelta(days=7)
RELEASE_ONLY_FILES = frozenset({"pyproject.toml", "uv.lock", "CHANGELOG.md"})

_CHECKBOX = re.compile(r"^\s*[-*]\s+\[(?P<mark>[ xX])\]\s+(?P<text>.+?)\s*$")
_VERSION_LINE = re.compile(r'^version\s*=\s*"[^"]*"\s*$')


def last_rc(final: Version, tags: Iterable[Version]) -> Version:
    rcs = [t for t in tags if kind_of(t) == "rc" and t.base_version == final.base_version]
    if not rcs:
        raise ReleaseError(f"{final} has no release candidate; release an rc first")
    return max(rcs)


def check_final(
    rc: Version, rc_date: datetime, changed_since_rc: Iterable[str], now: datetime
) -> None:
    """A final ships the last rc's code unchanged, after the rc soaked for RC_MIN_AGE."""
    age = now - rc_date
    if age < RC_MIN_AGE:
        days_left = (RC_MIN_AGE - age).days + 1
        raise ReleaseError(f"{rc} is only {age.days} day(s) old; wait {days_left} more day(s)")
    code_changes = sorted(set(changed_since_rc) - RELEASE_ONLY_FILES)
    if code_changes:
        raise ReleaseError(
            f"files changed since {rc}; release a new rc first: {', '.join(code_changes)}"
        )


def unchecked_items(markdown: str) -> list[str]:
    """Text of every unticked `- [ ]` item."""
    items: list[str] = []
    for line in markdown.splitlines():
        match = _CHECKBOX.match(line)
        if match and match["mark"] == " ":
            items.append(match["text"])
    return items


def resolve_version_conflicts(text: str) -> str | None:
    """Resolve merge conflicts that only touch `version = "..."` lines, keeping ours.

    Returns the resolved text, or None if any conflict touches anything else.
    """
    out: list[str] = []
    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        if not lines[i].startswith("<<<<<<< "):
            out.append(lines[i])
            i += 1
            continue
        ours: list[str] = []
        theirs: list[str] = []
        section = ours
        i += 1
        while i < len(lines) and not lines[i].startswith(">>>>>>> "):
            line = lines[i]
            if line.startswith("||||||| "):
                section = []  # diff3 base section: ignored
            elif line.rstrip("\r\n") == "=======":
                section = theirs
            else:
                section.append(line)
            i += 1
        if i == len(lines):
            return None  # unterminated conflict
        i += 1
        changed = [ln for ln in (*ours, *theirs) if ln.strip()]
        if not changed or not all(_VERSION_LINE.match(ln.strip()) for ln in changed):
            return None
        out.extend(ours)
    return "".join(out)
