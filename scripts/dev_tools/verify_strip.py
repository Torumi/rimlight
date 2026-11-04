"""Interactive check of docs/protocols/strip_37fa_8202.md on the real strip, run by the maintainer.

Answers the spec's open questions and confirms the "likely" reports. Sends only the documented
commands 0x03 (LED count) and 0x02 (color frame); the queries 06-0c are never sent.

Close the vendor app first, then: uv run python scripts/dev_tools/verify_strip.py
"""

import sys
import time

import numpy as np

from rimlight.device.driver import LedColors, solid
from rimlight.device.drivers.strip_37fa_8202 import Strip37FA8202Driver
from rimlight.device.registry import default_registry
from rimlight.device.transport import DeviceNotRespondingError, HidTransport

FRAME_INTERVAL_S = 0.05  # the vendor app's pace is about 21 frames per second


def stream(driver: Strip37FA8202Driver, colors: LedColors, seconds: float) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        driver.show(colors)
        time.sleep(FRAME_INTERVAL_S)


def ask(results: dict[str, str], key: str, question: str) -> None:
    results[key] = input(f"{question} ").strip() or "(no answer)"


def run(driver: Strip37FA8202Driver, count: int, results: dict[str, str]) -> None:
    print("\nStep 1: solid colors, 3 seconds each.")
    for name, rgb in (("red", (255, 0, 0)), ("green", (0, 255, 0)), ("blue", (0, 0, 255))):
        print(f"  Showing {name}...")
        stream(driver, solid(rgb, count), 3)
        ask(results, f"color_{name}", f"  What color was the strip (expected {name})?")

    print("\nStep 2: first and last LED only: LED 0 red, last LED blue.")
    ends = solid((0, 0, 0), count)
    ends[0] = (255, 0, 0)
    ends[-1] = (0, 0, 255)
    stream(driver, ends, 4)
    ask(results, "ends", "  Did the two physical ends of the strip light up (red, blue)?")

    print("\nStep 3: LED order, a green dot walks along the strip.")
    for i in range(count):
        dot = np.zeros((count, 3), dtype=np.uint8)
        dot[i] = (0, 255, 0)
        driver.show(dot)
        time.sleep(FRAME_INTERVAL_S)
    ask(results, "walk", "  Where did it start, and which way did it go (seen from the front)?")

    print("\nStep 4: dark frames: 0f 0f 0f for 3 s, then 00 00 00 for 3 s.")
    stream(driver, solid((15, 15, 15), count), 3)
    print("  Now all zeros...")
    stream(driver, solid((0, 0, 0), count), 3)
    ask(results, "dark", "  Was the strip lit in either phase? Which one looked off?")

    print("\nStep 5: one white frame, then no frames for 15 seconds.")
    driver.show(solid((255, 255, 255), count))
    start = time.monotonic()
    time.sleep(15)
    ask(
        results,
        "no_stream",
        "  Did it stay white the whole time? If not, when did it change?",
    )
    try:
        driver.show(solid((0, 0, 0), count))
        results["ack_after_pause"] = f"yes, after {time.monotonic() - start:.0f} s"
    except DeviceNotRespondingError:
        results["ack_after_pause"] = "NO"


def main() -> int:
    found = default_registry().find_supported()
    if not found:
        print("Strip not found. Is it plugged in?")
        return 1
    input("Close the vendor app (also from the tray), then press Enter. ")

    results: dict[str, str] = {}
    transport = HidTransport(found[0].info)
    with transport:
        count = Strip37FA8202Driver(transport, 1).read_led_count()
        results["led_count"] = str(count)
        print(f"Device reports {count} LEDs.")
        driver = Strip37FA8202Driver(transport, count)
        driver.initialize()
        try:
            driver.show(solid((0, 0, 0), count))
            results["frames_after_03_only"] = "yes"
        except DeviceNotRespondingError:
            results["frames_after_03_only"] = "NO: no answer to a frame"
            print("The device did not answer a frame after 0x03 alone. Stopping here.")
        else:
            try:
                run(driver, count, results)
            finally:
                driver.show(solid((0, 0, 0), count))

    print("\nResults, please paste these back:")
    for key, value in results.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
