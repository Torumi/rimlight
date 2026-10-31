import pytest
from packaging.version import Version

from release_tools.versions import (
    ReleaseError,
    ReleaseKind,
    allowed_tag_branches,
    check_newer_than_tags,
    kind_of,
    parse_tag,
    parse_version,
    plan_version,
    post_release_bump,
    stale_release_branches,
    target_branch,
)

V = Version


@pytest.mark.parametrize(
    ("kind", "current", "branch", "expected"),
    [
        ("alpha", "0.5.0a3", "dev", "0.5.0a3"),  # dev already holds the next alpha
        ("beta", "0.5.0a3", "dev", "0.5.0b1"),  # promotion
        ("beta", "0.5.0b1", "main", "0.5.0b2"),
        ("rc", "0.5.0b2", "main", "0.5.0rc1"),
        ("rc", "0.5.0rc1", "main", "0.5.0rc2"),
        ("final", "0.5.0rc2", "main", "0.5.0"),
        ("patch", "0.5.0", "main", "0.5.1"),
        ("patch", "0.4.1", "release/0.4", "0.4.2"),
    ],
)
def test_plan_version(kind: ReleaseKind, current: str, branch: str, expected: str) -> None:
    assert plan_version(kind, V(current), branch) == V(expected)


@pytest.mark.parametrize(
    ("kind", "current", "branch", "message"),
    [
        ("alpha", "0.5.0a1", "main", "alpha releases run on dev"),
        ("beta", "0.4.0", "main", "starts by running 'beta' on dev"),
        ("rc", "0.5.0a1", "dev", "rc releases run on main"),
        ("final", "0.5.0b2", "main", "needs an rc"),
        ("patch", "0.5.0b2", "main", "beta line is in progress"),
        ("patch", "0.4.0", "release/0.3", "does not match"),
        ("patch", "0.4.0", "dev", "main or release/X.Y"),
    ],
)
def test_plan_version_rejects(kind: ReleaseKind, current: str, branch: str, message: str) -> None:
    with pytest.raises(ReleaseError, match=message):
        plan_version(kind, V(current), branch)


def test_promotion_targets_main() -> None:
    assert target_branch("beta", "dev") == "main"
    assert target_branch("beta", "main") == "main"
    assert target_branch("alpha", "dev") == "dev"


@pytest.mark.parametrize(
    ("released", "base", "expected"),
    [
        ("0.5.0a1", "dev", "0.5.0a2"),
        ("0.5.0b1", "main", "0.6.0a1"),  # promotion moves dev to the next minor
        ("0.5.0b2", "main", None),
        ("0.5.0", "main", None),
        ("0.4.1", "release/0.4", None),
    ],
)
def test_post_release_bump(released: str, base: str, expected: str | None) -> None:
    bump = post_release_bump(V(released), base)
    assert (str(bump) if bump else None) == expected


def test_newer_than_tags() -> None:
    tags = [V("0.4.0"), V("0.5.0b2")]
    check_newer_than_tags(V("0.5.0rc1"), tags)
    check_newer_than_tags(V("0.4.1"), tags)  # patches compare within their line
    with pytest.raises(ReleaseError, match="not newer"):
        check_newer_than_tags(V("0.5.0b2"), tags)
    with pytest.raises(ReleaseError, match="not newer"):
        check_newer_than_tags(V("0.4.0"), tags)


def test_kinds_and_branches() -> None:
    assert [kind_of(V(v)) for v in ("1.0.0a1", "1.0.0b1", "1.0.0rc1", "1.0.0", "1.0.1")] == [
        "alpha",
        "beta",
        "rc",
        "final",
        "patch",
    ]
    assert allowed_tag_branches(V("0.4.1")) == ("main", "release/0.4")
    assert allowed_tag_branches(V("0.5.0a1")) == ("dev",)


def test_parse() -> None:
    assert parse_tag("v0.5.0b1") == V("0.5.0b1")
    assert parse_tag("0.5.0") is None
    assert parse_tag("vnext") is None
    for bad in ("0.5", "0.5.0.dev1", "0.5.0+local", "nope"):
        with pytest.raises(ReleaseError):
            parse_version(bad)


def test_stale_release_branches() -> None:
    branches = ["main", "dev", "release/0.3", "release/0.4", "release/0.5", "release/x"]
    assert stale_release_branches(V("0.5.0"), branches) == ["release/0.3", "release/0.4"]
    assert stale_release_branches(V("0.5.0rc1"), branches) == []
