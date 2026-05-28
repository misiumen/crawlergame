"""Revamp configuration."""

# ── Window / display ──────────────────────────────────────────────────────
SUPPORTED_RESOLUTIONS = [
    (1280, 720),
    (1366, 768),
    (1600, 900),
    (1920, 1080),
    (2560, 1440),
    (3440, 1440),
]
DEFAULT_RESOLUTION = (1280, 720)
FULLSCREEN_ENABLED = False
UI_SCALE = "auto"       # "auto" or float multiplier applied to font_scale

# Legacy constants — kept as defaults for back-compat. Anything that needs
# the live size should read `pygame.display.get_surface().get_size()` or
# call `revamp.layout.calculate_layout(w, h)`.
SCREEN_W = DEFAULT_RESOLUTION[0]
SCREEN_H = DEFAULT_RESOLUTION[1]
FPS = 60
TITLE = "Dungeon Kraulem"

# Localization
LANGUAGE = "pl"            # "pl" | "en"
LANG_DEBUG_MISSING = False
LOCALES_DIR = "dungeon_kraulem/ui/locales"

# Time system (minutes per in-game unit)
MINUTES_PER_DAY = 24 * 60
FLOOR1_DEADLINE_DAYS = 14

# P29.53k — DCC canon: each floor has its own deadline + carryover
# bonus on descend. Book pattern: F1 jest "łagodne" (14d intro),
# kolejne piętra coraz krótsze (5-10d), a zejście dorzuca 5d.
# Tak gracz może bankować czas — jeśli skończył poprzednie piętro
# szybko, dostaje fory na następnym.
DEADLINE_DAYS_BY_FLOOR = {
    1: 14, 2: 10, 3: 10, 4: 8, 5: 8, 6: 7, 7: 7, 8: 6, 9: 6,
    10: 5, 11: 5, 12: 5, 13: 5, 14: 5, 15: 5, 16: 5, 17: 5, 18: 5,
}
DEADLINE_DAYS_DEFAULT = 5
DEADLINE_CARRYOVER_BONUS_DAYS = 5


def deadline_minutes_for_floor(floor_number: int) -> int:
    """Return total deadline window (in minutes) for the given floor's
    base. Carryover from a previous floor is handled separately by
    Game._descend_or_win."""
    days = DEADLINE_DAYS_BY_FLOOR.get(int(floor_number),
                                      DEADLINE_DAYS_DEFAULT)
    return int(days) * MINUTES_PER_DAY

# Floor generation
USE_HANDMADE_FLOOR_1 = False    # if True, load the 15-room vertical slice instead
FLOOR_GEN_MAX_RETRIES = 8        # retries when validation fails

# Parser
# ── LLM (Ollama) integration ─────────────────────────────────────────────
# Local LLM is OPT-IN and strictly cosmetic / interpretive. The engine
# owns all truth (objects, loot, damage, NPC state, campaign progress).
# Models may only contribute text, alternate phrasing, structured
# suggestions, or flavor — every output is validated before use.
#
# Three runtime modes preset the four role flags below:
#   "performance" — all LLM features off (default, no model required)
#   "enhanced"    — intent parser + main narrator
#   "full_show"   — intent + narrator + lootbox flavor + dialogue/interview
#
# Models are addressed by role so swapping or disabling one model never
# affects the others.
OLLAMA_URL              = "http://localhost:11434"
OLLAMA_TIMEOUT_SECONDS  = 2

# Per-role model assignments. Override individually if you want to test
# a different model for one role.
LLM_INTENT_MODEL    = "qwen2.5:3b"      # quick intent parsing + memetic enrichment
LLM_NARRATOR_MODEL  = "qwen3:30b"       # main narrator
LLM_LOOTBOX_MODEL   = "qwen3:14b"       # lootbox flavor / lightweight fallback
LLM_DIALOGUE_MODEL  = "llama3.3:70b"    # interviews + sponsor personalities

# Runtime mode. Setting this at module load implies the four flags below
# — the values below are then overridden by `apply_llm_mode(LLM_MODE)`.
LLM_MODE = "performance"

