from dev_tools.roadmap import (
    ROADMAP_MD,
    Item,
    Milestone,
    Roadmap,
    issue_body,
    issue_labels,
    known_labels,
    load,
    md_disagreements,
    validate,
)


def test_roadmap_json_is_valid() -> None:
    assert validate(load(), known_labels()) == []


def test_roadmap_md_agrees_with_json() -> None:
    assert md_disagreements(load(), ROADMAP_MD.read_text(encoding="utf-8")) == []


def _item(moscow: str = "Could", milestone: str | None = None) -> Item:
    return Item("X1", moscow, milestone, "Do X", ("area: ui",), "Summary.", ("It works",))


def test_md_disagreement_is_reported() -> None:
    roadmap = load()
    first = roadmap.items[0]
    markdown = ROADMAP_MD.read_text(encoding="utf-8").replace(
        f"| {first.id} |", f"| {first.id}X |", 1
    )
    errors = md_disagreements(roadmap, markdown)
    assert f"{first.id}: missing from roadmap.md" in errors


def test_validate_catches_bad_items() -> None:
    roadmap = Roadmap(
        (Milestone("0.1", ""),),
        (_item("Must", None), _item("Could", "0.1"), _item("Sometime", "9.9")),
    )
    errors = validate(roadmap, {"enhancement", "area: ui", "help wanted"})
    assert any("duplicate id" in e for e in errors)
    assert any("Could items have no milestone" in e for e in errors)
    assert any("unknown milestone 9.9" in e for e in errors)
    assert any("MoSCoW must be one of" in e for e in errors)


def test_issue_labels_and_body() -> None:
    could = _item()
    assert issue_labels(could) == ["enhancement", "area: ui", "help wanted"]
    assert "help wanted" not in issue_labels(_item("Must", "0.1"))
    body = issue_body(could)
    assert body.startswith("<!-- roadmap:X1 -->\n")
    assert "- [ ] It works" in body
    assert "no milestone (help wanted)" in body
