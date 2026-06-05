"""Optional local Ollama-backed parser.

Off-grid safe. Uses only the standard library (json, urllib, socket).
Falls back gracefully whenever Ollama is unavailable, slow, or misbehaving.

Public API:
    is_ollama_available() -> bool
    parse_with_ollama(player_text: str, compact_context: dict) -> dict | None

The function returns a *dict* matching the schema below — NOT an ActionIntent.
parser_core.py is responsible for converting the dict into an ActionIntent
and feeding it to the validator.

Schema:
    {
        "intent": "string",
        "verb": "string or null",
        "targets": ["string", ...],
        "tool": "string or null",
        "destination": "string or null",
        "desired_outcome": "string or null",
        "suggested_stat": "STR|DEX|CON|INT|WIS|CHA|null",
        "risk_level": "low|medium|high|null",
        "confidence": 0.0
    }

Ollama is only allowed to interpret intent. It must not decide
success/failure, damage, rewards, room contents, item creation, NPC state,
or any world-state change. Those are exclusively decided by the
deterministic validator + resolver downstream.
"""
import json
import socket
import sys
import urllib.error
import urllib.request

from ..config import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS


_VALID_STATS = {"STR", "DEX", "CON", "INT", "WIS", "CHA"}
_VALID_RISK = {"low", "medium", "high"}

# Debounced debug logging — print each warning once per process lifetime.
_warned_unavailable = False
_warned_invalid_json = False
_warned_http = False


# ── Health check ──────────────────────────────────────────────────────────────

def is_ollama_available() -> bool:
    """Quick health check against the Ollama daemon. Never raises."""
    global _warned_unavailable
    url = f"{OLLAMA_URL.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=1.0) as r:
            return 200 <= r.status < 300
    except (urllib.error.URLError, socket.timeout, socket.error, OSError):
        if not _warned_unavailable:
            _warned_unavailable = True
            print("[dungeon_kraulem.llm] Ollama unavailable — falling back to deterministic parser.",
                  file=sys.stderr)
        return False
    except Exception:
        return False


# ── Prompt ────────────────────────────────────────────────────────────────────

_SYSTEM_INSTRUCTION = (
    "You are an intent parser for a dungeon RPG.\n"
    "Return valid JSON only.\n"
    "Do not use markdown.\n"
    "Do not use code fences.\n"
    "Do not explain.\n"
    "Do not decide success or failure.\n"
    "Do not invent room objects.\n"
    "Use listed visible objects/entities when possible.\n"
    "If the player refers to something not listed, include the raw target text anyway.\n"
    "\n"
    "Required JSON schema:\n"
    "{\n"
    '  "intent": "string",\n'
    '  "verb": "string or null",\n'
    '  "targets": ["string"],\n'
    '  "tool": "string or null",\n'
    '  "destination": "string or null",\n'
    '  "desired_outcome": "string or null",\n'
    '  "suggested_stat": "STR|DEX|CON|INT|WIS|CHA|null",\n'
    '  "risk_level": "low|medium|high|null",\n'
    '  "confidence": 0.0,\n'
    '  "method": "string or null (memetic only: rumor|lie|mythic_comparison|false_order|religious_framing|logic_exploit|identity_attack|propaganda|taboo_creation|sponsor_disinformation|social_proof|performance|forged_evidence)",\n'
    '  "core_claim": "string or null (memetic only: the proposition)",\n'
    '  "target_tags": ["string"],\n'
    '  "spread_channel": "string or null (e.g. crawler_gossip, machine_radio, sponsor_replay, safehouse_rumor, graffiti, terminal_logs, audience_memes)",\n'
    '  "emotional_hook": "string or null",\n'
    '  "logic_hook": "string or null"\n'
    "}\n"
    "Memetic intents Ollama may produce: seed_belief, spread_rumor,\n"
    "create_taboo, issue_false_order, logic_exploit, identity_attack,\n"
    "sow_distrust, incite_panic, religious_framing,\n"
    "sponsor_disinformation, propaganda, forge_social_proof.\n"
    "Ollama may interpret the idea but never decides whether it spreads.\n"
)


def _build_prompt(player_text: str, compact_context: dict) -> str:
    """Assemble a compact, deterministic prompt for the model."""
    ctx = compact_context or {}
    lines = [_SYSTEM_INSTRUCTION, "", "GAME CONTEXT:"]

    mode = ctx.get("mode", "exploration")
    lines.append(f"  mode: {mode}")

    room_desc = (ctx.get("room_short_description") or "").strip()
    if room_desc:
        # Trim — we deliberately keep prompts compact.
        lines.append(f"  room: {room_desc[:240]}")

    def _csv(label: str, key: str, limit: int = 20):
        items = ctx.get(key) or []
        if not items:
            return
        items = [str(i) for i in items if i][:limit]
        if items:
            lines.append(f"  {label}: " + ", ".join(items))

    _csv("visible_objects", "visible_objects")
    _csv("visible_entities", "visible_entities")
    _csv("exits", "exits")
    _csv("inventory", "inventory")

    lines.append("")
    safe_text = (player_text or "").replace("\n", " ").strip()
    if len(safe_text) > 400:
        safe_text = safe_text[:400]
    lines.append(f"PLAYER COMMAND: {safe_text}")
    lines.append("")
    lines.append("JSON:")
    return "\n".join(lines)


