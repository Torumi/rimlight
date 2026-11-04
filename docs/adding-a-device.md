# Adding a device

Supporting another device means adding a driver; the engine, UI and CLI talk only to the generic
`DeviceDriver` and do not change. Devices from other vendors are out of scope before 1.0
(see [roadmap.md](roadmap.md)), but the structure allows them.

Open an issue first. You need the device, or captures from someone who has it, and someone able
to run the verification on real hardware.

## Layout

```
src/rimlight/device/          shared code only; knows nothing about a specific device
  driver.py                   DeviceDriver, DeviceMatch, DeviceCapabilities
  transport.py                Transport, HidTransport
  discovery.py, registry.py, manager.py
  drivers/
    __init__.py               BUILTIN_DRIVERS
    <device>/
      __init__.py             exports the driver class
      driver.py               DeviceDriver subclass, its USB IDs
      protocol.py             pure encode/decode, no I/O
    fake/                     test doubles (driver.py, transport.py), not registered

docs/protocols/<device>.md    the spec
tests/device/<device>/        tests
tests/fixtures/<device>/      byte fixtures extracted from captures
```

Name `<device>` after what the device is and its IDs, for example `strip_37fa_8202`. It must be a
valid Python identifier, and the vendor's name stays out of it. Test file names must be unique
across `tests/`.

`tests/device/test_layout.py` enforces the structure: required files, registration in
`BUILTIN_DRIVERS`, shared modules not importing device directories, and pure `protocol.py` files.

## Steps

1. **Capture** the device's USB traffic ([capture-guide.md](capture-guide.md)). Each device needs
   its own captures: the clean-room rules in [CONTRIBUTING.md](../CONTRIBUTING.md) apply in full,
   and one device's protocol says nothing about another's.
2. **Write the spec** in `docs/protocols/<device>.md`, following
   [protocols/README.md](protocols/README.md). Every field cites its capture.
3. **Extract fixtures**: short report bytes in `tests/fixtures/<device>/`, without serial numbers.
4. **Write `protocol.py` and `driver.py`**: set `id`, `match` and `capabilities`, implement
   `initialize` and `_show`, and `set_brightness`, `set_power` or `read_led_count` if the device
   has them. The engine emulates what `capabilities` says is missing.
5. **Signal a dead device**: raise `DeviceNotRespondingError` if the device stops answering and
   `TransportError` on I/O failures or unexpected answers. `DeviceManager` handles only these, so
   a driver's own exceptions must not escape it.
6. **Register** the driver in `BUILTIN_DRIVERS` in `drivers/__init__.py`.
7. **Linux**: add the device to `packaging/linux/99-rimlight.rules`.
8. **Verify on hardware**: a `@pytest.mark.hardware` test, or a script like
   `scripts/dev_tools/verify_strip.py`, sending only what the spec documents. Move what it
   reproduces to **confirmed** in the spec.
