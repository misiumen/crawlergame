"""Combat-resolution rules — extracted from game.py (Phase 0.5 decoupling).

Originally methods on the Game class, tangled into the orchestrator but
pygame-free. Pulled into a mixin verbatim so Game inherits them unchanged
(every self.* call still resolves). This is the prep that turns the GDScript
port into a per-module translation. See docs/GODOT_PORT_PLAN.md Phase 0.5.
"""
from __future__ import annotations
from ..config import (LOG_NORMAL, LOG_SYSTEM, LOG_WARN, LOG_SUCCESS,
                      LOG_SYNDIC, LOG_DANGER)
from ..ui.lang import t
from ..ui import audio
from .validation import validate


def _roll_dice_spec(spec: str, rng) -> int:
    """Roll '1d6+2' / '2d4' / '3' via engine.dice.roll_spec (moved with the
    combat damage path that is its only caller)."""
    from .dice import roll_spec
    return roll_spec(spec, rng)


class CombatRulesMixin:
    """Combat resolution mixed into Game. No own state; operates on self.*."""

    def _tick_systemic_on(self, ent) -> None:
        """P29.63 — tyknij efekty systemowe (DoT + żywotność) na encji
        i pokaż widoczne skutki. DoT może dobić → trup."""
        from . import systemic as _sys
        if ent is None:
            return
        info = _sys.tick(ent)
        if info is None:
            return
        died = False
        if info.damage > 0:
            self.log(f"{ent.display_name()} — {info.flavor}: "
                     f"-{info.damage} ({info.hp}/{info.max_hp}).", LOG_WARN)
            if info.hp <= 0 and getattr(ent, "max_hp", 0) > 0:
                victim = ent.display_name()
                try:
                    from . import corpses as _cp
                    _cp.transform_to_corpse(self.world, ent,
                                            killer=self.world.character)
                    died = True
                except Exception:
                    pass
                if died:
                    self.log(f"„{victim}” dogorywa od „{info.status}”.",
                             LOG_SUCCESS)
        if info.expired and not died and ent.is_alive():
            self.log(f"  efekt „{info.status}” mija.", LOG_NORMAL)
    def _run_enemy_turn(self, cs) -> None:
        from . import combat as _cmb
        from . import enemy_ai as _ai
        from . import time_system as ts
        from . import systemic as _sys
        import random as _r_sys
        room = self.world.current_floor.current_room()
        ch = self.world.character
        if room is None:
            return
        cs.side = "enemies"
        # P30 — morale: anyone who fell since the last enemy turn (player
        # kills during their phase, DoT, crossfire) rattles the survivors.
        self._combat_morale_check_deaths(cs)
        for eid in list(cs.participants):
            ent = self.world.get(eid)
            if ent is None or not ent.is_alive():
                continue
            # P30 — read the telegraphed intent. If the enemy was winding
            # up a special and is now stunned/prone (player interrupt) or
            # systemically paralysed, the special fizzles.
            intent = (cs.enemy_intents or {}).get(eid) or {}
            was_charging = (intent.get("category") == _ai.CAT_SPECIAL)
            blocked = (_cmb.has_status(ent, _cmb.STATUS_STUNNED)
                       or _cmb.has_status(ent, _cmb.STATUS_PRONE))
            # P29.63 — paraliż systemowy (porażony/zamrożony) może
            # zabrać wrogowi turę. Walka przestaje być wymianą ciosów.
            if _sys.roll_stun(ent, _r_sys):
                if was_charging:
                    self.log(f"{ent.display_name()} — spazm przerywa "
                             f"szykowany cios!", LOG_SUCCESS)
                else:
                    self.log(f"{ent.display_name()} — spazm mięśni, "
                             f"traci turę.", LOG_SUCCESS)
                _ai.tick_cooldowns(ent)
                continue
            if blocked and was_charging:
                self.log(f"{ent.display_name()} szykował cios, ale "
                         f"powalony — atak się rozsypuje!", LOG_SUCCESS)
            action = _ai.realize_intent(self.world, cs, ent)
            self._apply_enemy_action(cs, ent, action)
            _ai.tick_cooldowns(ent)
            if not ch.is_alive():
                break
        # Catch deaths that happened during this enemy turn (crossfire).
        self._combat_morale_check_deaths(cs)
        # Tick statuses on all participants (including player via clocks on character)
        for eid in list(cs.participants):
            ent = self.world.get(eid)
            _cmb.tick_statuses(ent)
            self._tick_systemic_on(ent)          # P29.63 — DoT + żywotność
        _cmb.tick_statuses(ch)
        # P29.63 — ogień pełznie po pokoju (reaktywne otoczenie).
        for line in _sys.spread_fire(self.world, room):
            self.log(line, LOG_WARN)
        # Reset per-round player buffs.
        cs.player_defend = 0
        cs.player_dodge = False
        cs.round += 1
        cs.side = "player"
        ts.advance(self.world, 1)
        if not ch.is_alive():
            self._check_player_dead("combat_round_end",
                                    "na koniec rundy walki")
            return
        # Re-check end: if all hostiles dead/fled/disabled, end combat.
        hostiles = _cmb.alive_hostiles_in(room)
        if not hostiles:
            _cmb.end_combat(room, self.world, outcome="all_down")
            self.log(t("feedback_combat_won",
                       fallback="Wszyscy wrogowie pokonani."), LOG_SUCCESS)
            return
        # P30 — telegraph the next round's intentions for the player phase.
        try:
            _ai.plan_intents(self.world, cs)
        except Exception:
            pass
    def _combat_morale_check_deaths(self, cs) -> None:
        """P30 — detect participants who died since the last check and shake
        the survivors' morale. Uses a transient snapshot on the combat state
        (recomputed fresh after load, so a reloaded fight never double-dips)."""
        from . import enemy_ai as _ai
        cur_alive = {eid for eid in (cs.participants or [])
                     if (self.world.get(eid) is not None
                         and self.world.get(eid).is_alive())}
        prev = getattr(cs, "_alive_snapshot", None)
        if prev is None:
            try:
                cs._alive_snapshot = set(cur_alive)
            except Exception:
                pass
            return
        for dead in (prev - cur_alive):
            for ent2, mor in _ai.note_ally_down(self.world, cs, dead):
                if mor <= 30:
                    self.log(f"{ent2.display_name()} traci animusz — "
                             f"towarzysz padł.", LOG_SUCCESS)
        try:
            cs._alive_snapshot = set(cur_alive)
        except Exception:
            pass
    def _apply_enemy_action(self, cs, ent, action) -> None:
        from . import combat as _cmb
        ch = self.world.character
        room = self.world.current_floor.current_room()
        name = ent.display_name()
        if action.kind == "wait":
            self.log(f"{name}: {action.note or 'czeka'}.", LOG_NORMAL)
            return
        if action.kind == "approach":
            cs.bands[ent.entity_id] = _cmb.BAND_ENGAGED
            self.log(f"{name} zbliża się ({action.note or 'naciera'}).", LOG_WARN)
            return
        if action.kind == "back_off":
            cs.bands[ent.entity_id] = _cmb.BAND_AT_RANGE
            self.log(f"{name} cofa się, próbując utrzymać dystans.", LOG_NORMAL)
            return
        if action.kind == "flee":
            self.log(f"{name} ucieka z pola walki.", LOG_SUCCESS)
            ent.state = ent.state or {}
            ent.state["fled"] = True
            ent.hp = 0     # treated as no-longer-in-fight
            return
        if action.kind == "defend":
            # P30 — defensive stance: enemy braces, harder to hit this round.
            _cmb.add_status(ent, _cmb.STATUS_GUARDING, 1)
            self.log(f"{name} unosi gardę i czeka na okazję.", LOG_NORMAL)
            return
        if action.kind in ("attack", "special"):
            is_special = (action.kind == "special")
            if is_special:
                from . import enemy_ai as _ai
                spec_label = action.label_pl or "potężny cios"
                self.log(f"⚠ {name}: {action.note or spec_label}!",
                         LOG_DANGER)
                _ai.commit_special_used(ent)
            dmg = int(action.damage or 1)
            # COMBAT-1 Slice C — a STAGGERED enemy (you rocked it last turn)
            # swings weaker: its outgoing damage is cut by a third. Pays off
            # the heavy hit beyond raw HP, and reads in the symmetric log.
            if _cmb.has_status(ent, _cmb.STATUS_STAGGERED):
                dmg = max(1, (dmg * 2) // 3)
                self.log(f"{name} wciąż zachwiany — cios słabszy.",
                         LOG_NORMAL)
            e_crit = False
            # P27.6 (P27-UX-7): symmetric enemy roll log. Player only
            # saw final damage — never knew WHY they got hit or what
            # AC the enemy needed. Now we show the enemy's d20 + atk
            # vs player AC, so the math is transparent.
            try:
                import random as _r_enemy
                from .dice_labels import stat_pl as _spl_e
                e_raw = _r_enemy.randint(1, 20)
                e_atk = int(getattr(ent, "attack_bonus", 0) or 0)
                # P29.63 — spowolnienie systemowe (zmrożony/spowolniony)
                # psuje celność wroga.
                from . import systemic as _sys_slow
                if _sys_slow.is_slowed(ent):
                    e_atk -= 2
                player_ac = ch.effective_ac(self.world)
                e_total = e_raw + e_atk
                e_crit = (e_raw == 20)
                e_outcome = ("KRYT" if e_raw == 20 else
                             ("trafienie" if e_total >= player_ac else
                              ("pudło" if e_raw > 1 else "fuks")))
                self.log(f"  [atak wroga] {ent.display_name()}: "
                         f"d20({e_raw}) + atak({e_atk:+d}) = "
                         f"{e_total} vs twoje AC {player_ac} → {e_outcome}",
                         LOG_SYSTEM)
                # Honor the roll: if enemy "missed" per the symmetric
                # math, suppress damage (was always landing before; now
                # there's a real miss chance shown to player).
                if e_total < player_ac and e_raw != 20:
                    self.log(f"{name} chybia.", LOG_NORMAL)
                    return
            except Exception:
                pass
            # P29.65 — kryt wroga PODWAJA obrażenia (dotąd log mówił „KRYT", a
            # dmg był ten sam). Liczone przed mitygacją (defend/dodge/tarcza).
            if e_crit:
                dmg = int(dmg) * 2
            # P26b: faction-aware retarget. If the AI picked a rival
            # combat participant, damage that rival instead of the
            # player. Crossfire is the audience-pleasing scenario the
            # player can engineer by luring factions together.
            rival_id = getattr(action, "target_id", None)
            if rival_id is not None:
                rival = self.world.get(rival_id)
                if rival is not None and rival.is_alive():
                    rival.hp = max(0, rival.hp - dmg)
                    self.log(t("feedback_crossfire",
                               fallback=f"{name} atakuje rywala "
                                        f"„{rival.display_name()}” na {dmg} HP "
                                        f"(zostało {rival.hp}/{rival.max_hp}).",
                               attacker=name,
                               rival=rival.display_name(),
                               dmg=dmg,
                               hp=rival.hp, max_hp=rival.max_hp),
                             LOG_NORMAL)
                    # Crossfire is good TV — audience bump.
                    try:
                        from . import sponsors as _sp
                        _sp.note_player_tag(self.world, "crossfire", weight=2)
                    except Exception:
                        pass
                    # If the rival died, transform to corpse.
                    if rival.hp <= 0:
                        self.log(f"„{rival.display_name()}” pada.", LOG_SUCCESS)
                        try:
                            from . import corpses as _cp
                            _cp.transform_to_corpse(self.world, rival, killer=ent)
                        except Exception:
                            pass
                    return
            # Player target path (default / fallback).
            # P29.55 — precog_dodge (void): pierwszy hit/piętro
            # automatycznie missuje. Consumed one-shot.
            try:
                from . import species_effects as _sp_fx
                if _sp_fx.precog_dodge_consume(self.world):
                    self.log(f"Przewidujesz cios. {name} chybia w "
                             f"pustkę.", LOG_SUCCESS)
                    return
            except Exception:
                pass
            if _cmb.has_status(ch, _cmb.STATUS_BEHIND_COVER) and \
                    cs.bands.get(ent.entity_id) == _cmb.BAND_AT_RANGE:
                dmg = max(0, dmg - 2)
            if cs.player_dodge:
                # COMBAT-1 Slice B — reading the tell pays off. A dodge timed
                # against a TELEGRAPHED SPECIAL (the big wind-up the HUD warned
                # you about) fully negates it on success; an ordinary attack is
                # only halved. Dodge always consumes (reset at end of round).
                import random as _r
                if _r.randint(1, 20) + ch.stat_mod("DEX") >= 12:
                    if is_special:
                        dmg = 0
                        self.log(f"Czytasz zamach — robisz unik i {name} "
                                 f"trafia w próżnię. Specjał spalony!",
                                 LOG_SUCCESS)
                    else:
                        dmg = max(0, dmg // 2)
                        self.log(f"Unikasz większej części ataku od {name}.",
                                 LOG_NORMAL)
                elif is_special:
                    self.log(f"Próbujesz uniku, ale {name} cię dosięga.",
                             LOG_WARN)
            # Prompt 23: shield in offhand reduces damage by AC bonus.
            shield_bonus = ch.offhand_ac_bonus(self.world)
            if shield_bonus > 0:
                dmg = max(0, dmg - shield_bonus)
            # Slice B — defending against a telegraphed special halves the
            # remaining hit (on top of the flat block) before the flat
            # subtraction, so bracing for the big one is meaningfully better
            # than bracing for a jab.
            if is_special and cs.player_defend > 0:
                dmg = max(0, dmg // 2)
                self.log(f"Zwierasz gardę pod specjał {name} — cios "
                         f"traci impet.", LOG_NORMAL)
            dmg = max(0, dmg - cs.player_defend)
            if dmg <= 0:
                self.log(f"{name} atakuje, ale nie robi krzywdy.", LOG_NORMAL)
                return
            ch.take_damage(dmg)
            # P29.55 — glassblood (bleeds_easy): 20% szansy na bleed
            # gdy gracz dostaje HP loss. Doliczamy STATUS_BLEEDING
            # tylko jeśli nie ma już bleed-immune.
            try:
                import random as _r_bleed
                from . import species_effects as _sp_fx
                if _sp_fx.bleed_on_hit_check(ch, _r_bleed):
                    if not _sp_fx.status_blocked(ch, "bleeding"):
                        _cmb.add_status(ch, _cmb.STATUS_BLEEDING, 3)
                        self.log("Glassblood ranny — krwawisz.",
                                 LOG_WARN)
            except Exception:
                pass
            # P34-SFX-1 (P27.5): player_hit hook (always); player_crit
            # variant when ≥50% max HP in one blow.
            try:
                if dmg >= max(1, ch.max_hp // 2):
                    audio.play_sfx("player_crit_hit")
                else:
                    audio.play_sfx("player_hit")
            except Exception:
                pass
            self.log(f"{name} trafia cię na {dmg} HP "
                     f"(zostało {ch.hp}/{ch.max_hp}).", LOG_DANGER)
            # P29.65 / P2 game-juice: czerwona liczba + błysk + shake + kick.
            # Player chip recoils LEFT when hit. Shake values in ms so they
            # actually persist a few frames (old 3-7 decayed instantly).
            self._spawn_combat_fx("player", f"-{dmg}", (255, 90, 90),
                                  big=e_crit,
                                  shake=(200.0 if e_crit else 110.0),
                                  kick=(-12 if e_crit else -7))
            # Heavy hits cause bleeding sometimes.
            if dmg >= 5:
                _cmb.add_status(ch, _cmb.STATUS_WOUNDED, 4)
            # P30 — landing a blow buoys the attacker's morale; charged
            # specials also inflict their telegraphed status on the player.
            try:
                from . import enemy_ai as _ai
                _ai.note_hit_player(ent, dmg, ch.max_hp)
                if is_special and action.target_status:
                    _cmb.add_status(ch, action.target_status,
                                    int(action.target_status_duration or 1))
                    self.log(f"  cios pozostawia efekt: "
                             f"{_cmb.status_label(action.target_status, 'pl')}.",
                             LOG_WARN)
            except Exception:
                pass
            # P29.8 — check death immediately after the hit lands, not
            # only at end-of-round. Without this, multiple enemies in
            # one round can each land a "killing" blow before the
            # state actually flips, which messes with the log order
            # and the run-summary "cause of death".
            if self._check_player_dead(
                    f"combat:{ent.key}",
                    f"od ciosu „{ent.display_name()}”"):
                return

    # ── Player combat actions ──────────────────────────────────────────────
    def _combat_attack(self, intent, cs, mode: str = "normal"):
        from . import combat as _cmb
        from .utils_compat import roll_d20
        import random as _r
        room = self.world.current_floor.current_room()
        ch = self.world.character
        # Pick the first engaged enemy. Player can specify a name target via
        # intent.targets; we honor that if it resolves to a participant.
        target = None
        if intent.targets:
            from .validation import _resolve_entities
            candidates = _resolve_entities(room, intent.targets[0])
            if candidates and candidates[0].entity_id in cs.participants:
                target = candidates[0]
        if target is None:
            engaged = [self.world.get(eid) for eid in cs.participants
                       if cs.bands.get(eid) == _cmb.BAND_ENGAGED]
            engaged = [e for e in engaged if e and e.is_alive()]
            target = engaged[0] if engaged else \
                next((self.world.get(eid) for eid in cs.participants
                      if self.world.get(eid) and self.world.get(eid).is_alive()),
                     None)
        if target is None:
            self.log(t("feedback_combat_no_target",
                       fallback="Nie widzisz w kim uderzyć."), LOG_WARN)
            return
        band = cs.bands.get(target.entity_id, _cmb.BAND_ENGAGED)
        if band == _cmb.BAND_AT_RANGE:
            self.log(t("feedback_combat_out_of_range",
                       fallback=f"„{target.display_name()}” jest poza zasięgiem zwarcia. "
                                f"Zbliż się albo użyj czegoś z dystansu.",
                       name=target.display_name()), LOG_WARN)
            self._combat_after_player_action(cs)
            return
        raw = roll_d20()
        mod = ch.stat_mod("STR")
        to_hit_bonus = 0
        damage_bonus = 0
        defense_change = 0
        noise = 3
        # P29.21 — consume the show-director dramatic_zoom flag if
        # set. One-shot +1 to-hit. Flag lives on character.flags so
        # it survives save/load.
        if (ch.flags or {}).get("dramatic_zoom_attack"):
            to_hit_bonus += 1
            try:
                ch.flags["dramatic_zoom_attack"] = 0
            except Exception:
                pass
        # P29.14 — masterwork / good / flawed weapon quality + permanent
        # enhancement bonuses (grip tape, balance weight). Read from the
        # wielded main hand. Quality table:
        #   masterwork: +1 hit, +1 dmg
        #   good:       +0 hit, +1 dmg
        #   normal:     0 / 0
        #   flawed:     -1 hit, 0 dmg
        # Enhancements stack on top:
        #   attack_bonus_perm (grip tape)
        #   damage_bonus_perm (balance weight)
        try:
            from ..content import crafting as _cr
            _w = self.world.get(ch.wielded_main_id) if ch.wielded_main_id else None
            if _w is not None and _w.state:
                _q = _w.state.get("quality", "normal")
                _qb = _cr.quality_bonus_for_weapon(_q)
                to_hit_bonus += int(_qb.get("attack_bonus", 0))
                damage_bonus += int(_qb.get("damage_bonus", 0))
                to_hit_bonus += int(_w.state.get("attack_bonus_perm", 0))
                damage_bonus += int(_w.state.get("damage_bonus_perm", 0))
                # P29.14 — silent enhancement reduces attack noise.
                if "silent" in (_w.tags or []):
                    noise = max(1, noise - 2)
                # P29.29 — surface masterwork / good quality + perm
                # enhancements once per combat, so the player can
                # SEE that the +1s are working. The dice-roll log
                # line already shows the resulting bonus number, but
                # players can't tell which input contributed.
                if _q in ("masterwork", "good") or \
                   int(_w.state.get("attack_bonus_perm", 0)) or \
                   int(_w.state.get("damage_bonus_perm", 0)):
                    qlabel = _cr.quality_label_pl(_q)
                    parts = []
                    if qlabel:
                        parts.append(qlabel)
                    if int(_w.state.get("attack_bonus_perm", 0)):
                        parts.append(f"+{_w.state['attack_bonus_perm']} trafienie")
                    if int(_w.state.get("damage_bonus_perm", 0)):
                        parts.append(f"+{_w.state['damage_bonus_perm']} obrażenia")
                    if parts:
                        cs_state = getattr(cs, "state", None)
                        if cs_state is None:
                            try:
                                cs.state = {}
                                cs_state = cs.state
                            except Exception:
                                cs_state = None
                        if cs_state is not None and not cs_state.get(
                                "logged_weapon_quality"):
                            self.log(
                                f"„{_w.display_name()}” — "
                                f"{' · '.join(parts)}.",
                                LOG_SYSTEM)
                            cs_state["logged_weapon_quality"] = True
        except Exception:
            pass
        if mode == "careful":
            to_hit_bonus = 2
            damage_bonus = -1
            defense_change = 1
            noise = 2
        elif mode == "heavy":
            to_hit_bonus = -2
            damage_bonus = _r.randint(1,4)
            defense_change = -2
            noise = 5
        # P27.7 — class passive bonuses.
        try:
            from ..systems import class_features as _cf
            # Unarmed bruisers / demolitionists get extra damage.
            if ch.wielded_main_id is None:
                damage_bonus += _cf.passive_bonus(ch, "unarmed_dmg")
            # Buff flag set by the bruiser active.
            if ch.flags.pop("class_buff_next_attack_x2", False):
                damage_bonus += 10
        except Exception:
            pass
        dc = max(6, getattr(target, "ac", 10))
        # P30 — enemy defensive stance raises the bar to land a clean hit.
        if _cmb.has_status(target, _cmb.STATUS_GUARDING):  dc += 3
        total = raw + mod + to_hit_bonus
        # Status modifiers
        if _cmb.has_status(target, _cmb.STATUS_PRONE):     total += 2
        if _cmb.has_status(target, _cmb.STATUS_BLINDED):   total += 3
        if _cmb.has_status(target, _cmb.STATUS_STUNNED):   total += 3
        if _cmb.has_status(ch, _cmb.STATUS_BLINDED):       total -= 3
        # Prompt 21: status interactions get real teeth.
        if _cmb.has_status(target, _cmb.STATUS_CHILLED):   total += 2  # slow
        if _cmb.has_status(target, _cmb.STATUS_CORRODED):  total += 1  # AC -1
        if _cmb.has_status(ch, _cmb.STATUS_AFRAID):        total -= 2
        # Prompt 26a — maim modifiers.
        if _cmb.has_status(target, _cmb.STATUS_SLOWED):    total += 2  # easier to hit
        if _cmb.has_status(target, _cmb.STATUS_DISARMED):  total += 1  # off-balance
        if _cmb.has_status(ch, _cmb.STATUS_SLOWED):        total -= 2
        if _cmb.has_status(ch, _cmb.STATUS_DISARMED):
            # Player's arm is broken — main attacks are massively penalized.
            total -= 3
            damage_bonus -= 1
        # Prompt 21: prone+stunned compound auto-hit (was: just +5).
        if (_cmb.has_status(target, _cmb.STATUS_PRONE) and
                _cmb.has_status(target, _cmb.STATUS_STUNNED)):
            total += 5
        # Prompt 19 — companion advantage: +2 to-hit on the next player
        # attack after `użyj zwierzęcia jako wabika` fires in combat.
        # Consumed on use; one bonus per encounter.
        if getattr(cs, "companion_advantage_pending", False):
            total += 2
            cs.companion_advantage_pending = False
            self.log(t("companion_advantage_consumed",
                       fallback="(Towarzysz odwraca uwagę: +2 do trafienia.)"),
                     LOG_SYSTEM)
        # Prompt 26a — body-zone targeting. Reads the selected zone for
        # this target (defaults to "torso"). Applies to-hit modifier and
        # damage multiplier from the body plan. Already-broken zones get
        # a +1 to-hit because the wound makes them easier to hit again.
        from ..content.data import body_plans as _bp
        _bp.init_body_parts(target)
        plan = _bp.plan_for_entity(target)
        zone_key = (cs.targeted_zone_by_eid or {}).get(target.entity_id)
        if not zone_key or zone_key not in plan:
            # Default to torso if available; else the first zone.
            zone_key = "torso" if "torso" in plan else next(iter(plan.keys()))
        zone_props = plan.get(zone_key, {})
        zone_to_hit = int(zone_props.get("to_hit_mod", 0))
        zone_dmg_mul = float(zone_props.get("damage_mul", 1.0))
        total += zone_to_hit
        zone_part = target.body_parts.get(zone_key) or {}
        if zone_part.get("broken"):
            total += 1   # weakened zone, easier follow-up
        # P29.53m — graduated penalties from player's own body damage.
        # Damaged arm: −1 dmg. Crippled arm: −2 dmg, −1 to-hit. Damaged
        # head: −1 to-hit. Doesn't double-dip with STATUS_DISARMED
        # (broken parts) — that's handled separately above.
        player_body_mods = _bp.body_combat_mods(ch)
        total -= int(player_body_mods.get("attack_to_hit_delta", 0))
        damage_bonus -= int(player_body_mods.get("attack_dmg_delta", 0))
        # P29.53p — audience-as-lever: gorąca widownia "podkręca" gracza
        # (+1 / +2 to-hit), zimna sprawia że gracz traci flow (−1).
        # Małe wartości — bonusy nie zastąpią normalnej taktyki, tylko
        # nagradzają utrzymywanie spektaklu.
        try:
            from . import audience as _aud
            aud_mods = _aud.combat_mods_for_world(self.world)
            total += int(aud_mods.get("to_hit", 0))
        except Exception:
            pass
        # P29.55 — species: sun_sensitive penalty w jasnym pokoju
        # (safehouse / studio). Half_dead: −2 to-hit gdy w bright.
        try:
            from . import species_effects as _sp_fx
            room_for_species = (self.world.current_floor.current_room()
                                if self.world.current_floor else None)
            total += int(_sp_fx.to_hit_modifier(
                ch, room=room_for_species))
        except Exception:
            pass
        crit = (raw == 20)
        # Prompt 21: shocked players fumble on 1-2 instead of just 1.
        shocked_fumble_floor = 2 if _cmb.has_status(ch, _cmb.STATUS_SHOCKED) else 1
        fumble = (raw <= shocked_fumble_floor)
        hit = (not fumble) and (crit or total >= dc)
        mode_label = {"normal":"atak","careful":"ostrożny atak","heavy":"ryzykowny atak"}[mode]
        outcome_pl = ("KRYT" if crit else
                      ("trafienie" if hit else
                       ("pudło" if not fumble else "fuks")))
        from .dice_labels import stat_pl as _spl
        bonus_str = f" + bonus({to_hit_bonus:+d})" if to_hit_bonus else ""
        # Combat to-hit rolls vs AC (not TT) — AC is a target stat, not a
        # difficulty check, so it keeps its name. P26a: append the zone
        # label so the player sees WHICH part they swung at.
        zone_label_pl = zone_props.get("label_pl", zone_key) if zone_props else ""
        zone_str = f" → {zone_label_pl}" if zone_label_pl else ""
        zone_mod_str = (f" zona({zone_to_hit:+d})" if zone_to_hit else "")
        self.log(f"  [{mode_label}] d20({raw}) + {_spl('STR')}({mod:+d})"
                 f"{bonus_str}{zone_mod_str} = {total} vs AC {dc} → "
                 f"{outcome_pl}{zone_str}",
                 LOG_SYSTEM)
        # P27 — SFX hooks (silent until assets/sfx/* drops).
        try:
            if crit:        audio.play_sfx("hit_crit")
            elif hit:       audio.play_sfx("hit_landed")
            elif fumble:    audio.play_sfx("attack_fumble")
            else:           audio.play_sfx("attack_miss")
        except Exception:
            pass
        if hit:
            # Prompt 23: damage comes from the wielded main weapon
            # (damage_dice + damage_type). Unarmed default 1d6+2.
            # Coating, if present, overrides damage_type for this hit
            # and decrements. Routes through damage.apply_damage so
            # resistance/vulnerability/status-on-hit work uniformly.
            from . import damage as _dmg
            weapon = self.world.get(ch.wielded_main_id) if ch.wielded_main_id else None
            if weapon is not None:
                dmg_dice = weapon.damage_dice or "1d6+2"
                dmg_type = weapon.damage_type or "physical"
                weapon_name = weapon.display_name()
            else:
                # P29.65 fixed-dice: pięść jest ŚCIŚLE najsłabszą „bronią"
                # (1d4). Wcześniej hardkod 2d6+8 (~15) sprawiał, że gołe ręce
                # biły mocniej niż realna broń (Bug #19) — bo kości broni i tak
                # nie trafiały na encję. Teraz broń tnie swoją kością, a pięść
                # to ostateczność.
                dmg_dice = "1d4"
                dmg_type = "physical"
                weapon_name = "pięść"
            # Coating override.
            coating_status_applied = None
            coating = (weapon.state or {}).get("coating") if weapon else None
            if coating and coating.get("hits_remaining", 0) > 0:
                dmg_type = coating.get("damage_type", dmg_type)
            # Roll dice.
            base = _roll_dice_spec(dmg_dice, _r)
            dmg = base + mod + damage_bonus
            if crit:
                dmg *= 2
                # P29.55 — crit_amplifier trait (chimera): krytyki ×1.5
                # NA TOP normalnego ×2, czyli effective ×3.
                try:
                    from . import species_effects as _sp_fx
                    dmg = int(round(dmg * _sp_fx.outgoing_crit_mul(ch)))
                except Exception:
                    pass
            # Prompt 26a — scale damage by the zone's multiplier (head 1.5×,
            # limbs 0.8×, etc.).
            dmg = max(1, int(round(dmg * zone_dmg_mul)))
            # P29.5 — landing a hit reveals full stats (you learn HP
            # and AC from combat math). Promote target → inspected.
            try:
                from . import visibility as _vis
                _vis.mark_inspected(self.world, target)
            except Exception:
                pass
            # Apply via damage module (resistance + status on hit).
            res = _dmg.apply_damage(self.world, target, dmg,
                                    damage_type=dmg_type,
                                    source=f"weapon:{weapon_name}")
            # Prompt 26a — also debit zone HP. Damage applied to zone is
            # the actual amount dealt (post-resistance). Breaks trigger
            # maim status on the victim.
            actual = int(res.get("amount_dealt", dmg) or 0)
            if actual > 0 and zone_key in target.body_parts:
                zp = target.body_parts[zone_key]
                zp["hp"] = max(0, int(zp.get("hp", 0)) - actual)
                if zp["hp"] <= 0 and not zp.get("broken"):
                    zp["broken"] = True
                    maim = zone_props.get("maim_status")
                    if maim:
                        _cmb.add_status(target, maim, 3)
                    zone_label_pl = zone_props.get("label_pl", zone_key)
                    # COMBAT-1 P4 / CMB-8 (partial) — sharp weapons SEVER, blunt
                    # weapons BREAK. A clean sever also briefly staggers/stuns
                    # (the shock of losing a limb), per the user's note. Full
                    # cut-vs-break system (amputation drops, bleed scaling) is
                    # still CMB-8; this is the readable first cut.
                    _sharp = bool(weapon and "sharp" in (weapon.tags or []))
                    zp["severed"] = _sharp   # UI shows odcięta vs złamana
                    if _sharp:
                        self.log(t("feedback_zone_severed",
                                   fallback=f"„{target.display_name()}”: "
                                            f"{zone_label_pl} odcięta!",
                                   name=target.display_name(),
                                   zone=zone_label_pl),
                                 LOG_DANGER)
                        # Shock of the cut — brief stagger.
                        if not _cmb.has_status(target, _cmb.STATUS_STAGGERED):
                            _cmb.add_status(target, _cmb.STATUS_STAGGERED, 1)
                        try:
                            audio.play_sfx("sever")
                        except Exception:
                            pass
                    else:
                        self.log(t("feedback_zone_broken",
                                   fallback=f"„{target.display_name()}”: "
                                            f"{zone_label_pl} złamana!",
                                   name=target.display_name(),
                                   zone=zone_label_pl),
                                 LOG_DANGER)
                        try:
                            audio.play_sfx("limb_broken")
                        except Exception:
                            pass
            # COMBAT-1 Slice B — interrupt feedback. If this hit just stunned
            # the target (head shot / heavy) WHILE it was charging a special,
            # surface that the read paid off. The enemy turn already fizzles a
            # charged special on stun/prone (see _run_enemy_turn); this just
            # tells the player their attack-the-windup choice worked.
            try:
                from . import enemy_ai as _ai
                _intent = (cs.enemy_intents or {}).get(target.entity_id) or {}
                if (_intent.get("category") == _ai.CAT_SPECIAL
                        and (_cmb.has_status(target, _cmb.STATUS_STUNNED)
                             or _cmb.has_status(target, _cmb.STATUS_PRONE))):
                    self.log(f"Trafiasz w zamachu — „{target.display_name()}” "
                             f"traci szykowany specjał!", LOG_SUCCESS)
            except Exception:
                pass
            # COMBAT-1 Slice C — make every solid hit FEEL like it landed.
            # The "I broke its torso and it didn't react" complaint: a hit
            # that deals no maim still needs a visible reaction. Rules:
            #   * any hit that bites (>=1 dmg, target alive) → short flinch line
            #   * a BIG hit (crit, or >=1/3 of max HP, or a heavy/head zone)
            #     also STAGGERS: STATUS_STAGGERED for 1 turn (weakens its next
            #     move; the enemy turn reads it). Head shots additionally roll
            #     a brief stun. This is reused by the enemy-turn weakening.
            try:
                if actual > 0 and target.is_alive():
                    big = (crit
                           or actual >= max(1, int(target.max_hp or 1) // 3)
                           or zone_dmg_mul >= 1.4
                           or zone_key == "head")
                    zlabel = zone_props.get("label_pl", zone_key)
                    if big and not _cmb.has_status(target, _cmb.STATUS_STAGGERED):
                        _cmb.add_status(target, _cmb.STATUS_STAGGERED, 1)
                        self.log(f"Mocne trafienie w {zlabel} — "
                                 f"„{target.display_name()}” się zachwiał!",
                                 LOG_SUCCESS)
                        try:
                            audio.play_sfx("stagger")
                        except Exception:
                            pass
                        # Head: a heavy crack has a chance to briefly stun.
                        if zone_key == "head" and not _cmb.has_status(
                                target, _cmb.STATUS_STUNNED):
                            if _r.randint(1, 20) + (3 if crit else 0) >= 14:
                                _cmb.add_status(target, _cmb.STATUS_STUNNED, 1)
                                self.log(f"Cios w głowę ogłusza "
                                         f"„{target.display_name()}”!",
                                         LOG_SUCCESS)
                    elif not big:
                        # Ordinary hit — light flinch so it never reads inert.
                        self.log(f"„{target.display_name()}” wzdryga się "
                                 f"od ciosu w {zlabel}.", LOG_NORMAL)
                    # COMBAT-1 Slice D — the show loves a spectacle. A crit or
                    # a clean staggering blow gives the crowd a small jolt
                    # (separate from the bigger on-kill bump below). Reuses the
                    # audience lever; the band-cross feedback handles its own
                    # logging.
                    if big:
                        try:
                            from . import audience as _aud_fx
                            _aud_fx.change_audience(self.world,
                                                    2 if crit else 1,
                                                    source="combat_flourish")
                        except Exception:
                            pass
                    # Finisher tell: enemy alive but on its last legs after this
                    # hit → prompt the player to end it (drama + clarity).
                    if 0 < target.hp <= max(1, int(target.max_hp or 1) // 5):
                        self.log(f"„{target.display_name()}” ledwo stoi — "
                                 f"dokończ go!", LOG_WARN)
            except Exception:
                pass
            # P29.55 — ferromanta magnetic_disarm: 25% chance na
            # ściągnięcie broni z metal-armed targetu po hicie.
            try:
                from . import species_effects as _sp_fx
                if _sp_fx.magnetic_disarm_check(ch, target, _r):
                    _cmb.add_status(target, _cmb.STATUS_DISARMED, 3)
                    self.log(
                        f"Twoje pole magnetyczne wyrywa broń z dłoni "
                        f"„{target.display_name()}”.",
                        LOG_SUCCESS)
            except Exception:
                pass
            # Decrement coating on a landed hit.
            if coating and coating.get("hits_remaining", 0) > 0:
                coating["hits_remaining"] -= 1
                if coating["hits_remaining"] <= 0:
                    weapon.state["coating"] = None
                    self.log(t("feedback_coating_worn",
                               fallback=f"Powłoka „{weapon.display_name()}” się "
                                        f"zużyła."),
                             LOG_SYSTEM)
            tag = ""
            if res.get("immune"):
                tag = " (odporny)"
            elif res.get("resisted"):
                tag = " (osłabione)"
            elif res.get("vulnerable"):
                tag = " (podatny!)"
            type_label = _dmg.damage_type_label(dmg_type)
            # P29.65 game-juice: pływająca liczba + błysk na karcie wroga.
            # Kolor wg wyniku: kryt złoty, podatny pomarańcz, osłabione/odporny
            # szary, zwykły biały.
            _amt = int(res.get("amount_dealt", dmg) or 0)
            if res.get("immune") or res.get("resisted"):
                _fxcol = (150, 160, 170)
            elif res.get("vulnerable"):
                _fxcol = (255, 120, 90)
            elif crit:
                _fxcol = (255, 210, 70)
            else:
                _fxcol = (235, 235, 235)
            # COMBAT-1 P2 — enemy recoils right when the player lands a hit
            # (bigger kick on crit). Shake scaled up a touch for punch.
            self._spawn_combat_fx(target.entity_id, f"-{_amt}", _fxcol,
                                  big=crit,
                                  shake=(160.0 if crit else 90.0),
                                  kick=(14 if crit else 8))
            self.log(f"„{target.display_name()}”: "
                     f"-{res['amount_dealt']} HP "
                     f"({type_label}){tag} "
                     f"(zostało {target.hp}/{target.max_hp}).",
                     LOG_SUCCESS if crit else LOG_NORMAL)
            if target.hp <= 0:
                self.log(f"„{target.display_name()}” pada.", LOG_SUCCESS)
                # COMBAT-1 Slice D — a kill is the money shot. Crowd pops, and
                # a FLASHY kill (crit, or a finishing blow to head/limb) pops
                # harder and is more likely to draw a sponsor's eye. The
                # generic enemy_killed sponsor tag still fires below; this is
                # the audience-meter spectacle on top.
                try:
                    from . import audience as _aud_kill
                    flashy = bool(crit or zone_key in ("head",) or
                                  zone_dmg_mul >= 1.4)
                    _aud_kill.change_audience(self.world, 4 if flashy else 2,
                                              source="combat_kill")
                    if flashy:
                        self.log("Widownia ryczy — efektowne wykończenie!",
                                 LOG_SYNDIC)
                        try:
                            audio.play_sfx("finisher")
                        except Exception:
                            pass
                        # A flashy kill can summon an opportunistic sponsor pod.
                        try:
                            from . import sponsors as _sp_fx
                            _sp_fx.note_player_tag(self.world,
                                                   "flashy_kill", weight=3)
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    audio.play_sfx("enemy_death")
                except Exception:
                    pass
                # Prompt 24 — corpse on death. Mutates target in place to
                # entity_type=corpse so all existing references (combat
                # state, sponsor tag bus, room.entities) stay valid. The
                # action bar will pick up the new affordances on its
                # next rebuild.
                try:
                    from . import corpses as _cp
                    _tags_pre = list(target.tags or [])
                    _cp.transform_to_corpse(self.world, target,
                                            killer=self.world.character)
                    # P29.44 — minibossy dropią kawałek mapy. Sprawdzamy
                    # tagi PRZED transformacją (corpse-tagi dodają się
                    # idempotentnie, ale na wszelki wypadek snapshot).
                    if "miniboss" in _tags_pre:
                        try:
                            self._drop_miniboss_map_fragment(target)
                        except Exception:
                            pass
                        # P29.49 — counter dla „klepacz_minibossow".
                        try:
                            ch_ = self.world.character
                            n = int(ch_.flags.get(
                                "floor_minibosses_killed", 0) or 0)
                            ch_.flags["floor_minibosses_killed"] = n + 1
                        except Exception:
                            pass
                    # P29.57d — Boss Box drop per rank. Każdy boss z
                    # tagiem `boss_rank:*` produkuje Skrzynkę odpowiedniej
                    # rangi w EQ gracza (DCC canon: zabójca dostaje łup).
                    # Plus bonus widowni zgodnie z rangą.
                    try:
                        _had_rank = any(
                            isinstance(t, str)
                            and t.startswith("boss_rank:")
                            for t in _tags_pre)
                        if _had_rank:
                            # Trzymamy snapshot tagów na bossie — corpse
                            # transform mógł je przepiąć, ale drop_boss_box
                            # czyta z entity, więc dorzucamy stare tagi
                            # z powrotem jeśli zostały zgubione.
                            for _t in _tags_pre:
                                if (isinstance(_t, str)
                                        and _t.startswith("boss_rank:")
                                        and _t not in (target.tags or [])):
                                    target.tags = (target.tags or []) + [_t]
                            from .handlers import boss_box as _bbx
                            _bbx.drop_boss_box(self.world, target,
                                               killer=self.world.character)
                            _bonus = _bbx.audience_bonus_for_dead_boss(target)
                            if _bonus > 0:
                                try:
                                    from . import audience as _aud2
                                    _aud2.change_audience(
                                        self.world, _bonus,
                                        source="boss_kill_rank")
                                except Exception:
                                    pass
                            # P29.57e — Wiercimajster codex: zapisz kill
                            # do persistent history (między runami).
                            try:
                                from . import run_history as _rh2
                                _fn = int(getattr(
                                    self.world.current_floor,
                                    "floor_number", 1) or 1)
                                _rh2.record_boss_kill(target, _fn)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    # P29.49 — counter floor_kills (achievement
                    # „kazdy_ma_imie" sprawdza floor_kills==floor_butchered).
                    try:
                        ch_ = self.world.character
                        n = int(ch_.flags.get("floor_kills", 0) or 0)
                        ch_.flags["floor_kills"] = n + 1
                    except Exception:
                        pass
                    # P29.46 — CRITICAL FIX: ubicie floor_boss odblokowuje
                    # wyjście z piętra. Bez tego hook'a floor.exits_unlocked
                    # nigdy nie był ustawiany przez kod produkcyjny i
                    # gracz nie mógł zejść w dół. Bug pokrywał wszystkie
                    # 18 pięter — odkryty podczas playthrough.
                    if ("floor_boss" in _tags_pre
                            or "final_boss" in _tags_pre):
                        try:
                            self._unlock_floor_exits(reason="boss_defeated")
                        except Exception:
                            pass
                    # Tag-bus event: enemy_killed. Sponsor reactions, P28
                    # title tracking, and P31 vendetta hook into this.
                    try:
                        from . import sponsors as _sp
                        _sp.note_player_tag(self.world, "enemy_killed",
                                            weight=1)
                    except Exception:
                        pass
                    # P29.53p — audience-as-lever: kill daje +N widowni
                    # zależnie od bandu. HOT/VIRAL = +3/+5 (spektakl),
                    # COLD = +1 (widownia nudzi się). Dynamicznie nagradza
                    # za utrzymywanie show'u — gracz nie wydaje widowni,
                    # ale jej STAN dynamizuje progresję.
                    try:
                        from . import audience as _aud
                        kbonus = int(
                            _aud.combat_mods_for_world(self.world)
                            .get("audience_on_kill", 1))
                        if kbonus > 0:
                            _aud.change_audience(self.world, kbonus,
                                                 source="kill_band_bonus")
                    except Exception:
                        pass
                    # P29.8 — bump kill counter for the run summary.
                    self._bump_run_counter("run_kills", 1)
                    # P29.76 — XP za zabójstwo (wg tieru z `_tags_pre` +
                    # skalowanie piętrem). Boss/miniboss kille też tędy
                    # (jeden hook = brak podwójnego naliczenia). award_xp
                    # sam obsłuży ewentualny awans(y) + nagrody.
                    try:
                        from . import leveling as _lvl
                        _fn_xp = int(getattr(self.world.current_floor,
                                             "floor_number", 1) or 1)
                        _lvl.award_xp(
                            self.world,
                            _lvl.xp_for_kill_tags(_tags_pre, _fn_xp))
                    except Exception:
                        pass
                    # P29.20 — companion chatter on kill.
                    try:
                        from . import companion_voice as _cv
                        _cv.maybe_say(self.world, "enemy_killed")
                    except Exception:
                        pass
                    # P29.15 — combat achievement triggers.
                    try:
                        from ..systems import achievements as _ach
                        ch_ = self.world.character
                        kills = int(ch_.run_kills or 0)
                        if kills == 1:
                            _ach.unlock(ch_, "pierwsza_krew", world=self.world)
                        if kills >= 50:
                            _ach.unlock(ch_, "rzeznia_kontrolowana",
                                        world=self.world)
                        if crit:
                            _ach.unlock(ch_, "finiszer_kanalu",
                                        world=self.world)
                        if "boss" in (target.tags or []) or \
                           "floor_boss" in (target.tags or []) or \
                           "final_boss" in (target.tags or []):
                            _ach.unlock(ch_, "boss_padl_pierwszy",
                                        world=self.world)
                    except Exception:
                        pass
                except Exception:
                    pass
            if mode == "heavy" and not crit:
                # Heavy attack exposes the player.
                _cmb.add_status(ch, _cmb.STATUS_WOUNDED, 2)
        else:
            if fumble:
                self.log(f"Twój atak idzie w bok i odsłaniasz się.", LOG_WARN)
                _cmb.add_status(ch, _cmb.STATUS_PRONE, 1)
            else:
                self.log(f"Chybiasz.", LOG_NORMAL)
        # Defense window for the enemy's reply.
        if defense_change != 0:
            cs.player_defend = max(0, cs.player_defend + max(0, defense_change))
        self._bump_threat(noise, source="combat_attack", room=room)
        cs.noise_added += noise
        cs.last_action = f"attack:{mode}"
        ch.affinity["melee"] = ch.affinity.get("melee", 0) + 1
        self._combat_after_player_action(cs)
    def _combat_defend(self, intent, cs):
        from . import combat as _cmb
        cs.player_defend = max(cs.player_defend, 3)
        self.log(t("feedback_combat_defend",
                   fallback="Bronisz się. Kolejny cios zaboli mniej."), LOG_SUCCESS)
        # P29.48 — track consecutive defends dla osiągnięcia
        # „reklama_przerywa_walke" (5 rund obrony pod rząd).
        prior = cs.last_action if hasattr(cs, "last_action") else ""
        if prior == "defend":
            cs.defend_streak = int(getattr(cs, "defend_streak", 0)) + 1
        else:
            cs.defend_streak = 1
        if cs.defend_streak >= 5:
            try:
                from ..systems import achievements as _ach
                _ach.unlock(self.world.character,
                            "reklama_przerywa_walke",
                            world=self.world)
            except Exception:
                pass
        cs.last_action = "defend"
        self._combat_after_player_action(cs)
    def _combat_dodge(self, intent, cs):
        cs.player_dodge = True
        self.log(t("feedback_combat_dodge",
                   fallback="Przygotowujesz się do uniku."), LOG_SUCCESS)
        cs.last_action = "dodge"
        self._combat_after_player_action(cs)
    def _combat_assess(self, intent, cs):
        from . import combat as _cmb
        if cs.assessed:
            self.log(t("feedback_combat_assessed_already",
                       fallback="Wiesz już wszystko, co da się ocenić bez bliższego oka."),
                     LOG_NORMAL)
            return
        cs.assessed = True
        self.log(t("feedback_combat_assess_h",
                   fallback="Oceniasz sytuację:"), LOG_SYSTEM)
        for eid in cs.participants:
            e = self.world.get(eid)
            if e is None or not e.is_alive():
                continue
            band = _cmb.describe_band(cs, e)
            threat = _cmb.describe_threat(e)
            behavior = _cmb.default_behavior(e)
            status = _cmb.list_status_pl(e)
            self.log(f"  • „{e.display_name()}” — {band}, {threat}. "
                     f"Styl: {behavior}. Status: {status}.", LOG_NORMAL)
        # Mention environment cues.
        room = self.world.current_floor.current_room()
        cues = []
        for e in (room.entities if room else []):
            tags = set(e.tags or [])
            if (e.state or {}).get("broken") or (e.state or {}).get("destroyed"):
                continue
            if "fragile" in tags or "glass" in tags:
                cues.append(f"{e.display_name()} — można rozbić")
            if "furniture" in tags and "salvageable" in tags:
                cues.append(f"{e.display_name()} — można przewrócić")
            if (room.state or {}).get("player_traps"):
                cues.append("masz w pokoju rozstawioną pułapkę — można w nią zwabić")
                break
        if cues:
            self.log("  Otoczenie: " + "; ".join(cues[:4]) + ".", LOG_NORMAL)
        cs.last_action = "assess"
        # Assess is free — DOES NOT trigger an enemy turn.
    def _combat_flee(self, intent, cs):
        """Try to escape through a known unlocked exit."""
        from . import combat as _cmb
        from .utils_compat import roll_d20
        room = self.world.current_floor.current_room()
        ch = self.world.character
        # Pick a destination: explicit if the player said one, else first
        # non-locked non-hidden exit.
        target_label = None
        if intent.destination:
            from .validation import fold
            tgt_f = fold(intent.destination)
            for label, ed in (room.exits or {}).items():
                if ed.get("hidden") or ed.get("locked"):
                    continue
                if fold(label) == tgt_f or tgt_f in fold(label):
                    target_label = label; break
        if target_label is None:
            for label, ed in (room.exits or {}).items():
                if not ed.get("hidden") and not ed.get("locked"):
                    target_label = label; break
        if target_label is None:
            self.log(t("feedback_combat_no_exit",
                       fallback="Nie widzisz, którędy uciekać."), LOG_WARN)
            self._combat_after_player_action(cs); return
        # DC scales with number of engaged hostiles and presence of guards.
        engaged = [self.world.get(eid) for eid in cs.participants
                   if cs.bands.get(eid) == _cmb.BAND_ENGAGED]
        engaged = [e for e in engaged if e and e.is_alive()]
        guards = sum(1 for e in engaged
                     if _cmb.default_behavior(e) == _cmb.BEHAVIOR_GUARD)
        dc = 10 + 2 * len(engaged) + 3 * guards
        raw = roll_d20()
        mod = ch.stat_mod("DEX")
        total = raw + mod
        from .dice_labels import stat_pl as _spl
        self.log(f"  [ucieczka] d20({raw}) + {_spl('DEX')}({mod:+d}) = "
                 f"{total} vs TT {dc}", LOG_SYSTEM)
        if total >= dc or raw == 20:
            self.log(t("feedback_combat_flee_ok",
                       fallback=f"Wycofujesz się przez „{target_label}”.",
                       exit=target_label), LOG_SUCCESS)
            _cmb.end_combat(room, self.world, outcome="player_flee")
            # Move through the exit by submitting a normal move command.
            self.submit_generated_command(f"idź {target_label}")
            return
        else:
            self.log(t("feedback_combat_flee_fail",
                       fallback="Nie udaje ci się zerwać. Wrogowie wykorzystują moment."),
                     LOG_WARN)
            cs.last_action = "flee_fail"
            self._combat_after_player_action(cs)
    def _combat_reposition(self, intent, cs, toward: bool):
        from . import combat as _cmb
        # Move ALL enemies' bands in the chosen direction relative to player.
        # Approach (toward=True) sets engaged; back away sets at_range.
        new_band = _cmb.BAND_ENGAGED if toward else _cmb.BAND_AT_RANGE
        for eid in cs.participants:
            cs.bands[eid] = new_band
        if toward:
            self.log(t("feedback_combat_close_in",
                       fallback="Zbliżasz się do wrogów."), LOG_NORMAL)
        else:
            self.log(t("feedback_combat_back_off",
                       fallback="Cofasz się na dystans."), LOG_NORMAL)
        cs.last_action = "reposition"
        self._combat_after_player_action(cs)
    def _try_systemic_chain(self, intent, cs) -> bool:
        """P29.61 — przekierowuje wepchnij/zwab/rzuć przez systemowy
        silnik reguł (engine/systemic). Zwraca True jeśli reguła
        zadziałała (log + tura wroga).

        Semantyka per czasownik:
          * wepchnij/zwab/pchnij OBJ w DEST → DEST(hazard)=źródło,
            OBJ(wróg)=cel
          * rzuć OBJ w DEST → OBJ(przedmiot)=źródło, DEST(wróg)=cel
        """
        from . import systemic as _sys
        from .validation import _resolve_entities
        room = self.world.current_floor.current_room()
        if room is None or not intent.targets:
            return False
        obj = _resolve_entities(room, intent.targets[0])
        dest_frag = getattr(intent, "destination", None)
        dest = _resolve_entities(room, dest_frag) if dest_frag else []
        obj_e = obj[0] if obj else None
        dest_e = dest[0] if dest else None

        verb = (intent.verb or "").lower()
        is_throw = (intent.intent == "throw_at"
                    or verb in ("rzuc", "rzuć", "cisnij", "ciśnij",
                                "throw", "hurl"))
        if is_throw:
            source, target = obj_e, dest_e   # rzuć PRZEDMIOT w WROGA
        else:
            source, target = dest_e, obj_e   # wepchnij WROGA w HAZARD

        if source is None or target is None:
            return False
        # Cel musi być istotą (nie wepchniemy szafy w szafę dla efektu).
        if target.entity_type not in ("monster", "crawler", "npc"):
            return False

        # P29.61 — złap nazwę ŻYWEGO wroga PRZED interakcją; po
        # transform_to_corpse entity nazywa się już „padlina …" i
        # log „X pada" pokazywałby nazwę trupa zamiast wroga (bug).
        victim_name = target.display_name()
        ac_before = int(getattr(target, "ac", 0) or 0)
        res = _sys.apply_environmental(self.world, verb, source, target)
        if not res.matched:
            # P29.66 — materia nie zadziałała → spróbuj PSYCHIKI (lęk/
            # odraza/pragnienie). „Rzuć szczura w bossa, który boi się
            # robactwa" → panika. Tożsamość źródła ∩ psyche celu.
            res = _sys.resolve_psyche(self.world, verb, source, target)
        if not res.matched:
            return False
        for ln in res.lines:
            self.log(ln, LOG_SUCCESS)
        # P29.63 — telegraf: korozja pokazuje spadek AC, a efekt trwały
        # zapowiada się, żeby gracz wiedział że to się nie kończy na hicie.
        if res.ac_delta and target.is_alive():
            ac_after = int(getattr(target, "ac", 0) or 0)
            self.log(f"  Pancerz słabnie — AC {ac_before}→{ac_after}.",
                     LOG_NORMAL)
        if target.is_alive():
            st_sys = (getattr(target, "state", None) or {})
            lingering = st_sys.get("systemic_statuses") or []
            if lingering and int(st_sys.get("systemic_turns", 0)) > 0:
                self.log(f"  {victim_name}: „{lingering[-1]}” — to się "
                         f"utrzyma.", LOG_NORMAL)
        # Sprawdź czy cel padł od interakcji.
        if not target.is_alive():
            self.log(f"„{victim_name}” pada.", LOG_SUCCESS)
            try:
                from . import corpses as _cp
                _cp.transform_to_corpse(self.world, target,
                                        killer=self.world.character)
            except Exception:
                pass
        # Tura wroga / hooki combat tylko gdy walka aktywna.
        if cs is not None:
            cs.last_action = f"systemic:{res.effect}"
            self._combat_after_player_action(cs)
        return True
    def _combat_use_environment(self, intent, cs) -> bool:
        """Break/throw/push in combat: in addition to the normal effect,
        apply a situational status to an engaged enemy if tags match.
        Returns True if a combat-environment hook fired (and an enemy turn
        followed); False if the action should just run normally."""
        from . import combat as _cmb
        room = self.world.current_floor.current_room()
        if room is None:
            return False
        # P29.61 — systemowy silnik PIERWSZY. Wepchnij/zwab wroga w
        # hazard lub rzuć czymś w wroga → resolver reguł tagów. Jeśli
        # zadziała (np. ogień+łatwopalne→pożar), bierzemy to; inaczej
        # fall-through do starej (hardkodowanej) logiki środowiska.
        if self._try_systemic_chain(intent, cs):
            return True
        from .validation import _resolve_entities
        if not intent.targets:
            return False
        candidates = _resolve_entities(room, intent.targets[0])
        if not candidates:
            return False
        target = candidates[0]
        tags = set(target.tags or [])
        engaged = [self.world.get(eid) for eid in cs.participants
                   if cs.bands.get(eid) == _cmb.BAND_ENGAGED and
                   self.world.get(eid) and self.world.get(eid).is_alive()]
        if not engaged:
            return False
        victim = engaged[0]
        applied = None
        # Order matters: electrical+machine victim FIRST (so a panel
        # with both `electrical` and `fragile` tags shocks a machine
        # instead of just blinding it), then furniture push, then
        # generic fragile/glass break, then throw.
        if intent.intent == "break" and ("electrical" in tags or "wire" in tags) \
                and _cmb.default_behavior(victim) == _cmb.BEHAVIOR_MACHINE:
            _cmb.add_status(victim, _cmb.STATUS_SHOCKED, 2)
            applied = "shocked"
        elif intent.intent == "push_into" and "furniture" in tags:
            _cmb.add_status(victim, _cmb.STATUS_PRONE, 2)
            applied = "prone"
        elif intent.intent == "break" and ("glass" in tags or "fragile" in tags):
            _cmb.add_status(victim, _cmb.STATUS_BLINDED, 2)
            applied = "blinded"
        elif intent.intent == "throw_at" and "fragile" in tags:
            _cmb.add_status(victim, _cmb.STATUS_BLINDED, 1)
            applied = "blinded"
        if applied:
            self.log(t(f"feedback_combat_env_{applied}",
                       fallback=f"Otoczenie zwraca się przeciw „{victim.display_name()}” "
                                f"— status: {_cmb.status_label(applied)}.",
                       name=victim.display_name()), LOG_SUCCESS)
            # Don't double-process: run the underlying intent to actually
            # break/push/throw, then take an enemy turn.
            self._fallback_to_standard_pipeline(intent)
            cs.last_action = f"env:{applied}"
            self._combat_after_player_action(cs)
            return True
        return False
    def _combat_lure(self, intent, cs) -> None:
        from . import combat as _cmb
        room = self.world.current_floor.current_room()
        traps = (room.state or {}).get("player_traps") or []
        untriggered = [tr for tr in traps if not tr.get("triggered")]
        if not untriggered:
            self.log(t("feedback_combat_no_trap",
                       fallback="Nie masz w pokoju gotowej pułapki, do której można kogoś zwabić."),
                     LOG_WARN)
            return
        # Pick the first engaged hostile as the victim.
        engaged = [self.world.get(eid) for eid in cs.participants
                   if cs.bands.get(eid) == _cmb.BAND_ENGAGED and
                   self.world.get(eid) and self.world.get(eid).is_alive()]
        if not engaged:
            engaged = [self.world.get(eid) for eid in cs.participants
                       if self.world.get(eid) and self.world.get(eid).is_alive()]
        if not engaged:
            self.log(t("feedback_combat_no_target",
                       fallback="Nie widzisz w kogo wciągnąć w pułapkę."), LOG_WARN)
            return
        victim = engaged[0]
        # CHA check.
        from .utils_compat import roll_d20
        ch = self.world.character
        raw = roll_d20()
        mod = ch.stat_mod("CHA")
        if raw + mod >= 11:
            tr = untriggered[0]
            tr["triggered"] = True
            payload = tr.get("effect") or {}
            dmg = int(payload.get("amount", 3))
            victim.hp = max(0, victim.hp - dmg)
            self.log(t("feedback_combat_lure_ok",
                       fallback=f"„{victim.display_name()}” wpada w pułapkę — -{dmg} HP.",
                       name=victim.display_name(), amount=dmg), LOG_SUCCESS)
            if payload.get("type") == "damage_and_stun":
                _cmb.add_status(victim, _cmb.STATUS_STUNNED, 2)
            elif payload.get("type") == "knockdown":
                _cmb.add_status(victim, _cmb.STATUS_PRONE, 2)
        else:
            self.log(t("feedback_combat_lure_fail",
                       fallback="Próbujesz go zwabić, ale nie chwyta."),
                     LOG_WARN)
        cs.last_action = "lure"
        self._combat_after_player_action(cs)
