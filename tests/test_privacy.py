"""Checks tracked files for personal details, per the Privacy rules in CLAUDE.md.

The repo is public. The only personal details allowed are the city and the
owner's call sign, so this fails on anything that could place the owner more
precisely: coordinates, grid squares, street addresses, DC neighborhoods,
network addresses, local paths, device serial numbers, and email addresses.

Run with: python3 -m unittest discover tests
"""

import pathlib
import re
import shutil
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Each check is (what it finds, pattern, allowed matches).
CHECKS = [
    # DC-area decimal degrees. CENTER in refresh.py is downtown DC on purpose.
    ("coordinates", r"(?<![\d.])-?(3[89]|7[67])\.\d{3,}", {"38.9072", "-77.0369"}),
    # Maidenhead grid squares around DC (FM18, FM19), finer than the 4-character square.
    ("grid square", r"(?i)\bFM1[89][a-x]{2}\b", set()),
    ("street address", r"\b\d+ [A-Z][a-z]+ (St|Street|Ave|Avenue|Rd|Road|Pl|Place|Blvd|Dr|Drive|Ct|Ln|Ter|Terrace)\b", set()),
    ("DC quadrant", r"\b(NW|NE|SW|SE)\b", set()),
    ("IP address", r"\b(\d{1,3}\.){3}\d{1,3}\b", set()),
    ("MAC address", r"(?i)\b([0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b", set()),
    ("local path", r"/(Users|home)/\w+", set()),
    # A real port name's suffix can be the CP2102's serial number. Short ones
    # like usbserial-1 are test placeholders.
    ("serial port", r"usbserial-\w{4,}", {"usbserial-XXXX"}),
    # Pat's telnet alias uses the public CMS login, which looks like an email.
    ("email address", r"[\w.+-]+@[\w-]+(\.[\w-]+)*\.[A-Za-z]{2,}\b", {"CMSTelnet@cms.winlink.org"}),
]

# Repeater sites come from RepeaterBook and can legitimately name a neighborhood,
# so the channel list is exempt from this one check.
NEIGHBORHOODS = re.compile(
    r"(?i)\b(adams morgan|anacostia|bloomingdale|brightwood|brookland|capitol hill|"
    r"chevy chase|cleveland park|columbia heights|congress heights|dupont|eckington|"
    r"foggy bottom|forest hills|friendship heights|georgetown|glover park|kalorama|"
    r"logan circle|mount pleasant|navy yard|noma|palisades|petworth|shaw|spring valley|"
    r"takoma|tenleytown|van ness|woodley park)\b"
)
NEIGHBORHOOD_EXEMPT = {"frequencies.csv"}


def tracked_files():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True, text=True)
    for name in out.stdout.split("\0"):
        if not name:
            continue
        try:
            yield name, (ROOT / name).read_text()
        except (UnicodeDecodeError, FileNotFoundError):
            continue  # binary, or deleted but not yet staged


@unittest.skipUnless(shutil.which("git") and (ROOT / ".git").exists(), "needs a git checkout")
class PrivacyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = dict(tracked_files())

    def test_no_personal_details(self):
        found = []
        for name, text in self.files.items():
            if name == "tests/test_privacy.py":
                continue  # its own patterns and allowlists would match
            for lineno, line in enumerate(text.splitlines(), 1):
                for label, pattern, allowed in CHECKS:
                    for match in re.finditer(pattern, line):
                        if match.group(0) not in allowed:
                            found.append(f"{name}:{lineno}: {label} {match.group(0)!r}")
                if name not in NEIGHBORHOOD_EXEMPT:
                    for match in NEIGHBORHOODS.finditer(line):
                        found.append(f"{name}:{lineno}: neighborhood {match.group(0)!r}")
        self.assertEqual(found, [], "Personal details in tracked files (see Privacy in CLAUDE.md):\n" + "\n".join(found))

    def test_pat_sends_no_locator(self):
        # Pat would send a grid square to the gateway, which places the station.
        self.assertRegex(self.files["pat/config.json"], r'"locator": ""')

    def test_generated_files_untracked(self):
        # Radio images and the card hold the owner's settings and aren't for the repo.
        leaked = [n for n in self.files if n.startswith(("backups/", "out/")) or n.endswith(".img")]
        self.assertEqual(leaked, [])


if __name__ == "__main__":
    unittest.main()
