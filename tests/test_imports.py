import importlib
import subprocess
import sys

import pytest

CORE_MODULES = [
    "rimlight",
    "rimlight.cli",
    "rimlight.app",
    "rimlight.device.ids",
    "rimlight.device.protocol",
    "rimlight.device.discovery",
    "rimlight.device.transport",
    "rimlight.device.manager",
    "rimlight.device.driver",
    "rimlight.device.drivers",
    "rimlight.device.registry",
    "rimlight.device.fake",
    "rimlight.capture.base",
    "rimlight.capture.factory",
    "rimlight.mapping",
    "rimlight.processing",
    "rimlight.power.events",
    "rimlight.power.factory",
    "rimlight.engine",
    "rimlight.config",
    "rimlight.ui",
]


@pytest.mark.parametrize("module", CORE_MODULES)
def test_core_module_imports(module: str) -> None:
    importlib.import_module(module)


@pytest.mark.parametrize(
    "module",
    [
        "rimlight.capture.windows_dxgi",
        "rimlight.capture.linux_x11",
        "rimlight.capture.linux_portal",
        "rimlight.power.windows",
        "rimlight.power.linux",
    ],
)
def test_platform_stubs_import_on_any_os(module: str) -> None:
    importlib.import_module(module)


@pytest.mark.slow
def test_core_does_not_import_qt() -> None:
    code = (
        "import importlib, sys\n"
        f"for m in {CORE_MODULES!r}: importlib.import_module(m)\n"
        "sys.exit(1 if any(n.startswith('PySide6') for n in sys.modules) else 0)\n"
    )
    result = subprocess.run([sys.executable, "-c", code], check=False)
    assert result.returncode == 0, "a core module imported PySide6"
