"""Settings model and TOML persistence.

A settings file is edited by hand and may come from another version, so loading never fails:
invalid or unknown values are reported and the defaults used instead.
"""

import os
import re
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final, cast

import platformdirs
import tomli_w

FILE_NAME: Final = "settings.toml"
# The hardware-safety cap: see device/rate_limit.py.
MAX_ALLOWED_FPS: Final = 60

_COLOR = re.compile(r"#[0-9a-fA-F]{6}")

type Rgb = tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class Settings:
    led_count: int | None = None
    """LEDs on the strip; None uses the count the device reports."""
    max_fps: int = MAX_ALLOWED_FPS
    color: Rgb = (255, 255, 255)
    brightness: float = 1.0
    """0.0-1.0."""
    power_on: bool = True


@dataclass(frozen=True, slots=True)
class LoadResult:
    settings: Settings
    problems: tuple[str, ...] = ()
    """What was wrong with the file, for the log. Empty if it was fine or did not exist."""


def default_path() -> Path:
    return platformdirs.user_config_path("rimlight", appauthor=False, roaming=True) / FILE_NAME


def _int_in(low: int, high: int) -> Callable[[Any], int]:
    def parse(value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ValueError(f"expected an integer {low}..{high}")
        return value

    return parse


def _brightness(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not 0 <= value <= 1:
        raise ValueError("expected a number 0.0..1.0")
    return float(value)


def _color(value: Any) -> Rgb:
    if not isinstance(value, str) or not _COLOR.fullmatch(value):
        raise ValueError('expected a color like "#ff8800"')
    return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))


def _bool(value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValueError("expected true or false")
    return value


# TOML section and key -> Settings field and parser.
_FIELDS: Final[dict[str, dict[str, tuple[str, Callable[[Any], Any]]]]] = {
    "device": {
        "led_count": ("led_count", _int_in(1, 10_000)),
        "max_fps": ("max_fps", _int_in(1, MAX_ALLOWED_FPS)),
    },
    "light": {
        "color": ("color", _color),
        "brightness": ("brightness", _brightness),
        "on": ("power_on", _bool),
    },
}


def parse(data: Mapping[str, Any]) -> LoadResult:
    settings = Settings()
    problems: list[str] = []
    for section, value in data.items():
        fields = _FIELDS.get(section)
        if fields is None:
            problems.append(f"unknown section [{section}]")
        elif not isinstance(value, dict):
            problems.append(f"{section}: expected a section")
        else:
            for key, raw in cast(dict[str, Any], value).items():
                if key not in fields:
                    problems.append(f"unknown key {section}.{key}")
                    continue
                field, parser = fields[key]
                try:
                    settings = replace(settings, **{field: parser(raw)})
                except ValueError as exc:
                    problems.append(f"{section}.{key}: {exc}, got {raw!r}; using the default")
    return LoadResult(settings, tuple(problems))


def load(path: Path | None = None) -> LoadResult:
    """Read settings; a file that is not valid TOML is kept as `*.invalid` for the user."""
    path = path or default_path()
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return LoadResult(Settings())
    except (OSError, UnicodeDecodeError) as exc:
        return LoadResult(Settings(), (f"cannot read {path.name}: {exc}",))
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        backup = path.with_name(path.name + ".invalid")
        os.replace(path, backup)
        return LoadResult(
            Settings(), (f"{path.name} is not valid TOML ({exc}); see {backup.name}",)
        )
    return parse(data)


def to_toml_data(settings: Settings) -> dict[str, dict[str, Any]]:
    r, g, b = settings.color
    device: dict[str, Any] = {"max_fps": settings.max_fps}
    if settings.led_count is not None:
        device["led_count"] = settings.led_count
    return {
        "device": device,
        "light": {
            "color": f"#{r:02x}{g:02x}{b:02x}",
            "brightness": settings.brightness,
            "on": settings.power_on,
        },
    }


def save(settings: Settings, path: Path | None = None) -> None:
    """Write settings atomically, so a crash never leaves a half-written file."""
    path = path or default_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(tomli_w.dumps(to_toml_data(settings)).encode("utf-8"))
    os.replace(temporary, path)
