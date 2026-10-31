"""Tests for radio-settings.json, scripts/radio_settings.py, and scripts/program.py.

The program.py tests need uv (to fetch CHIRP) and a radio image in backups/,
which only exists after `uv run scripts/program.py` has read a radio. They
skip otherwise, so the rest of the suite still runs anywhere.
"""

import copy
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SETTINGS_PATH = ROOT / "radio-settings.json"
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import radio_settings
finally:
    sys.path.pop(0)

SAMPLE = {
    "Basic Settings": {
        "squelch": {"label": "Carrier Squelch Level", "value": 5},
        "beep": {"label": "Beep", "value": True},
    },
    "Other Settings": {
        "poweron_msg.line1": {"label": "Power-On Message 1", "value": "WELCOME"},
    },
}


class RadioSettingsTest(unittest.TestCase):
    def test_flatten(self):
        flat = radio_settings.flatten(SAMPLE)
        self.assertEqual(flat["squelch"], ("Basic Settings", "Carrier Squelch Level", 5))
        self.assertEqual(len(flat), 3)

    def test_diff_identical(self):
        self.assertEqual(radio_settings.diff(SAMPLE, copy.deepcopy(SAMPLE)), [])

    def test_diff_reports_change(self):
        desired = copy.deepcopy(SAMPLE)
        desired["Basic Settings"]["squelch"]["value"] = 3
        self.assertEqual(
            radio_settings.diff(SAMPLE, desired),
            [("squelch", "Carrier Squelch Level", 5, 3)],
        )

    def test_diff_ignores_string_padding(self):
        current = copy.deepcopy(SAMPLE)
        current["Other Settings"]["poweron_msg.line1"]["value"] = "WELCOME   "
        self.assertEqual(radio_settings.diff(current, SAMPLE), [])

    def test_diff_flags_unknown_key(self):
        desired = copy.deepcopy(SAMPLE)
        desired["Basic Settings"]["sqelch"] = {"label": "typo", "value": 3}
        self.assertEqual(radio_settings.diff(SAMPLE, desired), [("sqelch", "typo", None, 3)])

    def test_diff_only_checks_desired_keys(self):
        # Settings the file doesn't list are left alone, not reported.
        desired = {"Basic Settings": {"squelch": SAMPLE["Basic Settings"]["squelch"]}}
        self.assertEqual(radio_settings.diff(SAMPLE, desired), [])

    def test_load_missing_returns_none(self):
        self.assertIsNone(radio_settings.load(ROOT / "does-not-exist.json"))

    def test_dump_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "s.json"
            radio_settings.dump(SAMPLE, path)
            self.assertEqual(radio_settings.load(path), SAMPLE)


class SettingsFileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = SETTINGS_PATH.read_text(encoding="utf-8")
        cls.settings = json.loads(cls.raw)

    def test_canonical_format(self):
        # Hand edits must keep the dump format, so --save-settings diffs stay clean.
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "s.json"
            radio_settings.dump(self.settings, path)
            self.assertEqual(path.read_text(encoding="utf-8"), self.raw)

    def test_entries(self):
        for key, (group, label, value) in radio_settings.flatten(self.settings).items():
            with self.subTest(key=key):
                self.assertTrue(group and label)
                self.assertIsInstance(value, (bool, int, float, str))

    def test_band_limits_cover_the_channel_list(self):
        flat = {k: v for k, (_, _, v) in radio_settings.flatten(self.settings).items()}
        self.assertLessEqual(int(flat["limits_new.vhf.lower"]), 136)
        self.assertGreaterEqual(int(flat["limits_new.vhf.upper"]), 174)
        self.assertLessEqual(int(flat["limits_new.uhf.lower"]), 400)
        self.assertGreaterEqual(int(flat["limits_new.uhf.upper"]), 520)
        self.assertTrue(flat["limits_new.vhf.enable"])
        self.assertTrue(flat["limits_new.uhf.enable"])

    def test_alarm_never_transmits(self):
        # "Tone" and "Code" key up on whatever channel is selected, which
        # could be an emergency-only GMRS channel. "Site" only sounds locally.
        flat = {k: v for k, (_, _, v) in radio_settings.flatten(self.settings).items()}
        self.assertEqual(flat["almod"], "Site")


def latest_image():
    images = sorted((ROOT / "backups").glob("uv5r-*.img"))
    return images[-1] if images else None


@unittest.skipUnless(shutil.which("uv") and latest_image(), "needs uv and a radio image in backups/")
class ProgramTest(unittest.TestCase):
    def run_program(self, *args):
        return subprocess.run(
            ["uv", "run", "--quiet", str(ROOT / "scripts" / "program.py"),
             "--image", str(latest_image()), *args],
            capture_output=True, text=True, timeout=600,
        )

    def test_csv_and_settings_convert_for_the_radio(self):
        result = self.run_program()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Dry run: nothing written", result.stdout)

    def test_settings_change_is_detected_and_applies(self):
        desired = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        squelch = desired["Basic Settings"]["squelch"]
        squelch["value"] = 9 if squelch["value"] != 9 else 1
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "s.json"
            radio_settings.dump(desired, path)
            result = self.run_program("--settings", str(path))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("setting Carrier Squelch Level (squelch)", result.stdout)

    def test_unknown_setting_is_rejected(self):
        desired = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        desired["Basic Settings"]["sqelch"] = {"label": "typo", "value": 3}
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "s.json"
            radio_settings.dump(desired, path)
            result = self.run_program("--settings", str(path))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sqelch: not a setting on this radio", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
