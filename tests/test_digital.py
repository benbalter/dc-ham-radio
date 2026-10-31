"""Tests for the Winlink packet setup: direwolf/, pat/, and scripts/digirig.py.

Standard library only, and no hardware: none of these open the Digirig, so the
suite runs the same on a laptop with nothing plugged in and in CI.
"""

import csv
import json
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIREWOLF_CONF = ROOT / "direwolf" / "direwolf.conf"
PAT_CONFIG = ROOT / "pat" / "config.json"
PAT_ENV = ROOT / "pat" / "winlink.env"
CSV_PATH = ROOT / "frequencies.csv"
CALL = "KO6EYB"

sys.path.insert(0, str(ROOT / "scripts"))
try:
    import digirig
finally:
    sys.path.pop(0)


def direwolf_lines():
    lines = [line.split("#", 1)[0].strip() for line in DIREWOLF_CONF.read_text().splitlines()]
    return [line for line in lines if line]


class DirewolfConfTest(unittest.TestCase):
    def test_station(self):
        lines = direwolf_lines()
        self.assertIn(f"MYCALL {CALL}", lines)
        self.assertIn("MODEM 1200", lines)

    def test_ptt_on_digirig_rts(self):
        self.assertIn("PTT @PTT_PORT@ RTS", direwolf_lines())

    def test_no_beacons(self):
        # Nothing should transmit unless the operator starts a Pat session.
        for line in direwolf_lines():
            self.assertNotRegex(line, r"^(PBEACON|OBEACON|TBEACON|CBEACON|IBEACON|DIGIPEAT|IGSERVER)\b")

    def test_kiss_off(self):
        self.assertIn("KISSPORT 0", direwolf_lines())

    def test_render_fills_placeholders(self):
        out = digirig.render(DIREWOLF_CONF.read_text(), "USB Audio Device", "/dev/cu.usbserial-1")
        self.assertNotRegex(out, r"@[A-Z_]+@")
        self.assertIn('ADEVICE "USB Audio Device" "USB Audio Device"', out)
        self.assertIn("PTT /dev/cu.usbserial-1 RTS", out)

    def test_render_rejects_missing_placeholder(self):
        with self.assertRaises(ValueError):
            digirig.render("MYCALL KO6EYB\n", "x", "y")


class AudioDevicesTest(unittest.TestCase):
    def test_needs_input_and_output(self):
        profile = {
            "SPAudioDataType": [
                {
                    "_items": [
                        {"_name": "Speakers", "coreaudio_device_output": 2},
                        {"_name": "USB Audio Device", "coreaudio_device_input": 1, "coreaudio_device_output": 2},
                        {"_name": "Microphone", "coreaudio_device_input": 1},
                    ]
                }
            ]
        }
        self.assertEqual(digirig.audio_devices(profile), ["USB Audio Device"])

    def test_empty_profile(self):
        self.assertEqual(digirig.audio_devices({}), [])


class PatConfigTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(PAT_CONFIG.read_text())

    def test_no_password_on_disk(self):
        # The password comes from 1Password through pat/winlink.env. If Pat ever
        # writes one here (pat init, the web UI's config page), this fails
        # before it can be committed.
        self.assertEqual(self.config["secure_login_password"], "")
        self.assertRegex(PAT_ENV.read_text(), r"(?m)^PAT_SECURELOGINPASSWORD=op://\S+$")

    def test_call_sign(self):
        self.assertEqual(self.config["mycall"], CALL)

    def test_uses_direwolf(self):
        self.assertEqual(self.config["ax25"]["engine"], "agwpe")
        self.assertEqual(self.config["agwpe"]["addr"], "localhost:8000")
        agwport = [line for line in direwolf_lines() if line.startswith("AGWPORT")]
        self.assertEqual(agwport, ["AGWPORT 8000"])

    def test_no_beacon(self):
        self.assertEqual(self.config["ax25"]["beacon"]["every"], 0)

    def test_gateways_are_programmed(self):
        # Each AX.25 alias must point at a gateway the radio has a channel for.
        with CSV_PATH.open(newline="") as f:
            comments = [row["Comment"] for row in csv.DictReader(f)]
        aliases = {k: v for k, v in self.config["connect_aliases"].items() if v.startswith("ax25")}
        self.assertTrue(aliases)
        for name, url in aliases.items():
            gateway = url.rsplit("/", 1)[1]
            with self.subTest(alias=name):
                self.assertTrue(
                    any(re.search(rf"\b{re.escape(gateway)}\b.*Winlink", c) for c in comments),
                    f"{gateway} isn't a Winlink row in frequencies.csv",
                )


if __name__ == "__main__":
    unittest.main()
