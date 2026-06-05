"""Phase 0 — extract pure-data content modules to JSON for the Godot port.

For each content module it dumps every module-level dict/list that is
JSON-serializable into godot/data/<module>.json, and REPORTS anything that
isn't (closures, dataclass instances, sets) — those are "data+logic" that must
be ported as GDScript, not JSON. This script empirically separates the two.

Run from repo root:  python -m dungeon_kraulem.tools.export_json
"""
from __future__ import annotations
import importlib, json, os, types

OUT = os.path.join("godot", "data")
MODULES = [
    "dungeon_kraulem.content.data.entity_templates",
    "dungeon_kraulem.content.data.room_pool",
    "dungeon_kraulem.content.data.recipe_templates",
    "dungeon_kraulem.content.data.experimental_recipes",
    "dungeon_kraulem.content.data.salvage_tables",
    "dungeon_kraulem.content.data.monster_salvage",
    "dungeon_kraulem.content.data.body_plans",
    "dungeon_kraulem.content.data.item_templates",
    "dungeon_kraulem.content.data.npc_templates",
    "dungeon_kraulem.content.data.npc_dialogues",
    "dungeon_kraulem.content.data.encounter_templates",
    "dungeon_kraulem.content.data.floor_archetypes",
    "dungeon_kraulem.content.data.floor_biomes",
    "dungeon_kraulem.content.data.floor_objective_templates",
    "dungeon_kraulem.content.data.sponsors",
    "dungeon_kraulem.content.data.sponsor_voice_lines",
    "dungeon_kraulem.content.data.memetic_templates",
    "dungeon_kraulem.content.data.rumor_templates",
    "dungeon_kraulem.content.data.clue_templates",
    "dungeon_kraulem.content.data.failure_templates",
    "dungeon_kraulem.content.data.safehouse_templates",
    "dungeon_kraulem.content.data.celebrities",
    "dungeon_kraulem.content.data.pets",
    "dungeon_kraulem.engine.meta_progression",  # expect: closures -> reported
]


def _serializable(v) -> bool:
    try:
        json.dumps(v, ensure_ascii=False)
        return True
    except (TypeError, ValueError):
        return False


def _count(v):
    try:
        return len(v)
    except TypeError:
        return 1


def main():
    os.makedirs(OUT, exist_ok=True)
    exported, needs_code, import_fail = [], [], []
    for modname in MODULES:
        try:
            mod = importlib.import_module(modname)
        except Exception as e:  # noqa
            import_fail.append((modname, f"{type(e).__name__}: {e}"))
            continue
        bundle = {}
        for name in dir(mod):
            if name.startswith("_"):
                continue
            val = getattr(mod, name)
            if isinstance(val, (types.ModuleType, types.FunctionType)):
                continue
            if not isinstance(val, (dict, list)):
                continue
            if _serializable(val):
                bundle[name] = val
            else:
                needs_code.append((modname.split(".")[-1], name))
        if bundle:
            short = modname.split(".")[-1]
            path = os.path.join(OUT, short + ".json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(bundle, f, ensure_ascii=False, indent=1)
            exported.append((short, sum(_count(v) for v in bundle.values()), list(bundle.keys())))

    print("=" * 64)
    print(f"EXPORTED -> {OUT}/")
    for short, n, keys in sorted(exported):
        print(f"  {short:<28} {n:>5} entries   {keys}")
    print(f"\n  {len(exported)} files written")
    if needs_code:
        print("\nNEEDS CODE PORT (data+logic, NOT serializable):")
        for mod, name in needs_code:
            print(f"  {mod}.{name}")
    if import_fail:
        print("\nIMPORT FAILED (likely pulls in pygame/engine state):")
        for mod, why in import_fail:
            print(f"  {mod}  -- {why}")
    print("=" * 64)


if __name__ == "__main__":
    main()
