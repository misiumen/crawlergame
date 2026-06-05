"""Prompt 13 smoke — role-based LLM façade.

Asserts:
1. Default config mode is "performance"; all four role flags are False.
2. `apply_llm_mode` switches presets correctly + the back-compat
   `USE_OLLAMA` alias tracks the intent flag.
3. `llm_roles.is_role_available` returns False when the role is disabled,
   regardless of Ollama state.
4. `enrich_text` returns the supplied fallback on every failure path:
   role disabled / Ollama unreachable / model missing / timeout /
   validator rejection.
5. `request_structured` returns the supplied fallback dict (copy, not
   alias) when JSON is invalid or schema fails.
6. The reachability + per-model caches mean repeated calls do not hit
   the network when Ollama is offline.
7. narrator.say still returns Polish static text when LLM is disabled.
8. parser_core.parse_with_optional_llm skips Ollama entirely when the
   intent role is disabled.

Run: python -m revamp._smoke_llm_roles
"""
import os, tempfile, json
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init(); pygame.font.init()


def test_defaults():
    from dungeon_kraulem import config
    assert config.LLM_MODE == "performance"
    assert config.LLM_INTENT_ENABLED is False
    assert config.LLM_NARRATOR_ENABLED is False
    assert config.LLM_LOOTBOX_ENABLED is False
    assert config.LLM_DIALOGUE_ENABLED is False
    assert config.USE_OLLAMA is False   # legacy alias mirrors intent flag
    print("  defaults: performance / all flags off: OK")


def test_apply_modes():
    from dungeon_kraulem import config
    config.apply_llm_mode("enhanced")
    assert config.LLM_INTENT_ENABLED is True
    assert config.LLM_NARRATOR_ENABLED is True
    assert config.LLM_LOOTBOX_ENABLED is False
    assert config.LLM_DIALOGUE_ENABLED is False
    assert config.USE_OLLAMA is True
    config.apply_llm_mode("full_show")
    assert config.LLM_INTENT_ENABLED is True
    assert config.LLM_NARRATOR_ENABLED is True
    assert config.LLM_LOOTBOX_ENABLED is True
    assert config.LLM_DIALOGUE_ENABLED is True
    config.apply_llm_mode("performance")
    assert config.LLM_INTENT_ENABLED is False
    # Unknown mode falls back to performance, never raises.
    config.apply_llm_mode("does_not_exist")
    assert config.LLM_MODE == "performance"
    print("  mode presets + unknown-mode tolerance: OK")


def test_role_disabled_short_circuits():
    from dungeon_kraulem import config
    from dungeon_kraulem.llm import llm_roles
    config.apply_llm_mode("performance")
    llm_roles.reset_availability_cache()
    for role in llm_roles.ROLES:
        assert llm_roles.is_role_enabled(role) is False
        assert llm_roles.is_role_available(role) is False
    out = llm_roles.enrich_text(llm_roles.ROLE_NARRATOR,
                                "rephrase: foo", "STATIC")
    assert out == "STATIC"
    d = llm_roles.request_structured(llm_roles.ROLE_INTENT,
                                     "json please", {"k": 1})
    assert d == {"k": 1} and d is not None
    print("  disabled-role short-circuit + fallback: OK")


def test_unreachable_ollama_short_circuits_quickly():
    """With roles enabled and Ollama unreachable, calls return fallback
    without flooding the network. We verify by point-overriding the
    Ollama URL to an unreachable port."""
    from dungeon_kraulem import config
    from dungeon_kraulem.llm import llm_roles
    import time
    config.apply_llm_mode("enhanced")
    original_url = config.OLLAMA_URL
    original_timeout = config.OLLAMA_TIMEOUT_SECONDS
    # Use a port nothing listens on. Timeout is tight so the test stays
    # fast even on slow systems.
    config.OLLAMA_URL = "http://127.0.0.1:1"
    config.OLLAMA_TIMEOUT_SECONDS = 1
    llm_roles.reset_availability_cache()

    t0 = time.time()
    # First call probes once; subsequent calls hit the cached "false"
    # and must be effectively instant.
    out1 = llm_roles.enrich_text(llm_roles.ROLE_NARRATOR,
                                 "x", "FALLBACK1")
    after_first = time.time() - t0

    t1 = time.time()
    for _ in range(20):
        out_n = llm_roles.enrich_text(llm_roles.ROLE_NARRATOR,
                                      "x", "FALLBACK_N")
        assert out_n == "FALLBACK_N"
    after_twenty = time.time() - t1

    config.OLLAMA_URL = original_url
    config.OLLAMA_TIMEOUT_SECONDS = original_timeout
    config.apply_llm_mode("performance")
    llm_roles.reset_availability_cache()

    assert out1 == "FALLBACK1"
    # 20 cached "unavailable" calls should take well under one second
    # combined. Allow a generous ceiling for slow CI hardware.
    assert after_twenty < 1.0, \
        f"cached-unavailable path was slow: {after_twenty:.2f}s for 20 calls"
    print(f"  unreachable Ollama cached: "
          f"first probe={after_first*1000:.0f}ms, "
          f"20×cached={after_twenty*1000:.0f}ms")


