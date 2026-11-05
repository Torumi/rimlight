from pathlib import Path

import pytest

from rimlight.cli import main
from rimlight.config.settings import FILE_NAME, RecoverySettings, Settings, load, save


class FakeResetter:
    def __init__(self, installed: bool = False, error: OSError | None = None) -> None:
        self.installed = installed
        self.error = error
        self.calls: list[str] = []

    def is_installed(self) -> bool:
        return self.installed

    def install(self) -> None:
        self.calls.append("install")
        if self.error is not None:
            raise self.error
        self.installed = True

    def uninstall(self) -> None:
        self.calls.append("uninstall")
        self.installed = False


@pytest.fixture
def settings_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / FILE_NAME
    monkeypatch.setattr("rimlight.config.settings.default_path", lambda: path)
    return path


def _use(monkeypatch: pytest.MonkeyPatch, resetter: FakeResetter | None) -> None:
    def create(_match: object) -> FakeResetter | None:
        return resetter

    monkeypatch.setattr("rimlight.device.reset.create_resetter", create)


def test_enable_installs_the_task_and_turns_it_on(
    settings_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    resetter = FakeResetter()
    _use(monkeypatch, resetter)
    save(Settings(recovery=RecoverySettings(auto_reset=False)), settings_path)
    assert main(["recovery", "enable"]) == 0
    assert resetter.calls == ["install"]
    assert load(settings_path).settings.recovery.auto_reset is True
    out = capsys.readouterr().out
    assert "ask for permission" in out
    assert "4348:55E0" in out  # restarting another ID is a thing the user should know about


def test_enable_with_the_task_present_asks_nothing(
    settings_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resetter = FakeResetter(installed=True)
    _use(monkeypatch, resetter)
    assert main(["recovery", "enable"]) == 0
    assert resetter.calls == []


def test_refused_prompt_is_reported_and_changes_nothing(
    settings_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _use(monkeypatch, FakeResetter(error=OSError("exit code 1")))
    assert main(["recovery", "enable"]) == 1
    assert "exit code 1" in capsys.readouterr().err
    assert not settings_path.exists()


def test_disable_keeps_the_task_and_needs_no_elevation(
    settings_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resetter = FakeResetter(installed=True)
    _use(monkeypatch, resetter)
    assert main(["recovery", "disable"]) == 0
    assert resetter.calls == []
    assert resetter.installed
    assert load(settings_path).settings.recovery.auto_reset is False


def test_remove_deletes_the_task(settings_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    resetter = FakeResetter(installed=True)
    _use(monkeypatch, resetter)
    assert main(["recovery", "remove"]) == 0
    assert resetter.calls == ["uninstall"]
    assert load(settings_path).settings.recovery.auto_reset is False


def test_status(
    settings_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _use(monkeypatch, FakeResetter())
    assert main(["recovery", "status"]) == 0
    assert "Automatic restart: on; restart task: not installed." in capsys.readouterr().out
    assert not settings_path.exists()


def test_other_settings_survive(settings_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _use(monkeypatch, FakeResetter(installed=True))
    save(Settings.model_validate({"device": {"max_fps": 30}}), settings_path)
    assert main(["recovery", "disable"]) == 0
    assert load(settings_path).settings.device.max_fps == 30


def test_unavailable_platform(
    settings_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _use(monkeypatch, None)
    assert main(["recovery", "enable"]) == 1
    assert "not available" in capsys.readouterr().err
