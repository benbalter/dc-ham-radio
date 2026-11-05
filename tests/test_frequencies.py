"""Checks frequencies.csv against the format rules in CLAUDE.md.

Run with: python3 -m unittest discover tests
"""

import csv
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "frequencies.csv"

HEADER = (
    "Location,Name,Frequency,Duplex,Offset,Tone,rToneFreq,cToneFreq,DtcsCode,"
    "DtcsPolarity,RxDtcsCode,CrossMode,Mode,TStep,Skip,Power,Comment,URCALL,"
    "RPT1CALL,RPT2CALL,DVCODE"
)

# What the UV-5R can tune.
RX_BANDS = [(136.0, 174.0), (400.0, 520.0)]
# Where this operator may transmit: the 2m and 70cm amateur bands.
TX_BANDS = [(144.0, 148.0), (420.0, 450.0)]
# GMRS/FRS simplex channels (47 CFR 95.563). The UV-5R isn't certified for
# them, so they're programmed for life-threatening emergencies only, which
# 47 CFR 97.403/97.405 are commonly cited to cover. Nothing else outside the
# ham bands may transmit.
GMRS_SIMPLEX = {
    462.5625, 462.5875, 462.6125, 462.6375, 462.6625, 462.6875, 462.7125,
    467.5625, 467.5875, 467.6125, 467.6375, 467.6625, 467.6875, 467.7125,
    462.5500, 462.5750, 462.6000, 462.6250, 462.6500, 462.6750, 462.7000, 462.7250,
}
NATIONAL_CALLING = ("146.520000", "446.000000")


def in_bands(freq, bands, top_inclusive=True):
    if top_inclusive:
        return any(lo <= freq <= hi for lo, hi in bands)
    return any(lo <= freq < hi for lo, hi in bands)


def tx_freq(row):
    """Transmit frequency in MHz, or None for a receive-only row."""
    freq = float(row["Frequency"])
    offset = float(row["Offset"] or 0)
    duplex = row["Duplex"]
    if duplex == "off":
        return None
    if duplex == "+":
        return freq + offset
    if duplex == "-":
        return freq - offset
    if duplex == "":
        return freq
    raise ValueError(f"unexpected Duplex {duplex!r}")


class FrequenciesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = CSV_PATH.read_bytes()
        with open(CSV_PATH, newline="") as f:
            cls.rows = list(csv.DictReader(f))

    def test_header(self):
        self.assertEqual(self.raw.split(b"\r\n", 1)[0].decode(), HEADER)

    def test_crlf_and_ascii(self):
        self.raw.decode("ascii")
        self.assertNotIn(b"\n", self.raw.replace(b"\r\n", b""))

    def test_locations_contiguous(self):
        locations = [int(r["Location"]) for r in self.rows]
        self.assertEqual(locations, list(range(len(locations))))
        self.assertLessEqual(len(locations), 128)

    def test_names(self):
        for r in self.rows:
            name = r["Name"]
            with self.subTest(slot=r["Location"], name=name):
                self.assertTrue(0 < len(name) <= 7)
                self.assertEqual(name, name.upper())

    def test_receive_range(self):
        for r in self.rows:
            with self.subTest(slot=r["Location"], name=r["Name"]):
                self.assertTrue(in_bands(float(r["Frequency"]), RX_BANDS))

    def test_tones(self):
        for r in self.rows:
            with self.subTest(slot=r["Location"], name=r["Name"]):
                self.assertIn(r["Tone"], ("", "Tone", "TSQL"))
                if r["Tone"] == "TSQL":
                    self.assertEqual(r["cToneFreq"], r["rToneFreq"])
                else:
                    self.assertEqual(r["cToneFreq"], "88.5")

    def test_duplex_and_power(self):
        for r in self.rows:
            with self.subTest(slot=r["Location"], name=r["Name"]):
                self.assertIn(r["Duplex"], ("", "+", "-", "off"))
                self.assertEqual(r["Power"], "4.0W")

    def test_transmit_only_in_amateur_bands(self):
        # One rule covers MURS, marine, NOAA and typos: anything that can key
        # up must land in 2m or 70cm, be an emergency-only GMRS simplex
        # channel, or be Duplex "off".
        for r in self.rows:
            tx = tx_freq(r)
            if tx is None:
                continue
            with self.subTest(slot=r["Location"], name=r["Name"], tx=tx):
                if round(tx, 6) in GMRS_SIMPLEX:
                    self.assertEqual(r["Duplex"], "")
                    self.assertIn("life-threatening emergency", r["Comment"])
                    continue
                # Top edge exclusive: a carrier on 148.000 or 450.000 spills out of band.
                self.assertTrue(in_bands(round(tx, 6), TX_BANDS, top_inclusive=False))

    def test_weather_skipped_in_scan(self):
        # NOAA transmits nonstop, so a scan would pause or, with Scan Resume "CO",
        # park on it forever. Weather channels are picked by hand.
        for r in self.rows:
            if 162.4 <= float(r["Frequency"]) <= 162.55:
                with self.subTest(slot=r["Location"], name=r["Name"]):
                    self.assertEqual(r["Skip"], "S")

    def test_only_family_and_calling_gmrs_scanned(self):
        # FRS radios and baby monitors keep the rest busy, and this radio only
        # transmits on GMRS in an emergency, so scan just the channels that matter.
        for r in self.rows:
            if r["Name"].startswith("GMRS "):
                with self.subTest(name=r["Name"]):
                    want = "" if r["Name"] in ("GMRS 19", "GMRS 20") else "S"
                    self.assertEqual(r["Skip"], want)

    def test_national_calling_present(self):
        simplex = {r["Frequency"] for r in self.rows if r["Duplex"] == ""}
        for freq in NATIONAL_CALLING:
            with self.subTest(freq=freq):
                self.assertIn(freq, simplex)


class CardTest(unittest.TestCase):
    def test_card_renders_every_sticker_slot(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            import card
        finally:
            sys.path.pop(0)

        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "card.html"
            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "card.py"), "-o", str(out)],
                check=True,
            )
            page = out.read_text(encoding="utf-8")
        sticker = page.split('<div class="sticker">', 1)[1].split("</div>", 1)[0]
        rows = card.load(CSV_PATH)
        on_sticker = {float(f) for _, f in card.STICKER}
        for freq in NATIONAL_CALLING:
            self.assertIn(float(freq), on_sticker)
        for name, freq in card.STICKER:
            with self.subTest(name=name, freq=freq):
                row = card.find(rows, name, freq)
                self.assertIn(f'data-slot="{row["Location"]}"', sticker)


if __name__ == "__main__":
    unittest.main()
