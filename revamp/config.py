"""Revamp configuration."""

# Window
SCREEN_W = 1280
SCREEN_H = 800
FPS = 60
TITLE = "CRAWL PROTOCOL — Revamp"

# Localization
LANGUAGE = "pl"            # "pl" | "en"
LANG_DEBUG_MISSING = False
LOCALES_DIR = "revamp/locales"

# Time system (minutes per in-game unit)
MINUTES_PER_DAY = 24 * 60
FLOOR1_DEADLINE_DAYS = 14

# Parser
USE_OLLAMA = False
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.1:8b"
OLLAMA_TIMEOUT_SECONDS = 4

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
