# Device protocol specification

Device: USB HID LED strip `37FA:8202` (driver `strip_37fa_8202`).

Status: **framing, color frames, the LED-count query and the init sequence documented** from
captures 00–09 (2026-11-01); nothing reproduced by rimlight yet. Brightness and power have no
device commands.

This file is the single source of truth for how rimlight talks to the strip. Code in
`src/rimlight/device/` implements only what is written here.

## Rules

- Knowledge comes only from USB traffic captured by the project (see
  [capture-guide.md](capture-guide.md)) and from behavior observed on the device.
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
- Byte offsets are 0-based and count from the first byte of the 64-byte HID report (there is
  no report ID byte; see Transport).

## Captures index

All captured on Windows 11 with Wireshark + USBPcap (`\\.\USBPcap1`), filtered to the strip
(bus 1, device address 13 unless noted), vendor app open. Strip cut to fewer LEDs than shipped.

| File | Scenario | Date | Notes |
|------|----------|------|-------|
| `00-plug-in.pcapng` | strip plugged in | 2026-11-01 | vendor app was running; enumeration, descriptors, init, frames |
| `01-app-start.pcapng` | vendor app started | 2026-11-01 | init (frames 23–45), then frames |
| `02-solid-red-100.pcapng` | static `#FF0000`, 100% | 2026-11-01 | transition, then steady frames |
| `03-solid-green-100.pcapng` | static `#00FF00`, 100% | 2026-11-01 | |
| `04-solid-blue-100.pcapng` | static `#0000FF`, 100% | 2026-11-01 | |
| `05-brightness-change.pcapng` | white, 100 → 75 → 50 → 25 → 0 → 100% | 2026-11-01 | |
| `06-power-off-on.pcapng` | off, then on, in the vendor app | 2026-11-01 | |
| `07-mirror-5s.pcapng` | mirroring: left red / right blue, then left yellow / right cyan | 2026-11-01 | |
| `08-sleep-resume.pcapng` | PC sleep and wake with the app running | 2026-11-01 | device stops answering after resume |
| `09-replug-after-resume.pcapng` | two USB port cycles (USB Device Tree Viewer), then mirroring restarted | 2026-11-01 | addresses 13 → 14 → 15 |

## 1. Transport

| Property | Value | Source | Confidence |
|----------|-------|--------|------------|
| VID:PID | `0x37FA:0x8202`, bcdDevice `0x0105` | 00 frame 2 | likely |
| Configuration | 1 configuration, 1 interface, bus-powered, remote wakeup, 70 mA | 00 frame 6 | likely |
| Interface | 0, HID class, no subclass/protocol | 00 frame 6 | likely |
| Endpoints | interrupt IN `0x82` and OUT `0x02`, 64 bytes, bInterval 1 | 00 frame 6; 09 frames 16, 64 | likely |
| HID report descriptor | 34 bytes: usage page `0xFF00`, usage `0x01`, one 64-byte Input and one 64-byte Output report, 8-bit fields | 00 frame 12; 09 frames 22, 70 | likely |
| Report IDs | none | 00 frame 12 | likely |
| Transfer method | interrupt OUT for host → device, interrupt IN for device → host; no SET_REPORT or feature reports | all captures | likely |

HID report descriptor (00 frame 12):

```
06 00 ff 09 01 a1 01 09 02 15 00 26 00 ff 75 08 95 40 81 06
09 02 15 00 26 00 ff 75 08 95 40 91 06 c0
```

With hidapi, a write is the report prefixed with report ID `0x00` (65 bytes); a read returns
the 64-byte report.

## 2. Message framing

Every exchange is a request from the host and a response from the device. A message may span
several 64-byte reports. All captures (≈18 000 reports) reassemble under these rules with no
leftovers and only zero padding.

**Request** (host → device):

| Offset | Size | Field | Values |
|--------|------|-------|--------|
| 0 | 1 | command | see Commands |
| 1 | 2 | payload length, big-endian | 0 for queries, 171 (`0x00ab`) for a 57-LED frame |
| 3 | n | payload | |

**Response** (device → host):

| Offset | Size | Field | Values |
|--------|------|-------|--------|
| 0 | 1 | command `| 0x80` | e.g. `0x82` for command `0x02` |
| 1 | 2 | length of status + data, big-endian | |
| 3 | 1 | status | `0x00` in every response captured |
| 4 | n−1 | data | command-specific |

**Continuation:** if `3 + length > 64`, the message continues in the next report(s) of the
same direction with no header; the last report is zero-padded to 64 bytes
(02 frames 735, 737, 739: 61 + 64 + 46 payload bytes).

Source: all captures; reassembly checked over every report. Confidence: **likely**.

## 3. Commands

| Cmd | Request payload | Response data | Meaning | Source | Confidence |
|-----|-----------------|---------------|---------|--------|------------|
| `0x02` | colors, 3 bytes per LED | none (status only) | show a color frame | all captures | likely |
| `0x03` | none | u16 big-endian: `0x0039` = 57 | number of LEDs the device drives | 00 f41–43, 01 f23–25, 09 f113–115 | likely (value matches the 57 colors per frame) |
| `0x06` | none | u16: `0x0001` | unknown | 00, 01, 09 | guess |
| `0x08` | none | u16: `0x00ff` = 255 | unknown | 00, 01, 09 | guess |
| `0x0a` | none | u16: `0x0015` = 21 | unknown | 00, 01, 09 | guess |
| `0x0b` | none | 2 ASCII characters (`"13"`) | unknown; possibly a firmware version | 00, 01, 09 | guess |
| `0x0c` | none | 6 ASCII characters | unknown; looks like a model identifier | 00, 01, 09 | guess |

