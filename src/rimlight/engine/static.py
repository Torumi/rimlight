"""Static color mode: one color and brightness, on or off.

The strip has no brightness or power commands, so both happen here in software.
"""

import numpy as np

from rimlight.device.driver import LedColors, solid
from rimlight.device.manager import FrameRenderer


def static_frame(color: tuple[int, int, int], brightness: float, on: bool) -> FrameRenderer:
    """A renderer for `DeviceManager.show`, which also re-applies it after every reconnect."""
    level = brightness if on else 0.0
    scaled = np.rint(np.array(color, dtype=np.float64) * level).astype(np.uint8)
    rgb = (int(scaled[0]), int(scaled[1]), int(scaled[2]))

    def render(led_count: int) -> LedColors:
        return solid(rgb, led_count)

    return render
