"""CRAWL PROTOCOL v2 - Game state machine."""
import pygame
from config import *
from utils import clamp, rating_label
from narrator import get_narrator
from parser import parse_input
from combat import (CombatState, process_player_action,
                    award_combat_xp, award_combat_credits)
from dungeon import Floor
from save_load import save_game, load_game, delete_save, save_exists
from rooms import (ROOM_COMBAT, ROOM_TRAP, ROOM_TREASURE, ROOM_REST,
                   ROOM_MERCHANT, ROOM_LORE, ROOM_MUTATION,
                   ROOM_CHECKPOINT, ROOM_BOSS, ROOM_START)


# ── Game states ────────────────────────────────────────────────────────────────

STATE_TITLE      = "title"
STATE_HOWTOPLAY  = "howtoplay"
STATE_CHAR_CREATE = "char_create"
STATE_INTRO      = "intro"        # backstory reveal before dungeon starts
STATE_EXPLORE    = "explore"
STATE_COMBAT     = "combat"
STATE_MERCHANT   = "merchant"
STATE_INVENTORY  = "inventory"
STATE_POPUP      = "popup"
STATE_VICTORY    = "victory"
STATE_DEFEAT     = "defeat"
STATE_LOAD       = "load"


class Game:
    def __init__(self, screen):
        self.screen = screen
        self.state = STATE_TITLE
        self.player = None
        self.floor = None
        self.combat_state = None
        self.n = get_narrator()

        # Message log: list of (text, category) tuples
        self.log = []
        self.log_scroll = 0

        # Input bar
        self.input_text = ""
        self.cursor_blink = True
        self.cursor_timer = 0
        self._suppress_textinput = False   # swallows the TEXTINPUT that follows a nav KEYDOWN

        # UI state
        self.hovered_node = None
        self.popup_data = None          # dict for current popup
        self.creation_state = {}        # char creation sub-state
        self.merchant_stock = []
        self.merchant_selected = 0
        self.inventory_selected = 0
        self.active_backstory = None    # current backstory dict for intro screen
        self.intro_page = 0             # which page of the intro we're on

        # Timing
        self.clock = pygame.time.Clock()

        # Level-up pending flag
        self._prev_level = 1

    # ── Logging ───────────────────────────────────────────────────────────────

    def msg(self, text, category=LOG_NORMAL):
        self.log.append((text, category))
        # Keep log bounded
        if len(self.log) > 500:
            self.log = self.log[-400:]

    def syndicate(self, category, **kwargs):
        line = self.n.say(category, **kwargs)
        self.msg(f"[SYNDICATE] {line}", LOG_SYNDIC)

    # ── State transitions ──────────────────────────────────────────────────────

    def start_new_game(self):
        from character import create_character_data, apply_backstory_gear
        from procgen import get_backstory
        cs = self.creation_state
        bg_key = cs.get("background_key", "Drifter")
        stats = cs.get("stats", {s: 10 for s in BASE_STATS})
        name = cs.get("name", "Contestant")
        self.player = create_character_data(name, bg_key, stats)
        self._prev_level = 1
        # Get backstory and apply flavor gear
        backstory = get_backstory(bg_key)
        apply_backstory_gear(self.player, backstory)
        self.active_backstory = backstory
        self.intro_page = 0
        self.state = STATE_INTRO

    def start_random_game(self):
        from character import randomize_character
        player, backstory = randomize_character()
        self.player = player
        self._prev_level = 1
        self.active_backstory = backstory
        self.intro_page = 0
        self.state = STATE_INTRO

    def _launch_dungeon(self):
        """Called after intro is dismissed — actually starts the dungeon."""
        self.floor = Floor(1)
        self.log = []
        self.msg("=== CRAWL PROTOCOL BEGINS ===", LOG_SYSTEM)
        self.msg("You have been selected. Congratulations.", LOG_SYNDIC)
        self.syndicate("enter_floor", floor=1)
        self.msg(f"  {self.floor.theme_desc}", LOG_NORMAL)
        self.state = STATE_EXPLORE
        self._enter_room(self.floor.current_id)

    def _enter_room(self, node_id):
        room = self.floor.rooms.get(node_id)
        if not room:
            return
        room.visited = True
        self.floor.current_id = node_id
        self.player.current_room_index = node_id
        self.msg(f"-- Entering: {room.name} [{room.room_type.upper()}] --", LOG_SYSTEM)
        self.syndicate("enter_room")

        rtype = room.room_type

        if rtype == ROOM_COMBAT or rtype == ROOM_BOSS:
            if not room.cleared:
                self._start_combat(room)
            else:
                self.msg("  Room cleared. Nothing left to fight.", LOG_NORMAL)

        elif rtype == ROOM_TRAP:
            if not room.cleared:
                self._start_trap(room)
            else:
                self.msg("  Trap already disarmed.", LOG_NORMAL)

        elif rtype == ROOM_TREASURE:
            if not room.cleared:
                self._open_treasure(room)
            else:
                self.msg("  Already looted.", LOG_NORMAL)

        elif rtype == ROOM_REST:
            self._enter_rest(room)

        elif rtype == ROOM_MERCHANT:
            self._enter_merchant(room)

        elif rtype == ROOM_LORE:
            if not room.cleared:
                self.msg(f"  DATA FRAGMENT: {room.lore_text}", LOG_SYSTEM)
                room.cleared = True
                self.player.add_audience(2)
            else:
                self.msg("  Already read.", LOG_NORMAL)

        elif rtype == ROOM_MUTATION:
            if not room.cleared:
                self._offer_mutation(room)
            else:
                self.msg("  Mutation already taken.", LOG_NORMAL)

        elif rtype == ROOM_CHECKPOINT:
            self._enter_checkpoint(room)

        elif rtype == ROOM_START:
            self.msg("  Starting point. Paths branch ahead.", LOG_NORMAL)

    def _start_combat(self, room):
        enemies = room.enemies
        if not enemies:
            room.cleared = True
            return
        self.combat_state = CombatState(self.player, enemies)
        self.combat_state.start_round()
        self.state = STATE_COMBAT
        self.syndicate("combat_start")
        for e in enemies:
            self.msg(f"  Hostile: {e.name}  HP:{e.hp}  AC:{e.ac}", LOG_WARN)
        self._show_combat_prompt()

    def _show_combat_prompt(self):
        feats = [f for f in self.player.features if f.is_available()]
        self.msg("  [1] Attack  [2] Use Item  [3] Defend  [4] Flee  [5] Inspect", LOG_SYSTEM)
        for i, f in enumerate(feats[:4]):
            self.msg(f"  [{i+6}] {f.name}", LOG_SYSTEM)
        self.msg("  Or type any action...", LOG_DIM if hasattr(self, 'LOG_DIM') else LOG_NORMAL)

    def _open_treasure(self, room):
        from items import open_box
        tier = room.loot_tier
        items = open_box(tier)
        self.syndicate("box_opened")
        self.msg(f"  {tier.upper()} BOX:", LOG_LOOT)
        loot_items = []
        for item in items:
            if isinstance(item, tuple) and item[0] == "credits":
                self.player.credits += item[1]
                self.msg(f"  + {item[1]} Credits", LOG_LOOT)
            else:
                self.player.add_to_inventory(item)
                self.msg(f"  + {item.display()}", LOG_LOOT)
                loot_items.append(item)
        room.cleared = True
        self.player.rooms_cleared += 1
        self.player.add_audience(3)
        self.syndicate("loot_found")

        # Check for Class Box
        import random
        if tier in ("Gold", "Platinum", "Titanium") and not self.player.class_key:
            if random.random() < 0.4:
                self._offer_class_box()

    def _enter_rest(self, room):
        healed = self.player.short_rest()
        self.msg(f"  Short rest: recovered {healed} HP. HP now {self.player.hp}/{self.player.max_hp}", LOG_SUCCESS)
        self.syndicate("rest")
        room.cleared = True

    def _enter_merchant(self, room):
        if not room.shop_stock:
            self.msg("  Merchant has nothing to sell.", LOG_NORMAL)
            room.cleared = True
            return
        self.merchant_stock = room.shop_stock
        self.merchant_selected = 0
        self.state = STATE_MERCHANT
        self.syndicate("merchant")
        self.msg("  Merchant reached. Credits: " + str(self.player.credits), LOG_ACCENT if False else LOG_SYSTEM)

    def _offer_mutation(self, room):
        pool = room.mutation_pool
        if not pool:
            room.cleared = True
            return
        # For now offer first mutation automatically with a confirm popup
        import random
        mut = random.choice(pool)
        self.popup_data = {
            "type": "mutation_offer",
            "mutation": mut,
            "room": room,
        }
        lines = [
            f"  Anomalous exposure detected.",
            f"  Mutation offered: {mut['name']}",
            f"  {mut['desc']}",
            "",
            "  [Y] Accept   [N] Decline",
        ]
        self.popup_data["lines"] = lines
        self.popup_data["title"] = "MUTATION EVENT"
        self.state = STATE_POPUP
        self.syndicate("mutation")

    def _enter_checkpoint(self, room):
        self.msg("  === CHECKPOINT ===", LOG_SYSTEM)
        self.syndicate("checkpoint")
        self.player.short_rest()
        self.msg(f"  HP restored to {self.player.hp}/{self.player.max_hp}", LOG_SUCCESS)
        if room.faction:
            name, tag, desc = room.faction
            self.msg(f"  Faction present: {name}", LOG_SYNDIC)
            self.msg(f"  {desc}", LOG_NORMAL)
        room.cleared = True

    def _offer_class_box(self):
        from items import open_class_box
        from character import CLASSES
        all_keys = list(CLASSES.keys())
        choices = open_class_box(all_keys)
        self.popup_data = {
            "type": "class_choice",
            "choices": choices,
        }
        self.state = STATE_POPUP
        self.msg("  CLASS BOX FOUND!", LOG_LOOT)
        self.syndicate("class_earned")

    def _complete_combat(self):
        room = self.floor.rooms.get(self.floor.current_id)
        enemies = self.combat_state.enemies
        xp = award_combat_xp(self.player, enemies)
        cr = award_combat_credits(self.player, enemies)
        self.msg(f"  Victory! +{xp} XP, +{cr} Credits.", LOG_SUCCESS)
        self.player.add_audience(5)
        if room:
            room.cleared = True
            self.player.rooms_cleared += 1
            # Check boss
            if room.is_boss_room:
                self._handle_boss_victory()
                return
            # Loot drop from boss-adjacent rooms
            import random
            if random.random() < 0.4:
                tier = self.floor._generate.__func__ if False else None  # hack
                from items import open_box, floor_loot_tier
                tier = floor_loot_tier(self.floor.floor_num)
                items = open_box(tier)
                for item in items:
                    if isinstance(item, tuple) and item[0] == "credits":
                        self.player.credits += item[1]
                        self.msg(f"  Loot: +{item[1]} Credits", LOG_LOOT)
                    else:
                        self.player.add_to_inventory(item)
                        self.msg(f"  Loot: {item.display()}", LOG_LOOT)

        # Check level up
        self._check_level_up()

        self.combat_state = None
        self.state = STATE_EXPLORE
        self._show_navigation_hint()

    def _handle_boss_victory(self):
        fn = self.floor.floor_num
        self.msg(f"  === FLOOR {fn} BOSS DEFEATED ===", LOG_SYSTEM)
        self.syndicate("boss_death")
        self.player.add_audience(20)

        # Boss loot
        from items import open_box
        tier = ["Gold", "Gold", "Platinum", "Platinum", "Titanium"][min(fn - 1, 4)]
        items = open_box(tier)
        for item in items:
            if isinstance(item, tuple) and item[0] == "credits":
                self.player.credits += item[1]
                self.msg(f"  Boss loot: +{item[1]} Credits", LOG_LOOT)
            else:
                self.player.add_to_inventory(item)
                self.msg(f"  Boss loot: {item.display()}", LOG_LOOT)

        # Possibly offer mutation
        import random
        if random.random() < 0.5:
            from rooms import random_mutation
            mut = random_mutation()
            self.player.add_mutation(mut)
            self.msg(f"  Mutation from boss: {mut['name']} - {mut['desc']}", LOG_LOOT)

        from config import MAX_FLOOR
        if fn >= MAX_FLOOR:
            self.state = STATE_VICTORY
            delete_save()
            return

        # Descend
        next_floor = fn + 1
        self.msg(f"  Descending to Floor {next_floor}...", LOG_SYSTEM)
        self.player.current_floor = next_floor
        self.floor = Floor(next_floor)
        self.player.current_room_index = 0
        # Reset feature cooldowns
        for f in self.player.features:
            f.restore()
        self.syndicate("enter_floor", floor=next_floor)
        self.msg(f"  {self.floor.theme_desc}", LOG_NORMAL)
        self.state = STATE_EXPLORE
        self._enter_room(self.floor.start_id)
        self._check_level_up()

    def _check_level_up(self):
        if self.player.level > self._prev_level:
            new_level = self.player.level
            self._prev_level = new_level
            self.syndicate("level_up")
            self.msg(f"  === LEVEL UP: {new_level} ===", LOG_SUCCESS)
            self.msg(f"  HP: {self.player.max_hp}  Prof: +{self.player.prof()}", LOG_SYSTEM)
            # Offer class choice at level 3 if not yet classed
            if new_level == 3 and not self.player.class_key:
                self._offer_class_box()
            # Offer evolution at level 5 if classed
            if new_level == 5 and self.player.class_key and not self.player.specialization:
                self._offer_evolution()

    def _offer_evolution(self):
        from character import CLASSES
        self.popup_data = {
            "type": "evolution",
        }
        self.state = STATE_POPUP

    def _show_navigation_hint(self):
        room = self.floor.rooms.get(self.floor.current_id)
        if not room:
            return
        reachable = room.connections
        if reachable:
            hints = []
            for nid in reachable:
                r2 = self.floor.rooms.get(nid)
                if r2:
                    hints.append(f"{r2.symbol()}{nid}:{r2.room_type}")
            self.msg(f"  Paths: {', '.join(hints)}", LOG_SYSTEM)
            self.msg("  Click a room node or type 'go to [room]'", LOG_NORMAL)
        else:
            self.msg("  No paths forward from here.", LOG_WARN)

    def _navigate_to_node(self, node_id):
        """Player attempts to navigate to a node_id."""
        current = self.floor.rooms.get(self.floor.current_id)
        if node_id not in (current.connections if current else []):
            self.msg(f"  Cannot reach room {node_id} from here.", LOG_WARN)
            return
        self._enter_room(node_id)

    # ── Input handling ─────────────────────────────────────────────────────────

    def handle_text_submit(self):
        text = self.input_text.strip()
        self.input_text = ""
        if not text:
            return
        self.msg(f"> {text}", LOG_NORMAL)
        self._dispatch_text(text)

    def _dispatch_text(self, text):
        state = self.state

        if state == STATE_EXPLORE:
            self._explore_text_action(text)

        elif state == STATE_COMBAT:
            action = parse_input(text, context="combat")
            process_player_action(self.combat_state, action)
            # Flush combat log
            for line, cat in self.combat_state.log_lines:
                self.msg(line, cat)
            self.combat_state.log_lines = []

            if self.combat_state.result == "victory":
                self._complete_combat()
            elif self.combat_state.result == "defeat":
                self.state = STATE_DEFEAT
                delete_save()
            elif self.combat_state.result == "fled":
                self.msg("  You escaped.", LOG_WARN)
                self.player.add_audience(-3)
                self.combat_state = None
                self.state = STATE_EXPLORE
                self._show_navigation_hint()
            else:
                self.combat_state.start_round()
                self._show_combat_prompt()

        elif state == STATE_MERCHANT:
            self._merchant_text_action(text)

        elif state == STATE_POPUP:
            self._popup_text_action(text)

        elif state == STATE_TITLE:
            self._title_text_action(text)

        elif state == STATE_CHAR_CREATE:
            self._creation_text_action(text)

    def _explore_text_action(self, text):
        lower = text.lower()
        # Navigation
        import re
        m = re.search(r'(?:go|move|navigate|travel|head).*?(\d+)', lower)
        if m:
            nid = int(m.group(1))
            self._navigate_to_node(nid)
            return
        if any(w in lower for w in ("inventory", "items", "bag", "pack")):
            self.state = STATE_INVENTORY
            return
        if any(w in lower for w in ("save", "quit", "exit")):
            self._do_save_quit()
            return
        if any(w in lower for w in ("rest", "sleep", "recover")):
            healed = self.player.short_rest()
            self.msg(f"  Short rest: +{healed} HP", LOG_SUCCESS)
            return
        if any(w in lower for w in ("map", "floor", "layout")):
            self.msg("  [Map is shown on the left panel]", LOG_SYSTEM)
            return
        if any(w in lower for w in ("stat", "sheet", "character", "status")):
            for line in self.player.stat_block_lines():
                self.msg(f"  {line}", LOG_NORMAL)
            return
        # Free-text exploration action
        action = parse_input(text, context="explore")
        from parser import skill_check, describe_result
        result = skill_check(self.player, action)
        for line in describe_result(result, "explore"):
            self.msg(line, LOG_NORMAL)
        self.player.add_audience(result.get("aud_delta", 0))

    def _merchant_text_action(self, text):
        lower = text.lower()
        if any(c in lower for c in ("esc", "leave", "exit", "done", "quit")):
            self.state = STATE_EXPLORE
            self.msg("  Left the merchant.", LOG_NORMAL)
            return
        # Try numeric
        import re
        m = re.match(r'^(\d+)$', lower.strip())
        if m:
            idx = int(m.group(1)) - 1
            self._buy_merchant_item(idx)
            return
        if lower.startswith("s"):
            self.state = STATE_INVENTORY
            return
        if lower.startswith("h"):
            cost = 30
            if self.player.credits >= cost:
                self.player.credits -= cost
                self.player.heal(10)
                self.msg(f"  Healed 10 HP for {cost} CR. HP: {self.player.hp}/{self.player.max_hp}", LOG_SUCCESS)
            else:
                self.msg("  Not enough credits.", LOG_WARN)
            return
        # Free-text buy intent
        if "buy" in lower or "purchase" in lower or "take" in lower:
            import re
            m2 = re.search(r'(?:buy|purchase|take)\s+(?:the\s+)?(.+)', lower)
            if m2:
                item_name = m2.group(1).strip()
                for i, (item, price) in enumerate(self.merchant_stock):
                    if item_name in item.name.lower():
                        self._buy_merchant_item(i)
                        return

    def _buy_merchant_item(self, idx):
        if 0 <= idx < len(self.merchant_stock):
            item, price = self.merchant_stock[idx]
            discount = self.player.trinket and self.player.trinket.passive == "merchant_10"
            final_price = int(price * 0.9) if discount else price
            if self.player.credits >= final_price:
                self.player.credits -= final_price
                self.player.add_to_inventory(item)
                self.merchant_stock.pop(idx)
                self.msg(f"  Bought {item.display()} for {final_price} CR.", LOG_LOOT)
                self.merchant_selected = 0
            else:
                self.msg(f"  Not enough credits (need {final_price}).", LOG_WARN)
        else:
            self.msg("  Invalid selection.", LOG_WARN)

    def _popup_text_action(self, text):
        lower = text.lower().strip()
        pdata = self.popup_data or {}
        ptype = pdata.get("type")

        if ptype == "mutation_offer":
            room = pdata.get("room")
            mut = pdata.get("mutation")
            if lower in ("y", "yes", "1", "accept"):
                self.player.add_mutation(mut)
                self.msg(f"  Mutation accepted: {mut['name']}", LOG_LOOT)
                if room:
                    room.cleared = True
            else:
                self.msg("  Mutation declined.", LOG_NORMAL)
                if room:
                    room.cleared = True
            self.popup_data = None
            self.state = STATE_EXPLORE

        elif ptype == "class_choice":
            choices = pdata.get("choices", [])
            try:
                idx = int(lower.strip()) - 1
                if 0 <= idx < len(choices):
                    key = choices[idx]
                    self.player.assign_class(key)
                    self.msg(f"  Class assigned: {self.player.class_name}", LOG_SUCCESS)
                    self.syndicate("class_earned")
                    self._prev_level = self.player.level
                    self.popup_data = None
                    self.state = STATE_EXPLORE
                else:
                    self.msg("  Invalid choice.", LOG_WARN)
            except ValueError:
                self.msg("  Enter a number.", LOG_WARN)

        elif ptype == "evolution":
            self._handle_evolution_text(lower)

        else:
            # Generic dismiss
            if lower in ("enter", "", "ok", "yes", "continue", "1"):
                self.popup_data = None
                self.state = STATE_EXPLORE

    def _handle_evolution_text(self, text):
        from character import CLASSES
        if "1" in text or "spec" in text:
            # Specialization — add bonus feature
            from features import features_for_class
            if self.player.class_key:
                extras = features_for_class(self.player.class_key, 1)
                if extras:
                    self.player.features.append(extras[0])
                    self.msg(f"  Specialized: gained {extras[0].name}", LOG_SUCCESS)
            self.player.specialization = self.player.class_name
            self.popup_data = None
            self.state = STATE_EXPLORE
        elif "2" in text or "hyb" in text:
            # Hybridize — pick a second class
            current_key = self.player.class_key
            compat = [k for k in CLASSES if k != current_key]
            import random
            second_key = random.choice(compat)
            second_cls = CLASSES[second_key]
            self.player.secondary_class = second_cls["name"]
            self.player.hybrid_class = f"{self.player.class_name}/{second_cls['name']}"
            from features import features_for_class
            extras = features_for_class(second_key, 2)
            for f in extras:
                self.player.features.append(f)
            self.msg(f"  Hybrid class: {self.player.hybrid_class}", LOG_SUCCESS)
            self.msg(f"  Gained features: {', '.join(f.name for f in extras)}", LOG_SUCCESS)
            self.popup_data = None
            self.state = STATE_EXPLORE

    def _title_text_action(self, text):
        lower = text.strip().lower()
        if lower in ("1", "build", "new", "new game"):
            self._begin_char_creation()
        elif lower in ("2", "random", "rand", "randomize"):
            self.start_random_game()
        elif lower in ("3", "load", "load game"):
            self._do_load_game()
        elif lower in ("4", "help", "how to play"):
            self.state = STATE_HOWTOPLAY
        elif lower in ("5", "quit", "exit"):
            import sys
            pygame.quit()
            sys.exit()

    def _begin_char_creation(self):
        self.creation_state = {
            "step": "name",
            "name_input": "",
            "name": "",
            "selected_bg": 0,
            "background_key": "Drifter",
            "stats": {s: 8 for s in BASE_STATS},
            "point_pool": POINT_BUY_BUDGET,
            "cursor": 0,
        }
        self.input_text = ""
        self._suppress_textinput = True   # eat any TEXTINPUT still in the queue
        self.state = STATE_CHAR_CREATE

    def _creation_text_action(self, text):
        cs = self.creation_state
        step = cs.get("step")
        if step == "name":
            cs["name"] = text
            cs["name_input"] = text
            cs["step"] = "background"

    def _do_load_game(self):
        if not save_exists():
            self.msg("  No save file found.", LOG_WARN)
            return
        player, floor_data = load_game()
        if player is None:
            self.msg("  Could not load save (incompatible version?).", LOG_WARN)
            return
        self.player = player
        self._prev_level = player.level
        if floor_data:
            self.floor = Floor.from_dict(floor_data)
        else:
            self.floor = Floor(player.current_floor)
        self.log = []
        self.msg("  Save loaded.", LOG_SUCCESS)
        self.msg(f"  Welcome back, {player.name}.", LOG_SYNDIC)
        self.state = STATE_EXPLORE
        self._show_navigation_hint()

    def _do_save_quit(self):
        if self.player and self.floor:
            save_game(self.player, self.floor)
            self.msg("  Game saved.", LOG_SUCCESS)
        import sys
        pygame.quit()
        sys.exit()

    # ── Keyboard handling ──────────────────────────────────────────────────────

    # Map pygame number key constants to digit characters
    _NUM_KEYS = {
        pygame.K_1: "1", pygame.K_2: "2", pygame.K_3: "3",
        pygame.K_4: "4", pygame.K_5: "5", pygame.K_6: "6",
        pygame.K_7: "7", pygame.K_8: "8", pygame.K_9: "9",
        pygame.K_0: "0",
        pygame.K_KP1: "1", pygame.K_KP2: "2", pygame.K_KP3: "3",
        pygame.K_KP4: "4", pygame.K_KP5: "5", pygame.K_KP6: "6",
        pygame.K_KP7: "7", pygame.K_KP8: "8", pygame.K_KP9: "9",
        pygame.K_KP0: "0",
    }

    def handle_keydown(self, event):
        key = event.key
        state = self.state
        digit = self._NUM_KEYS.get(key)

        # ── Title screen: number keys fire immediately, no Enter needed ──────
        if state == STATE_TITLE:
            if digit in ("1", "2", "3", "4", "5"):
                self._suppress_textinput = True   # eat the TEXTINPUT that follows
                self.input_text = ""
                self._title_text_action(digit)
                return
            if key == pygame.K_RETURN and self.input_text.strip():
                self.handle_text_submit()
            return

        # ── Intro screen: any key / Enter advances ────────────────────────────
        if state == STATE_INTRO:
            if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                self.intro_page += 1
                # Intro has one page of story + one page of gear summary
                if self.intro_page >= 2:
                    self._launch_dungeon()
            return

        # ── How-to-play / end screens ─────────────────────────────────────────
        if state in (STATE_VICTORY, STATE_DEFEAT, STATE_HOWTOPLAY):
            if key in (pygame.K_RETURN, pygame.K_ESCAPE):
                self.state = STATE_TITLE
                self.player = None
                self.floor = None
                self.log = []
            return

        # ── Character creation ────────────────────────────────────────────────
        if state == STATE_CHAR_CREATE:
            cs = self.creation_state
            step = cs.get("step")

            if step == "name":
                if key == pygame.K_RETURN:
                    self._creation_confirm()
                elif key == pygame.K_BACKSPACE:
                    cs["name_input"] = cs.get("name_input", "")[:-1]
                # typing handled by handle_textinput
                return

            if step == "background":
                if digit:
                    from character import BACKGROUNDS
                    bg_keys = list(BACKGROUNDS.keys())
                    idx = int(digit) - 1
                    if 0 <= idx < len(bg_keys):
                        self._suppress_textinput = True
                        cs["selected_bg"] = idx
                        cs["background_key"] = bg_keys[idx]
                        cs["step"] = "stats"
                        return
                if key == pygame.K_RETURN:
                    self._creation_confirm()
                elif key == pygame.K_BACKSPACE or key == pygame.K_ESCAPE:
                    self._creation_back()
                elif key in (pygame.K_UP, pygame.K_DOWN):
                    self._handle_nav_key(key)
                return

            if step == "stats":
                if key == pygame.K_RETURN:
                    self._creation_confirm()
                elif key == pygame.K_BACKSPACE or key == pygame.K_ESCAPE:
                    self._creation_back()
                elif key in (pygame.K_UP, pygame.K_DOWN):
                    self._handle_nav_key(key)
                elif key in (pygame.K_LEFT, pygame.K_RIGHT):
                    self._handle_stat_adjust(key)
                return

            if step == "confirm":
                if key == pygame.K_RETURN:
                    self._creation_confirm()
                elif key == pygame.K_BACKSPACE or key == pygame.K_ESCAPE:
                    self._creation_back()
                return
            return

        # ── Gameplay states ───────────────────────────────────────────────────
        if state in (STATE_EXPLORE, STATE_COMBAT, STATE_MERCHANT, STATE_POPUP):
            if key == pygame.K_RETURN:
                self.handle_text_submit()

            elif key == pygame.K_BACKSPACE:
                self.input_text = self.input_text[:-1]

            elif key == pygame.K_ESCAPE:
                if state == STATE_INVENTORY:
                    self.state = STATE_EXPLORE
                elif state == STATE_MERCHANT:
                    self.state = STATE_EXPLORE
                elif state == STATE_POPUP:
                    pdata = self.popup_data or {}
                    if pdata.get("type") not in ("class_choice", "evolution"):
                        self.popup_data = None
                        self.state = STATE_EXPLORE

            elif key in (pygame.K_UP, pygame.K_DOWN):
                self._handle_nav_key(key)

            elif key in (pygame.K_LEFT, pygame.K_RIGHT):
                self._handle_stat_adjust(key)

    def handle_textinput(self, event):
        """pygame.TEXTINPUT event — append to input buffer."""
        if self._suppress_textinput:
            self._suppress_textinput = False
            return
        state = self.state
        if state in (STATE_EXPLORE, STATE_COMBAT, STATE_MERCHANT, STATE_POPUP):
            self.input_text += event.text
        elif state == STATE_CHAR_CREATE:
            cs = self.creation_state
            step = cs.get("step")
            if step == "name":
                cs["name_input"] = cs.get("name_input", "") + event.text
            elif step in ("background", "stats", "confirm") and event.text.isdigit():
                # Route digit keys to handle_keydown logic by synthesizing a fake event
                # Easier: just dispatch directly
                digit = event.text
                if step == "background":
                    from character import BACKGROUNDS
                    bg_keys = list(BACKGROUNDS.keys())
                    idx = int(digit) - 1
                    if 0 <= idx < len(bg_keys):
                        cs["selected_bg"] = idx
                        cs["background_key"] = bg_keys[idx]
                        cs["step"] = "stats"

    def handle_mouseclick(self, pos, button):
        state = self.state
        if state == STATE_EXPLORE and self.floor:
            mx, my = pos
            # Only handle left panel (map area)
            if mx < MAP_W:
                node_id = None
                import math
                offset_y = 38
                for nid, room in self.floor.rooms.items():
                    nx = room.x + MAP_RECT[0]
                    ny = room.y + MAP_RECT[1] + offset_y
                    if math.sqrt((mx - nx) ** 2 + (my - ny) ** 2) <= 18:
                        node_id = nid
                        break
                if node_id is not None and node_id != self.floor.current_id:
                    self._navigate_to_node(node_id)

    def handle_mousemotion(self, pos):
        if self.state == STATE_EXPLORE and self.floor:
            mx, my = pos
            if mx < MAP_W:
                import math
                offset_y = 38
                self.hovered_node = None
                for nid, room in self.floor.rooms.items():
                    nx = room.x + MAP_RECT[0]
                    ny = room.y + MAP_RECT[1] + offset_y
                    if math.sqrt((mx - nx) ** 2 + (my - ny) ** 2) <= 18:
                        self.hovered_node = nid
                        break

    def handle_mousewheel(self, y):
        if LOG_RECT[1] <= pygame.mouse.get_pos()[1] <= LOG_RECT[1] + LOG_H:
            self.log_scroll = clamp(self.log_scroll - y, 0, max(0, len(self.log) - 10))

    # ── Creation sub-state ─────────────────────────────────────────────────────

    def _creation_confirm(self):
        cs = self.creation_state
        step = cs.get("step")
        if step == "name":
            name = cs.get("name_input", "").strip()
            if name:
                cs["name"] = name
                cs["step"] = "background"
        elif step == "background":
            from character import BACKGROUNDS
            idx = cs.get("selected_bg", 0)
            bg_keys = list(BACKGROUNDS.keys())
            cs["background_key"] = bg_keys[idx % len(bg_keys)]
            cs["step"] = "stats"
        elif step == "stats":
            cs["step"] = "confirm"
        elif step == "confirm":
            self.start_new_game()

    def _creation_back(self):
        cs = self.creation_state
        step = cs.get("step")
        steps = ["name", "background", "stats", "confirm"]
        idx = steps.index(step) if step in steps else 0
        if idx > 0:
            cs["step"] = steps[idx - 1]
        else:
            self.state = STATE_TITLE

    def _handle_nav_key(self, key):
        cs = self.creation_state
        state = self.state
        if state == STATE_CHAR_CREATE:
            step = cs.get("step")
            if step == "background":
                from character import BACKGROUNDS
                n = len(BACKGROUNDS)
                if key == pygame.K_UP:
                    cs["selected_bg"] = (cs.get("selected_bg", 0) - 1) % n
                else:
                    cs["selected_bg"] = (cs.get("selected_bg", 0) + 1) % n
            elif step == "stats":
                n = len(BASE_STATS)
                if key == pygame.K_UP:
                    cs["cursor"] = (cs.get("cursor", 0) - 1) % n
                else:
                    cs["cursor"] = (cs.get("cursor", 0) + 1) % n
        elif state == STATE_MERCHANT:
            n = len(self.merchant_stock)
            if key == pygame.K_UP:
                self.merchant_selected = (self.merchant_selected - 1) % max(1, n)
            else:
                self.merchant_selected = (self.merchant_selected + 1) % max(1, n)
        elif state == STATE_INVENTORY:
            n = len(self.player.inventory) if self.player else 0
            if key == pygame.K_UP:
                self.inventory_selected = (self.inventory_selected - 1) % max(1, n)
            else:
                self.inventory_selected = (self.inventory_selected + 1) % max(1, n)

    def _handle_stat_adjust(self, key):
        cs = self.creation_state
        if self.state == STATE_CHAR_CREATE and cs.get("step") == "stats":
            cursor = cs.get("cursor", 0)
            stat = BASE_STATS[cursor]
            stats = cs["stats"]
            pool = cs["point_pool"]
            from config import STAT_COST
            if key == pygame.K_RIGHT:  # increase
                new_val = stats[stat] + 1
                if new_val <= 15:
                    cost = STAT_COST.get(new_val, 99)
                    if pool >= cost:
                        old_cost = STAT_COST.get(stats[stat], 0)
                        actual_cost = cost - old_cost  # incremental
                        # Actually point buy cost is total, not incremental
                        # Recalculate pool from scratch
                        new_stats = dict(stats)
                        new_stats[stat] = new_val
                        total_spent = sum(STAT_COST.get(v, 0) - STAT_COST.get(8, 0) for v in new_stats.values())
                        new_pool = POINT_BUY_BUDGET - total_spent
                        if new_pool >= 0:
                            stats[stat] = new_val
                            cs["point_pool"] = new_pool
            elif key == pygame.K_LEFT:  # decrease
                new_val = stats[stat] - 1
                if new_val >= 8:
                    new_stats = dict(stats)
                    new_stats[stat] = new_val
                    total_spent = sum(STAT_COST.get(v, 0) - STAT_COST.get(8, 0) for v in new_stats.values())
                    new_pool = POINT_BUY_BUDGET - total_spent
                    stats[stat] = new_val
                    cs["point_pool"] = new_pool

    # ── Update (called every frame) ────────────────────────────────────────────

    def update(self, dt):
        self.cursor_timer += dt
        if self.cursor_timer >= 500:
            self.cursor_blink = not self.cursor_blink
            self.cursor_timer = 0

    # ── Draw ───────────────────────────────────────────────────────────────────

    def draw(self):
        import ui
        screen = self.screen
        state = self.state

        screen.fill(DARK_BG)

        if state == STATE_TITLE:
            ui.draw_title_screen(screen)

        elif state == STATE_HOWTOPLAY:
            ui.draw_howtoplay(screen)

        elif state == STATE_CHAR_CREATE:
            ui.draw_char_creation(screen, self.creation_state)

        elif state == STATE_INTRO:
            ui.draw_intro_screen(screen, self.player, self.active_backstory, self.intro_page)

        elif state in (STATE_EXPLORE, STATE_COMBAT, STATE_MERCHANT,
                       STATE_INVENTORY, STATE_POPUP):
            # Map panel
            if self.floor:
                ui.draw_map_panel(screen, self.floor, self.floor.current_id, self.hovered_node)

            # Info panel
            current_room = self.floor.rooms.get(self.floor.current_id) if self.floor else None
            ui.draw_info_panel(screen, self.player, current_room,
                               self.combat_state if state == STATE_COMBAT else None)

            # Log panel
            ui.draw_log_panel(screen, self.log, self.log_scroll)

            # Input bar (not in merchant/inventory/popup overlays)
            ui.draw_input_bar(screen, self.input_text, blink=self.cursor_blink)

            # Overlays
            if state == STATE_MERCHANT:
                ui.draw_merchant(screen, self.player, self.merchant_stock, self.merchant_selected)

            elif state == STATE_INVENTORY:
                ui.draw_inventory(screen, self.player, self.inventory_selected)

            elif state == STATE_POPUP and self.popup_data:
                pdata = self.popup_data
                ptype = pdata.get("type")
                if ptype == "mutation_offer":
                    ui.draw_popup(screen, pdata.get("title", "EVENT"), pdata.get("lines", []))
                elif ptype == "class_choice":
                    ui.draw_class_choice(screen, pdata.get("choices", []))
                elif ptype == "evolution":
                    lines = [
                        "  Level 5 reached. Evolution available.",
                        "",
                        "  [1] Specialize - master your current class (gain bonus feature)",
                        "  [2] Hybridize  - merge with a compatible class (gain 2 features)",
                    ]
                    ui.draw_popup(screen, "CLASS EVOLUTION", lines,
                                  [("1", "Specialize"), ("2", "Hybridize")])

        elif state == STATE_VICTORY:
            ui.draw_victory_screen(screen, self.player)

        elif state == STATE_DEFEAT:
            ui.draw_defeat_screen(screen, self.player)

        pygame.display.flip()
