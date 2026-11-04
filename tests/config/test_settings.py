from pathlib import Path

import pytest

from rimlight.config.settings import (
    FILE_NAME,
    Settings,
    default_path,
    load,
    parse,
    save,
)


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "nested" / FILE_NAME


@pytest.mark.parametrize(
    "settings",
    [
        Settings(),
        Settings(led_count=57, max_fps=30, color=(1, 128, 255), brightness=0.25, power_on=False),
    ],
)
def test_round_trip(path: Path, settings: Settings) -> None:
    save(settings, path)
    assert load(path).settings == settings
    assert load(path).problems == ()


def test_missing_file_gives_defaults_without_problems(path: Path) -> None:
    result = load(path)
    assert result.settings == Settings()
    assert result.problems == ()


def test_saved_file_is_readable_toml(path: Path) -> None:
    save(Settings(color=(255, 136, 0)), path)
    text = path.read_text(encoding="utf-8")
    assert '[light]\ncolor = "#ff8800"' in text
    assert "led_count" not in text  # None means "ask the device"
    assert [p.name for p in path.parent.iterdir()] == [FILE_NAME]  # no temporary left


def test_partial_file_keeps_other_defaults() -> None:
    result = parse({"light": {"brightness": 1}})
    assert result.settings == Settings(brightness=1.0)
    assert result.problems == ()


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("device", "led_count", 0),
        ("device", "led_count", "75"),
        ("device", "led_count", True),
        ("device", "max_fps", 61),
        ("device", "max_fps", 0),
        ("light", "color", "red"),
        ("light", "color", "#12345"),
        ("light", "color", 5),
        ("light", "brightness", 1.5),
        ("light", "brightness", -0.1),
        ("light", "brightness", True),
        ("light", "on", 1),
    ],
)
def test_invalid_values_are_reported_and_defaulted(section: str, key: str, value: object) -> None:
    result = parse({section: {key: value}})
    assert result.settings == Settings()
    assert len(result.problems) == 1
    assert f"{section}.{key}" in result.problems[0]


def test_one_bad_value_does_not_lose_the_others() -> None:
    result = parse({"device": {"led_count": -1, "max_fps": 30}})
    assert result.settings == Settings(max_fps=30)
    assert len(result.problems) == 1


def test_unknown_keys_and_sections_are_reported() -> None:
    result = parse({"future": {"x": 1}, "light": {"sparkle": True}, "device": 5})
    assert result.settings == Settings()
    assert result.problems == (
        "unknown section [future]",
        "unknown key light.sparkle",
        "device: expected a section",
    )


def test_invalid_toml_is_kept_for_the_user(path: Path) -> None:
    path.parent.mkdir(parents=True)
    path.write_text("not [valid toml", encoding="utf-8")
    result = load(path)
    assert result.settings == Settings()
    assert "not valid TOML" in result.problems[0]
    assert not path.exists()
    assert path.with_name(FILE_NAME + ".invalid").read_text(encoding="utf-8") == "not [valid toml"


def test_undecodable_file_is_reported(path: Path) -> None:
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\xff\xfe\x00")
    result = load(path)
    assert result.settings == Settings()
    assert "cannot read" in result.problems[0]


def test_default_path_is_per_user_config() -> None:
    assert default_path().name == FILE_NAME
    assert "rimlight" in default_path().parts
