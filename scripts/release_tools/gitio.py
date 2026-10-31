"""Thin git and filesystem wrappers. Everything here shells out; keep logic elsewhere."""

import subprocess
import tomllib
from datetime import datetime
from pathlib import Path

from packaging.version import Version

from release_tools.versions import parse_tag, parse_version


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def release_tags() -> dict[Version, str]:
    tags: dict[Version, str] = {}
    for tag in git("tag", "--list", "v*").splitlines():
        version = parse_tag(tag)
        if version is not None:
            tags[version] = tag
    return tags


def commit_date(ref: str) -> datetime:
    return datetime.fromisoformat(git("log", "-1", "--format=%cI", ref))


def changed_files(base: str, head: str) -> list[str]:
    return git("diff", "--name-only", base, head).splitlines()


def remote_branches(contains: str | None = None) -> list[str]:
    args = ["branch", "--remotes", "--format=%(refname:short)"]
    if contains is not None:
        args += ["--contains", contains]
    names = git(*args).splitlines()
    return [n.removeprefix("origin/") for n in names if n.startswith("origin/") and n != "origin"]


def project_version(pyproject: Path = Path("pyproject.toml")) -> Version:
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return parse_version(str(data["project"]["version"]))
