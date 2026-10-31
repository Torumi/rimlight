"""rimlight: open-source driver app for USB monitor-backlight LED strips."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("rimlight")
except PackageNotFoundError:  # running from a source tree without installation
    __version__ = "0.0.0"

__all__ = ["__version__"]
