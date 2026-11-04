"""Architecture rules for src/rimlight/device (see docs/adding-a-device.md)."""

import ast
import importlib
from pathlib import Path

import pytest

import rimlight.device
from rimlight.device.drivers import BUILTIN_DRIVERS

DEVICE = Path(next(iter(rimlight.device.__path__)))
DRIVERS = DEVICE / "drivers"
DRIVERS_PACKAGE = "rimlight.device.drivers"
TEST_DOUBLES = "fake"

DEVICE_DIRS = sorted(p for p in DRIVERS.iterdir() if p.is_dir() and p.name != "__pycache__")
REAL_DEVICE_DIRS = [p for p in DEVICE_DIRS if p.name != TEST_DOUBLES]
SHARED_MODULES = sorted(DEVICE.glob("*.py"))

# protocol.py is pure: only these imports, so no transport, hidapi or other I/O.
PROTOCOL_ALLOWED_IMPORTS = {"collections", "dataclasses", "enum", "numpy", "struct", "typing"}


def _ids(paths: list[Path]) -> list[str]:
    return [p.name for p in paths]


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_there_is_a_real_device_and_the_test_doubles() -> None:
    assert REAL_DEVICE_DIRS
    assert TEST_DOUBLES in _ids(DEVICE_DIRS)


@pytest.mark.parametrize("device_dir", DEVICE_DIRS, ids=_ids(DEVICE_DIRS))
def test_device_directory_has_required_files(device_dir: Path) -> None:
    required = {"__init__.py", "driver.py"}
    if device_dir.name != TEST_DOUBLES:
        required.add("protocol.py")
    assert required <= {p.name for p in device_dir.iterdir()}


@pytest.mark.parametrize("device_dir", REAL_DEVICE_DIRS, ids=_ids(REAL_DEVICE_DIRS))
def test_real_device_is_registered(device_dir: Path) -> None:
    module = f"{DRIVERS_PACKAGE}.{device_dir.name}"
    importlib.import_module(module)
    assert any(d.__module__.startswith(f"{module}.") for d in BUILTIN_DRIVERS)


def test_test_doubles_are_not_registered() -> None:
    assert not any(
        d.__module__.startswith(f"{DRIVERS_PACKAGE}.{TEST_DOUBLES}") for d in BUILTIN_DRIVERS
    )


@pytest.mark.parametrize("module", SHARED_MODULES, ids=_ids(SHARED_MODULES))
def test_shared_modules_do_not_reach_into_device_directories(module: Path) -> None:
    device_imports = {i for i in _imports(module) if i.startswith(DRIVERS_PACKAGE)}
    if module.name == "registry.py":
        assert device_imports == {DRIVERS_PACKAGE}  # for BUILTIN_DRIVERS
    else:
        assert not device_imports


@pytest.mark.parametrize("device_dir", REAL_DEVICE_DIRS, ids=_ids(REAL_DEVICE_DIRS))
def test_protocol_is_pure(device_dir: Path) -> None:
    roots = {name.split(".")[0] for name in _imports(device_dir / "protocol.py")}
    assert roots <= PROTOCOL_ALLOWED_IMPORTS


@pytest.mark.parametrize("device_dir", DEVICE_DIRS, ids=_ids(DEVICE_DIRS))
def test_device_directories_do_not_import_each_other(device_dir: Path) -> None:
    own = f"{DRIVERS_PACKAGE}.{device_dir.name}"
    for path in device_dir.glob("*.py"):
        others = {
            i
            for i in _imports(path)
            if i.startswith(f"{DRIVERS_PACKAGE}.") and not i.startswith(own)
        }
        assert not others, path
