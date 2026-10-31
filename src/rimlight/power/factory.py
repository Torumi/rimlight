"""Construct the power event source for the running platform."""

import sys

from rimlight.power.events import PowerEventSource


def create_power_source(platform: str = sys.platform) -> PowerEventSource:
    if platform == "win32":
        from rimlight.power.windows import WindowsPowerSource

        return WindowsPowerSource()
    if platform.startswith("linux"):
        from rimlight.power.linux import LogindPowerSource

        return LogindPowerSource()
    raise RuntimeError(f"unsupported platform: {platform}")
