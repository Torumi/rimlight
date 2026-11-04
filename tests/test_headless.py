import threading
from pathlib import Path

import numpy as np
import pytest

from rimlight.cli import main
from rimlight.config.settings import FILE_NAME, DeviceSettings, LightSettings, Settings, load, save
from rimlight.device.drivers.fake import FakeDriver, FakeTransport
from rimlight.device.manager import Connection, DeviceState
from rimlight.device.registry import default_registry
from rimlight.engine.static import static_frame
from rimlight.headless import available_resetter, run
from rimlight.power.events import PowerEvent, PowerEventCallback


class FakePower:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.callback: PowerEventCallback | None = None
        self.stopped = False

    def start(self, callback: PowerEventCallback) -> None:
        if self.error is not None:
            raise self.error
        self.callback = callback

    def stop(self) -> None:
        self.stopped = True


class FakeDevice:
    def __init__(self) -> None:
        self.transport = FakeTransport()
        self.driver = FakeDriver(self.transport, led_count=2)
        self.first_frame = threading.Event()
        self.connects = 0

    def connect(self) -> Connection:
        self.connects += 1
        self.transport.open()
        self.first_frame.set()
        return Connection(self.transport, self.driver)


def _wait_for_frame(device: FakeDevice) -> None:
    assert device.first_frame.wait(5)
    for _ in range(500):
        if device.driver.frames:
            return
        threading.Event().wait(0.01)
    pytest.fail("no frame shown")


@pytest.mark.parametrize(
    ("color", "brightness", "on", "expected"),
    [
        ((255, 136, 0), 1.0, True, [255, 136, 0]),
        ((200, 100, 50), 0.5, True, [100, 50, 25]),
        ((255, 255, 255), 0.0, True, [0, 0, 0]),
        ((255, 255, 255), 1.0, False, [0, 0, 0]),
    ],
)
def test_static_frame(
    color: tuple[int, int, int], brightness: float, on: bool, expected: list[int]
) -> None:
    frame = static_frame(color, brightness, on)(3)
    assert frame.dtype == np.uint8
    assert frame.tolist() == [expected] * 3


def test_run_shows_the_configured_light_and_closes_the_device() -> None:
    device = FakeDevice()
    power = FakePower()
    settings = Settings(light=LightSettings(color=(10, 20, 30), brightness=0.5))
    run(
        settings,
        device.connect,
        wait=lambda: _wait_for_frame(device),
        resetter=None,
        power=power,
    )
    assert device.driver.frames[0].tolist() == [[5, 10, 15]] * 2
    assert not device.transport.is_open
    assert power.stopped


def test_resume_events_reach_the_manager() -> None:
    device = FakeDevice()
    power = FakePower()
    states: list[DeviceState] = []

    def wait() -> None:
        _wait_for_frame(device)
        assert power.callback is not None
        power.callback(PowerEvent.SLEEP)
        power.callback(PowerEvent.RESUME)

    run(
        Settings(),
        device.connect,
        wait=wait,
        resetter=None,
        power=power,
        on_state=states.append,
    )
    assert DeviceState.CONNECTED in states


@pytest.mark.parametrize("error", [NotImplementedError(), OSError("no events")])
def test_missing_power_events_are_not_fatal(error: Exception) -> None:
    device = FakeDevice()
    run(
        Settings(),
        device.connect,
        wait=lambda: _wait_for_frame(device),
        resetter=None,
        power=FakePower(error),
    )
    assert device.driver.frames


class FakeResetter:
    def __init__(self, installed: bool) -> None:
        self.installed = installed

    def is_installed(self) -> bool:
        return self.installed

    def reset(self) -> None:
        pass


@pytest.mark.parametrize(
    ("auto_reset", "installed", "used"),
    [(True, True, True), (True, False, False), (False, True, False)],
)
def test_resetter_needs_the_setting_and_the_task(
    monkeypatch: pytest.MonkeyPatch, auto_reset: bool, installed: bool, used: bool
) -> None:
    resetter = FakeResetter(installed)

    def create(_match: object) -> FakeResetter:
        return resetter

    monkeypatch.setattr("rimlight.headless.create_resetter", create)
    settings = Settings.model_validate({"recovery": {"auto_reset": auto_reset}})
    assert (available_resetter(default_registry(), settings) is resetter) == used


@pytest.fixture
def settings_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / FILE_NAME
    monkeypatch.setattr("rimlight.config.settings.default_path", lambda: path)
    return path


def test_cli_set_changes_only_what_is_given(settings_path: Path) -> None:
    save(Settings(device=DeviceSettings(max_fps=30)), settings_path)
    assert main(["set", "--color", "#ff8800"]) == 0
    assert main(["set", "--brightness", "50", "--off"]) == 0
    settings = load(settings_path).settings
    assert settings.device.max_fps == 30
    assert settings.light == LightSettings(color=(255, 136, 0), brightness=0.5, on=False)
    assert main(["set", "--on"]) == 0
    assert load(settings_path).settings.light.on is True


@pytest.mark.parametrize(
    "arguments", [["--color", "red"], ["--brightness", "101"], ["--brightness", "-1"]]
)
def test_cli_set_rejects_bad_values(
    settings_path: Path, capsys: pytest.CaptureFixture[str], arguments: list[str]
) -> None:
    assert main(["set", *arguments]) == 1
    assert "Invalid" in capsys.readouterr().err
    assert not settings_path.exists()


def test_cli_set_needs_something_to_set(
    settings_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["set"]) == 1
    assert "Nothing to set" in capsys.readouterr().err


def test_cli_run_reports_state_and_stops_on_ctrl_c(
    settings_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_run(
        settings: Settings, registry: object, *, resetter: object, wait: object, on_state: object
    ) -> None:
        assert resetter is None
        assert callable(on_state)
        on_state(DeviceState.CONNECTED)

    def no_resetter(registry: object, settings: object) -> None:
        return None

    monkeypatch.setattr("rimlight.headless.run_with_defaults", fake_run)
    monkeypatch.setattr("rimlight.headless.available_resetter", no_resetter)
    monkeypatch.setattr("rimlight.logs.setup_logging", lambda: Path("x.log"))
    monkeypatch.setattr("rimlight.logs.stop_logging", lambda: None)
    assert main(["run"]) == 0
    out = capsys.readouterr().out
    assert "CONNECTED" in out
    assert "restart of a hung device: off" in out
