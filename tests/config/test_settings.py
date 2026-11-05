from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from rimlight.config.settings import (
    FILE_NAME,
    DeviceSettings,
    LightSettings,
    RecoverySettings,
    Settings,
    default_path,
    load,
    parse,
    save,
)

# Differs from the defaults in every field, so a field that is not saved or read back shows up.
NON_DEFAULT = Settings(
    device=DeviceSettings(max_fps=30),
    light=LightSettings(color=(1, 128, 255), brightness=0.25, on=False),
    recovery=RecoverySettings(auto_reset=False),
)


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "nested" / FILE_NAME


@pytest.mark.parametrize("settings", [Settings(), NON_DEFAULT])
def test_round_trip(path: Path, settings: Settings) -> None:
    save(settings, path)
    result = load(path)
    assert result.settings == settings
    assert result.problems == ()


def _leaf_fields(model: BaseModel, prefix: str = "") -> dict[str, object]:
    leaves: dict[str, object] = {}
    for name in type(model).model_fields:
        value = getattr(model, name)
        if isinstance(value, BaseModel):
            leaves |= _leaf_fields(value, f"{prefix}{name}.")
        else:
            leaves[f"{prefix}{name}"] = value
    return leaves


def test_round_trip_sample_covers_every_setting() -> None:
    """A new setting must be added to NON_DEFAULT, which test_round_trip then covers."""
    defaults, sample = _leaf_fields(Settings()), _leaf_fields(NON_DEFAULT)
    assert [name for name in defaults if defaults[name] == sample[name]] == []


def test_missing_file_gives_defaults_without_problems(path: Path) -> None:
    result = load(path)
    assert result.settings == Settings()
    assert result.problems == ()


def test_saved_file_is_readable_toml(path: Path) -> None:
    save(Settings(light=LightSettings(color=(255, 136, 0))), path)
    text = path.read_text(encoding="utf-8")
    assert '[light]\ncolor = "#ff8800"' in text
    assert [p.name for p in path.parent.iterdir()] == [FILE_NAME]  # no temporary left


def test_partial_file_keeps_other_defaults() -> None:
    result = parse({"light": {"brightness": 1}})
    assert result.settings == Settings(light=LightSettings(brightness=1.0))
    assert result.problems == ()


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("device", "max_fps", 61),
        ("device", "max_fps", 0),
        ("light", "color", "red"),
        ("light", "color", "#12345"),
        ("light", "color", 5),
        ("light", "color", [1, 2, 3]),
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


def test_bad_values_do_not_lose_the_others() -> None:
    result = parse(
        {"device": {"max_fps": -1}, "light": {"on": "no", "brightness": 0.5}, "recovery": {}}
    )
    assert result.settings == Settings(light=LightSettings(brightness=0.5))
    assert len(result.problems) == 2


def test_file_with_the_removed_led_count_still_loads() -> None:
    """Earlier versions had this setting; the device reports the count now."""
    result = parse({"device": {"led_count": 57, "max_fps": 30}})
    assert result.settings == Settings(device=DeviceSettings(max_fps=30))
    assert result.problems == ("unknown setting device.led_count",)


def test_unknown_keys_and_sections_are_reported() -> None:
    result = parse({"future": {"x": 1}, "light": {"sparkle": True}, "device": 5})
    assert result.settings == Settings()
    assert "unknown setting future" in result.problems
    assert "unknown setting light.sparkle" in result.problems
    assert any(p.startswith("device:") for p in result.problems)
    assert len(result.problems) == 3


def test_settings_are_immutable_and_validated_in_code() -> None:
    with pytest.raises(ValidationError):
        LightSettings(brightness=2.0)
    with pytest.raises(ValidationError):
        NON_DEFAULT.light.on = True  # pyright: ignore[reportAttributeAccessIssue]


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