No other commands appear in any capture.

### Color frame (`0x02`)

| Offset (in payload) | Size | Field | Values | Source | Confidence |
|---------------------|------|-------|--------|--------|------------|
| 3·i | 1 | **green** of LED i | 0–255 | 02 f735 (`#FF0000` → `0f ff 0f`), 03 f487 (`#00FF00` → `ff 0f 0f`), 04 f343 (`#0000FF` → `0f 0f ff`) | likely |
| 3·i + 1 | 1 | **red** of LED i | 0–255 | same | likely |
| 3·i + 2 | 1 | **blue** of LED i | 0–255 | same | likely |

- Channel order is **G, R, B**.
- Payload length is 3 × LED count (171 for 57 LEDs); it matches the `0x03` response in every
  capture.
- LED order around the screen (07): with the screen split left/right, LEDs 0–15 and 49–56
  show the right half, 18–46 the left half, 16–17 and 47–48 sit at the vertical center line
  (07 frames 7 and 1287). The strip runs around the screen, starting in the right half;
  direction and start side are not known yet (needs a top/bottom capture).
- The device answers each frame with `82 00 01 00` (status 0) about 25 ms later (median over
  02, 07, 01; max 40 ms in steady state).
- The vendor app sends frames continuously at about 21 per second (median interval 46 ms,
  02/07/01), also when the colors do not change. Whether the device needs a steady stream
  (e.g. a timeout) is not known.

### Init sequence

After the device appears, the vendor app sends the queries `03, 06, 08, 0a, 0b, 0c`, each
answered before the next, then starts frames (01 frames 23–47, 09 frames 113–137, 00 frames
41–65). Identical in all three captures. Confidence: **likely** for the sequence; the meaning
of `06`–`0c` is a **guess**.

rimlight's driver starts with `0x03` (it needs the LED count). Whether the device accepts frames
without the other queries is the first thing to verify on hardware. If it does not, replaying
`06`–`0c` exactly as observed needs a maintainer decision recorded here first: they look like
read-only queries, but their meaning is a guess, and guess reports are not sent.

## 4. Brightness

There is **no brightness command**. The vendor app scales the frame colors (05: white
`b3 ff 8a` at 100% → `88 c1 6a` at 75% → `5e 82 4a` at 50% → `35 47 2b` at 25% →
`12 14 12` at 0%; frames 7, 1023, 1759, 2287, 2743). rimlight implements brightness in software
(`DeviceCapabilities.hardware_brightness = False`).

Observations about the vendor app, not the protocol: its "white" is R 255, G 179, B 138, its
lowest channel value is about `0x0f`, and it fades between colors over several frames
(02 frames 639–735).

## 5. Power (on/off)

There is **no power command**. "Off" in the vendor app is a fade to frames of `0f 0f 0f`
(06 frames 1153–1169), "on" a fade back (06 frames 2353–2369). rimlight implements power as
frames (`DeviceCapabilities.hardware_power = False`). Whether `0f 0f 0f` and `00 00 00` look
different on the strip is not known.

### Sleep / resume observations

08 (sleep about 11.8 s into the capture, wake about 37 s):

1. At sleep, Windows cancels the pending interrupt IN transfers (`USBD_STATUS_CANCELED`,
   frames 2345–2346).
2. At wake, Windows sends `SET_IDLE` and re-submits IN transfers on the **same address**
   (frames 2347–2350); the device is not re-enumerated.
3. From 41 s the vendor app sends frames again. The **OUT transfers complete successfully**,
   but the device **never answers** (no `0x82`) for the rest of the capture, 218 s
   (frames 2351–2405).
4. The app then polls with `0x03` every ~6 s, later every ~60 s; no answer either
   (frames 2423–2507).

09 (after 08, still unanswered): a USB **port cycle** removes the device (frames 7–10, transfers
aborted), it re-enumerates at address 14 (frame 11) and answers one `0x83`; a second port cycle
(frames 49–58) re-enumerates it at address 15, the app runs the init sequence and frames are
acknowledged again (frames 113–137).

Conclusions for recovery (issue #21, **likely**):

- After resume the device can stay on the bus, accept writes, and not process them. A write
  error is **not** a reliable signal; a **missing `0x82` acknowledgement** within a timeout is.
- Reopening the HID handle alone is unlikely to help (the host side is healthy in 08). A USB
  port cycle or device restart brings the device back; the init sequence must follow.
- Earlier, outside these captures, the HID node showed Code 28 after resume. Not observed
  in 08; recorded as a second form of the same failure.

## 6. Unknown

| First bytes | Direction | When seen | Source | Notes |
|-------------|-----------|-----------|--------|-------|
| `06`, `08`, `0a`, `0b`, `0c` (length 0) | OUT | init only | 00, 01, 09 | read-only queries by their shape; meaning unknown |
| `00 00 00` (length 0) | IN | once, right after the first port cycle | 09 frame 56 | completed with an error status as the device disappeared |

## Open questions

1. Does the device accept frames after `0x03` alone, without `06`–`0c`?
2. Does it need a continuous frame stream, and what happens if frames stop?
3. Does `0x03` report the cut length on its own, or was it stored by the vendor app at setup?
   (Verify by lighting LED 0 and the last LED.)
4. LED order: direction and start side around the screen (capture with a top/bottom split).
5. Is `0f 0f 0f` visibly off, or is `00 00 00` needed for a dark strip?
6. Can a port cycle or device restart be done without administrator rights on Windows?
