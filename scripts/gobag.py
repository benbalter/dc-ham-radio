"""Copy what you need to restore the radios offline onto a USB stick.

Usage: python3 scripts/gobag.py /Volumes/STICK [--dry-run]

Writes a dated folder (dc-ham-radio-YYYY-MM-DD) holding:
  - the newest backup image of each radio (backups/<radio>-*.img), which any
    laptop with CHIRP can upload back to the radio (File > Open, Radio > Upload)
  - both printable channel cards, freshly rendered
  - the channel lists, settings, and the Dire Wolf and Pat configs
  - the README, for the steps

program.py saves its backup before writing, so after a write the newest
image is the radio's old state. Run the preview (uv run scripts/program.py,
with --radio uv5g for a UV-5G) once more after reprogramming, so the newest
image matches what's on the radio, then rerun this.

Nothing here is secret: Pat's password comes from 1Password and is never
stored.
"""

import argparse
import datetime
import pathlib
import shutil

import card
import uv5g

ROOT = pathlib.Path(__file__).resolve().parent.parent
RADIOS = ("uv5r", "uv5g")
FILES = [
    "README.md",
    "frequencies.csv",
    "radio-settings.json",
    "uv5g/radio-settings.json",
    "uv5g/repeaters.csv",
    "direwolf/direwolf.conf",
    "pat/config.json",
]


def newest_images(backups):
    """The newest image per radio, by the timestamp in its file name."""
    found = {}
    for radio in RADIOS:
        images = sorted(pathlib.Path(backups).glob(f"{radio}-*.img"))
        if images:
            found[radio] = images[-1]
    return found


def plan(dest, root=ROOT, today=None):
    """[(source or None, destination, what)] for everything to write."""
    today = today or datetime.date.today()
    folder = pathlib.Path(dest) / f"dc-ham-radio-{today.isoformat()}"
    items = [(path, folder / "backups" / path.name, "radio image")
             for path in newest_images(root / "backups").values()]
    items += [(root / name, folder / name, "file") for name in FILES if (root / name).exists()]
    items += [(None, folder / "uv5r-card.html", "card"), (None, folder / "uv5g-card.html", "card")]
    return folder, items


def write(items):
    for source, target, _ in items:
        target.parent.mkdir(parents=True, exist_ok=True)
        if source is not None:
            shutil.copy2(source, target)
        elif target.name == "uv5r-card.html":
            target.write_text(card.render(card.load(ROOT / "frequencies.csv"), "uv5r"), encoding="utf-8")
        else:
            target.write_text(card.render(card.load(uv5g.build()), "uv5g"), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dest", help="where to write, usually the USB stick (/Volumes/NAME)")
    parser.add_argument("--dry-run", action="store_true", help="list what would be copied")
    args = parser.parse_args()
    dest = pathlib.Path(args.dest)
    if not dest.is_dir():
        raise SystemExit(f"{dest} isn't a folder. Plug in the stick and pass its /Volumes path.")
    folder, items = plan(dest)
    images = [s for s, _, what in items if what == "radio image"]
    missing = [r for r in RADIOS if not any(p.name.startswith(f"{r}-") for p in images)]
    for source, target, what in items:
        print(f"  {what:<11} {target.relative_to(dest)}" + (f"  (from {source.name})" if what == "radio image" else ""))
    if missing:
        print(f"No backup image yet for: {', '.join(missing)}. Read that radio with program.py first.")
    print("Images are taken before each write: if you just reprogrammed, run the preview once more first.")
    if args.dry_run:
        print("Dry run: nothing written.")
        return
    write(items)
    print(f"Wrote {folder}")


if __name__ == "__main__":
    main()
