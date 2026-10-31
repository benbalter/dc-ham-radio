"""Tests for scripts/refresh.py, using a small synthetic RepeaterBook page."""

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import refresh
finally:
    sys.path.pop(0)


def row(freq, offset, tone, call, city, use="OPEN", modes="FM", miles=1.0, status="Operational"):
    return f"""<tr>
<td><input type="checkbox"></td>
<td><a href="details.php?state_id=11&amp;ID=1"> {freq} </a></td>
<td>{offset}</td><td>{tone}</td><td>{call}</td><td>{city}</td><td>DC</td>
<td><span class="badge">{use}</span></td><td> {modes} </td>
<td data-sort="{miles}"> {miles:.2f} </td><td>N</td>
<td><span class="status-icon" title="{status}">o</span></td>
</tr>"""


PAGE = "<table>" + "".join([
    row("147.2700", "+0.6 MHz", "100.0", "W3DCA", "Washington", miles=0.5),
    row("146.6100", "-0.6 MHz", "", "K3GMR", "Bladensburg", miles=1.0),
    row("444.0500", "+5.0 MHz", "NAC 293 156.7", "N0AAA", "Silver Spring", modes="FM P-25", miles=2.0),
    row("442.2375", "+5.0 MHz", "CC 1", "N0BBB", "Ashton", modes="FM DMR", miles=3.0),
    row("449.0250", "-5.0 MHz", "156.7", "N3AUY", "Silver Spring", miles=4.0, status="Unknown Status"),
    row("448.0000", "-5.0 MHz", "77.0", "N0CCC", "Closed Town", use="CLOSED", miles=5.0),
    row("447.0000", "-5.0 MHz", "77.0", "N0DDD", "Dark Town", miles=6.0, status="Not Operational"),
    row("223.9400", "-1.6 MHz", "77.0", "N0EEE", "Far Band", miles=7.0),
    row("449.0250", "-5.0 MHz", "156.7", "N3AUY", "Haymarket", miles=30.0, status="Unknown Status"),
    row("146.7600", "-0.6 MHz", "107.2", "N0FFF", "Too Far", miles=40.0),
]) + "</table>"

TEMPLATE = {
    "Location": "", "Name": "", "Frequency": "", "Duplex": "", "Offset": "", "Tone": "",
    "rToneFreq": "88.5", "cToneFreq": "88.5", "DtcsCode": "023", "DtcsPolarity": "NN",
    "RxDtcsCode": "023", "CrossMode": "Tone->Tone", "Mode": "FM", "TStep": "5.00", "Skip": "",
    "Power": "4.0W", "Comment": "", "URCALL": "", "RPT1CALL": "", "RPT2CALL": "", "DVCODE": "",
}


class RefreshTest(unittest.TestCase):
    def setUp(self):
        self.reps = list(refresh.parse(PAGE))

    def build(self, keep=(), room=100, old=()):
        return refresh.build(list(old), set(keep), self.reps, TEMPLATE, room)

    def test_parse(self):
        self.assertEqual(len(self.reps), 10)
        first = self.reps[0]
        self.assertEqual((first["freq"], first["call"], first["status"]), (147.27, "W3DCA", "Operational"))

    def test_filters(self):
        names = [r["Name"] for r in self.build()]
        # Closed, not operational, 1.25m, digital-only (CC 1), and too-far rows drop out.
        self.assertEqual(names, ["W3DCA W", "K3GMR B", "N0AAA S", "N3AUY S"])

    def test_nearest_duplicate_wins(self):
        auy = [r for r in self.build() if r["Name"].startswith("N3AUY")]
        self.assertEqual(len(auy), 1)
        self.assertEqual(auy[0]["Comment"], "Silver Spring")

    def test_tones(self):
        rows = {r["Name"]: r for r in self.build()}
        self.assertEqual((rows["W3DCA W"]["Tone"], rows["W3DCA W"]["rToneFreq"]), ("Tone", "100.0"))
        self.assertEqual((rows["K3GMR B"]["Tone"], rows["K3GMR B"]["rToneFreq"]), ("", "88.5"))
        # P-25 NAC is ignored; the analog tone after it is used.
        self.assertEqual(rows["N0AAA S"]["rToneFreq"], "156.7")

    def test_offsets(self):
        rows = {r["Name"]: r for r in self.build()}
        self.assertEqual((rows["W3DCA W"]["Duplex"], rows["W3DCA W"]["Offset"]), ("+", "0.600000"))
        self.assertEqual((rows["N3AUY S"]["Duplex"], rows["N3AUY S"]["Offset"]), ("-", "5.000000"))

    def test_favorites_not_repeated(self):
        names = [r["Name"] for r in self.build(keep={"147.270000"})]
        self.assertNotIn("W3DCA W", names)

    def test_room_limit(self):
        self.assertEqual(len(self.build(room=2)), 2)

    def test_curated_comment_kept(self):
        old = [dict(TEMPLATE, Name="W3DCA W", Frequency="147.270000", Comment="Washington; emergency power")]
        rows = {r["Name"]: r for r in self.build(old=old)}
        self.assertEqual(rows["W3DCA W"]["Comment"], "Washington; emergency power")

    def test_mixed_mode_comment(self):
        rows = {r["Name"]: r for r in self.build()}
        self.assertEqual(rows["N0AAA S"]["Comment"], "Silver Spring (FM/P-25)")

    def test_name(self):
        self.assertEqual(refresh.name("K4AF", "Arlington"), "K4AF AR")
        self.assertEqual(refresh.name("WB3GXW", "Silver Spring"), "WB3GXW")


if __name__ == "__main__":
    unittest.main()
