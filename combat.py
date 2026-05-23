"""CRAWL PROTOCOL v2 - Combat engine."""
import random
from utils import d20, parse_dice, clamp
from narrator import get_narrator


# ── Condition helpers ──────────────────────────────────────────────────────────

def _apply_condition(target, condition):
    if condition and condition not in target.conditions:
        target.conditions.append(condition)


def _remove_condition(target, condition):
    if condition in target.conditions:
        target.conditions.remove(condition)


def _tick_conditions(target, log):
    to_remove = []
    if "poisoned" in target.conditions:
        dmg = parse_dice("1d4")
        target.take_damage(dmg)
        log(f"  {target.name} takes {dmg} poison damage.")
    if "burning" in target.conditions:
        dmg = parse_dice("1d6")
        target.take_damage(dmg)
        log(f"  {target.name} takes {dmg} fire damage.")
    if "hexed" in target.conditions:
        dmg = parse_dice("1d6")
        target.take_damage(dmg)
        log(f"  {target.name} takes {dmg} necrotic damage.")
    if "stunned" in target.conditions:
        to_remove.append("stunned")
    if "dominated" in target.conditions:
        to_remove.append("dominated")
    if "fleeing" in target.conditions:
        to_remove.append("fleeing")
    for c in to_remove:
        _remove_condition(target, c)


# ── Feature resolver ───────────────────────────────────────────────────────────

def resolve_feature(feat, attacker, target, log):
    """Execute a feature effect. Returns (player_hp_change, damage_dealt)."""
    if not feat.is_available():
        log(f"  {feat.name} is not available.")
        return 0, 0

    feat.use()
    etype = feat.effect_type
    evalue = feat.effect_value

    if etype == "damage_bonus":
        dmg = parse_dice(evalue)
        multiplier = 2 if "crit" in getattr(attacker, "_combat_flags", []) else 1
        total_dmg = dmg * multiplier
        target.take_damage(total_dmg)
        log(f"  {feat.name}: dealt {total_dmg} extra damage.")
        return 0, total_dmg

    elif etype == "heal":
        amount = parse_dice(evalue) + attacker.level
        attacker.heal(amount)
        log(f"  {feat.name}: restored {amount} HP.")
        return amount, 0

    elif etype == "condition":
        if evalue == "free_flee":
            log(f"  {feat.name}: smoke cover - fleeing for free.")
            return 0, 0
        _apply_condition(target, evalue)
        log(f"  {feat.name}: {target.name} is now {evalue}.")
        return 0, 0

    elif etype == "shield":
        try:
            amount = int(evalue)
            attacker.temp_ac_bonus += amount
            log(f"  {feat.name}: +{amount} AC this combat.")
        except ValueError:
            log(f"  {feat.name}: activated.")
        return 0, 0

    elif etype == "aoe":
        dmg = parse_dice(evalue)
        target.take_damage(dmg)
        log(f"  {feat.name}: {dmg} AoE damage to {target.name}.")
        return 0, dmg

    elif etype == "extra_attack":
        raw, roll = attacker.attack_roll()
        if roll >= target.effective_ac() or raw == 20:
            dmg = attacker.damage_roll()
            target.take_damage(dmg)
            log(f"  {feat.name} extra attack: hit for {dmg}.")
            return 0, dmg
        else:
            log(f"  {feat.name} extra attack: missed.")
            return 0, 0

    elif etype == "utility":
        log(f"  {feat.name}: {feat.description}")
        return 0, 0

    return 0, 0


# ── Combat state ───────────────────────────────────────────────────────────────

class CombatState:
    def __init__(self, player, enemies):
        self.player = player
        self.enemies = list(enemies)
        self.log_lines = []        # accumulated message log
        self.round = 0
        self.result = None         # "victory" | "defeat" | "fled"
        self.pending_action = None # action dict from parser
        self.waiting_for_input = True
        self.phase = "player"      # "player" or "enemy"
        self.inspect_target = None
        self.defend_active = False
        self.dodge_active = False

    def active_enemies(self):
        return [e for e in self.enemies if e.is_alive()]

    def primary_target(self):
        alive = self.active_enemies()
        return alive[0] if alive else None

    def log(self, text, category=None):
        self.log_lines.append((text, category or "normal"))

    def is_over(self):
        return self.result is not None

    def all_dead(self):
        return not self.active_enemies()

    def start_round(self):
        self.round += 1
        self.defend_active = False
        self.dodge_active = False
        self.log(f"-- Round {self.round} --", "system")
        # Tick conditions on enemies
        for e in self.active_enemies():
            _tick_conditions(e, lambda t: self.log(t, "combat"))


