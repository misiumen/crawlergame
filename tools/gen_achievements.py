"""Generate dungeon-kraulem-godot/sim/achievements_catalog.gd from the Python
achievements catalog (systems/achievements.py). DCC-flavored Polish names +
descriptions ported verbatim. Re-run if the catalog changes.
"""
import sys, os, types, importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "dungeon-kraulem-pygame", "dungeon_kraulem", "systems", "achievements.py")
OUT = os.path.join(ROOT, "dungeon-kraulem-godot", "sim", "achievements_catalog.gd")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    for pkg in ("dungeon_kraulem", "dungeon_kraulem.systems"):
        m = types.ModuleType(pkg)
        m.__path__ = []
        sys.modules[pkg] = m
    ach = _load("dungeon_kraulem.systems.achievements", SRC)
    cat = ach._ACHIEVEMENTS

    def esc(s):
        return (s or "").replace("\\", "\\\\").replace('"', '\\"')

    L = []
    L.append("class_name AchievementsCatalog")
    L.append("extends RefCounted")
    L.append("## DCC-flavored achievement catalog, GENERATED from the Python")
    L.append("## systems/achievements.py by tools/gen_achievements.py (Polish verbatim).")
    L.append("## key -> {name, desc, category, hidden}")
    L.append("")
    L.append("const CATALOG: Dictionary = {")
    for key, a in cat.items():
        L.append('\t"%s": {"name": "%s", "desc": "%s", "category": "%s", "hidden": %s},'
                 % (esc(key), esc(a.fallback_name_pl), esc(a.fallback_description_pl),
                    esc(a.category), "true" if a.hidden else "false"))
    L.append("}")
    L.append("")
    L.append("## Stable display order: catalog order, grouped by category in the UI.")
    L.append("const ORDER: Array = [")
    for key in cat.keys():
        L.append('\t"%s",' % esc(key))
    L.append("]")
    L.append("")

    open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(L))
    print("wrote %s with %d achievements" % (OUT, len(cat)))


if __name__ == "__main__":
    main()
