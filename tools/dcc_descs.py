# -*- coding: utf-8 -*-
"""Rewrite achievement DESCRIPTIONS in Dungeon-Crawler-Carl voice (System/Borant
notification: audience/sponsor-obsessed, deadpan-cruel, absurd). Reads the new
descriptions from dcc_descs.txt (key:::desc, one per line — UTF-8, no ASCII quote
issues) and regex-replaces each key's "desc" in both Godot catalogs in place.
Names + everything else are left untouched.
"""
import re, io, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "tools", "dcc_descs.txt")
FILES = [
    os.path.join(ROOT, "dungeon-kraulem-godot", "sim", "achievements_catalog.gd"),
    os.path.join(ROOT, "dungeon-kraulem-godot", "sim", "achievements_extra.gd"),
]


def load_descs():
    descs = {}
    for line in io.open(DATA, encoding="utf-8").read().splitlines():
        line = line.strip()
        if not line or ":::" not in line:
            continue
        key, desc = line.split(":::", 1)
        assert '"' not in desc, "ASCII quote in desc for %s" % key
        descs[key.strip()] = desc.strip()
    return descs


def patch(path, descs):
    src = io.open(path, encoding="utf-8").read()
    n = 0
    for key, desc in descs.items():
        pat = re.compile(r'("' + re.escape(key) + r'":\s*\{[^}]*?"desc":\s*")([^"]*)(")')
        new, c = pat.subn(lambda m: m.group(1) + desc + m.group(3), src)
        if c:
            src = new
            n += 1
    io.open(path, "w", encoding="utf-8", newline="\n").write(src)
    print("patched %s: %d descriptions" % (os.path.basename(path), n))


if __name__ == "__main__":
    descs = load_descs()
    print("loaded %d descriptions" % len(descs))
    for f in FILES:
        patch(f, descs)
