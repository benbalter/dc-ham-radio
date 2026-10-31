"""Radio settings as plain data, so they can live in git and be diffed.

A snapshot is {group: {key: {"label": str, "value": bool | int | float | str}}},
where key is CHIRP's internal setting name and label is what CHIRP shows.
This module is stdlib-only so the tests can run without CHIRP installed;
scripts/program.py does the CHIRP conversion.
"""

import json
import pathlib


def load(path):
    path = pathlib.Path(path)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def dump(snapshot, path):
    text = json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    pathlib.Path(path).write_text(text, encoding="utf-8")


def flatten(snapshot):
    """{key: (group, label, value)} across all groups."""
    return {
        key: (group, entry["label"], entry["value"])
        for group, entries in snapshot.items()
        for key, entry in entries.items()
    }


def normalize(value):
    # String settings come back space-padded to their field width.
    return value.rstrip() if isinstance(value, str) else value


def diff(current, desired):
    """Settings whose desired value differs from the radio's.

    Returns [(key, label, old, new)], sorted by group then label. Keys in
    desired but not on the radio are reported with old=None so a typo or a
    driver change doesn't silently do nothing.
    """
    have = flatten(current)
    changes = []
    for key, (group, label, value) in flatten(desired).items():
        old = have.get(key, (None, None, None))[2]
        if normalize(old) != normalize(value):
            changes.append((group, label, key, old, value))
    changes.sort()
    return [(key, label, old, new) for _, label, key, old, new in changes]
