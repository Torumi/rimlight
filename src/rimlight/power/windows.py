"""Windows power events (RegisterSuspendResumeNotification / WM_POWERBROADCAST,
WTS session lock notifications). Not implemented yet."""

from rimlight.power.events import PowerEventCallback


class WindowsPowerSource:
    def start(self, callback: PowerEventCallback) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        pass
