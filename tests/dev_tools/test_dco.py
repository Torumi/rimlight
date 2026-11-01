from typing import Any

from dev_tools.dco import Commit, commits_from_api, is_signed_by, strip_comments, unsigned

SIGNED = "feat: x\n\nSigned-off-by: Jane Doe <Jane@Example.org>\n"


def test_signoff_must_match_author_email_case_insensitively() -> None:
    assert is_signed_by(SIGNED, "jane@example.org")
    assert not is_signed_by(SIGNED, "someone@else.org")
    assert not is_signed_by("feat: x\n\nsigned-off-by: Jane <jane@example.org>", "jane@example.org")


def test_unsigned_skips_merge_commits() -> None:
    commits = [
        Commit("a" * 40, "jane@example.org", SIGNED, 1),
        Commit("b" * 40, "jane@example.org", "fix: y", 1),
        Commit("c" * 40, "jane@example.org", "Merge branch 'dev'", 2),
    ]
    assert [c.sha[0] for c in unsigned(commits)] == ["b"]


def _api_commit(sha: str, email: str, message: str, parents: int) -> dict[str, Any]:
    return {
        "sha": sha,
        "commit": {"author": {"email": email}, "message": message},
        "parents": [{"sha": "p"}] * parents,
    }


def test_commits_from_api_accepts_slurped_pages() -> None:
    pages = [[_api_commit("1", "a@b.c", "m1", 1)], [_api_commit("2", "a@b.c", "m2", 2)]]
    commits = commits_from_api(pages)
    assert [(c.sha, c.parent_count) for c in commits] == [("1", 1), ("2", 2)]
    assert commits_from_api([_api_commit("3", "a@b.c", "m3", 1)])[0].sha == "3"


def test_strip_comments() -> None:
    assert strip_comments("feat: x\n# Please enter\nSigned-off-by: A <a@b.c>") == (
        "feat: x\nSigned-off-by: A <a@b.c>"
    )