# Per-role enable flags. Read by `llm_roles.is_role_enabled` at call
# sites. `apply_llm_mode` overwrites these to match the runtime mode.
LLM_INTENT_ENABLED   = False
LLM_NARRATOR_ENABLED = False
LLM_LOOTBOX_ENABLED  = False
LLM_DIALOGUE_ENABLED = False

# Legacy alias — older code paths read USE_OLLAMA. Kept as a derived view
# of LLM_INTENT_ENABLED so a single source of truth controls the parser.
USE_OLLAMA = LLM_INTENT_ENABLED
OLLAMA_MODEL = LLM_INTENT_MODEL


_MODE_PRESETS = {
    "performance": dict(intent=False, narrator=False, lootbox=False, dialogue=False),
    "enhanced":    dict(intent=True,  narrator=True,  lootbox=False, dialogue=False),
    "full_show":   dict(intent=True,  narrator=True,  lootbox=True,  dialogue=True),
}


def apply_llm_mode(mode: str) -> str:
    """Set the four role flags + USE_OLLAMA alias from a mode preset.

    Returns the normalized mode key actually applied (falls back to
    'performance' on unknown input — never raises)."""
    global LLM_MODE, LLM_INTENT_ENABLED, LLM_NARRATOR_ENABLED
    global LLM_LOOTBOX_ENABLED, LLM_DIALOGUE_ENABLED, USE_OLLAMA
    norm = (mode or "performance").strip().lower()
    if norm not in _MODE_PRESETS:
        norm = "performance"
    preset = _MODE_PRESETS[norm]
    LLM_MODE = norm
    LLM_INTENT_ENABLED   = bool(preset["intent"])
    LLM_NARRATOR_ENABLED = bool(preset["narrator"])
    LLM_LOOTBOX_ENABLED  = bool(preset["lootbox"])
    LLM_DIALOGUE_ENABLED = bool(preset["dialogue"])
    USE_OLLAMA = LLM_INTENT_ENABLED
    return norm


# Apply the default mode on import so the legacy alias stays consistent.
apply_llm_mode(LLM_MODE)

# Audio
AUDIO_ENABLED = True
MASTER_VOLUME = 0.7
MUSIC_VOLUME  = 0.5
SFX_VOLUME    = 0.8

# Asset paths
ASSET_DIR  = "assets"
SFX_DIR    = "assets/audio/sfx"
MUSIC_DIR  = "assets/audio/music"
IMAGE_DIR  = "assets/images"

# Layout
TOP_BAR_H    = 60
LOG_H        = 200
INPUT_H      = 40
SIDEBAR_W    = 380           # right column: character/status/map
ROOM_PANEL_W = SCREEN_W - SIDEBAR_W  # left column: room description

# Colors
BLACK       = (0, 0, 0)
DARK_BG     = (10, 12, 18)
PANEL_BG    = (16, 18, 26)
BORDER      = (40, 60, 80)
DIM_TEXT    = (90, 110, 130)
NORMAL_TEXT = (190, 205, 220)
BRIGHT_TEXT = (230, 240, 255)
ACCENT      = (80, 200, 240)     # cyan
ACCENT2     = (200, 140, 240)    # magenta
WARN        = (230, 170, 60)     # amber
DANGER      = (230, 80, 80)
SUCCESS     = (90, 210, 120)
GOLD        = (230, 200, 70)
INPUT_BG    = (8, 10, 16)
LOG_BG      = (8, 10, 16)

# Log categories
LOG_NORMAL  = "normal"
LOG_SYSTEM  = "system"
LOG_WARN    = "warn"
LOG_DANGER  = "danger"
LOG_SUCCESS = "success"
LOG_SYNDIC  = "syndicate"

LOG_COLORS = {
    LOG_NORMAL:  NORMAL_TEXT,
    LOG_SYSTEM:  ACCENT,
    LOG_WARN:    WARN,
    LOG_DANGER:  DANGER,
    LOG_SUCCESS: SUCCESS,
    LOG_SYNDIC:  ACCENT2,
}

# Stats
BASE_STATS = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]

# Affinity kinds (drives dynamic class offer)
AFFINITY_KINDS = (
    "melee", "ranged", "stealth", "magic", "tech", "trap",
    "environment", "support", "social", "survival",
    "showmanship", "betrayal", "diplomacy", "crafting",
)
