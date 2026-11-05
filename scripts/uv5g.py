"""Build the Radioddity UV-5G's channel list from frequencies.csv.

Usage: python3 scripts/uv5g.py [-o out/uv5g.csv]

The UV-5G is the Part 95-certified GMRS version of the UV-5R. Its firmware
only transmits on GMRS, so it gets GMRS 1-22 for routine use, the GMRS
repeaters in uv5g/repeaters.csv, NOAA weather, and receive-only copies of a
few ham channels. Everything except the repeaters comes from frequencies.csv,
so a refresh or hand edit there flows through; nothing is copied by hand.
The output is generated, so it lives in out/ and isn't committed.

Slots match GMRS channel numbers, so channel 7 on the display is GMRS 7:

  0       WX1
  1-22    GMRS 1-22
  23-     GMRS repeaters, then WX2-WX7, then the ham monitor channels
"""

import argparse
import csv
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "frequencies.csv"
REPEATERS = ROOT / "uv5g" / "repeaters.csv"
SETTINGS_PATH = ROOT / "uv5g" / "radio-settings.json"
OUTPUT = ROOT / "out" / "uv5g.csv"

# UV-5R settings the UV-5G must never inherit or have written, so it keeps its
# own factory values: the transmit band limits and band-range override (a
# certified radio could keep its GMRS-only lock there; this one's firmware does
# it, but don't rely on that), the per-unit squelch calibration, and the VFOs,
# whose 2.5 kHz factory step is what reaches GMRS's 12.5 kHz channels.
NOT_INHERITED = ("limits_new.", "allrange", "squelch_new.", "vfoa.", "vfob.")

# CHIRP's UV-5R-family power levels: High is 4 W, Low is 1 W.
HIGH, LOW = "4.0W", "1.0W"
# FRS/GMRS 8-14 are the 467 MHz interstitials: narrowband, low power (47 CFR 95.1767).
INTERSTITIAL = range(8, 15)

# The family's simplex channels. 19 has no repeater output within about 15
# miles, unlike most of 15-22. The backup is one of 1-7, which are never
# repeater outputs; 1 is skipped because FRS radios default to it.
# uv5g/radio-settings.json starts channel A on FAMILY.
FAMILY, BACKUP = 19, 3

# Receive-only ham channels from frequencies.csv, as (Name, Frequency) so they
# survive renumbering, the same way card.py's STICKER does.
MONITOR = [
    ("WAMU TO", "449.975"),
    ("N3ADV W", "447.175"),
    ("W3DCA W", "147.270"),
    ("SKYWARN", "147.300"),
    ("SKYWRN2", "147.300"),
    ("2M CALL", "146.520"),
    ("70CM CA", "446.000"),
]

WEATHER = [f"WX{n}" for n in range(1, 8)]


def load(path):
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def find(rows, name, freq=None):
    for r in rows:
        if r["Name"] == name and (freq is None or float(r["Frequency"]) == float(freq)):
            return dict(r)
    where = f"{name} {freq}" if freq else name
    raise SystemExit(f"UV-5G channel {where} isn't in {SOURCE.name}")


def gmrs(rows, n):
    """GMRS n as a routine, transmit-capable channel on a certified radio."""
    r = find(rows, f"GMRS {n}")
    low = n in INTERSTITIAL
    r.update(
        Duplex="",
        Offset="0.000000",
        Mode="NFM" if low else "FM",
        Power=LOW if low else HIGH,
        Skip="",
        Comment=f"GMRS/FRS {n}"
        + {FAMILY: "; family channel", BACKUP: "; backup family channel"}.get(n, "")
        + ("; narrowband, low power (95.1767)" if low else ""),
    )
    return r


def receive_only(r, why):
    r = dict(r)
    r.update(Duplex="off", Offset="0.000000", Power=HIGH, Comment=f"{why}; {r['Comment']}")
    return r


def build_rows():
    fields, rows = load(SOURCE)
    weather = [receive_only(find(rows, wx), "RX only") for wx in WEATHER]
    for wx in weather:
        wx["Skip"] = "S"  # NOAA transmits nonstop, so a scan would park on it.
    repeaters = load(REPEATERS)[1] if REPEATERS.exists() else []
    out = (
        weather[:1]
        + [gmrs(rows, n) for n in range(1, 23)]
        + [dict(r, Power=HIGH) for r in repeaters]
        + weather[1:]
        + [receive_only(find(rows, name, freq), "Ham, RX only") for name, freq in MONITOR]
    )
    for slot, r in enumerate(out):
        r["Location"] = str(slot)
    return fields, out


def write(fields, rows, path):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="ascii") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def build(path=OUTPUT):
    """Write the UV-5G channel list and return its path."""
    return write(*build_rows(), path)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-o", "--output", default=str(OUTPUT))
    args = parser.parse_args()
    print(build(args.output))


if __name__ == "__main__":
    main()
