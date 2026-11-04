"""Sleep/resume experiments on the real strip, run by the maintainer (issue #21).

Finds out when the device stops answering after sleep and what brings it back. Sends only the
confirmed commands 0x03 (LED count) and 0x02 (color frame); see
docs/protocols/strip_37fa_8202.md.

Close the vendor app first (also from the tray), then for each scenario:

    uv run python scripts/dev_tools/verify_sleep.py a

and put the PC to sleep when told to. The result is printed after you wake it.

    a  handle open, no frames during sleep
    b  handle closed during sleep, opened after waking
    c  frames streaming into sleep, as the vendor app does (capture 08); stops at the first failure
    d  frames stream for a while, then stop and the handle closes before you put the PC to sleep
"""

import subprocess
import sys
import time
from collections.abc import Callable

from rimlight.device.driver import solid
from rimlight.device.drivers.strip_37fa_8202 import Strip37FA8202Driver
from rimlight.device.drivers.strip_37fa_8202.protocol import ProtocolError
from rimlight.device.registry import default_registry
from rimlight.device.transport import HidTransport, TransportError

GREEN = (0, 40, 0)
BLUE = (0, 0, 40)
FRAME_INTERVAL_S = 0.05
STREAM_BEFORE_CLOSING_S = 15
# time.time() jumps over a sleep, so a gap in a short loop means the PC slept.
WAKE_GAP_S = 5.0
SAME_HANDLE_PROBE_S = 60
NEW_HANDLE_PROBE_S = 90
PROBE_INTERVAL_S = 2.0


def connect() -> tuple[HidTransport, Strip37FA8202Driver]:
    """Open the strip and set up a driver for its reported length."""
    found = default_registry().find_supported()
    if not found:
        raise TransportError("device not enumerated")
    transport = HidTransport(found[0].info)
    transport.open()
    try:
        count = Strip37FA8202Driver(transport, 1).read_led_count()
        return transport, Strip37FA8202Driver(transport, count)
    except (TransportError, ProtocolError):
        transport.close()
        raise


def wait_for_wake(work: Callable[[], None] = lambda: time.sleep(0.5)) -> float:
    """Run `work` in a loop until the clock jumps. Returns the length of the sleep."""
    while True:
        before = time.time()
        work()
        gap = time.time() - before
        if gap > WAKE_GAP_S:
            return gap


def probe_same_handle(driver: Strip37FA8202Driver, seconds: float) -> float | None:
    """Seconds until the device answers on this handle, or None."""
    start = time.monotonic()
    while time.monotonic() - start < seconds:
        try:
            driver.read_led_count()
            return time.monotonic() - start
        except (TransportError, ProtocolError):
            time.sleep(PROBE_INTERVAL_S)
    return None


def probe_new_handle(seconds: float) -> float | None:
    """Seconds until a freshly opened handle gets an answer, or None."""
    start = time.monotonic()
    while time.monotonic() - start < seconds:
        try:
            transport, _ = connect()
            transport.close()
            return time.monotonic() - start
        except (TransportError, ProtocolError):
            time.sleep(PROBE_INTERVAL_S)
    return None


def probe_new_process() -> bool:
    result = subprocess.run([sys.executable, __file__, "probe"], check=False)
    return result.returncode == 0


def describe(seconds: float | None) -> str:
    return "NO ANSWER" if seconds is None else f"answered after {seconds:.0f} s"


def confirm_on_strip(results: dict[str, str]) -> None:
    """Whether an answer also means the strip works: show a frame the user can see."""
    try:
        transport, driver = connect()
    except (TransportError, ProtocolError) as exc:
        results["frame_after_recovery"] = f"could not connect: {exc}"
        return
    try:
        driver.show(solid(BLUE, driver.led_count))
        results["frame_acknowledged"] = "yes"
        results["strip_turned_blue"] = (
            input("Did the strip turn dim blue? ").strip() or "(no answer)"
        )
    except (TransportError, ProtocolError) as exc:
        results["frame_acknowledged"] = f"NO: {exc}"
    finally:
        transport.close()


def scenario_a(results: dict[str, str]) -> None:
    transport, driver = connect()
    try:
        driver.show(solid(GREEN, driver.led_count))
        print("Handle stays open, no more frames. Put the PC to sleep now, then wake it.")
        results["slept_s"] = f"{wait_for_wake():.0f}"
        answer = probe_same_handle(driver, SAME_HANDLE_PROBE_S)
        results["same_handle"] = describe(answer)
    finally:
        transport.close()
    if answer is None:
        results["new_handle"] = describe(probe_new_handle(NEW_HANDLE_PROBE_S))


def scenario_b(results: dict[str, str]) -> None:
    transport, driver = connect()
    driver.show(solid(GREEN, driver.led_count))
    transport.close()
    print("Handle closed. Put the PC to sleep now, then wake it.")
    results["slept_s"] = f"{wait_for_wake():.0f}"
    results["new_handle"] = describe(probe_new_handle(NEW_HANDLE_PROBE_S))


def scenario_c(results: dict[str, str]) -> None:
    transport, driver = connect()
    colors = solid(GREEN, driver.led_count)
    failures: list[str] = []

    def stream() -> None:
        try:
            driver.show(colors)
        except (TransportError, ProtocolError) as exc:
            if not failures:
                failures.append(str(exc))
            raise
        time.sleep(FRAME_INTERVAL_S)

    try:
        print("Frames are streaming. Put the PC to sleep now, then wake it.")
        results["slept_s"] = f"{wait_for_wake(stream):.0f}"
        results["frame_failure_around_sleep"] = failures[0] if failures else "none"
        answer = probe_same_handle(driver, SAME_HANDLE_PROBE_S)
        results["same_handle"] = describe(answer)
    finally:
        transport.close()
    if answer is None:
        results["new_handle"] = describe(probe_new_handle(NEW_HANDLE_PROBE_S))
    if answer is None and "NO ANSWER" in results["new_handle"]:
        results["new_process"] = "answered" if probe_new_process() else "NO ANSWER"


def scenario_d(results: dict[str, str]) -> None:
    transport, driver = connect()
    colors = solid(GREEN, driver.led_count)
    print(f"Streaming frames for {STREAM_BEFORE_CLOSING_S} s, please wait...")
    end = time.monotonic() + STREAM_BEFORE_CLOSING_S
    while time.monotonic() < end:
        driver.show(colors)
        time.sleep(FRAME_INTERVAL_S)
    transport.close()
    print("Frames stopped and handle closed. Put the PC to sleep now, then wake it.")
    results["slept_s"] = f"{wait_for_wake():.0f}"
    results["new_handle"] = describe(probe_new_handle(NEW_HANDLE_PROBE_S))


SCENARIOS: dict[str, Callable[[dict[str, str]], None]] = {
    "a": scenario_a,
    "b": scenario_b,
    "c": scenario_c,
    "d": scenario_d,
}


def main(argv: list[str]) -> int:
    if argv == ["probe"]:  # also the separate process of scenario c
        answer = probe_new_handle(NEW_HANDLE_PROBE_S)
        print(f"probe: {describe(answer)}")
        return 0 if answer is not None else 1
    if len(argv) != 1 or argv[0] not in SCENARIOS:
        print(__doc__)
        return 2
    scenario = argv[0]
    input("Close the vendor app (also from the tray), then press Enter. ")
    results = {"scenario": scenario}
    try:
        SCENARIOS[scenario](results)
    except (TransportError, ProtocolError) as exc:
        results["failed"] = str(exc)
    if "failed" not in results:
        confirm_on_strip(results)
    print("\nResults, please paste these back:")
    for key, value in results.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
