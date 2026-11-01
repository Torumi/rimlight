"""Developer Certificate of Origin (https://developercertificate.org) sign-off checks.

Every non-merge commit must carry `Signed-off-by: Name <email>` with its author's email,
which `git commit -s` adds. See CONTRIBUTING.md.

Usage:
  python scripts/dev_tools/dco.py commit-msg <message-file>   # git commit-msg hook
  python scripts/dev_tools/dco.py pr <commits.json>           # CI, from
      gh api --paginate --slurp repos/OWNER/REPO/pulls/N/commits
"""

import json
import re
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

_SIGNOFF = re.compile(r"^Signed-off-by: .+? <(?P<email>[^<>]+)>\s*$", re.MULTILINE)
_IDENT_EMAIL = re.compile(r"<(?P<email>[^<>]+)>")

HOW_TO_FIX = """\
Sign off your commits to certify the Developer Certificate of Origin (see CONTRIBUTING.md):
  new commit:        git commit -s
  last commit:       git commit --amend --no-edit -s
  whole branch:      git rebase --signoff origin/dev   (then git push --force-with-lease)"""


@dataclass(frozen=True, slots=True)
class Commit:
    sha: str
    author_email: str
    message: str
    parent_count: int


def signoff_emails(message: str) -> set[str]:
    return {m["email"].strip().lower() for m in _SIGNOFF.finditer(message)}


def is_signed_by(message: str, author_email: str) -> bool:
    return author_email.strip().lower() in signoff_emails(message)


def unsigned(commits: Iterable[Commit]) -> list[Commit]:
    """Commits missing their author's sign-off. Merge commits are exempt."""
    return [
        c for c in commits if c.parent_count < 2 and not is_signed_by(c.message, c.author_email)
    ]


def commits_from_api(data: Any) -> list[Commit]:
    """Parse `gh api --paginate --slurp .../pulls/N/commits` (a list of pages) or one page."""
    pages = cast(list[Any], data)
    if pages and isinstance(pages[0], list):
        items = [item for page in pages for item in cast(list[Any], page)]
    else:
        items = pages
    commits: list[Commit] = []
    for raw in items:
        item = cast(dict[str, Any], raw)
        detail = cast(dict[str, Any], item["commit"])
        author = cast(dict[str, Any], detail["author"])
        commits.append(
            Commit(
                sha=str(item["sha"]),
                author_email=str(author["email"]),
                message=str(detail["message"]),
                parent_count=len(cast(list[Any], item["parents"])),
            )
        )
    return commits


def strip_comments(message: str) -> str:
    """Drop the `#` lines git removes from a commit message before committing."""
    return "\n".join(line for line in message.splitlines() if not line.startswith("#"))


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False)


def check_commit_msg(message_file: Path) -> int:
    if _git("rev-parse", "-q", "--verify", "MERGE_HEAD").returncode == 0:
        return 0  # merge commits are exempt
    ident = _git("var", "GIT_AUTHOR_IDENT").stdout
    match = _IDENT_EMAIL.search(ident)
    if match is None:
        print("dco: cannot determine the author email (git var GIT_AUTHOR_IDENT)")
        return 1
    message = strip_comments(message_file.read_text(encoding="utf-8"))
    if is_signed_by(message, match["email"]):
        return 0
    print(f"dco: commit message has no 'Signed-off-by:' for {match['email']}.\n{HOW_TO_FIX}")
    return 1


def check_pr(commits_file: Path) -> int:
    commits = commits_from_api(json.loads(commits_file.read_text(encoding="utf-8")))
    missing = unsigned(commits)
    for c in missing:
        subject = c.message.splitlines()[0] if c.message else ""
        print(f"::error::{c.sha[:7]} {subject!r} has no Signed-off-by for {c.author_email}")
    if missing:
        print(HOW_TO_FIX)
        return 1
    print(f"dco: all {len(commits)} commit(s) signed off")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "commit-msg":
        return check_commit_msg(Path(argv[1]))
    if len(argv) == 2 and argv[0] == "pr":
        return check_pr(Path(argv[1]))
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
