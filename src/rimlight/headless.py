"""Runs the device without a user interface: `rimlight-cli run`."""

import logging
from collections.abc import Callable
from functools import partial

from rimlight.config.settings import Settings
from rimlight.device.manager import (
    Connector,
    DeviceManager,
    DeviceResetter,
    DeviceState,
    open_first_device,
)
from rimlight.device.registry import DriverRegistry
from rimlight.device.reset import create_resetter
from rimlight.engine.static import static_frame
from rimlight.power.events import PowerEvent, PowerEventSource
from rimlight.power.factory import create_power_source

_log = logging.getLogger(__name__)


def available_resetter(registry: DriverRegistry, settings: Settings) -> DeviceResetter | None:
    """The resetter, if the setting allows it and its task is set up."""
    if not settings.recovery.auto_reset:
        return None
    resetter = create_resetter(registry.drivers[0])
    if resetter is None or not resetter.is_installed():
        return None
    return resetter


def run(
    settings: Settings,
    connect: Connector,
    *,
    wait: Callable[[], None],
    resetter: DeviceResetter | None,
    power: PowerEventSource,
    on_state: Callable[[DeviceState], None] | None = None,
) -> None:
    """Hold the configured light until `wait` returns, recovering the device as needed."""
    manager = DeviceManager(connect, resetter=resetter, on_state=on_state)

    def on_power(event: PowerEvent) -> None:
        if event is PowerEvent.RESUME:
            manager.notify_resume()

    light = settings.light
    manager.show(static_frame(light.color, light.brightness, light.on))
    manager.start()
    try:
        try:
            power.start(on_power)
        except (OSError, NotImplementedError) as exc:
            # The regular health check still notices a dead device, only later.
            _log.warning("no sleep and resume events: %s", exc)
        try:
            wait()
        finally:
            power.stop()
    finally:
        manager.stop()


def run_with_defaults(
    settings: Settings,
    registry: DriverRegistry,
    *,
    resetter: DeviceResetter | None,
    wait: Callable[[], None],
    on_state: Callable[[DeviceState], None] | None = None,
) -> None:
    """`run` with the real device and power events."""
    connect = partial(open_first_device, registry, max_fps=settings.device.max_fps)
    _log.info("automatic device restart: %s", "on" if resetter else "off")
    run(
        settings,
        connect,
        wait=wait,
        resetter=resetter,
        power=create_power_source(),
        on_state=on_state,
    )
