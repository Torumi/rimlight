# Capturing USB traffic

How to record the strip's USB traffic for [protocol.md](protocol.md). Captures are the only
allowed source of protocol knowledge, so a clean, well-labelled capture matters more than a
long one.

Raw captures go into `captures/` in the repository root. That directory is gitignored: captures
can contain serial numbers and unrelated USB traffic, so they never get committed. Only small
extracted byte fixtures go into `tests/fixtures/`.

## General rules

- **One scenario per file**, named `NN-scenario.pcapng` (see the list below).
- Keep each capture short (10–30 s) and do the action a few seconds after starting, so it
  is easy to find.
- Next to each capture write a `NN-scenario.txt` with what you did and roughly when
  ("t=5s set red", "t=12s set green"), the app version, and the LED count.
- Unplug other USB devices you don't need on the same controller if you can; less noise.
- Don't move the mouse to other USB HID devices more than needed (mouse/keyboard traffic
  ends up in the same capture on the same root hub).

## Windows: Wireshark + USBPcap

1. Install [Wireshark](https://www.wireshark.org/download.html). In the installer, tick
   **Install USBPcap**. Reboot when asked.
2. Find which root hub the strip is on: run `C:\Program Files\USBPcap\USBPcapCMD.exe` as
   administrator. It lists `\\.\USBPcap1`, `\\.\USBPcap2`, … with the devices under each.
   Look for the strip (VID `37fa`, PID `8202`). Close the tool.
3. Start Wireshark **as administrator** and open the gear icon next to that `USBPcapN`
   interface. Keep *Capture from all devices connected* off and tick only the strip if it is
   listed, plus *Capture from newly connected devices* (needed for `00-plug-in`).
4. Start the capture, perform the scenario, stop the capture.
5. *File → Save As…*, format **pcapng**, name `NN-scenario.pcapng`, into `captures/`.

Finding the strip in a capture: look for `GET DESCRIPTOR` responses with `idVendor 0x37fa`,
note the device address (e.g. `1.7.0`), then filter with `usb.device_address == 7`.

## Linux: usbmon

1. Load the module: `sudo modprobe usbmon`.
2. Find the bus and device number: `lsusb -d 37fa:8202` → e.g. `Bus 003 Device 007`.
3. Capture on that bus (`usbmon3` for bus 3):
   ```
   sudo dumpcap -i usbmon3 -w captures/NN-scenario.pcapng
   ```
   or pick `usbmon3` in Wireshark (run as root, or add yourself to the `wireshark` group and
   `sudo setfacl -m u:$USER:r /dev/usbmon*`). Stop with Ctrl+C.
4. Filter in Wireshark with `usb.device_address == 7`. The address changes after replugging
   and after resume.

If the vendor app does not run on Linux, Linux captures are still useful for observing what the
device does on plug-in and around sleep/resume, and later for checking rimlight's own traffic.

## Scenarios

| File | What to do |
|------|------------|
| `00-plug-in.pcapng` | Recommended first. Start capturing, then plug the strip in; wait 10 s. Vendor app closed. This captures the USB and HID report descriptors. |
| `01-app-start.pcapng` | Strip plugged in, vendor app closed. Start capturing, launch the vendor app, wait until the strip shows its first output, wait 10 s more. |
| `02-solid-red-100.pcapng` | In the app: static color, pure red (`#FF0000`), brightness 100 %. Start capturing, apply the color, wait 10 s. |
| `03-solid-green-100.pcapng` | Same with pure green (`#00FF00`). |
| `04-solid-blue-100.pcapng` | Same with pure blue (`#0000FF`). |
| `05-brightness-change.pcapng` | Static color (e.g. white). Step brightness 100 → 75 → 50 → 25 → 0 → 100 %, ~3 s apart; write the times in the `.txt`. |
| `06-power-off-on.pcapng` | Turn the strip off in the app, wait 5 s, turn it on, wait 5 s. |
| `07-mirror-5s.pcapng` | Screen mirroring on, with a simple, known picture (e.g. left half of the screen red, right half blue, full screen). Capture ~5 s, then ~5 s with a different known picture. |
| `08-sleep-resume.pcapng` | App running and the strip lit. Start capturing, put the PC to sleep (Start → Power → Sleep), wake it after ~30 s, wait 20 s, stop. Write down what the strip does and the device state in Device Manager (e.g. Code 28 on the HID node). If the capture stops during sleep, save it and immediately start `08b-after-resume.pcapng`. |
| `09-replug-after-resume.pcapng` | Optional, right after `08`: start capturing, do whatever restores the strip (replug, or disable/enable in Device Manager), wait until the app drives it again. |

Tips for the color scenarios: these give the cleanest view of the color frame layout, so keep
the color fixed during the whole capture and avoid touching any other setting.

## Extracting payloads (optional)

For a quick look without the GUI, `tshark` (installed with Wireshark) can dump the data part of
transfers to and from the device:

```
tshark -r captures/02-solid-red-100.pcapng -Y "usb.device_address == 7" -T fields -e frame.number -e frame.time_relative -e usb.endpoint_address -e usb.transfer_type -e usbhid.data -e usb.capdata
```

Findings go into `protocol.md`, each field citing the capture file(s) it came from.