# ── Main entry point ──────────────────────────────────────────────────────────

def parse_with_ollama(player_text: str, compact_context: dict):
    """Call Ollama and return a normalized dict, or None on any failure."""
    global _warned_invalid_json, _warned_http

    if not player_text or not player_text.strip():
        return None

    prompt = _build_prompt(player_text, compact_context or {})

    body = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_URL.rstrip('/')}/api/generate",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT_SECONDS) as r:
            raw = r.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, socket.timeout, socket.error, OSError):
        if not _warned_http:
            _warned_http = True
            print("[dungeon_kraulem.llm] Ollama HTTP error / timeout — falling back.",
                  file=sys.stderr)
        return None
    except Exception:
        return None

    # Outer envelope
    try:
        envelope = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        if not _warned_invalid_json:
            _warned_invalid_json = True
            print("[dungeon_kraulem.llm] Ollama returned invalid envelope JSON.", file=sys.stderr)
        return None

    response_text = ""
    if isinstance(envelope, dict):
        response_text = envelope.get("response", "")
    if not isinstance(response_text, str) or not response_text.strip():
        return None

    # Inner JSON returned by the model
    try:
        parsed = json.loads(response_text)
    except (json.JSONDecodeError, ValueError):
        if not _warned_invalid_json:
            _warned_invalid_json = True
            print("[dungeon_kraulem.llm] Ollama returned invalid inner JSON.", file=sys.stderr)
        return None

    return _normalize(parsed)


# ── Normalization ─────────────────────────────────────────────────────────────

def _normalize(raw) -> dict | None:
    """Coerce the raw model output into the required schema. Reject if hopeless."""
    if not isinstance(raw, dict):
        return None

    intent_v = raw.get("intent")
    if not isinstance(intent_v, str) or not intent_v.strip():
        return None
    intent_v = intent_v.strip().lower()

    verb_v = raw.get("verb")
    if isinstance(verb_v, str):
        verb_v = verb_v.strip() or None
    else:
        verb_v = None

    targets_v = raw.get("targets")
    if isinstance(targets_v, str):
        targets_v = [targets_v]
    if not isinstance(targets_v, list):
        targets_v = []
    targets_v = [str(t).strip() for t in targets_v if str(t).strip()]

    tool_v = raw.get("tool")
    tool_v = tool_v.strip() if isinstance(tool_v, str) and tool_v.strip() else None

    dest_v = raw.get("destination")
    dest_v = dest_v.strip() if isinstance(dest_v, str) and dest_v.strip() else None

    out_v = raw.get("desired_outcome")
    out_v = out_v.strip() if isinstance(out_v, str) and out_v.strip() else None

    stat_v = raw.get("suggested_stat")
    if isinstance(stat_v, str):
        stat_v = stat_v.strip().upper()
        if stat_v not in _VALID_STATS:
            stat_v = None
    else:
        stat_v = None

    risk_v = raw.get("risk_level")
    if isinstance(risk_v, str):
        risk_v = risk_v.strip().lower()
        if risk_v not in _VALID_RISK:
            risk_v = None
    else:
        risk_v = None

    conf_v = raw.get("confidence")
    try:
        conf_v = float(conf_v)
    except (TypeError, ValueError):
        conf_v = 0.5
    if conf_v < 0.0:
        conf_v = 0.0
    elif conf_v > 1.0:
        conf_v = 1.0

    # Prompt 07: memetic extras. Optional; pass through as strings/lists.
    def _str(name):
        v = raw.get(name)
        return v.strip() if isinstance(v, str) and v.strip() else None
    method_v = _str("method")
    core_claim_v = _str("core_claim")
    spread_channel_v = _str("spread_channel")
    emotional_hook_v = _str("emotional_hook")
    logic_hook_v = _str("logic_hook")
    target_tags_v = raw.get("target_tags")
    if isinstance(target_tags_v, str):
        target_tags_v = [target_tags_v]
    if not isinstance(target_tags_v, list):
        target_tags_v = []
    target_tags_v = [str(t).strip() for t in target_tags_v if str(t).strip()]

    return {
        "intent": intent_v,
        "verb": verb_v,
        "targets": targets_v,
        "tool": tool_v,
        "destination": dest_v,
        "desired_outcome": out_v,
        "suggested_stat": stat_v,
        "risk_level": risk_v,
        "confidence": conf_v,
        "method": method_v,
        "core_claim": core_claim_v,
        "spread_channel": spread_channel_v,
        "emotional_hook": emotional_hook_v,
        "logic_hook": logic_hook_v,
        "target_tags": target_tags_v,
    }


# Back-compat alias used by parser_core.parse_with_optional_llm in earlier shape.
def is_available() -> bool:
    return is_ollama_available()
