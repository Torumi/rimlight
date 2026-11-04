# Device protocol specifications

One file per device, named like its driver directory:
[strip_37fa_8202.md](strip_37fa_8202.md). Adding a device is described in
[adding-a-device.md](../adding-a-device.md).

## Rules

- Knowledge comes only from USB traffic captured by the project (see
  [capture-guide.md](../capture-guide.md)) and from behavior observed on the device.
  No decompilation or reading of vendor software.
- Every field cites the capture file(s) it was derived from (`NN-scenario.pcapng`, frame
  numbers where useful). Captures contributed by others are cited by their "Protocol capture"
  issue (`#123: 02-solid-red-100`).
- Confidence levels: **confirmed** (seen in ≥2 captures and reproduced by rimlight on the
  device), **likely** (consistent across captures, not yet reproduced), **guess** (single
  observation or meaning not understood).
- rimlight sends only reports whose fields are **confirmed**. A **likely** report may be sent
  only by hardware verification tests the maintainer runs on purpose (`pytest -m hardware`),
  to confirm it. **Guess** reports are never sent.
- Byte offsets are 0-based and count from the first byte of the report as it travels on USB.
- Specs never quote serial numbers or other unit-specific identifiers.
