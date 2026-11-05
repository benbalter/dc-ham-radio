# /// script
# requires-python = ">=3.10,<3.14"
# dependencies = ["chirp @ git+https://github.com/kk7ds/chirp"]
# ///
"""Program the UV-5R (or the UV-5G) from frequencies.csv and radio-settings.json over a serial cable (e.g. a Digirig's SERIAL jack).

Usage:
  uv run scripts/program.py                  # back up the radio and show what would change
  uv run scripts/program.py --write          # back up, then write channels and settings to the radio
  uv run scripts/program.py --save-settings  # back up, then save the radio's settings to radio-settings.json
  uv run scripts/program.py --image X.img    # same, reading a saved image instead of the radio
  uv run scripts/program.py --radio uv5g     # any of the above for the Radioddity UV-5G (GMRS)

The UV-5G's channels are built from frequencies.csv by scripts/uv5g.py, and
its settings are radio-settings.json with uv5g/radio-settings.json layered on
top, so it follows the UV-5R's configuration except where the override says.

Every radio read saves the image to backups/, so you can restore it in CHIRP
(File > Open, then Radio > Upload). The radio ends up matching the CSV
exactly: slots that aren't in the CSV are erased. Settings in
radio-settings.json are applied; settings it doesn't list are left alone.

The radio must be on, with the cable fully seated in the K1 jack.
"""

import argparse
import datetime
import glob
import pathlib
import sys
import time

import serial
from chirp import chirp_common, directory, errors, import_logic
from chirp import settings as chirp_settings
from chirp.drivers import generic_csv

import radio_settings
import uv5g

ROOT = pathlib.Path(__file__).resolve().parent.parent
SETTINGS_PATH = ROOT / "radio-settings.json"

# Each radio: CHIRP model ID, where its channels come from, and its settings
# files, base first. The last settings file is the radio's own: --settings
# replaces it and --save-settings writes to it.
RADIOS = {
    "uv5r": {
        "model": "Baofeng_UV-5R",
        "csv": lambda: ROOT / "frequencies.csv",
        "settings": [SETTINGS_PATH],
        "not_inherited": (),
    },
    "uv5g": {
        # Same protocol, memory layout, and settings as the UV-5R; CHIRP
        # checks the radio's ident on download, so the wrong radio fails fast.
        "model": "Radioddity_UV-5G",
        "csv": uv5g.build,
        "settings": [SETTINGS_PATH, uv5g.SETTINGS_PATH],
        "not_inherited": uv5g.NOT_INHERITED,
    },
}


def setting_value(element):
    """A CHIRP setting's value as a JSON-friendly Python value."""
    value = element.value
    if isinstance(value, chirp_settings.RadioSettingValueBoolean):
        return bool(value)
    if isinstance(value, chirp_settings.RadioSettingValueInteger):
        return int(value)
    if isinstance(value, chirp_settings.RadioSettingValueFloat):
        return float(value)
    return str(value).rstrip()


def walk_settings(group, top=None):
    """Yield (top-level group name, RadioSetting) for every mutable setting."""
    for element in group:
        if isinstance(element, chirp_settings.RadioSetting):
            if element.value.get_mutable():
                yield top or group.get_shortname(), element
        else:
            yield from walk_settings(element, top or element.get_shortname())


def snapshot_settings(radio):
    snapshot = {}
    for group, element in walk_settings(radio.get_settings()):
        snapshot.setdefault(group, {})[element.get_name()] = {
            "label": element.get_shortname(),
            "value": setting_value(element),
        }
    return snapshot


def apply_settings(radio, desired):
    """Set every setting listed in desired; exit on unknown keys or bad values."""
    wanted = {key: value for key, (_, _, value) in radio_settings.flatten(desired).items()}
    tree = radio.get_settings()
    problems = []
    for _, element in walk_settings(tree):
        key = element.get_name()
        if key not in wanted:
            continue
        try:
            element.value.set_value(wanted.pop(key))
        except (ValueError, chirp_settings.InternalError) as e:
            problems.append(f"{key}: {e}")
    problems += [f"{key}: not a setting on this radio" for key in wanted]
    if problems:
        sys.exit("Can't apply settings:\n  " + "\n  ".join(problems))
    radio.set_settings(tree)
