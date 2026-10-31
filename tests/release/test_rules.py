from datetime import UTC, datetime, timedelta

import pytest
from packaging.version import Version

from release_tools.rules import check_final, last_rc, resolve_version_conflicts, unchecked_items
from release_tools.versions import ReleaseError

NOW = datetime(2026, 11, 1, tzinfo=UTC)


def test_last_rc() -> None:
    tags = [Version(v) for v in ("0.5.0b1", "0.5.0rc1", "0.5.0rc2", "0.6.0rc1")]
    assert last_rc(Version("0.5.0"), tags) == Version("0.5.0rc2")
    with pytest.raises(ReleaseError, match="no release candidate"):
        last_rc(Version("0.7.0"), tags)


def test_final_allowed_after_soak_with_release_files_only() -> None:
    check_final(
        Version("0.5.0rc1"),
        NOW - timedelta(days=7),
        ["pyproject.toml", "uv.lock", "CHANGELOG.md"],
        NOW,
    )


def test_final_rejects_young_rc() -> None:
    with pytest.raises(ReleaseError, match="wait 2 more day"):
        check_final(Version("0.5.0rc1"), NOW - timedelta(days=5, hours=1), [], NOW)


def test_final_rejects_code_changes() -> None:
    with pytest.raises(ReleaseError, match=r"src/rimlight/cli\.py"):
        check_final(
            Version("0.5.0rc1"), NOW - timedelta(days=9), ["uv.lock", "src/rimlight/cli.py"], NOW
        )


def test_unchecked_items() -> None:
    body = "Intro\n- [x] Tests pass\n- [ ] Sleep/resume on Windows\n* [X] done\n  - [ ] Linux\n"
    assert unchecked_items(body) == ["Sleep/resume on Windows", "Linux"]


def test_resolve_version_conflict_keeps_ours() -> None:
    text = (
        "[project]\n"
        'name = "rimlight"\n'
        "<<<<<<< HEAD\n"
        'version = "0.6.0a1"\n'
        "=======\n"
        'version = "0.5.0b2"\n'
        ">>>>>>> origin/main\n"
        "dependencies = []\n"
    )
    assert resolve_version_conflicts(text) == (
        '[project]\nname = "rimlight"\nversion = "0.6.0a1"\ndependencies = []\n'
    )


def test_resolve_version_conflict_with_diff3_base() -> None:
    text = (
        "<<<<<<< ours\n"
        'version = "0.6.0a1"\n'
        "||||||| base\n"
        'version = "0.5.0a3"\n'
        "=======\n"
        'version = "0.5.0b2"\n'
        ">>>>>>> theirs\n"
    )
    assert resolve_version_conflicts(text) == 'version = "0.6.0a1"\n'


def test_resolve_refuses_other_conflicts() -> None:
    text = '<<<<<<< ours\nversion = "1"\n"numpy>=2"\n=======\nversion = "2"\n>>>>>>> theirs\n'
    assert resolve_version_conflicts(text) is None


def test_resolve_without_conflicts_is_identity() -> None:
    assert resolve_version_conflicts("a = 1\n") == "a = 1\n"
