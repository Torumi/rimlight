"""Settings model and TOML persistence.

Adding a setting means adding one field below; reading, validation and saving follow from it.

A settings file is edited by hand and may come from another version, so loading never fails:
invalid or unknown values are reported and the defaults used instead.
"""

import os
import re
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Any, Final, cast

import platformdirs
import tomli_w
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer, ValidationError

from rimlight.device.rate_limit import DEFAULT_MAX_FPS, MAX_ALLOWED_FPS

FILE_NAME: Final = "settings.toml"

_COLOR = re.compile(r"#[0-9a-fA-F]{6}")

type _Channel = Annotated[int, Field(ge=0, le=255)]


def _parse_color(value: Any) -> Any:
    """Accept "#ff8800" from the file; tuples pass through for code building settings."""
    if isinstance(value, str):
        if not _COLOR.fullmatch(value):
            raise ValueError('expected a color like "#ff8800"')
        return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))
    return value


def _format_color(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


type Color = Annotated[
    tuple[_Channel, _Channel, _Channel],
    BeforeValidator(_parse_color),
    PlainSerializer(_format_color),
]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")


class DeviceSettings(_Model):
    max_fps: int = Field(default=DEFAULT_MAX_FPS, ge=1, le=MAX_ALLOWED_FPS)


class LightSettings(_Model):
    color: Color = (255, 255, 255)
    brightness: float = Field(default=1.0, ge=0.0, le=1.0)
    on: bool = True


class RecoverySettings(_Model):
    auto_reset: bool = True
    """Restart a hung device automatically, if the restart task has been set up."""


class Settings(_Model):
    device: DeviceSettings = DeviceSettings()
    light: LightSettings = LightSettings()
    recovery: RecoverySettings = RecoverySettings()


class LoadResult(_Model):
    settings: Settings
    problems: tuple[str, ...] = ()
    """What was wrong with the file, for the log. Empty if it was fine or did not exist."""


def default_path() -> Path:
    return platformdirs.user_config_path("rimlight", appauthor=False, roaming=True) / FILE_NAME


def parse(data: Mapping[str, Any]) -> LoadResult:
    """Validate file contents, dropping only the values that are wrong."""
    remaining = {
        key: dict(cast(dict[str, Any], value)) if isinstance(value, dict) else value
        for key, value in data.items()
    }
    problems: dict[str, str] = {}
    while True:
        try:
            settings = Settings.model_validate(remaining)
            return LoadResult(settings=settings, problems=tuple(problems.values()))
        except ValidationError as exc:
            for error in exc.errors():
                # A setting is at most section.key: an error deeper than that drops all of it.
                location = [str(part) for part in error["loc"][:2]]
                name = ".".join(location)
                problems.setdefault(name, _describe(name, error["type"], error["msg"]))
                section = remaining.get(location[0])
                if len(location) == 2 and isinstance(section, dict):
                    cast(dict[str, Any], section).pop(location[1], None)
                else:
                    remaining.pop(location[0], None)


def _describe(name: str, error_type: str, message: str) -> str:
    if error_type == "extra_forbidden":
        return f"unknown setting {name}"
    return f"{name}: {message}; using the default"


def load(path: Path | None = None) -> LoadResult:
    """Read settings; a file that is not valid TOML is kept as `*.invalid` for the user."""
    path = path or default_path()
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return LoadResult(settings=Settings())
    except (OSError, UnicodeDecodeError) as exc:
        return LoadResult(settings=Settings(), problems=(f"cannot read {path.name}: {exc}",))
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        backup = path.with_name(path.name + ".invalid")
        os.replace(path, backup)
        problem = f"{path.name} is not valid TOML ({exc}); see {backup.name}"
        return LoadResult(settings=Settings(), problems=(problem,))
    return parse(data)


def save(settings: Settings, path: Path | None = None) -> None:
    """Write settings atomically, so a crash never leaves a half-written file."""
    path = path or default_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    data = settings.model_dump(mode="json", exclude_none=True)
    temporary.write_bytes(tomli_w.dumps(data).encode("utf-8"))
    os.replace(temporary, path)
