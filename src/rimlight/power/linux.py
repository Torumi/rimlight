"""Linux power events (logind PrepareForSleep, session Lock/Unlock over D-Bus).
Not implemented yet."""

from rimlight.power.events import PowerEventCallback


class LogindPowerSource:
    def start(self, callback: PowerEventCallback) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        pass
