"""CRAWL PROTOCOL v2 - Configuration constants."""

# --- Window ---
SCREEN_W = 1280
SCREEN_H = 720
FPS = 60
TITLE = "CRAWL PROTOCOL"

# --- Localization ---
LANGUAGE = "pl"            # default UI language ("pl" | "en")
LANG_DEBUG_MISSING = False  # render missing keys as "[?key]" when True

# --- Audio (reserved — implemented in Step 1) ---
AUDIO_ENABLED = True
MASTER_VOLUME = 0.7
MUSIC_VOLUME  = 0.5
SFX_VOLUME    = 0.8
ASSET_DIR  = "assets"
SFX_DIR    = "assets/sfx"
MUSIC_DIR  = "assets/music"
ICON_DIR   = "assets/icons"

# --- Panel layout ---
MAP_W = 480
INFO_W = SCREEN_W - MAP_W          # 800
LOG_H = 200
INPUT_H = 40
MAP_H = SCREEN_H - LOG_H - INPUT_H # 480

# Panel origins
MAP_RECT = (0, 0, MAP_W, MAP_H)
INFO_RECT = (MAP_W, 0, INFO_W, MAP_H)
LOG_RECT = (0, MAP_H, SCREEN_W, LOG_H)
INPUT_RECT = (0, MAP_H + LOG_H, SCREEN_W, INPUT_H)

# --- Colors (dark sci-fi palette) ---
BLACK       = (0, 0, 0)
DARK_BG     = (10, 10, 18)
PANEL_BG    = (14, 14, 24)
BORDER      = (40, 60, 80)
DIM_TEXT    = (80, 100, 120)
NORMAL_TEXT = (180, 200, 220)
BRIGHT_TEXT = (220, 240, 255)
ACCENT      = (60, 180, 220)        # cyan
ACCENT2     = (180, 120, 220)       # purple
WARN        = (220, 160, 40)        # amber
DANGER      = (220, 60, 60)        # red
SUCCESS     = (60, 200, 100)        # green
GOLD_COLOR  = (220, 180, 50)
HP_BAR_FG   = (60, 200, 100)
HP_BAR_BG   = (60, 30, 30)
XP_BAR_FG   = (60, 120, 220)
XP_BAR_BG   = (20, 30, 50)
RATING_FG   = (220, 180, 50)
NODE_CURR   = (60, 220, 180)
NODE_VISIT  = (60, 80, 100)
NODE_UNVIS  = (30, 40, 55)
NODE_BOSS   = (200, 60, 60)
NODE_SAFE   = (60, 180, 120)
NODE_BORDER = (100, 140, 180)
EDGE_COLOR  = (40, 60, 80)
INPUT_BG    = (8, 8, 16)
INPUT_CURSOR= (60, 180, 220)
LOG_BG      = (8, 10, 16)

# Box tier colors
BOX_COPPER   = (180, 110, 60)
BOX_SILVER   = (180, 190, 210)
BOX_GOLD     = (220, 180, 50)
BOX_PLATINUM = (160, 220, 240)
BOX_TITANIUM = (200, 160, 255)
BOX_CLASS    = (220, 120, 60)
BOX_SKILL    = (100, 220, 120)

# --- Fonts (loaded at runtime in ui.py) ---
FONT_MONO   = "Courier New"
FONT_SIZE_SM = 13
FONT_SIZE_MD = 15
FONT_SIZE_LG = 18
FONT_SIZE_XL = 22

# --- Game constants ---
MAX_FLOOR = 5
LEVEL_CAP = 10
XP_THRESHOLDS = {1: 0, 2: 100, 3: 300, 4: 700, 5: 1200,
                 6: 2000, 7: 3000, 8: 4200, 9: 5700, 10: 7500}
POINT_BUY_BUDGET = 27
STAT_COST = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
PROFICIENCY_BONUS = {1: 2, 2: 2, 3: 2, 4: 2, 5: 3,
                     6: 3, 7: 3, 8: 3, 9: 4, 10: 4}
BASE_STATS = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]

# Box tier names (ordered)
BOX_TIERS = ["Copper", "Silver", "Gold", "Platinum", "Titanium"]

# Audience rating thresholds
RATING_LABELS = [
    (0,   "Dead Air"),
    (10,  "Minor Interest"),
    (25,  "Gaining Viewers"),
    (50,  "Popular"),
    (100, "Sensation"),
    (200, "Phenomenon"),
    (500, "Legendary"),
]

# Log message categories (used for coloring)
LOG_NORMAL  = "normal"
LOG_COMBAT  = "combat"
LOG_LOOT    = "loot"
LOG_SYSTEM  = "system"
LOG_WARN    = "warn"
LOG_SYNDIC  = "syndicate"
LOG_SUCCESS = "success"

LOG_COLORS = {
    LOG_NORMAL:  NORMAL_TEXT,
    LOG_COMBAT:  WARN,
    LOG_LOOT:    GOLD_COLOR,
    LOG_SYSTEM:  ACCENT,
    LOG_WARN:    DANGER,
    LOG_SYNDIC:  ACCENT2,
    LOG_SUCCESS: SUCCESS,
}
