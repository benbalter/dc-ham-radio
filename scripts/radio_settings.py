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


def merge(*snapshots):
    """Layer snapshots in order, so later ones win key by key.

    A key keeps the group of the snapshot that set it last. None (a missing
    file) is skipped, so an absent override file just means "no overrides".
    """
    merged = {}
    for snapshot in snapshots:
        for group, entries in (snapshot or {}).items():
            for key, entry in entries.items():
                for other in merged.values():
                    other.pop(key, None)
                merged.setdefault(group, {})[key] = dict(entry)
    return {group: entries for group, entries in merged.items() if entries}


def subtract(snapshot, base):
    """The entries of snapshot whose value differs from base, or that base lacks.

    Used to save an override file that lists only what differs from the
    settings it's layered on.
    """
    have = flatten(base or {})
    out = {}
    for key, (group, label, value) in flatten(snapshot).items():
        if key in have and normalize(have[key][2]) == normalize(value):
            continue
        out.setdefault(group, {})[key] = {"label": label, "value": value}
    return out


def drop(snapshot, prefixes):
    """snapshot without the keys that start with any of prefixes."""
    out = {}
    for group, entries in (snapshot or {}).items():
        kept = {k: e for k, e in entries.items() if not k.startswith(tuple(prefixes))}
        if kept:
            out[group] = kept
    return out
