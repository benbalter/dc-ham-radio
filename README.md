# UV-5R channels for Washington, DC

A channel list, settings, and programming tools for a [Baofeng UV-5R](https://baofengtech.com/product/uv-5r/) handheld in Washington, DC, kept in git and programmed from the command line instead of by clicking through CHIRP.

- [`frequencies.csv`](frequencies.csv) is the channel list, in [CHIRP](https://chirpmyradio.com)'s CSV format: nearby repeaters, national calling frequencies, NOAA weather, SKYWARN, Winlink, and receive-only monitor channels.
- [`radio-settings.json`](radio-settings.json) holds the radio's settings (squelch, scan, alarm, startup channels…) as readable, diffable text.
- [`scripts/program.py`](scripts/program.py) backs up the radio, shows exactly what would change, and writes the channels and settings over a serial cable.
- [`scripts/refresh.py`](scripts/refresh.py) rebuilds the repeater list from [RepeaterBook](https://www.repeaterbook.com).
- [`scripts/card.py`](scripts/card.py) prints a battery sticker and a full channel sheet.
- [`direwolf/`](direwolf), [`pat/`](pat), and [`scripts/digirig.py`](scripts/digirig.py) set up [Winlink](#winlink-over-packet) email over packet radio.
- [`tests/`](tests) check the list, including that nothing can transmit where it shouldn't.

Fork it for your own area: point `refresh.py` at your coordinates, edit the primary channels and settings, and program your radio.

## Quick start

```sh
python3 -m unittest discover tests     # check the CSV and settings
uv run scripts/program.py              # back up the radio and preview the changes (writes nothing)
uv run scripts/program.py --write      # back up, then program the radio
python3 scripts/card.py                # write out/card.html, then print it
```

`program.py` needs [uv](https://docs.astral.sh/uv/), which installs the [CHIRP library](https://github.com/kk7ds/chirp) from source for that run (CHIRP has no Homebrew cask, and its download site is behind a bot check). Everything else uses only the Python standard library.

## Channel map

| Channels | What |
| --- | --- |
| 0–4 | Primary channels:<br>0: KC3VO<br>1: N3ERA/NERA on the WAMU tower<br>2–3: two DC repeaters with emergency power (N3ADV, W3DCA)<br>4: the nearest NOAA station (WNG736) |
| 5–6 | National simplex calling frequencies: 146.520 (2m) and 446.000 (70cm) |
| 7–63 | Open, on-air 2m and 70cm FM repeaters within 26 miles of downtown DC, nearest first |
| 64–70 | NOAA Weather Radio WX1–WX7, receive only, skipped in scan |
| 71–77 | Emergency ham channels:<br>71–72: SKYWARN (N3JLT 147.300, day and overnight tones)<br>73–74: Winlink packet gateways (KM4DC-10, NV4FM-10)<br>75: APRS 144.390<br>76–77: 2m simplex 146.550 and 146.580 |
| 78–99 | GMRS/FRS 1–22, transmit only in a life-threatening emergency (see below) |
| 100–105 | Receive only: MURS 1–5 and marine ch 16 |

Key channels:

| Ch | Name | Use |
| --- | --- | --- |
| 1 | `WAMU TO` | N3ERA/NERA 449.975 on the WAMU tower, PL 107.2 tone squelch. |
| 2, 3 | `N3ADV W`, `W3DCA W` | DC repeaters with emergency power. |
| 4 | `WNG736` | NOAA weather, Silver Spring. The closest station. |
| 5 | `2M CALL` | 146.520 simplex. The first thing to try when repeaters are down. |
| 34 | `KV3B RO` | Rockville, emergency power, SKYWARN-affiliated. |
| 71 | `SKYWARN` | N3JLT Bluemont, NWS Sterling's SKYWARN net. About 45 miles out, so a handheld can usually listen but may not get in. |
| 97 | `GMRS 20` | 462.675 with PL 141.3, a common travel/emergency channel. Emergency-only on this radio. |

Repeaters are limited to 2m and 70cm because the UV-5R only receives 136–174 and 400–520 MHz, and those are the only ham bands in that range. The UV-5R is analog FM only, so digital-only repeaters (DMR, D-STAR, P-25, Fusion) are left out. Mixed analog/digital repeaters are included, with the other modes named in the comment. On 4 W with the stock antenna, expect anything past about 15 miles to be unreliable.

## Emergency-only GMRS and FRS

**Transmit on GMRS or FRS from the UV-5R only when someone's life is in immediate danger and normal communication isn't available.** For anything routine, use a certified GMRS or FRS radio.

- **Why:** the UV-5R isn't certified for the GMRS/FRS service ([47 CFR 95.335](https://www.ecfr.gov/current/title-47/part-95/section-95.335)), and holding a GMRS license doesn't change that.
- **The commonly cited defense:** [97.403](https://www.ecfr.gov/current/title-47/part-97/section-97.403) says no rule prevents an amateur station from using "any means of radiocommunication at its disposal" for the immediate safety of human life when normal communication systems aren't available, and [97.405](https://www.ecfr.gov/current/title-47/part-97/section-97.405) covers a station in distress. Neither explicitly authorizes an uncertified Part 95 transmission. Treat it as a defense for a real emergency, not a permission.
- **What's programmed:** GMRS/FRS 1–22 (channels 78–99) can transmit and are marked `EMG` on the printed card. Every one has a comment saying it's emergency-only, and the tests fail if one doesn't. GMRS 20 and 16 send PL 141.3.
- **If you have to use them:**
  - Use the lowest power that works. They're programmed at high power (4 W) so a call can get through; on most UV-5R firmware a short press of `#` switches to low (1 W).
  - FRS/GMRS 8–14 are normally capped at 0.5 W ([95.1767](https://www.ecfr.gov/current/title-47/part-95/section-95.1767)), so reach for GMRS 20 or 16 first.
  - Identify with your ham call sign, since you're operating as an amateur station, and your GMRS call sign too if you have one.
  - Keep it short, and log what you sent, when, and why.
- **Avoid keying up by accident.** Check the display before you press PTT, especially after a scan stops, since scans can stop on these channels. With dual watch on, PTT can transmit on whichever display line is active.
- **Always receive-only:** MURS, marine ch 16, and NOAA weather. Their channels are set to `Duplex` = `off`, which blocks transmitting **in channel mode**. In VFO mode (typing a frequency in directly) the radio can transmit anywhere, so stay in channel mode.

## Programming the radio

### With `program.py` (recommended)

1. Connect a programming cable to the radio's K1 jack. A [Digirig](https://digirig.net)'s serial jack with its Baofeng K1 serial cable works. Push the plug in hard: a half-seated K1 plug is the most common reason a read fails.
2. Turn the radio on.
3. Run `uv run scripts/program.py`. It reads the radio, saves a backup image to `backups/`, and lists every setting and channel that would change. It writes nothing.
4. If the list looks right, run `uv run scripts/program.py --write`.
5. Turn the radio off and on, then spot-check a few channels.

What to know:
- **Unlisted slots get erased.** The radio ends up matching the CSV exactly.
- **Settings:** `--write` also applies [`radio-settings.json`](radio-settings.json). To change a setting, edit the file, or change it on the keypad and run `uv run scripts/program.py --save-settings` to pull it into the repo, then commit. Settings the file doesn't list are left alone. An unknown key or invalid value stops the script before it writes anything.
- **No radio handy:** `--image backups/X.img` previews against a saved image instead.
- **Options:** `--port /dev/cu.usbserial-XXXX` if more than one USB serial device is plugged in; `--csv` and `--settings` to use other files.
- **Connection failures:** the write step reconnects and retries the handshake up to 3 times on its own, and a failed handshake writes nothing. If the first read fails, or all 3 retries do, the radio is probably stuck in programming mode: turn it off and on, reseat the K1 plug, and run it again.
- **Restoring a backup:** open the `.img` file in CHIRP (**File → Open**), then **Radio → Upload to radio**. `backups/` is gitignored.

### With the CHIRP app

1. **Radio → Download from radio**, then save the image as a backup.
2. **File → Import**, then choose `frequencies.csv`.
3. **Radio → Upload to radio**.

The CHIRP app doesn't read `radio-settings.json`; set those by hand or with `program.py`.

### Settings worth knowing

- **Alarm Mode is `Site`.** On the UV-5R, *Tone* and *Code* **transmit** an alarm on whatever channel is selected when the alarm button is held. *Site* only sounds the speaker. The tests require `Site`.
- **Scan Resume is `CO`** (resume when the signal drops), so a scan follows whole exchanges. NOAA transmits nonstop, so the weather channels are skipped in scan; pick them by hand.
- **Automatic Key Lock is on**, so a bump in a bag can't change channels. PTT still works; hold `#` to unlock.
- **Startup:** channel mode, with line A on ch 1 and line B on ch 97, watched together with dual watch.

## Winlink over packet

Send and receive Winlink email over 2m packet, through a [Digirig](https://digirig.net) and the UV-5R, with no internet. [Pat](https://getpat.io) is the Winlink client and [Dire Wolf](https://github.com/wb2osz/direwolf) is the software modem.

**You are the control operator.** Nothing here beacons or connects on its own. The radio transmits only during a `pat connect` you start.

### One-time setup

1. Install Dire Wolf: `brew install direwolf`.
2. Install Pat. There's no Homebrew formula, and the only macOS release is an Intel `.pkg` (it runs under Rosetta). To build it natively on Apple silicon: `mise use -g go:github.com/la5nta/pat@1.0.0`.
3. Create the Winlink account, if you don't have one, with a throwaway config so the password isn't saved anywhere: `pat --config "$TMPDIR/pat-init.json" init`, then `rm "$TMPDIR/pat-init.json"`.
4. Save the password in 1Password at the reference in [`pat/winlink.env`](pat/winlink.env), or edit that reference to match your item. Put your own call sign in [`pat/config.json`](pat/config.json) and [`direwolf/direwolf.conf`](direwolf/direwolf.conf).

### Each session

1. Plug the Digirig's **audio** cable into the radio's K1 jack. The programming cable won't work here.
2. Set the radio to the gateway's channel: ch 73 for KM4DC-10 (145.065) or ch 74 for NV4FM-10 (145.050).
3. Start the modem: `python3 scripts/digirig.py`. It finds the Digirig's sound card and serial port, writes `out/direwolf.conf`, and runs Dire Wolf. `--check` only reports what it found. If macOS asks whether direwolf may accept incoming connections, choose **Deny**: anyone who can reach that port can key your radio.
4. In a second terminal, connect:

   ```sh
   op run --env-file=pat/winlink.env -- pat --config pat/config.json connect km4dc
   ```

   Use `nv4fm` for the other gateway, or `telnet` to go over the internet.
5. Compose with `pat --config pat/config.json compose`, or in the web UI from `pat --config pat/config.json http` (its forms include ICS-213), then connect again to send.

The Pat steps follow Pat 1.0.0's source and haven't been run end to end yet.

### Levels

- **Receive:** with Dire Wolf running, turn the radio's volume until it prints an audio level around 50 on decoded packets.
- **Transmit:** set the "USB Audio Device" output volume in macOS Sound settings. Start low and raise it until the gateway answers.
- If gateways miss the start of your frames, raise `TXDELAY` in [`direwolf/direwolf.conf`](direwolf/direwolf.conf).

## Printable card

`python3 scripts/card.py` writes `out/card.html`: a sticker for the back of the battery with the channels you'd reach for first, and a full channel sheet.

1. Print at 100% scale, not "fit to page".
2. Check that the sticker measures 2 × 3.5 in. For a different battery, change `STICKER_WIDTH_IN` and `STICKER_HEIGHT_IN`.
3. Cut it out and cover it with clear packing tape.

The sticker's channels are listed in `STICKER` by name and frequency, so they still match after a renumber. Rerun and reprint after any channel change.

## Refreshing the repeater list

```sh
python3 scripts/refresh.py --dry-run   # show what RepeaterBook would change
python3 scripts/refresh.py             # rewrite the repeater block
```

`refresh.py` downloads RepeaterBook's proximity search around downtown DC and rebuilds only the repeater block. Primary channels, calling, weather, and the emergency block are copied over as-is. It keeps repeaters that are open, on 2m or 70cm, analog-FM capable, within 26 miles, and not marked off-air or testing, nearest first. Curated comments on repeaters already in the list are kept. To use it elsewhere, change `CENTER` and `MAX_MILES`.

Then run the tests, check the channel map above, reprint the card, and reprogram the radio. RepeaterBook statuses are user-reported, so confirm surprises with the club that runs the repeater. Ch 1, for example, is listed as closed, but [HacDC](https://w3hac.org/weekly-net/) invites everyone to its net there.

## Tests

`python3 -m unittest discover tests` checks that:

- The CSV has CHIRP's exact header, CRLF line endings, plain ASCII, channels 0..N with no gaps, at most 128 channels, and names of 7 characters or fewer.
- Every frequency is one the UV-5R can receive, and tone, duplex, and power fields are valid.
- **Every channel that can transmit does so inside the ham bands**: 144–148 or 420–450 MHz, top edges excluded, checked on the actual transmit frequency after the repeater offset. The only exceptions are the 22 GMRS/FRS simplex frequencies, each of which must be simplex and say `life-threatening emergency` in its comment.
- The national calling frequencies stay in the list and on the sticker, and NOAA channels are skipped in scan.
- `radio-settings.json` is in canonical format, its band limits cover the channel list, and Alarm Mode is `Site`.
- `refresh.py` parses RepeaterBook's table and applies its filters (a synthetic page, no network).
- The Dire Wolf and Pat configs use the right call sign and RTS PTT, never beacon, store no password, and point only at Winlink channels in the CSV.
- With uv and a backup image in `backups/`, `program.py` converts the CSV and settings for the radio, detects a setting change, and rejects an unknown setting. These skip otherwise, including in CI.

## Sources

- Repeaters: [RepeaterBook](https://www.repeaterbook.com) proximity search around downtown DC, pulled 2026-10-30. Statuses are user-reported snapshots.
- SKYWARN: [WX4LWX](https://www.wx4lwx.org/Frequencies.php) and [NWS Sterling](https://www.weather.gov/lwx/skywarn).
- Winlink gateways: [Winlink gateway list](https://cms.winlink.org:444/GatewayChannels.aspx) (packet).
- NOAA: [NWS NWR station list](https://www.weather.gov/nwr/).
- FRS/GMRS/MURS channels and rules: eCFR 47 CFR [95.563](https://www.ecfr.gov/current/title-47/part-95/section-95.563), [95.1763](https://www.ecfr.gov/current/title-47/part-95/section-95.1763), [95.2763](https://www.ecfr.gov/current/title-47/part-95/section-95.2763), [95.335](https://www.ecfr.gov/current/title-47/part-95/section-95.335).

## License

[GPL-3.0](LICENSE), matching [CHIRP](https://github.com/kk7ds/chirp), whose library `program.py` uses. Repeater data comes from RepeaterBook and the clubs that run the repeaters.
