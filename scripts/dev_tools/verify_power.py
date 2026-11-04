"""Prints sleep and resume events as they arrive, run by the maintainer (issue #21).

Does not touch the strip. Run it from a normal terminal, put the PC to sleep, wake it, wait a few
seconds, then press Ctrl+C:

    uv run python scripts/dev_tools/verify_power.py
"""

import sys
import time
from datetime import datetime

from rimlight.power.events import PowerEvent
from rimlight.power.factory import create_power_source


def print_event(event: PowerEvent) -> None:
    print(f"{datetime.now():%H:%M:%S} {event.name}", flush=True)


def main() -> int:
    source = create_power_source()
    source.start(print_event)
    print("Listening. Put the PC to sleep and wake it, then press Ctrl+C.", flush=True)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        return 0
    finally:
        source.stop()


if __name__ == "__main__":
    sys.exit(main())
