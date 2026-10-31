"""Version arithmetic for the dev/main release flow (PEP 440)."""

from collections.abc import Iterable
from typing import Literal, get_args

from packaging.version import InvalidVersion, Version

type ReleaseKind = Literal["alpha", "beta", "rc", "final", "patch"]
RELEASE_KINDS: tuple[ReleaseKind, ...] = get_args(ReleaseKind.__value__)

DEV = "dev"
MAIN = "main"
RELEASE_BRANCH_PREFIX = "release/"

_PRE_KIND: dict[str, ReleaseKind] = {"a": "alpha", "b": "beta", "rc": "rc"}


class ReleaseError(Exception):
    """A release rule was violated; the message says which and what to do instead."""


def parse_version(text: str) -> Version:
    try:
        version = Version(text)
    except InvalidVersion as exc:
        raise ReleaseError(f"not a PEP 440 version: {text!r}") from exc
    if version.dev is not None or version.post is not None or version.local is not None:
        raise ReleaseError(f"dev/post/local versions are not released: {text}")
    if len(version.release) != 3 or version.epoch:
        raise ReleaseError(f"expected MAJOR.MINOR.PATCH: {text}")
    return version


def parse_tag(tag: str) -> Version | None:
    """`v0.4.0b1` -> Version; None for tags that are not release tags."""
    if not tag.startswith("v"):
        return None
    try:
        return parse_version(tag[1:])
    except ReleaseError:
        return None


def tag_name(version: Version) -> str:
    return f"v{version}"


def kind_of(version: Version) -> ReleaseKind:
    if version.pre is not None:
        return _PRE_KIND[version.pre[0]]
    return "final" if version.micro == 0 else "patch"


def is_prerelease(version: Version) -> bool:
    return version.pre is not None


def _base(version: Version) -> str:
    return version.base_version


def _with_pre(version: Version, letter: str, number: int) -> Version:
    return Version(f"{_base(version)}{letter}{number}")


def release_branch_for(version: Version) -> str:
    return f"{RELEASE_BRANCH_PREFIX}{version.major}.{version.minor}"


def is_promotion(kind: ReleaseKind, branch: str) -> bool:
    return kind == "beta" and branch == DEV


def target_branch(kind: ReleaseKind, branch: str) -> str:
    """Branch the release PR is opened against."""
    return MAIN if is_promotion(kind, branch) else branch


def plan_version(kind: ReleaseKind, current: Version, branch: str) -> Version:
    """Version to release for `kind`, run on `branch` whose pyproject says `current`.

    On dev, pyproject holds the next unreleased alpha; elsewhere it holds the last release.
    """
    current_kind = kind_of(current)
    match kind:
        case "alpha":
            _require_branch(kind, branch, DEV)
            if current_kind != "alpha":
                raise ReleaseError(f"dev must hold an alpha version, found {current}")
            return current
        case "beta" if branch == DEV:
            if current_kind != "alpha":
                raise ReleaseError(f"dev must hold an alpha version, found {current}")
            return _with_pre(current, "b", 1)
        case "beta":
            _require_branch(kind, branch, MAIN, DEV)
            if current_kind != "beta":
                raise ReleaseError(
                    f"main is at {current}; a new beta line starts by running 'beta' on dev"
                )
            return _with_pre(current, "b", _pre_number(current) + 1)
        case "rc":
            _require_branch(kind, branch, MAIN)
            if current_kind == "beta":
                return _with_pre(current, "rc", 1)
            if current_kind == "rc":
                return _with_pre(current, "rc", _pre_number(current) + 1)
            raise ReleaseError(f"rc needs a beta or rc on main, found {current}")
        case "final":
            _require_branch(kind, branch, MAIN)
            if current_kind != "rc":
                raise ReleaseError(f"final needs an rc on main first, found {current}")
            return Version(_base(current))
        case "patch":
            if branch != MAIN and not branch.startswith(RELEASE_BRANCH_PREFIX):
                raise ReleaseError(f"patch runs on main or release/X.Y, not {branch}")
            if current_kind not in ("final", "patch"):
                raise ReleaseError(
                    f"{branch} is at {current} (a beta line is in progress); "
                    f"hotfix the stable line on its release/X.Y branch instead"
                )
            if branch != MAIN and branch != release_branch_for(current):
                raise ReleaseError(f"{branch} does not match its version {current}")
            return Version(f"{current.major}.{current.minor}.{current.micro + 1}")


def post_release_bump(released: Version, base_branch: str) -> Version | None:
    """Version dev moves to after `released` was tagged, if any (dev holds the next alpha)."""
    if base_branch == DEV and kind_of(released) == "alpha":
        return _with_pre(released, "a", _pre_number(released) + 1)
    if base_branch == MAIN and released.pre == ("b", 1):
        return Version(f"{released.major}.{released.minor + 1}.0a1")
    return None


def check_newer_than_tags(new: Version, tags: Iterable[Version]) -> None:
    """New releases must sort above every existing one; patches only within their line."""
    if kind_of(new) == "patch":
        tags = [t for t in tags if t.release[:2] == new.release[:2]]
    newest = max(tags, default=None)
    if newest is not None and newest >= new:
        raise ReleaseError(f"{new} is not newer than existing release {newest}")


def allowed_tag_branches(version: Version) -> tuple[str, ...]:
    """Branches a tagged commit for `version` must be reachable from."""
    match kind_of(version):
        case "alpha":
            return (DEV,)
        case "beta" | "rc" | "final":
            return (MAIN,)
        case "patch":
            return (MAIN, release_branch_for(version))


def stale_release_branches(released: Version, branches: Iterable[str]) -> list[str]:
    """release/X.Y branches that stop being supported once `released` (a final) is out."""
    if kind_of(released) != "final":
        return []
    stale: list[str] = []
    for branch in branches:
        if not branch.startswith(RELEASE_BRANCH_PREFIX):
            continue
        major, _, minor = branch.removeprefix(RELEASE_BRANCH_PREFIX).partition(".")
        if (
            major.isdigit()
            and minor.isdigit()
            and (int(major), int(minor)) < (released.major, released.minor)
        ):
            stale.append(branch)
    return stale


def _pre_number(version: Version) -> int:
    assert version.pre is not None
    return version.pre[1]


def _require_branch(kind: ReleaseKind, branch: str, *allowed: str) -> None:
    if branch not in allowed:
        raise ReleaseError(f"{kind} releases run on {' or '.join(allowed)}, not {branch}")
