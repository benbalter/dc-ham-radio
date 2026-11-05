"""Checks the UV-5G's channel list and settings, built by scripts/uv5g.py.

Run with: python3 -m unittest discover tests
"""

import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
try:
    from test_frequencies import GMRS_SIMPLEX, HEADER, RX_BANDS, in_bands, tx_freq

    import card
    import radio_settings
    import uv5g
finally:
    del sys.path[:2]

# GMRS repeater outputs (47 CFR 95.1763); inputs are 5 MHz up.
GMRS_REPEATER_OUT = {462.5500, 462.5750, 462.6000, 462.6250, 462.6500, 462.6750, 462.7000, 462.7250}


class UV5GChannelsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = uv5g.build(pathlib.Path(cls.tmp.name) / "uv5g.csv")
        cls.raw = cls.path.read_bytes()
        _, cls.rows = uv5g.load(cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_format(self):
        self.assertEqual(self.raw.split(b"\r\n", 1)[0].decode(), HEADER)
        self.assertNotIn(b"\n", self.raw.replace(b"\r\n", b""))
        self.raw.decode("ascii")
        self.assertEqual([int(r["Location"]) for r in self.rows], list(range(len(self.rows))))
        self.assertLessEqual(len(self.rows), 128)

    def test_names_and_receive_range(self):
        for r in self.rows:
            with self.subTest(slot=r["Location"], name=r["Name"]):
                self.assertLessEqual(len(r["Name"]), 7)
                self.assertEqual(r["Name"], r["Name"].upper())
                self.assertTrue(in_bands(float(r["Frequency"]), RX_BANDS))

    def test_slot_matches_gmrs_channel(self):
        # So "channel 7" on the display is GMRS 7.
        for n in range(1, 23):
            self.assertEqual(self.rows[n]["Name"], f"GMRS {n}")

    def test_transmit_only_on_gmrs(self):
        # The firmware enforces this too, but a row that can key up must be a
        # GMRS simplex channel or a GMRS repeater pair. Everything else is RX only.
        for r in self.rows:
            tx = tx_freq(r)
            if tx is None:
                continue
            with self.subTest(slot=r["Location"], name=r["Name"], tx=tx):
                freq = round(float(r["Frequency"]), 6)
                if r["Duplex"] == "":
                    self.assertIn(freq, GMRS_SIMPLEX)
                else:
                    self.assertIn(freq, GMRS_REPEATER_OUT)
                    self.assertEqual((r["Duplex"], float(r["Offset"])), ("+", 5.0))

    def test_family_channels(self):
        # Simplex, full power, not a repeater output in the list, and first on the sticker.
        outputs = {r["Frequency"] for r in self.rows if r["Duplex"] == "+"}
        for n, role in ((uv5g.FAMILY, "family channel"), (uv5g.BACKUP, "backup family channel")):
            with self.subTest(channel=n):
                r = self.rows[n]
                self.assertIn(role, r["Comment"])
                self.assertEqual((r["Duplex"], r["Power"]), ("", uv5g.HIGH))
                self.assertNotIn(r["Frequency"], outputs)
        self.assertEqual([n for n, _ in card.STICKER_UV5G[:2]], [f"GMRS {uv5g.FAMILY}", f"GMRS {uv5g.BACKUP}"])

    def test_interstitials_narrow_and_low(self):
        for n in uv5g.INTERSTITIAL:
            with self.subTest(channel=n):
                self.assertEqual((self.rows[n]["Mode"], self.rows[n]["Power"]), ("NFM", uv5g.LOW))

    def test_no_emergency_only_wording(self):
        # The UV-5G is certified, so GMRS is routine on it. That phrase marks
        # the UV-5R's emergency-only rows and mustn't carry over.
        for r in self.rows:
            self.assertNotIn("life-threatening emergency", r["Comment"])

    def test_weather_skipped_in_scan(self):
        for r in self.rows:
            if 162.4 <= float(r["Frequency"]) <= 162.55:
                with self.subTest(slot=r["Location"], name=r["Name"]):
                    self.assertEqual((r["Duplex"], r["Skip"]), ("off", "S"))

    def test_card_renders_every_sticker_slot(self):
        page = card.render(self.rows, "uv5g")
        sticker = page.split('<div class="sticker">', 1)[1].split("</div>", 1)[0]
        for name, freq in card.STICKER_UV5G:
            with self.subTest(name=name, freq=freq):
                row = card.find(self.rows, name, freq)
                self.assertIn(f'data-slot="{row["Location"]}"', sticker)
        self.assertNotIn("EMG", page)


class UV5GSettingsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = uv5g.SETTINGS_PATH.read_text(encoding="utf-8")
        cls.own = radio_settings.load(uv5g.SETTINGS_PATH)
        # The same layering program.py --radio uv5g does.
        base = radio_settings.drop(radio_settings.load(ROOT / "radio-settings.json"), uv5g.NOT_INHERITED)
        cls.flat = {k: v for k, (_, _, v) in radio_settings.flatten(radio_settings.merge(base, cls.own)).items()}

    def test_canonical_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "s.json"
            radio_settings.dump(self.own, path)
            self.assertEqual(path.read_text(encoding="utf-8"), self.raw)

    def test_tx_limits_and_calibration_stay_the_radios_own(self):
        # Writing the UV-5R's 136-174/400-520 TX limits could unlock ham-band
        # transmit on a certified GMRS radio. Neither file may set them.
        self.assertTrue(any(k.startswith("limits_new.") for k in radio_settings.flatten(
            radio_settings.load(ROOT / "radio-settings.json"))), "base no longer has limits; recheck NOT_INHERITED")
        for key in [*self.flat, *radio_settings.flatten(self.own)]:
            with self.subTest(key=key):
                self.assertFalse(key.startswith(uv5g.NOT_INHERITED))

    def test_keypad_locks(self):
        self.assertIs(self.flat["autolk"], True)
        self.assertIs(self.flat["keylock"], True)

    def test_hard_to_mess_up(self):
        # No transmitting over someone, no keypad factory reset, limited menus.
        self.assertIs(self.flat["bcl"], True)
        self.assertIs(self.flat["reset"], False)
        self.assertIs(self.flat["menu"], False)
        # Channel names, not frequencies, on both lines.
        self.assertEqual((self.flat["mdfa"], self.flat["mdfb"]), ("Name", "Name"))

    def test_alarm_never_transmits(self):
        self.assertEqual(self.flat["almod"], "Site")

    def test_starts_in_channel_mode_on_gmrs(self):
        _, rows = uv5g.build_rows()
        self.assertEqual(self.flat["workmode"], "Channel")
        for key in ("wmchannel.mrcha", "wmchannel.mrchb"):
            with self.subTest(key=key):
                self.assertTrue(rows[self.flat[key]]["Name"].startswith("GMRS "))
        self.assertEqual(self.flat["wmchannel.mrcha"], uv5g.FAMILY)


if __name__ == "__main__":
    unittest.main()
