import importlib, os, sys, glob, traceback
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
try:
    from dungeon_kraulem.engine import run_history as _rh
    _rh.reset()
except Exception: pass
mods = sorted(glob.glob("dungeon_kraulem/tests/test_*.py"))
fail = []
for m in mods:
    name = m.replace(os.sep, ".").replace("/", ".").replace(".py", "")
    try:
        if name in sys.modules: importlib.reload(sys.modules[name])
        else: importlib.import_module(name)
        if hasattr(sys.modules[name], "main"): sys.modules[name].main()
    except SystemExit: pass
    except Exception as e:
        fail.append((name, type(e).__name__, str(e), traceback.format_exc()))
        print(f"FAIL {name}: {e}")
print(f"\nTotal {len(mods)} Passed {len(mods)-len(fail)} Fail {len(fail)}")
for n,k,m,tb in fail: print(f"\n--- {n} ---\n{tb}")
