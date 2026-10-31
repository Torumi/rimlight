# Device protocol specification

Status: **empty — nothing documented yet.**

This file is the single source of truth for how rimlight talks to the strip. Code in
`src/rimlight/device/protocol.py` implements only what is written here.

## Rules

- Knowledge comes only from USB traffic captured by the project (see
  [capture-guide.md](capture-guide.md)) and from behavior observed on the device.
  No decompilation or reading of vendor software.
- Every field cites the capture file(s) it was derived from (`NN-scenario.pcapng`, frame
  numbers where useful).
- Confidence levels: **confirmed** (seen in ≥2 captures and reproduced), **likely** (consistent
  across captures, not yet reproduced), **guess** (single observation; must not be sent).
- Only reports with confirmed fields may be sent by rimlight.
- Byte offsets are 0-based and include the report ID byte, if any.

## Captures index

| File | Scenario | OS / tool | Date | Notes |
|------|----------|-----------|------|-------|
|      |          |           |      |       |

## 1. Transport

USB descriptors and the HID report descriptor (from a plug-in capture).

| Property | Value | Source capture(s) | Confidence |
|----------|-------|-------------------|------------|
| VID:PID | 0x37FA:0x8202 | (OS device list) | confirmed |
| Interfaces / usage pages | | | |
| Report IDs in use | | | |
| Output report size(s) | | | |
| Input report size(s) | | | |
| Feature report size(s) | | | |
| Transfer method (interrupt OUT / SET_REPORT) | | | |
| Endpoint(s) | | | |

## 2. Init / handshake

Sequence sent by the host before the device accepts color data.

| Step | Direction | Report ID | Bytes | Meaning | Source capture(s) | Confidence |
|------|-----------|-----------|-------|---------|-------------------|------------|
|      |           |           |       |         |                   |            |

## 3. Color frame

| Offset | Size | Field | Values | Source capture(s) | Confidence |
|--------|------|-------|--------|-------------------|------------|
|        |      |       |        |                   |            |

Open questions: LED order, color channel order, multi-report frames, maximum frame rate.

## 4. Brightness

| Offset | Size | Field | Values | Source capture(s) | Confidence |
|--------|------|-------|--------|-------------------|------------|
|        |      |       |        |                   |            |

## 5. Power (on/off)

| Offset | Size | Field | Values | Source capture(s) | Confidence |
|--------|------|-------|--------|-------------------|------------|
|        |      |       |        |                   |            |

### Sleep / resume observations

What the host and device do around system sleep, and what state the device is in after
resume.

## 6. Unknown

Reports seen in captures whose meaning is not understood. rimlight never sends these.

| Report ID / first bytes | Direction | When seen | Source capture(s) | Notes |
|-------------------------|-----------|-----------|-------------------|-------|
|                         |           |           |                   |       |