FIELDS = ("freq", "duplex", "offset", "tmode", "rtone", "ctone", "mode", "name", "power", "skip")


def find_port():
    ports = sorted(glob.glob("/dev/cu.usbserial-*") + glob.glob("/dev/cu.SLAB_USBtoUART*"))
    if len(ports) != 1:
        sys.exit(f"Found {len(ports) or 'no'} USB serial ports {ports}; pass --port.")
    return ports[0]


def shown(path):
    """A path relative to the repo when it's inside it, for messages."""
    path = pathlib.Path(path).resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def describe(mem):
    if mem is None or mem.empty:
        return "(empty)"
    tone = {"Tone": f" T{mem.rtone}", "TSQL": f" TSQL{mem.ctone}"}.get(mem.tmode, "")
    shift = {"": "", "split": " split", "off": " RX-only"}.get(
        mem.duplex, f" {mem.duplex}{chirp_common.format_freq(mem.offset)}"
    )
    skip = " skip" if mem.skip else ""
    return f"{mem.name:<7} {chirp_common.format_freq(mem.freq)}{shift}{tone} {mem.mode} {mem.power}{skip}"


def same(a, b):
    if a.empty or b.empty:
        return a.empty == b.empty
    return all(str(getattr(a, f)) == str(getattr(b, f)) for f in FIELDS)


