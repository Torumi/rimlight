import pytest

from rimlight.capture.base import CaptureUnavailableError
from rimlight.capture.factory import create_capture_backend, select_backend_name


@pytest.mark.parametrize(
    ("platform", "env", "expected"),
    [
        ("win32", {}, "windows_dxgi"),
        ("linux", {"XDG_SESSION_TYPE": "wayland"}, "linux_portal"),
        ("linux", {"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}, "linux_portal"),
        ("linux", {"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0"}, "linux_x11"),
    ],
)
def test_select_backend_name(platform: str, env: dict[str, str], expected: str) -> None:
    assert select_backend_name(platform, env) == expected


@pytest.mark.parametrize(("platform", "env"), [("linux", {}), ("darwin", {"DISPLAY": ":0"})])
def test_select_backend_name_unavailable(platform: str, env: dict[str, str]) -> None:
    with pytest.raises(CaptureUnavailableError):
        select_backend_name(platform, env)


def test_create_backend_by_name() -> None:
    assert create_capture_backend("linux_x11").name == "linux_x11"
