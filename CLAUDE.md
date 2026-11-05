# CLAUDE.md

This repo programs a Baofeng UV-5R and a Radioddity UV-5G used in Washington, DC. [`README.md`](README.md) is the user guide. This file is the set of rules for changing things.

## Layout

| Path | What it is |
| --- | --- |
| [`frequencies.csv`](frequencies.csv) | The channel list, in [CHIRP](https://chirpmyradio.com)'s CSV format. It's the single source of truth. |
| [`scripts/program.py`](scripts/program.py) | Backs up the radio and writes the CSV to it over serial. It's a [uv](https://docs.astral.sh/uv/) script that lists its own dependencies at the top of the file. Those pull the CHIRP library from [GitHub](https://github.com/kk7ds/chirp), because CHIRP has no Homebrew cask and chirpmyradio.com's downloads sit behind a Cloudflare challenge. Needs Python 3.10–3.13. |
| [`radio-settings.json`](radio-settings.json) | The radio's settings (squelch, scan resume, alarm mode, startup channels…), keyed by CHIRP's internal name with its display label. `program.py --write` applies it. Settings it doesn't list are left alone. Keep the dump format (sorted keys, 2-space indent, trailing newline); a test checks it. |
| [`scripts/radio_settings.py`](scripts/radio_settings.py) | Loads, saves, and diffs settings snapshots. Standard library only, so it tests without CHIRP. |
| [`scripts/refresh.py`](scripts/refresh.py) | Rebuilds the repeater block from RepeaterBook's proximity search around downtown DC. Standard library only. |
| [`scripts/card.py`](scripts/card.py) | Renders `out/card.html`: a battery sticker plus a full channel sheet. Standard library only. |
| [`tests/test_frequencies.py`](tests/test_frequencies.py) | Checks the CSV format, transmit limits, the calling channels, and the sticker. Standard library only. |
| [`tests/test_settings.py`](tests/test_settings.py) | Checks the settings helpers and file, including that the alarm never transmits. Its `ProgramTest` runs `program.py --image` against the newest `backups/*.img` through uv, and skips without uv or an image. |
| [`scripts/uv5g.py`](scripts/uv5g.py) | Builds the UV-5G's channel list, `out/uv5g.csv`, from `frequencies.csv` plus [`uv5g/repeaters.csv`](uv5g/repeaters.csv). `program.py --radio uv5g` and `card.py --radio uv5g` call it, so the output is never committed. Standard library only. |
| [`uv5g/repeaters.csv`](uv5g/repeaters.csv) | GMRS repeaters for the UV-5G, edited by hand from [RepeaterBook's GMRS search](https://www.repeaterbook.com/gmrs/) (or [myGMRS](https://mygmrs.com/repeaters)): open, on-air, CTCSS, within about 15 miles of downtown DC, nearest first, `TSQL` on the listed tone. Each `Comment` cites the RepeaterBook ID and its last-update date. Add a permission-required repeater only after its owner approves. CHIRP's CSV format; `Location` is ignored. |
| [`uv5g/radio-settings.json`](uv5g/radio-settings.json) | Only the UV-5G's differences from `radio-settings.json`: keypad lock, limited menus, no keypad reset, busy-channel lockout, and its startup channels. `program.py --radio uv5g` layers it on top, so the UV-5G follows the UV-5R's settings otherwise. `--save-settings --radio uv5g` writes only what differs. |
| [`tests/test_uv5g.py`](tests/test_uv5g.py) | Checks the built UV-5G list (format, GMRS-only transmit, 8–14 narrow and low, slots equal GMRS channel numbers), its sticker, and its merged settings, including the keypad lock. |
| [`tests/test_refresh.py`](tests/test_refresh.py) | Checks `refresh.py`'s parsing and filters against a synthetic page. No network. |
| [`direwolf/direwolf.conf`](direwolf/direwolf.conf) | Dire Wolf (software modem) template for 1200-baud packet through the Digirig: RTS PTT, AGW on 8000, KISS off, no beacons. `scripts/digirig.py` fills in the sound card and serial port. |
| [`pat/config.json`](pat/config.json), [`pat/winlink.env`](pat/winlink.env) | [Pat](https://getpat.io) Winlink config with gateway aliases `km4dc` and `nv4fm`. The password comes from 1Password through `op run --env-file=pat/winlink.env`. `secure_login_password` must stay empty; a test checks it. |
| [`scripts/digirig.py`](scripts/digirig.py) | Finds the Digirig's sound card and serial port, writes `out/direwolf.conf`, and starts Dire Wolf. `--check` only reports. Standard library only. |
| [`tests/test_digital.py`](tests/test_digital.py) | Checks the Dire Wolf and Pat configs: call sign, RTS PTT, no beacons, no stored password, and that each Pat gateway alias is a Winlink row in the CSV. No hardware. |
| [`tests/test_privacy.py`](tests/test_privacy.py) | Fails on personal details in tracked files: coordinates other than `CENTER`, grid squares, street addresses, DC neighborhoods (outside the two channel lists), IP/MAC addresses, local paths, real serial port names, and emails. Also checks that Pat sends no locator and that no radio image or card is tracked. If it flags something that's truly public, add it to that check's allowlist with a comment saying why. |
| [`ruff.toml`](ruff.toml) | Lint rules for `ruff check`, listed explicitly so a new ruff release can't change what CI fails on. |
| [`.github/workflows/test.yml`](.github/workflows/test.yml) | CI in one job: `ruff check`, the unit tests, and `uv run scripts/program.py --help`, which installs CHIRP from GitHub so a CHIRP change that breaks the import shows up there. |
| `out/`, `backups/` | Generated card and radio images. Both are gitignored. Never commit them. |

## Commands

```sh
python3 -m unittest discover tests     # run after every change to the CSV or scripts
uvx ruff check .                       # lint the scripts and tests
python3 scripts/card.py                # regenerate the card
python3 scripts/card.py --radio uv5g   # regenerate the UV-5G's card
uv run scripts/program.py              # reads the radio, saves a backup, and previews changes; writes nothing
uv run scripts/program.py --write      # writes channels and settings to the radio
uv run scripts/program.py --save-settings  # saves the radio's current settings to radio-settings.json
uv run scripts/program.py --image backups/X.img  # previews against a saved image; no radio needed
uv run scripts/program.py --radio uv5g # any of the above for the UV-5G
```

The UV-5G uses CHIRP's `Radioddity_UV-5G` driver, a subclass of the UV-5R's with the same protocol, memory layout, and settings, so `--image` takes the model from `--radio` instead of guessing it from the image. The same `--write` rules apply to it.

Run `program.py --write` only when the owner asks for it in that conversation. It changes hardware and erases every slot that isn't in the CSV. The dry run is safe, but it still needs the radio connected and turned on, so ask before running that too. Any K1 programming cable works; for example, a Digirig's serial jack with its Baofeng K1 serial cable. `--write` closes and reopens the port between the read and the write, then retries the upload handshake up to 3 times, 3 seconds apart. A failed handshake writes nothing. The read retries the same way, since a radio can miss the first handshake after the port opens (CHIRP may then call a UV-5G a "blacklisted model"; that's a timing artifact). If all 3 read or write attempts fail, the radio is usually stuck in programming mode or the plug isn't seated. Have the owner turn the radio off and on and push the K1 plug in until it's fully seated, then run the script again.

## Transmit policy

This is the rule that matters most. Treat any change that loosens it as a judgment call for the owner.

- **The ham bands are normal use.** Channels may transmit in 2m (144–148 MHz) and 70cm (420–450 MHz), top edges excluded. The test checks the actual transmit frequency: `Frequency` plus or minus `Offset`, depending on `Duplex`.
- **GMRS/FRS are for life-threatening emergencies only.** The UV-5R isn't certified for Part 95 ([47 CFR 95.335](https://www.ecfr.gov/current/title-47/part-95/section-95.335)). The commonly cited defense is [97.403](https://www.ecfr.gov/current/title-47/part-97/section-97.403)/[97.405](https://www.ecfr.gov/current/title-47/part-97/section-97.405): immediate safety of human life, with normal communication unavailable. Those sections say nothing "prevents" an amateur from using any means at hand. They don't explicitly authorize uncertified Part 95 transmission, so don't describe it as settled law. At the owner's direction, GMRS/FRS 1–22 are programmed transmit-capable for that case only, with these rules:
  - Each must be simplex (`Duplex` blank).
  - Its frequency must be one of the 22 values in `GMRS_SIMPLEX` in the test.
  - Its `Comment` must contain `life-threatening emergency`. The test and the card's `EMG` marking both match on that exact phrase, so keep the wording.
  - Never describe GMRS/FRS transmit as routine anywhere: not in the docs, the card, or comments. Routine GMRS/FRS traffic goes on certified radios.
  - Power is programmed at high (4 W), including on FRS/GMRS 8–14, so an emergency call can get through. Those seven channels are normally capped at 0.5 W ([95.1767](https://www.ecfr.gov/current/title-47/part-95/section-95.1767)). The docs tell the operator to use the lowest power that works, and to reach for GMRS 19 (the UV-5Gs' family channel), 20, or 16 first. Keep that guidance in README.md.
  - Don't add GMRS repeater pairs. The 467 MHz repeater inputs aren't in `GMRS_SIMPLEX`, so the test would fail on them anyway.
- **Everything else is receive-only.** That covers MURS, marine, NOAA, public safety, and anything outside the ham bands. Set `Duplex` = `off`, which blocks transmit on the UV-5R in channel mode only. VFO mode can still transmit there, and the README warns about that.
- **The UV-5G is the exception for GMRS.** It's Part 95-certified and its firmware only transmits on GMRS, so GMRS 1–22 and GMRS repeaters are routine there, under the owner's GMRS license. Its rows never carry the `life-threatening emergency` phrase; a test checks that. Ham and other non-GMRS rows on it are `Duplex` = `off`. Nothing here changes the UV-5R rules above.
- **Never write TX limits across radios.** `uv5g.NOT_INHERITED` keeps the UV-5R's band limits (`limits_new.*`), `allrange`, squelch calibration (`squelch_new.*`), and VFO settings (`vfoa.*`, `vfob.*`) off the UV-5G, since a certified radio may keep its GMRS-only lock in those limits. One UV-5G read in 2026-11 reported 136–174/400–520 with TX enabled, so its lock is in firmware, but don't shrink that list on the strength of one radio.
- **Claude never keys the transmitter.** The operator starts every transmission, including every `pat connect`. (Programming over the serial cable with `program.py` doesn't transmit.) Don't add beacons, digipeating, or unattended connects.
- **Don't weaken the guard.** Don't loosen `TX_BANDS`, `GMRS_SIMPLEX`, or the transmit test to make a row pass. Fix the row, or ask the owner.

## CSV format

- Keep CHIRP's exact header row, CRLF line endings, and plain ASCII. The test checks all three.
- `Location` runs 0..N with no gaps, and there are at most 128 channels (0–127).
- `Name` is 7 characters max, in uppercase. For repeaters, use the call sign, a space, then the start of the city (`K3ERA D`), cut off at 7 characters.
- Every `Frequency` must be one the UV-5R can receive: 136–174 or 400–520 MHz. So no 6m, 1.25m, 33cm, or 23cm repeaters.
- The UV-5R is analog FM only. Leave out digital-only repeaters (DMR, D-STAR, P-25, Fusion). Mixed analog/digital repeaters are fine; put the other modes in parentheses in `Comment`.
- `Tone`:
  - `Tone` sends `rToneFreq` on transmit only.
  - `TSQL` uses the same tone for transmit and receive, so `cToneFreq` equals `rToneFreq`.
  - Blank means no tone.
  - In every mode except `TSQL`, `cToneFreq` stays at CHIRP's default of 88.5.
- `Power` is `4.0W`, which is high power in CHIRP's UV-5R driver. The test currently requires it on every row.
- `Comment` holds the RepeaterBook location, plus any non-FM modes in parentheses. For emergency or receive-only rows, say why.

## Channel order

| Slots | Block | How it's maintained |
| --- | --- | --- |
| 0–4 | Primary channels | Set by the owner. Don't reorder, replace, or drop any without asking, even if one looks dead. |
| 5–6 | National calling, 146.520 and 446.000 | Required by the tests. |
| 7–63 | Repeaters, nearest first from downtown DC (`CENTER` in `refresh.py`) | Rebuilt from RepeaterBook. A repeater that's already a favorite doesn't appear here again. |
| 64–70 | NOAA WX1–WX7, receive only, `Skip` = `S` | Fixed. NOAA transmits nonstop, so a scan would park on it; the test requires Skip. |
| 71–105 | Emergency and monitor block: SKYWARN, Winlink, APRS, simplex, GMRS/FRS, MURS, marine | Edited by hand. A refresh copies it over unchanged. |

When slot numbers change, update everything that cites them:
- The README's channel map, key-channel table, and the slot numbers in its settings section
- The startup channels in `radio-settings.json` (`wmchannel.mrcha`, `wmchannel.mrchb`)
- The `STICKER` list in `card.py`, but only if a sticker channel was removed. It matches on name and frequency, not slot.
- The `MONITOR` list in `uv5g.py`, on the same terms. `uv5g.FAMILY` (GMRS 19) and `uv5g.BACKUP` (GMRS 3) are the family's simplex channels; they must stay simplex, full power, and off every repeater output in `uv5g/repeaters.csv` (a test checks), and channel A starts on `FAMILY`. The UV-5G's own slots are fixed: WX1 at 0 and GMRS 1–22 at 1–22, so its startup channels in `uv5g/radio-settings.json` only change if that layout does.

## Refreshing from RepeaterBook

Run `python3 scripts/refresh.py --dry-run`, review, then `python3 scripts/refresh.py`. It rebuilds only the repeater block and copies everything else over. Its rules:

- RepeaterBook's JSON export needs an auth token, so it parses the HTML proximity search (`mode%5B%5D=1`, analog FM). A repeater missing from the results may have gone digital rather than off the air.
- Keeps repeaters that are `OPEN`, on 2m or 70cm, FM-capable, within `MAX_MILES` of `CENTER`, and `Operational` or `Unknown Status`. Drops `Not Operational`, `Testing`, closed, and digital-first ones (a digital code like `CC 1` with no analog tone).
- The same call and frequency at more than one site (N3AUY 449.025) keeps the nearest.
- Skips frequencies already in the primary or calling block.
- Keeps an existing row's curated `Comment` when the name and frequency match.

Then run the tests, update the README's pull date and channel ranges, reprint the card, and ask before reprogramming the radio. RepeaterBook statuses are user-reported; confirm surprises with the club. [w3hac.org](https://w3hac.org/weekly-net/) shows ch 1 is open for its net even though RepeaterBook calls it closed.

## Privacy

This repo is public. The only personal details allowed are the city (Washington, DC) and the owner's call sign, which `radio-settings.json`, the Dire Wolf and Pat configs, and `test_digital.py` need. Naming the gear this repo programs (the UV-5R, the UV-5G, the Digirig, a Mac) is fine. Never add a neighborhood, street, home coordinates, or anything derived from them (`CENTER` is downtown DC on purpose, and channel order follows from it), household or family details (including who uses which radio), other gear the owner has at home, schedules, or which nets the owner personally joins. `test_privacy.py` catches the pattern-shaped leaks, but not things like schedules or nets, so before committing, also read the diff for anything more specific than "Washington, DC".