# ── Process a single player action ────────────────────────────────────────────

def process_player_action(state: CombatState, action_dict: dict):
    """
    Consume the action dict (from parser.py) and advance combat state.
    Mutates state.log_lines, state.result, enemy/player HP.
    Then runs enemy turn if player survived.
    """
    from parser import skill_check, describe_result, combat_action_from_result

    player = state.player
    target = state.primary_target()

    if target is None:
        state.result = "victory"
        return

    # Build a minimal action dict if numeric was passed
    atype = action_dict.get("intent", "attack")

    # ---- numeric shortcuts ----
    if atype == "numeric":
        n = action_dict.get("numeric", 1)
        # Map numbers to quick intents
        numeric_map = {
            1: {"intent": "attack",     "stat": "STR", "dc": 10, "label": "Attack",    "aud_bonus": 1, "is_combat": True, "has_env": False, "item_name": None, "ability_name": None},
            2: {"intent": "use_item",   "stat": "INT", "dc": 8,  "label": "Use item",  "aud_bonus": 0, "is_combat": True, "has_env": False, "item_name": None, "ability_name": None},
            3: {"intent": "defend",     "stat": "CON", "dc": 10, "label": "Defend",    "aud_bonus": 0, "is_combat": True, "has_env": False, "item_name": None, "ability_name": None},
            4: {"intent": "flee",       "stat": "DEX", "dc": 13, "label": "Flee",      "aud_bonus": 0, "is_combat": True, "has_env": False, "item_name": None, "ability_name": None},
            5: {"intent": "inspect",    "stat": "INT", "dc": 10, "label": "Inspect",   "aud_bonus": 0, "is_combat": True, "has_env": False, "item_name": None, "ability_name": None},
        }
        for i in range(6, 6 + len(player.features)):
            feat = player.features[i - 6]
            numeric_map[i] = {
                "intent": "use_ability", "stat": "INT", "dc": 10,
                "label": feat.name, "aud_bonus": 1, "is_combat": True,
                "has_env": False, "item_name": None, "ability_name": feat.name,
            }
        action_dict = numeric_map.get(n, numeric_map[1])
        atype = action_dict["intent"]

    # Roll skill check
    result = skill_check(player, action_dict)
    for line in describe_result(result, context="combat"):
        state.log(line, "combat")

    effect = combat_action_from_result(result, action_dict)

    # ---- Handle effect types ----
    if effect["type"] == "damage" or effect["type"] == "miss":
        if effect["type"] == "miss":
            n = get_narrator()
            if result["fumble"]:
                state.log(f"  {n.say('critical_miss')}", "warn")
            else:
                state.log("  Miss.", "combat")
        else:
            # Weapon attack
            raw, roll = player.attack_roll()
            if roll >= target.effective_ac() or raw == 20:
                dmg = player.damage_roll()
                if raw == 20:
                    dmg *= 2
                    state.log(f"  {get_narrator().say('critical_hit')}", "syndicate")
                multiplier = effect.get("damage_multiplier", 1)
                dmg *= multiplier
                target.take_damage(dmg)
                state.log(f"  Hit! {dmg} damage to {target.name}.", "combat")
                if target.condition_on_hit:
                    _apply_condition(target, target.condition_on_hit)
                    state.log(f"  {target.name} is now {target.condition_on_hit}.", "warn")
            else:
                state.log(f"  Missed {target.name} (roll {roll} vs AC {target.effective_ac()}).", "combat")

    elif effect["type"] == "condition":
        _apply_condition(target, effect["condition"])
        state.log(f"  {target.name} is now {effect['condition']}.", "combat")

    elif effect["type"] == "disarm":
        state.log(f"  {target.name} is disarmed (attack penalty for 2 rounds).", "combat")
        _apply_condition(target, "disarmed")

    elif effect["type"] == "self_buff":
        if effect["self_effect"] == "defend":
            state.defend_active = True
            player.temp_ac_bonus += 2
            state.log("  Defending: +2 AC this round.", "system")
        elif effect["self_effect"] == "dodge":
            state.dodge_active = True
            state.log("  Dodging: enemy attacks at disadvantage.", "system")

    elif effect["type"] == "flee":
        n = get_narrator()
        state.log(f"  {n.say('flee')}", "syndicate")
        state.result = "fled"
        state.waiting_for_input = False
        return

    elif effect["type"] == "inspect":
        state.inspect_target = target
        state.log(f"  {target.name}: HP {target.hp}/{target.max_hp} | AC {target.effective_ac()}", "system")
        state.log(f"  Tags: {', '.join(target.tags) if target.tags else 'none'}", "system")
        # Player used their action on inspect, enemy still attacks
        _run_enemy_turn(state)
        state.waiting_for_input = True
        _check_victory(state)
        return

    elif effect["type"] == "ability":
        aname = action_dict.get("ability_name", "")
        feat = _find_feature(player, aname)
        if feat:
            resolve_feature(feat, player, target, lambda t: state.log(t, "combat"))
        else:
            state.log(f"  No ability found matching '{aname}'.", "warn")

    elif effect["type"] == "item":
        iname = action_dict.get("item_name", "")
        item = _find_consumable(player, iname)
        if item:
            result_str = player.use_consumable(item)
            player.remove_from_inventory(item)
            state.log(f"  Used {item.name}: {result_str}", "loot")
        else:
            state.log(f"  No usable item matching '{iname}'.", "warn")

    elif effect["type"] == "environment":
        dmg = effect.get("damage", 4)
        target.take_damage(dmg)
        state.log(f"  Environmental damage: {dmg} to {target.name}.", "combat")
        state.log(f"  {get_narrator().say('audience_up')}", "syndicate")
        player.add_audience(5)

    # Audience delta
    delta = effect.get("aud_delta", 0) + result.get("aud_delta", 0)
    if delta:
        player.add_audience(delta)

    # Reset defend bonus at end of turn
    if state.defend_active and effect["type"] != "self_buff":
        state.defend_active = False
        player.temp_ac_bonus = max(0, player.temp_ac_bonus - 2)

    # Check win
    _check_victory(state)
    if state.result:
        return

    # Enemy turn
    _run_enemy_turn(state)
    _check_victory(state)

    state.waiting_for_input = True


