"""Find the Digirig's sound card and serial port, then start Dire Wolf with them.

Usage: python3 scripts/digirig.py [--check] [--port PORT] [--audio NAME]

Fills in direwolf/direwolf.conf's placeholders, writes out/direwolf.conf, and
runs direwolf with it. --check only reports what it found. Starting Dire Wolf
doesn't transmit by itself: it keys the radio only when a client such as Pat
sends something.
"""

import argparse
import glob
import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "direwolf" / "direwolf.conf"
OUTPUT = ROOT / "out" / "direwolf.conf"

# The name macOS gives the Digirig's CM108 sound card. Other generic USB sound
# cards use it too, so pass --audio if you have more than one plugged in.
AUDIO_NAME = "USB Audio Device"

# Same globs as program.py's find_port().
PORT_GLOBS = ("/dev/cu.usbserial-*", "/dev/cu.SLAB_USBtoUART*")


def find_ports():
    return sorted(p for pattern in PORT_GLOBS for p in glob.glob(pattern))


def audio_devices(profile):
    """Return the names of devices with both input and output, from system_profiler's JSON."""
    return [
        item["_name"]
        for entry in profile.get("SPAudioDataType", [])
        for item in entry.get("_items", [])
        if item.get("coreaudio_device_input") and item.get("coreaudio_device_output")
    ]


def read_audio_profile():
    out = subprocess.run(
        ["system_profiler", "-json", "SPAudioDataType"], capture_output=True, text=True, check=True
    ).stdout
    return json.loads(out)


def render(template, adevice, port):
    for placeholder in ("@ADEVICE@", "@PTT_PORT@"):
        if placeholder not in template:
            raise ValueError(f"{placeholder} missing from {TEMPLATE.name}")
    return template.replace("@ADEVICE@", adevice).replace("@PTT_PORT@", port)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report the devices found and exit")
    parser.add_argument("--port", help="serial port for PTT (default: the only /dev/cu.usbserial-*)")
    parser.add_argument("--audio", default=AUDIO_NAME, help=f"sound card name (default: {AUDIO_NAME!r})")
    args = parser.parse_args()

    problems = []

    port = args.port
    if not port:
        ports = find_ports()
        if len(ports) == 1:
            port = ports[0]
        elif ports:
            problems.append(f"Found several USB serial ports {ports}; pass --port.")
        else:
            problems.append("No Digirig serial port found. Is the Digirig's USB cable plugged in?")

    devices = audio_devices(read_audio_profile())
    if args.audio not in devices:
        problems.append(
            f"No sound card named {args.audio!r} found (have: {', '.join(devices) or 'none'}). "
            "Is the Digirig's USB cable plugged in? Pass --audio if it has another name."
        )

    if not shutil.which("direwolf"):
        problems.append("direwolf isn't installed: brew install direwolf")

    print(f"PTT port:   {port or '-'}")
    print(f"Sound card: {args.audio if args.audio in devices else '-'}")
    print("Cable:      the Digirig AUDIO jack to the radio's K1 jack (not the programming cable)")
    if problems:
        sys.exit("\n".join(problems))
    if args.check:
        return

    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(render(TEMPLATE.read_text(), args.audio, port))
    print(f"Wrote {OUTPUT.relative_to(ROOT)}; starting Dire Wolf (Ctrl-C to stop).")
    os.execvp("direwolf", ["direwolf", "-c", str(OUTPUT)])


if __name__ == "__main__":
    main()
