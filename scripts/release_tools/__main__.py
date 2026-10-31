"""CLI for the release workflows: `python -m release_tools <command>` (PYTHONPATH=scripts).

Results are printed and, inside GitHub Actions, also written to $GITHUB_OUTPUT.
"""

import argparse
import os
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from packaging.version import Version

from release_tools import gitio
from release_tools.rules import check_final, last_rc, resolve_version_conflicts, unchecked_items
from release_tools.versions import (
    RELEASE_KINDS,
    ReleaseError,
    allowed_tag_branches,
    check_newer_than_tags,
    is_prerelease,
    is_promotion,
    kind_of,
    parse_version,
    plan_version,
    post_release_bump,
    stale_release_branches,
    tag_name,
    target_branch,
)


def _emit(**outputs: str) -> None:
    for key, value in outputs.items():
        print(f"{key}={value}")
    if path := os.environ.get("GITHUB_OUTPUT"):
        with open(path, "a", encoding="utf-8") as fh:
            fh.writelines(f"{key}={value}\n" for key, value in outputs.items())


def _check_final_against(final: Version, ref: str) -> None:
    """Final rules, comparing the last rc tag with `ref` (HEAD or the final's own tag)."""
    tags = gitio.release_tags()
    rc = last_rc(final, tags)
    rc_tag = tags[rc]
    check_final(
        rc,
        gitio.commit_date(rc_tag),
        gitio.changed_files(rc_tag, ref),
        datetime.now(UTC),
    )


def cmd_plan(args: argparse.Namespace) -> None:
    current = gitio.project_version()
    if args.version:
        version = parse_version(args.version)
        if kind_of(version) != args.kind:
            raise ReleaseError(f"{version} is a {kind_of(version)} version, not {args.kind}")
    else:
        version = plan_version(args.kind, current, args.branch)
    check_newer_than_tags(version, gitio.release_tags())
    if args.kind == "final":
        _check_final_against(version, "HEAD")
    _emit(
        version=str(version),
        tag=tag_name(version),
        base=target_branch(args.kind, args.branch),
        head=f"release-prep/{version}",
        promotion=str(is_promotion(args.kind, args.branch)).lower(),
        prerelease=str(is_prerelease(version)).lower(),
    )


def cmd_check_tag(args: argparse.Namespace) -> None:
    version = parse_version(args.tag.removeprefix("v"))
    if (project := gitio.project_version()) != version:
        raise ReleaseError(f"tag {args.tag} does not match pyproject version {project}")
    others = [v for v in gitio.release_tags() if v != version]
    check_newer_than_tags(version, others)
    allowed = allowed_tag_branches(version)
    containing = gitio.remote_branches(contains=args.tag)
    if not set(allowed) & set(containing):
        raise ReleaseError(f"{args.tag} is not on {' or '.join(allowed)}")
    if kind_of(version) == "final":
        _check_final_against(version, args.tag)
    _emit(version=str(version), prerelease=str(is_prerelease(version)).lower())


def cmd_check_checklist(args: argparse.Namespace) -> None:
    unchecked = unchecked_items(Path(args.body_file).read_text(encoding="utf-8"))
    if unchecked:
        raise ReleaseError("unchecked release checklist items:\n- " + "\n- ".join(unchecked))


def cmd_post_bump(args: argparse.Namespace) -> None:
    bump = post_release_bump(parse_version(args.version), args.base)
    _emit(bump=str(bump) if bump else "")


def cmd_stale_branches(args: argparse.Namespace) -> None:
    stale = stale_release_branches(parse_version(args.version), gitio.remote_branches())
    _emit(branches=" ".join(stale))


def cmd_resolve_versions(args: argparse.Namespace) -> None:
    path = Path(args.file)
    resolved = resolve_version_conflicts(path.read_text(encoding="utf-8"))
    if resolved is None:
        raise ReleaseError(f"{path} has conflicts beyond the version line")
    path.write_text(resolved, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="release_tools", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("plan", help="compute and validate the next release")
    p.add_argument("--kind", choices=RELEASE_KINDS, required=True)
    p.add_argument("--branch", required=True)
    p.add_argument("--version", default="", help="explicit version override")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("check-tag", help="validate a pushed release tag")
    p.add_argument("tag")
    p.set_defaults(func=cmd_check_tag)

    p = sub.add_parser("check-checklist", help="fail on unticked checklist items")
    p.add_argument("--body-file", required=True)
    p.set_defaults(func=cmd_check_checklist)

    p = sub.add_parser("post-bump", help="version dev moves to after a release")
    p.add_argument("--version", required=True)
    p.add_argument("--base", required=True)
    p.set_defaults(func=cmd_post_bump)

    p = sub.add_parser("stale-branches", help="release/X.Y branches retired by a final")
    p.add_argument("--version", required=True)
    p.set_defaults(func=cmd_stale_branches)

    p = sub.add_parser("resolve-versions", help="resolve version-line-only merge conflicts")
    p.add_argument("file")
    p.set_defaults(func=cmd_resolve_versions)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except ReleaseError as exc:
        print(f"::error::{exc}" if os.environ.get("GITHUB_ACTIONS") else f"error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
