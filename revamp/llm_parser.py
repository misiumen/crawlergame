"""Optional Ollama-backed parser.

Off by default. Enable with config.USE_OLLAMA = True and a running
local Ollama daemon at http://localhost:11434.

Never decides game state — only returns an ActionIntent for the
deterministic validator to interpret.
"""
import json
import urllib.request
import urllib.error
from typing import Optional

from .config import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS
from .parser_core import ActionIntent


_PROMPT_TMPL = """You are a strict structured-output assistant for a Polish-first
text RPG parser. Your only job is to translate a player's natural language
command into a single JSON object. Never invent objects or destinations.

Allowed JSON keys:
  intent (string), verb (string), targets (array of strings),
  tool (string|null), destination (string|null), desired_outcome (string|null),
  modifiers (array), confidence (float 0-1).

Player input (language: {lang}):
"{text}"

Visible objects in current room (their canonical lower-case names):
{visible}

Output ONLY valid JSON. No commentary.
"""


def parse(text: str, world=None) -> Optional[ActionIntent]:
    """Send the player's text to Ollama; return ActionIntent or None on failure."""
    from .lang import get_language

    visible_str = ""
    if world is not None and world.current_floor is not None:
        room = world.current_floor.current_room()
        if room:
            visible = [e.key for e in room.visible_entities()]
            visible_str = ", ".join(visible) if visible else "(empty)"

    prompt = _PROMPT_TMPL.format(text=text.replace('"', '\\"'),
                                 lang=get_language(),
                                 visible=visible_str)

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_URL.rstrip('/')}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT_SECONDS) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None

    response_text = data.get("response", "").strip()
    if not response_text:
        return None
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None

    intent = ActionIntent(raw_text=text, parser_source="ollama")
    intent.intent       = str(parsed.get("intent", "unknown"))
    intent.verb         = str(parsed.get("verb", ""))
    intent.targets      = [str(t) for t in parsed.get("targets", []) if t]
    intent.tool         = parsed.get("tool")
    intent.destination  = parsed.get("destination")
    intent.desired_outcome = parsed.get("desired_outcome")
    intent.modifiers    = [str(m) for m in parsed.get("modifiers", [])]
    try:
        intent.confidence = float(parsed.get("confidence", 0.5))
    except (TypeError, ValueError):
        intent.confidence = 0.5
    return intent


def is_available() -> bool:
    """Quick health check against the Ollama daemon."""
    req = urllib.request.Request(f"{OLLAMA_URL.rstrip('/')}/api/tags")
    try:
        with urllib.request.urlopen(req, timeout=1) as r:
            return r.status == 200
    except Exception:
        return False
