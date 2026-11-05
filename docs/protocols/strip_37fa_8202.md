# Device protocol specification

Device: USB HID LED strip `37FA:8202` (driver `strip_37fa_8202`).

Status: **framing, color frames and the LED-count query confirmed**: derived from captures 00–09
(2026-11-01) and reproduced by rimlight on the device (`scripts/dev_tools/verify_strip.py`,
2026-11-04, see Verification). Brightness and power have no device commands.

This file is the single source of truth for how rimlight talks to the strip. Code in
`src/rimlight/device/drivers/strip_37fa_8202/` implements only what is written here.

Rules and confidence levels: [README.md](README.md).

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
| VID:PID | `0x37FA:0x8202`, bcdDevice `0x0105` | 00 frame 2 | confirmed |
| Configuration | 1 configuration, 1 interface, bus-powered, remote wakeup, 70 mA | 00 frame 6 | confirmed |
| Interface | 0, HID class, no subclass/protocol | 00 frame 6 | confirmed |
| Endpoints | interrupt IN `0x82` and OUT `0x02`, 64 bytes, bInterval 1 | 00 frame 6; 09 frames 16, 64 | confirmed |
| HID report descriptor | 34 bytes: usage page `0xFF00`, usage `0x01`, one 64-byte Input and one 64-byte Output report, 8-bit fields | 00 frame 12; 09 frames 22, 70 | confirmed |
| Report IDs | none | 00 frame 12 | confirmed |
| Transfer method | interrupt OUT for host → device, interrupt IN for device → host; no SET_REPORT or feature reports | all captures | confirmed |

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

Source: all captures; reassembly checked over every report; requests and answers reproduced
on the device. Confidence: **confirmed**.

## 3. Commands