def _run_enemy_turn(state: CombatState):
    player = state.player
    for enemy in state.active_enemies():
        if not player.is_alive():
            break
        # Skip if enemy is stunned/dominated/fleeing
        if any(c in enemy.conditions for c in ("stunned", "dominated", "fleeing")):
            state.log(f"  {enemy.name} is {enemy.conditions[0]} and cannot act.", "combat")
            continue

        raw, roll = enemy.attack_roll()
        player_ac = player.effective_ac()
        if state.dodge_active:
            # Roll twice, take lower
            raw2, roll2 = enemy.attack_roll()
            if roll2 < roll:
                raw, roll = raw2, roll2

        if roll >= player_ac or raw == 20:
            dmg = enemy.damage_roll()
            if raw == 20:
                dmg *= 2
                state.log(f"  {enemy.name} crits! {dmg} damage!", "warn")
            else:
                state.log(f"  {enemy.name} hits for {dmg}.", "combat")
            if state.defend_active:
                dmg = max(1, dmg // 2)
                state.log(f"  Defending: damage reduced to {dmg}.", "system")
            player.take_damage(dmg)
        else:
            state.log(f"  {enemy.name} misses (roll {roll} vs AC {player_ac}).", "combat")

        # Tick player conditions
        _tick_conditions(player, lambda t: state.log(t, "warn"))


def _check_victory(state: CombatState):
    if not state.player.is_alive():
        state.result = "defeat"
        state.log(get_narrator().say("player_death"), "warn")
    elif state.all_dead():
        state.result = "victory"
        state.log(get_narrator().say("boss_death" if any(e.is_boss for e in state.enemies) else "loot_found"), "syndicate")


def _find_feature(player, name):
    name_lower = name.lower()
    for f in player.features:
        if f.name.lower() == name_lower or name_lower in f.name.lower():
            if f.is_available():
                return f
    return None


def _find_consumable(player, name):
    name_lower = name.lower()
    for item in player.inventory:
        from items import Consumable
        if isinstance(item, Consumable):
            if not name_lower or name_lower in item.name.lower():
                return item
    return None


# ── XP award helper ────────────────────────────────────────────────────────────

def award_combat_xp(player, enemies):
    total_xp = sum(e.xp for e in enemies)
    bonus = 1.1 if player.trinket and player.trinket.passive == "bonus_xp_10" else 1.0
    total_xp = int(total_xp * bonus)
    leveled = player.add_xp(total_xp)
    return total_xp


def award_combat_credits(player, enemies):
    total_cr = sum(e.cr_drop for e in enemies)
    player.credits += total_cr
    return total_cr
