"""Checks scripts/gobag.py picks the right files without touching a real stick."""

import datetime
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import gobag
finally:
    sys.path.pop(0)


class GobagTest(unittest.TestCase):
    def test_newest_image_per_radio(self):
        with tempfile.TemporaryDirectory() as tmp:
            backups = pathlib.Path(tmp)
            for name in ("uv5r-20261030-221213.img", "uv5r-20261104-235813.img",
                         "uv5g-20261104-231132.img", "notes.txt"):
                (backups / name).write_bytes(b"")
            found = gobag.newest_images(backups)
        self.assertEqual({r: p.name for r, p in found.items()},
                         {"uv5r": "uv5r-20261104-235813.img", "uv5g": "uv5g-20261104-231132.img"})

    def test_plan_and_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder, items = gobag.plan(tmp, today=datetime.date(2026, 11, 5))
            self.assertEqual(folder.name, "dc-ham-radio-2026-11-05")
            names = {t.relative_to(folder).as_posix() for _, t, _ in items}
            for expected in ("README.md", "frequencies.csv", "pat/config.json",
                             "uv5r-card.html", "uv5g-card.html"):
                self.assertIn(expected, names)
            # No secrets: Pat's env file only points at 1Password, and isn't needed offline.
            self.assertNotIn("pat/winlink.env", names)
            gobag.write([i for i in items if i[2] != "radio image"])
            self.assertIn("UV-5G", (folder / "uv5g-card.html").read_text(encoding="utf-8"))
            self.assertTrue((folder / "direwolf/direwolf.conf").exists())


if __name__ == "__main__":
    unittest.main()