| Cmd | Request payload | Response data | Meaning | Source | Confidence |
|-----|-----------------|---------------|---------|--------|------------|
| `0x02` | colors, 3 bytes per LED | none (status only) | show a color frame | all captures; Verification | confirmed |
| `0x03` | none | 1 byte: `0x39` = 57 | number of LEDs the device drives | 00 f41–43, 01 f23–25, 09 f113–115; Verification | confirmed (the strip's physical ends are LEDs 0 and 56) |
| `0x06` | none | 1 byte: `0x01` | unknown | 00, 01, 09 | guess |
| `0x08` | none | 1 byte: `0xff` = 255 | unknown | 00, 01, 09 | guess |
| `0x0a` | none | 1 byte: `0x15` = 21 | unknown | 00, 01, 09 | guess |
| `0x0b` | none | 2 ASCII characters (`"13"`) | unknown; possibly a firmware version | 00, 01, 09 | guess |
| `0x0c` | none | 6 ASCII characters | unknown; looks like a model identifier | 00, 01, 09 | guess |

No other commands appear in any capture.

### Color frame (`0x02`)

| Offset (in payload) | Size | Field | Values | Source | Confidence |
|---------------------|------|-------|--------|--------|------------|
| 3·i | 1 | **green** of LED i | 0–255 | 02 f735 (`#FF0000` → `0f ff 0f`), 03 f487 (`#00FF00` → `ff 0f 0f`), 04 f343 (`#0000FF` → `0f 0f ff`); Verification | confirmed |
| 3·i + 1 | 1 | **red** of LED i | 0–255 | same | confirmed |
| 3·i + 2 | 1 | **blue** of LED i | 0–255 | same | confirmed |

- Channel order is **G, R, B**.
- Payload length is 3 × LED count (171 for 57 LEDs); it matches the `0x03` response in every
  capture.
- LED 0 is the strip's physical start and LED count − 1 its physical end (Verification).
- LED order around the screen (07): with the screen split left/right, LEDs 0–15 and 49–56
  show the right half, 18–46 the left half, 16–17 and 47–48 sit at the vertical center line
  (07 frames 7 and 1287). The strip runs around the screen, starting in the right half;
  direction and start side are not known yet (needs a top/bottom capture).
- The device answers each frame with `82 00 01 00` (status 0) about 25 ms later (median over
  02, 07, 01; max 40 ms in steady state).
- The vendor app sends frames continuously at about 21 per second (median interval 46 ms,
  02/07/01), also when the colors do not change. The device does **not** need this: a single
  frame stayed on the strip for 15 s, and the device still answered after about 30 s without
  frames (Verification).

### Init sequence

After the device appears, the vendor app sends the queries `03, 06, 08, 0a, 0b, 0c`, each
answered before the next, then starts frames (01 frames 23–47, 09 frames 113–137, 00 frames
41–65). Identical in all three captures. Confidence: **likely** for the sequence; the meaning
of `06`–`0c` is a **guess**.

rimlight's driver sends only `0x03` and then frames, and the device accepts that (Verification),
so the queries `06`–`0c` are not needed and stay unsent. The driver refuses frames of any other
length than the reported count, since none have been observed.

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
frames (`DeviceCapabilities.hardware_power = False`). Both `0f 0f 0f` and `00 00 00` look off on
the strip (Verification), so rimlight uses `00 00 00`. The lowest visible level is not known.

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

Experiments without the vendor app (`scripts/dev_tools/verify_sleep.py`, Windows, S3 sleep of
about 35 s, 2026-11-04). The strip answered `0x03` before every sleep:

| Before sleep | After wake |
|--------------|------------|
| frames streaming into sleep | first frame unanswered |
| handle open, no frames | no answer on the same handle (60 s) or a new handle (90 s) |
| frames for 15 s, then stopped and handle closed | no answer on a new handle (90 s) |
| handle closed | no answer on a new handle (90 s); at the end the device was not enumerated |

Recovery of a silent strip: an elevated `pnputil /restart-device` on the `USB\VID_37FA&PID_8202`
node made it answer `0x03` at once (one run; frames not checked in that run). A port cycle in
USB Device Tree Viewer, run as administrator, also brought it back between the runs above.
A scheduled task running that `pnputil` command as SYSTEM (now `rimlight-cli recovery enable`),
started by a normal user with `schtasks /run`, did the same: task result 0, `0x03` answered at once
(one run; frames not checked).

Conclusions for recovery (issue #21, **confirmed** on one PC):

- The device stops answering after S3 sleep whatever the host does before it: frames, an open
  handle, or neither. rimlight cannot prevent this with the commands it knows.
- A write error is **not** a reliable signal, since writes can still succeed (08). A **missing
  answer** within a timeout is.
- Reopening the handle does not help. Restarting the device does. That needs administrator rights
  on Windows, but a scheduled task lets a normal user trigger it after one elevated setup.
- It happens on every sleep: two sleeps within a minute in one `rimlight-cli run` session
  (2026-11-05) each left it silent, the first recovered by the restart task about 19 s
  after waking.
- Earlier, outside these captures, the HID node showed Code 28 after resume. Not observed
  in these runs; recorded as a possible second form of the same failure. See the bootloader
  mode below, which shows the same code.

### Bootloader mode (`4348:55E0`)

Observed on the device, Windows, one PC, 2026-11-04; no capture, seen in the Windows device list:

- After unplugging and replugging the cable the strip appears as `USB\VID_4348&PID_55E0`
  instead of `37FA:8202`, with Code 28 (no driver) and no HID interface, so hidapi cannot see
  it. This happened 5 of 5 times with rimlight stopped and 5 of 5 with `rimlight-cli run`
  running, so rimlight does not cause it.
- An elevated `pnputil /restart-device` on that node brings back `37FA:8202`. Through the
  scheduled task, in `rimlight-cli run`, it was back within 8 s in 3 of 4 restarts. The other
  restart, under 5 s after the node appeared, left it in this mode for at least 18 s, although
  a repeat worked; the cause is unknown, and the Windows event logs had nothing on it.
- The ID looks like a chip maker's bootloader rather than this product's (an assumption, from
  the vendor ID), so **another device can have the same ID**.

rimlight **never opens or writes to this device**: no report of any kind, and firmware stays with
the vendor's app. If the strip is missing, this node is present and automatic restart is on,
the only action is that same node restart. It repeats after 12 s, and after 3 restarts
without success only every 5 minutes, in case this is another device being flashed.

## 6. Unknown

| First bytes | Direction | When seen | Source | Notes |
|-------------|-----------|-----------|--------|-------|
| `06`, `08`, `0a`, `0b`, `0c` (length 0) | OUT | init only | 00, 01, 09 | read-only queries by their shape; meaning unknown |
| `00 00 00` (length 0) | IN | once, right after the first port cycle | 09 frame 56 | completed with an error status as the device disappeared |

## Verification

`scripts/dev_tools/verify_strip.py` on the real strip, Windows, vendor app closed, 2026-11-04,
sending only `0x03` and `0x02`:

| Check | Result |
|-------|--------|
| `0x03` | answered 57 |
| Frames after `0x03` alone | accepted and acknowledged |
| Pure red, green, blue (RGB input, encoded G, R, B) | shown as requested |
| LED 0 red, last LED blue | lit the two physical ends of the strip |
| One lit LED walking from 0 to the last | ran from the physical start to the physical end |
| `0f 0f 0f` for 3 s, then `00 00 00` for 3 s | no visible light in either |
| One white frame, then no frames for 15 s | stayed white |
| Frame after that pause (about 30 s since the white frame) | acknowledged |

## Open questions

1. LED order: direction and start side around the screen (capture with a top/bottom split, or
   note where the physical start is mounted). rimlight's layout settings make this configurable.
2. Does the failure also happen with Modern Standby, or on other PCs and Linux?
3. Does the device report its cut length on its own, or was it stored by the vendor app at setup?
   Only matters if the strip is cut again.
4. Is there a time limit beyond the observed 30 s without frames? (Sleep/resume aside.)
5. What is the lowest visible color level?
6. When does the strip come up in bootloader mode? Replugging does it every time (direct to the
   port, one PC). Port cycles in `09` came back as `37FA:8202` (frames 12 and 60). `00-plug-in` does
   not show the moment of plugging in: its only device descriptor is at 0 s, as in `01`-`08`, where
   nothing was replugged. So losing power may be the trigger, which would also mean power-on of the
   PC when USB power was off. After a shutdown that kept power on the port (the strip's LED
   kept blinking) it came up normally (one run), which fits but does not prove this. Power-on
   with USB power off and other PCs are untested.
