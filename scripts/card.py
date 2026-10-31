"""Render frequencies.csv as a printable UV-5R battery sticker and a full channel sheet.

Usage: python3 scripts/card.py [-o out/card.html]

Print at 100% scale (no "fit to page"), cut out the sticker, and cover it with
clear packing tape. Everything comes from the CSV, so rerun this after any
channel change and reprint.
"""

import argparse
import csv
import html
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Sticker size. Measure the back of your battery and adjust.
STICKER_WIDTH_IN = 2.0
STICKER_HEIGHT_IN = 3.5

# Channels on the sticker, as (Name, Frequency) so they survive renumbering.
# Name alone isn't unique (KV3B RO is two repeaters).
STICKER = [
    ("WAMU TO", "449.975"),
    ("N3ADV W", "447.175"),
    ("W3DCA W", "147.270"),
    ("WNG736", "162.450"),
    ("2M CALL", "146.520"),
    ("70CM CA", "446.000"),
    ("SIMP 55", "146.550"),
    ("KV3B RO", "146.955"),
    ("SKYWARN", "147.300"),
    ("KM4DC", "145.065"),
    ("GMRS 20", "462.675"),
]


def load(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def mhz(row):
    """Three decimals like a radio display, four for 12.5 kHz channels."""
    text = f"{float(row['Frequency']):.4f}"
    return text[:-1] if text.endswith("0") else text


def shift(row):
    if row["Duplex"] == "off":
        return "RX"
    if row["Duplex"] in ("+", "-"):
        return row["Duplex"] + f"{float(row['Offset']):g}"
    if row["Duplex"] == "" and "life-threatening emergency" in row["Comment"]:
        return "EMG"
    if row["Duplex"] == "":
        return "S"
    raise SystemExit(f"Unsupported Duplex {row['Duplex']!r} in slot {row['Location']}")


def tone(row):
    if row["Tone"] == "Tone":
        return row["rToneFreq"]
    if row["Tone"] == "TSQL":
        return row["rToneFreq"] + "T"
    return ""


def find(rows, name, freq):
    for r in rows:
        if r["Name"] == name and float(r["Frequency"]) == float(freq):
            return r
    raise SystemExit(f"Sticker channel {name} {freq} isn't in frequencies.csv")


def blocks(rows):
    """Split rows into the blocks CLAUDE.md describes."""
    wx = [i for i, r in enumerate(rows) if r["Name"] in {f"WX{n}" for n in range(1, 8)}]
    simplex = [i for i, r in enumerate(rows) if r["Name"] in ("2M CALL", "70CM CA")]
    if not wx or not simplex:
        raise SystemExit("frequencies.csv is missing the WX1-WX7 or simplex calling rows")
    first_wx, last_wx = min(wx), max(wx)
    first_rep = max(simplex) + 1
    return [
        ("Primary channels", rows[:min(simplex)]),
        ("Simplex calling", rows[min(simplex):first_rep]),
        ("Repeaters, nearest first", rows[first_rep:first_wx]),
        ("NOAA Weather Radio", rows[first_wx:last_wx + 1]),
        ("Emergency and monitor", rows[last_wx + 1:]),
    ]


def tr(row, comment=False):
    cells = [row["Location"], row["Name"], mhz(row), shift(row), tone(row)]
    if comment:
        cells.append(row["Comment"])
    tds = "".join(f"<td>{html.escape(c)}</td>" for c in cells)
    return f'<tr data-slot="{row["Location"]}">{tds}</tr>'


CSS = """
@page { size: letter; margin: 0.4in; }
* { box-sizing: border-box; }
body { font: 9pt/1.25 ui-monospace, Menlo, Consolas, monospace; color: #000; background: #fff; margin: 0; }
.sticker { width: %(w)sin; height: %(h)sin; border: 1px dashed #000; padding: 0.06in; overflow: hidden; }
.sticker h1 { font-size: 8pt; margin: 0 0 0.04in; text-align: center; }
.sticker table { width: 100%%; border-collapse: collapse; font-size: 7pt; }
.sticker td { padding: 0.035in 0.02in; border-bottom: 0.5px solid #999; white-space: nowrap; }
.sticker .key { font-size: 5.5pt; margin-top: 0.05in; }
.sheet { page-break-before: always; }
.sheet h1 { font-size: 12pt; margin: 0 0 4pt; }
.sheet h2 { font-size: 10pt; margin: 8pt 0 2pt; }
.sheet table { width: 100%%; border-collapse: collapse; font-size: 7.5pt; table-layout: fixed; }
.sheet td:nth-child(1) { width: 0.35in; }
.sheet td:nth-child(2) { width: 0.7in; }
.sheet td:nth-child(3) { width: 0.75in; }
.sheet td:nth-child(4) { width: 0.4in; }
.sheet td:nth-child(5) { width: 0.5in; }
.sheet td { padding: 1pt 3pt; border-bottom: 0.5px solid #bbb; vertical-align: top; }
.sheet td:nth-child(-n+5) { white-space: nowrap; }
.hint { font: 9pt/1.3 system-ui, sans-serif; margin: 0 0 0.2in; }
@media print { .hint { display: none; } }
"""

KEY = (
    "S simplex &middot; &plusmn; offset MHz &middot; T tone squelch &middot; "
    "RX receive only &middot; EMG transmit only in a life-threatening emergency"
)


def render(rows):
    sticker = "".join(tr(find(rows, n, f)) for n, f in STICKER)
    sheet = "".join(
        f"<h2>{html.escape(title)}</h2><table>{''.join(tr(r, True) for r in group)}</table>"
        for title, group in blocks(rows)
        if group
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>UV-5R channel card</title>
<style>{CSS % {"w": STICKER_WIDTH_IN, "h": STICKER_HEIGHT_IN}}</style></head>
<body>
<p class="hint">Print at 100% scale. Check the sticker measures {STICKER_WIDTH_IN} &times; {STICKER_HEIGHT_IN} in before cutting.</p>
<div class="sticker"><h1>UV-5R &middot; Washington DC</h1><table>{sticker}</table><div class="key">{KEY}</div></div>
<div class="sheet"><h1>UV-5R channels &middot; Washington, DC</h1><div>{KEY}</div>{sheet}</div>
</body></html>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-o", "--output", default=str(ROOT / "out" / "card.html"))
    parser.add_argument("-i", "--input", default=str(ROOT / "frequencies.csv"))
    args = parser.parse_args()
    out = pathlib.Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(load(args.input)), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
