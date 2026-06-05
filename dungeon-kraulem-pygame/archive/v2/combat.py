"""CRAWL PROTOCOL v2 - Combat engine."""
import random
from utils import d20, parse_dice, clamp
from narrator import get_narrator
from lang import tr


# ── Condition helpers ──────────────────────────────────────────────────────────

def _record_kill_method(player, target, kind: str):
    """Track how a kill was achieved (affinity, step 11 reads this)."""
    if not hasattr(player, "affinity"):
        return
    if not target.is_alive():
        player.affinity[kind] = player.affinity.get(kind, 0) + 1
        if hasattr(player, "kill_method_history"):
            player.kill_method_history.append(kind)
            # Cap history
            player.kill_method_history = player.kill_method_history[-50:]


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
    def __init__(self, player, enemies, room=None):
        self.player = player
        self.enemies = list(enemies)
        self.room = room  # Step 7: env/social/stealth resolution needs room context
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
        self.log(tr("v2_combat_round", n=self.round), "system")
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
                state.log("  " + tr("v2_combat_miss"), "combat")
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
                state.log("  " + tr("v2_combat_hit", dmg=dmg, target=target.name), "combat")
                if target.condition_on_hit:
                    _apply_condition(target, target.condition_on_hit)
                    state.log("  " + tr("v2_combat_target_cond", target=target.name, cond=target.condition_on_hit), "warn")
                # Affinity: melee/ranged based on weapon stat
                kind = "ranged" if (player.weapon and player.weapon.stat == "DEX") else "melee"
                _record_kill_method(player, target, kind)
            else:
                state.log("  " + tr("v2_combat_miss_target", target=target.name, roll=roll, ac=target.effective_ac()), "combat")

    elif effect["type"] == "condition":
        _apply_condition(target, effect["condition"])
        state.log("  " + tr("v2_combat_target_cond", target=target.name, cond=effect['condition']), "combat")

    elif effect["type"] == "disarm":
        state.log("  " + tr("v2_combat_disarmed", target=target.name), "combat")
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
        state.log("  " + tr("v2_combat_inspect", target=target.name, hp=target.hp, max=target.max_hp, ac=target.effective_ac()), "system")
        state.log("  " + tr("v2_combat_inspect_tags", tags=", ".join(target.tags) if target.tags else "—"), "system")
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
            state.log("  " + tr("v2_combat_no_match_ability", name=aname or ""), "warn")

    elif effect["type"] == "item":
        iname = action_dict.get("item_name", "")
        item = _find_consumable(player, iname)
        if item:
            result_str = player.use_consumable(item)
            player.remove_from_inventory(item)
            state.log("  " + tr("v2_combat_used_item", name=item.name, result=result_str), "loot")
        else:
            state.log("  " + tr("v2_combat_no_match_item", name=iname or ""), "warn")

    elif effect["type"] == "environment":
        dmg = effect.get("damage", 4)
        target.take_damage(dmg)
        state.log("  " + tr("v2_combat_env_dmg", dmg=dmg, target=target.name), "combat")
        state.log(f"  {get_narrator().say('audience_up')}", "syndicate")
        player.add_audience(5)

    elif effect["type"] == "env_use":
        # Single env object used as a weapon/condition source.
        from utils import parse_dice
        room = state.room
        ekey = action_dict.get("env_target_key")
        obj = next((o for o in (room.env_objects if room else []) if o.key == ekey and not o.consumed), None)
        if obj is None or obj.combat_effect is None:
            state.log("  Nothing usable there.", "warn")
        else:
            ce = obj.combat_effect
            dmg = parse_dice(ce.get("damage", "1d4"))
            target.take_damage(dmg)
            if ce.get("condition"):
                _apply_condition(target, ce["condition"])
            obj.consumed = True
            state.log(f"  {obj.name} -> {dmg} dmg to {target.name}.", "combat")
            player.add_audience(3)
            _record_kill_method(player, target, "env")

    elif effect["type"] == "env_combo":
        from utils import parse_dice
        room = state.room
        combo = action_dict.get("env_combo")
        if combo and room is not None:
            a_key, b_key, _label = combo
            objs = [o for o in room.env_objects if o.key in (a_key, b_key) and not o.consumed]
            if len(objs) >= 2:
                from environment import COMBO_TABLE
                tag_set = set(objs[0].combine_tags) | set(objs[1].combine_tags)
                eff = None
                for cset, e in COMBO_TABLE.items():
                    if cset.issubset(tag_set):
                        eff = e; break
                if eff:
                    dmg = parse_dice(eff.get("damage", "2d6"))
                    affected = state.active_enemies() if eff.get("aoe") else [target]
                    for e in affected:
                        e.take_damage(dmg)
                        if eff.get("condition"):
                            _apply_condition(e, eff["condition"])
                    objs[0].consumed = True
                    objs[1].consumed = True
                    state.log(f"  COMBO! {dmg} dmg ({'AoE' if eff.get('aoe') else 'single'}).", "syndicate")
                    player.add_audience(8)
                    for e in affected:
                        _record_kill_method(player, e, "env")
                else:
                    state.log("  No combo possible.", "warn")
            else:
                state.log("  Objects no longer available.", "warn")
        else:
            state.log("  No combo target.", "warn")

    elif effect["type"] == "strip":
        room = state.room
        ekey = action_dict.get("env_target_key")
        obj = next((o for o in (room.env_objects if room else []) if o.key == ekey and not o.stripped), None)
        if obj is None or not obj.strip_yield:
            state.log("  Nothing to strip.", "warn")
        else:
            for mat, qty in obj.strip_yield.items():
                player.materials[mat] = player.materials.get(mat, 0) + qty
            obj.stripped = True
            yields = ", ".join(f"{q}x {m}" for m, q in obj.strip_yield.items())
            state.log(f"  Stripped {obj.name}: {yields}", "loot")

    elif effect["type"] == "clarify":
        state.log("  ?  No such object here.", "warn")
        # Refund the turn: enemy does not attack.
        return

    elif effect["type"] == "social":
        # Talk / negotiate / threaten. Need result.success against enemy.social_dc.
        if not target.negotiable:
            state.log(f"  {target.name} cannot be reasoned with.", "warn")
        else:
            from utils import d20
            cha_mod = player.stat_mod("CHA")
            roll = d20() + cha_mod
            ok = roll >= target.social_dc
            if ok:
                # Enemy yields. Reduced rewards, no combat resolution.
                state.log(f"  {target.name} stands down. (CHA {roll} vs DC {target.social_dc})", "system")
                target.hp = 0   # remove from field — but flag as non-violent so XP scales
                target._resolved_socially = True
                _record_kill_method(player, target, "social")
                player.add_audience(2)
            else:
                state.log(f"  Failed to negotiate ({roll} vs DC {target.social_dc}). They attack.", "combat")

    elif effect["type"] == "stealth":
        from utils import d20
        dex_mod = player.stat_mod("DEX")
        roll = d20() + dex_mod
        ok = roll >= target.stealth_dc
        if ok:
            # Sneak attack: high damage from initial hit; eliminates a single target.
            from utils import parse_dice
            dmg = parse_dice("3d6") + dex_mod
            target.take_damage(dmg)
            state.log(f"  Sneak attack: {dmg} dmg ({roll} vs DC {target.stealth_dc}).", "combat")
            player.add_audience(2)
            _record_kill_method(player, target, "stealth")
        else:
            state.log(f"  Spotted. ({roll} vs DC {target.stealth_dc})", "warn")

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
            state.log("  " + tr("v2_combat_condition_skip", name=enemy.name, cond=enemy.conditions[0]), "combat")
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
                state.log("  " + tr("v2_combat_enemy_crits", enemy=enemy.name, dmg=dmg), "warn")
            else:
                state.log("  " + tr("v2_combat_enemy_hits", enemy=enemy.name, dmg=dmg), "combat")
            if state.defend_active:
                dmg = max(1, dmg // 2)
                state.log("  " + tr("v2_combat_defend_reduce", dmg=dmg), "system")
            player.take_damage(dmg)
        else:
            state.log("  " + tr("v2_combat_enemy_misses", enemy=enemy.name, roll=roll, ac=player_ac), "combat")

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
    if not name:
        return None
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