def planned_memories(radio, csv_path):
    """Convert each CSV row into a memory for this radio, or exit on any error."""
    src = generic_csv.CSVRadio(str(csv_path))
    features = src.get_features()
    lo, hi = src.get_features().memory_bounds
    planned, problems = {}, []
    for number in range(lo, hi + 1):
        mem = src.get_memory(number)
        if mem.empty:
            continue
        try:
            new = import_logic.import_mem(radio, features, mem, overrides={"number": number})
        except import_logic.ImportError as e:
            problems.append(f"slot {number} {mem.name}: {e}")
            continue
        for msg in radio.validate_memory(new):
            if isinstance(msg, chirp_common.ValidationError):
                problems.append(f"slot {number} {mem.name}: {msg}")
        planned[number] = new
    if problems:
        sys.exit(f"Can't convert {shown(csv_path)} for this radio:\n  " + "\n  ".join(problems))
    return planned


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", help="serial port (default: the only /dev/cu.usbserial-*)")
    parser.add_argument("--radio", choices=sorted(RADIOS), default="uv5r", help="which radio (default: uv5r)")
    parser.add_argument("--csv", help="channel list (default: the radio's own)")
    parser.add_argument("--write", action="store_true", help="write channels and settings to the radio")
    parser.add_argument(
        "--save-settings", action="store_true",
        help="save the radio's current settings to its settings file",
    )
    parser.add_argument("--image", help="read a saved .img instead of the radio (no writing)")
    parser.add_argument("--settings", help="settings JSON to use in place of the radio's own")
    args = parser.parse_args()
    if args.image and args.write:
        parser.error("--write needs the radio, not --image")
    profile = RADIOS[args.radio]
    *base_settings, own_settings = profile["settings"]
    args.settings = args.settings or str(own_settings)
    args.csv = args.csv or str(profile["csv"]())

    directory.import_drivers()
    cls = directory.get_radio(profile["model"])
    if args.image:
        # Not get_radio_by_image: CHIRP can't tell a UV-5G image from a UV-5R one.
        radio = cls(args.image)
        pipe = None
        print(f"Read {args.image} as {cls.VENDOR} {cls.MODEL}")
    else:
        port = args.port or find_port()
        pipe = serial.Serial(port, baudrate=cls.BAUD_RATE, timeout=0.25)
        radio = cls(pipe)
        print(f"Reading radio on {port}...")
        radio.status_fn = lambda s: None
        # Radios can miss the first handshake after the port opens (the UV-5G
        # did, and CHIRP then misreports it as a "blacklisted model"). Reading
        # changes nothing on the radio, so retry like the write does.
        for attempt in range(1, 4):
            try:
                radio.sync_in()
                break
            except errors.RadioError as e:
                print(f"  read attempt {attempt}: {e}")
                pipe.close()
                time.sleep(3)
                pipe.open()
                pipe.reset_input_buffer()
        else:
            sys.exit("Couldn't read the radio. Power-cycle it, push the K1 plug in until it's fully seated, and rerun.")
        backups = ROOT / "backups"
        backups.mkdir(exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = backups / f"{args.radio}-{stamp}.img"
        radio.save_mmap(str(backup))
        print(f"Backed up to {backup}")

    current_settings = snapshot_settings(radio)
    keep_own = profile["not_inherited"]
    base = radio_settings.drop(radio_settings.merge(*map(radio_settings.load, base_settings)), keep_own)
    if args.save_settings:
        # An override file keeps only what differs from the settings under it,
        # and never the radio's own TX limits or calibration.
        saved = current_settings
        if base_settings:
            saved = radio_settings.drop(radio_settings.subtract(current_settings, base), keep_own)
        radio_settings.dump(saved, args.settings)
        print(f"Saved {sum(map(len, saved.values()))} settings to {args.settings}")
        return

    settings_name = " + ".join(map(shown, [*base_settings, args.settings]))
    own = radio_settings.load(args.settings)
    if own and keep_own and radio_settings.drop(own, keep_own) != own:
        sys.exit(f"{shown(args.settings)} sets a key this radio keeps for itself: {', '.join(keep_own)}")
    desired_settings = None if own is None and not base else radio_settings.merge(base, own)
    setting_changes = []
    if desired_settings is None:
        print(f"No {settings_name}; settings are left alone. Run --save-settings to create it.")
    else:
        setting_changes = radio_settings.diff(current_settings, desired_settings)
        for key, label, old, new in setting_changes:
            print(f"  setting {label} ({key}): {old!r} -> {new!r}")
        print(f"{len(setting_changes)} setting(s) differ from {settings_name}.")
        if setting_changes:
            apply_settings(radio, desired_settings)

    planned = planned_memories(radio, args.csv)
    lo, hi = radio.get_features().memory_bounds
    changes = 0
    for number in range(lo, hi + 1):
        old = radio.get_memory(number)
        new = planned.get(number)
        if new is None:
            if not old.empty:
                print(f"  {number:>3} erase  {describe(old)}")
                radio.erase_memory(number)
                changes += 1
            continue
        if not same(old, new):
            print(f"  {number:>3} {describe(old)}\n      -> {describe(new)}")
            radio.set_memory(new)
            changes += 1
    print(f"{changes} slot(s) differ from {shown(args.csv)}.")

    if not args.write:
        print("Dry run: nothing written. Rerun with --write to program the radio.")
        return
    if not changes and not setting_changes:
        print("Radio already matches; nothing to write.")
        return
    print("Writing to radio. Don't touch it until this finishes...")
    # The UV-5R often ignores a new handshake right after a download, so
    # reopen the port, let it settle, and retry. A failed handshake writes nothing.
    for attempt in range(1, 4):
        pipe.close()
        time.sleep(3)
        pipe.open()
        pipe.reset_input_buffer()
        try:
            radio.sync_out()
            break
        except errors.RadioError as e:
            print(f"  attempt {attempt}: {e}")
    else:
        sys.exit("Couldn't reach the radio to write. Reseat the K1 plug, power-cycle the radio, and rerun.")
    print("Done. Power-cycle the radio, then spot-check a few channels.")


if __name__ == "__main__":
    main()
