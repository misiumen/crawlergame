"""Generate godot/sim/dialogue_trees.gd from the Python authored dialogue trees
(engine/dialogue.py dataclasses + content/data/npc_dialogues.py). The exact Polish
text + branch structure is ported verbatim — re-run if the trees change.

We load the two Python files as standalone modules (stubbing the package hierarchy)
so heavy package __init__ files never run.
"""
import sys, os, types, importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(ROOT, "dungeon_kraulem", "engine", "dialogue.py")
NPC = os.path.join(ROOT, "dungeon_kraulem", "content", "data", "npc_dialogues.py")
OUT = os.path.join(ROOT, "godot", "sim", "dialogue_trees.gd")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    # Stub the package hierarchy so relative imports resolve without running
    # the real (pygame-heavy) __init__ files.
    for pkg in ("dungeon_kraulem", "dungeon_kraulem.engine",
                "dungeon_kraulem.content", "dungeon_kraulem.content.data"):
        m = types.ModuleType(pkg)
        m.__path__ = []
        sys.modules[pkg] = m

    dlg = _load("dungeon_kraulem.engine.dialogue", ENGINE)
    _load("dungeon_kraulem.content.data.npc_dialogues", NPC)  # auto-registers
    trees = dlg._TREES

    def esc(s):
        return (s or "").replace("\\", "\\\\").replace('"', '\\"')

    def cons_to_gd(c):
        # a consequence dict {"kind":..., ...} -> GDScript dict literal
        parts = []
        for k, v in c.items():
            if isinstance(v, bool):
                vs = "true" if v else "false"
            elif isinstance(v, (int, float)):
                vs = str(v)
            else:
                vs = '"%s"' % esc(str(v))
            parts.append('"%s": %s' % (k, vs))
        return "{" + ", ".join(parts) + "}"

    def opt_to_gd(o):
        d = {}
        d['"label"'] = '"%s"' % esc(o.label)
        if o.next_node_id is not None:
            d['"next"'] = '"%s"' % esc(o.next_node_id)
        if o.skill_check is not None:
            stat, dc = o.skill_check
            d['"skill"'] = '["%s", %d]' % (esc(stat), int(dc))
        if o.fail_node_id is not None:
            d['"fail"'] = '"%s"' % esc(o.fail_node_id)
        if o.consequences:
            d['"cons"'] = "[" + ", ".join(cons_to_gd(c) for c in o.consequences) + "]"
        if o.fail_consequences:
            d['"fail_cons"'] = "[" + ", ".join(cons_to_gd(c) for c in o.fail_consequences) + "]"
        if o.requires_flag:
            d['"requires"'] = '"%s"' % esc(o.requires_flag)
        if o.forbids_flag:
            d['"forbids"'] = '"%s"' % esc(o.forbids_flag)
        if o.one_shot:
            d['"one_shot"'] = "true"
        return "{" + ", ".join("%s: %s" % (k, v) for k, v in d.items()) + "}"

    L = []
    L.append("class_name DialogueTrees")
    L.append("extends RefCounted")
    L.append("## Authored dialogue trees, GENERATED from dungeon_kraulem/content/data/")
    L.append("## npc_dialogues.py by tools/gen_dialogues.py — exact Polish text + branch")
    L.append("## structure ported verbatim. Consumed by sim/dialogue.gd. Re-run the")
    L.append("## generator if the Python trees change.")
    L.append("")
    L.append("const TREES: Dictionary = {")
    for key, tree in trees.items():
        L.append('\t"%s": {' % esc(key))
        L.append('\t\t"start": "%s",' % esc(tree.start_node))
        L.append('\t\t"nodes": {')
        for node_id, node in tree.nodes.items():
            L.append('\t\t\t"%s": {' % esc(node_id))
            L.append('\t\t\t\t"speaker": "%s",' % esc(node.speaker))
            L.append('\t\t\t\t"text": "%s",' % esc(node.text))
            if node.on_enter_consequences:
                inner = ", ".join(cons_to_gd(c) for c in node.on_enter_consequences)
                L.append('\t\t\t\t"on_enter": [%s],' % inner)
            L.append('\t\t\t\t"options": [')
            for o in node.options:
                L.append('\t\t\t\t\t%s,' % opt_to_gd(o))
            L.append('\t\t\t\t],')
            L.append('\t\t\t},')
        L.append('\t\t},')
        L.append('\t},')
    L.append("}")
    L.append("")

    open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(L))
    n_nodes = sum(len(t.nodes) for t in trees.values())
    print("wrote %s: %d trees, %d nodes" % (OUT, len(trees), n_nodes))


if __name__ == "__main__":
    main()