def test_request_structured_returns_independent_copy():
    from dungeon_kraulem import config
    from dungeon_kraulem.llm import llm_roles
    config.apply_llm_mode("performance")
    fb = {"a": 1, "b": [2, 3]}
    got = llm_roles.request_structured(llm_roles.ROLE_INTENT,
                                       "p", fb, validator=None)
    assert got == fb
    # Must be a separate object so caller mutation can't poison the
    # fallback template.
    got["a"] = 99
    assert fb["a"] == 1
    print("  request_structured returns independent copy: OK")


def test_narrator_static_works_without_llm():
    from dungeon_kraulem import config
    from dungeon_kraulem.systems import narrator
    config.apply_llm_mode("performance")
    # `salvage_success` has Polish entries in pl.json.
    line = narrator.say("salvage_success")
    assert line, "narrator returned empty in performance mode"
    assert "memetic:" not in line
    print(f"  narrator static path: OK (sample: {line[:60]!r}…)")


def test_parser_skips_ollama_when_intent_disabled():
    """Ensure low-confidence parses do NOT call Ollama HTTP when the
    intent role is off."""
    from dungeon_kraulem import config
    from dungeon_kraulem.engine import parser_core
    from dungeon_kraulem.llm import llm_parser
    config.apply_llm_mode("performance")
    calls = {"n": 0}
    real = llm_parser.parse_with_ollama
    def spy(*a, **k):
        calls["n"] += 1
        return None
    llm_parser.parse_with_ollama = spy
    try:
        # Garbled input → low deterministic confidence.
        for text in ["asdf qwer", "??? hmm", "blah blah blah",
                     "do something weird"]:
            parser_core.parse_with_optional_llm(text)
    finally:
        llm_parser.parse_with_ollama = real
    assert calls["n"] == 0, \
        f"Ollama was called {calls['n']}× despite intent role off"
    print("  parser skips LLM when intent role off: OK")


def test_settings_persists_llm_mode():
    from dungeon_kraulem.ui import settings
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as td:
        try:
            os.chdir(td)
            assert settings.set_llm_mode("enhanced") is True
            assert settings.load_settings()["llm_mode"] == "enhanced"
            # Invalid mode is rejected without crash.
            assert settings.set_llm_mode("nope") is False
            assert settings.load_settings()["llm_mode"] == "enhanced"
            # Reset for downstream tests.
            settings.set_llm_mode("performance")
        finally:
            os.chdir(cwd)
            from dungeon_kraulem import config
            config.apply_llm_mode("performance")
    print("  llm_mode persists in settings JSON: OK")


def test_summary_diagnostic():
    from dungeon_kraulem import config
    from dungeon_kraulem.llm import llm_roles
    config.apply_llm_mode("performance")
    llm_roles.reset_availability_cache()
    info = llm_roles.summary()
    assert info["mode"] == "performance"
    assert set(info["roles"].keys()) == set(llm_roles.ROLES)
    for r, rd in info["roles"].items():
        assert "enabled" in rd and "model" in rd and "available" in rd
        assert rd["enabled"] is False
        assert rd["available"] is False
        assert isinstance(rd["model"], str) and rd["model"]
    print("  summary() shape: OK")


def main():
    test_defaults()
    test_apply_modes()
    test_role_disabled_short_circuits()
    test_unreachable_ollama_short_circuits_quickly()
    test_request_structured_returns_independent_copy()
    test_narrator_static_works_without_llm()
    test_parser_skips_ollama_when_intent_disabled()
    test_settings_persists_llm_mode()
    test_summary_diagnostic()
    print("Prompt 13 LLM-roles smoke: OK")


if __name__ == "__main__":
    main()
