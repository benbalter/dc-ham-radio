"""Rebuild the repeater block of frequencies.csv from RepeaterBook.

Usage:
  python3 scripts/refresh.py              # fetch, rebuild, and print what changed
  python3 scripts/refresh.py --html X     # use a saved proximity-search page instead
  python3 scripts/refresh.py --dry-run    # print what would change; don't write

Only the repeater block changes. Primary channels, simplex calling, NOAA, and the
emergency block are copied over as-is. Repeaters are sorted nearest first
from downtown Washington, DC. Curated comments on repeaters that are already
in the list are kept. Standard library only.

RepeaterBook statuses are user-reported, so review the changes before you
commit or program the radio.
"""

import argparse
import csv
import datetime
import html
import pathlib
import re
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import card  # shares the block-splitting logic

ROOT = pathlib.Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "frequencies.csv"

# Downtown Washington, DC. Repeaters are sorted by distance from here.
CENTER = (38.9072, -77.0369)
MAX_MILES = 26  # past this, a 4 W handheld rarely reaches
UV5R_CHANNELS = 128
URL = (
    "https://www.repeaterbook.com/repeaters/prox_result.php"
    "?lat={lat}&long={lon}&distance=40&Dunit=m&band1=%25&mode%5B%5D=1"
    "&status_id=%25&use=%25&order=distance_calc"
)
BANDS = [(144.0, 148.0), (420.0, 450.0)]


def fetch(lat, lon):
    request = urllib.request.Request(URL.format(lat=lat, lon=lon), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", "replace")


def text(cell):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", cell))).strip()


def parse(page):
    """Yield one dict per repeater row, in RepeaterBook's (distance) order."""
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        if "details.php" not in row:
            continue
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) < 12:
            continue
        status = re.search(r'status-icon.*?title="([^"]*)"', row, re.S)
        miles = re.search(r'data-sort="([0-9.]+)"', cells[9])
        values = [text(c) for c in cells]
        yield {
            "freq": float(values[1]),
            "offset": values[2],
            "tone": values[3],
            "call": values[4],
            "city": values[5],
            "use": values[7],
            "modes": values[8].split(),
            "miles": float(miles.group(1)) if miles else float(values[9]),
            "status": status.group(1) if status else "",
        }


def usable(rep):
    return (
        rep["use"] == "OPEN"
        # "Unknown Status" isn't off-air; leave out only Not Operational and Testing.
        and rep["status"] in ("Operational", "Unknown Status")
        and "FM" in rep["modes"]
        and any(lo <= rep["freq"] <= hi for lo, hi in BANDS)
        and rep["miles"] <= MAX_MILES
        # A digital code with no analog tone (e.g. "CC 1") means digital-first.
        and not (re.search(r"\b(NAC|CC|RAN|DSQ)\b", rep["tone"]) and not tone(rep["tone"]))
    )


def shift(offset):
    match = re.fullmatch(r"([+-])\s*([0-9.]+) MHz", offset)
    if not match:
        return None
    return match.group(1), f"{float(match.group(2)):.6f}"


def tone(field):
    """The analog CTCSS tone, ignoring digital codes like NAC 293 or CC 1."""
    field = re.sub(r"\b(NAC|CC|RAN|DSQ)\s+\S+", "", field)
    tones = re.findall(r"\b\d{2,3}\.\d\b", field)
    return tones[-1] if tones else ""


def name(call, city):
    return f"{call} {city.upper()}"[:7].rstrip()


def comment(rep):
    other = [m for m in rep["modes"] if m != "FM"]
    return rep["city"] + (f" ({'/'.join(['FM'] + other)})" if other else "")


def build(old_repeaters, keep_freqs, reps, template, room):
    """New repeater rows from RepeaterBook data, nearest first."""
    old = {(r["Frequency"], r["Name"]): r for r in old_repeaters}
    rows, seen = [], set()
    for rep in reps:
        if not usable(rep):
            continue
        freq = f"{rep['freq']:.6f}"
        dup = shift(rep["offset"])
        if dup is None or freq in keep_freqs or (freq, rep["call"]) in seen:
            continue
        seen.add((freq, rep["call"]))
        row = dict(template)
        row.update({
            "Name": name(rep["call"], rep["city"]),
            "Frequency": freq,
            "Duplex": dup[0],
            "Offset": dup[1],
            "Tone": "Tone" if tone(rep["tone"]) else "",
            "rToneFreq": tone(rep["tone"]) or "88.5",
            "cToneFreq": "88.5",
            "Mode": "FM",
            "TStep": "5.00",
            "Skip": "",
            "Power": "4.0W",
        })
        previous = old.get((freq, row["Name"]))
        row["Comment"] = previous["Comment"] if previous else comment(rep)
        rows.append(row)
        if len(rows) == room:
            break
    return rows


def describe(row):
    tone_text = f" {row['rToneFreq']}" if row["Tone"] else ""
    return f"{row['Name']:<7} {float(row['Frequency']):.4f} {row['Duplex']}{float(row['Offset']):g}{tone_text}"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--html", help="saved RepeaterBook proximity-search page")
    parser.add_argument("--csv", default=str(CSV_PATH))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    page = pathlib.Path(args.html).read_text(errors="replace") if args.html else fetch(*CENTER)
    reps = list(parse(page))
    if not reps:
        sys.exit("No repeaters found in the RepeaterBook page; its layout may have changed.")

    rows = card.load(args.csv)
    header = list(rows[0].keys())
    blocks = dict(card.blocks(rows))
    favorites = blocks["Primary channels"]
    simplex = blocks["Simplex calling"]
    old_repeaters = blocks["Repeaters, nearest first"]
    tail = blocks["NOAA Weather Radio"] + blocks["Emergency and monitor"]

    keep_freqs = {r["Frequency"] for r in favorites + simplex}
    room = UV5R_CHANNELS - len(favorites) - len(simplex) - len(tail)
    new_repeaters = build(old_repeaters, keep_freqs, reps, old_repeaters[0], room)

    before = {describe(r) for r in old_repeaters}
    after = {describe(r) for r in new_repeaters}
    for line in sorted(before - after):
        print(f"  - {line}")
    for line in sorted(after - before):
        print(f"  + {line}")
    moved = [r for r in new_repeaters if describe(r) in before]
    print(f"{len(new_repeaters)} repeaters ({len(after - before)} added, {len(before - after)} removed, "
          f"{len(moved)} kept) within {MAX_MILES} mi of downtown DC, "
          f"pulled {datetime.date.today().isoformat()}.")

    if args.dry_run:
        return
    out = favorites + simplex + new_repeaters + tail
    for i, row in enumerate(out):
        row["Location"] = str(i)
    with open(args.csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(out)
    print(f"Wrote {args.csv}. Run the tests, update README's channel ranges, then reprogram the radio.")


if __name__ == "__main__":
    main()
