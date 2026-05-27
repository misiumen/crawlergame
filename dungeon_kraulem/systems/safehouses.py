"""Safehouse subtype catalog + services.

P29.4: real handlers for black_market / sponsor_kiosk / bulletin_board
services. Previously these returned "Nie stać cię" for everything because
`perform()` only had cafe/bathroom/lounge/clinic branches — buy / sell /
info / ad / intel / read all fell through to the catch-all refusal.
Player report: "interakcje z kioskiem nie maja sensu, mam 25 kredytów,
nie stać mnie na informację za 15 kredytów, k,upić też nic nie moge".
"""
import random as _r
from ..ui.lang import t


SUBTYPES = ("cafe","bathroom","lounge","clinic","black_market",
            "crawler_den","sponsor_kiosk","faction_checkpoint",
            "vending_hall","shower_block","bulletin_board","neutral_bar")


def services(subtype: str):
    """Return [(action_key, label_key, price)] for a subtype."""
    return {
        "cafe":  [("coffee", "safe_cafe_coffee", 5),
                  ("food",   "safe_cafe_food",   12),
                  ("chat",   "safe_cafe_chat",   0)],
        "bathroom": [("wash",   "safe_bath_wash",   0),
                     ("hide",   "safe_bath_hide",   0),
                     ("mirror", "safe_bath_mirror", 0)],
        "lounge": [("drink",   "safe_lounge_drink", 8),
                   ("schmooze","safe_lounge_chat",  0)],
        "clinic": [("heal",    "safe_clinic_heal",  20),
                   ("cure",    "safe_clinic_cure",  30),
                   ("full",    "safe_clinic_full",  60)],
        "black_market": [("buy",  "safe_bm_buy",   0),
                         ("sell", "safe_bm_sell",  0),
                         ("info", "safe_bm_info", 15)],
        "sponsor_kiosk": [("ad",   "safe_kiosk_ad",   0),
                          ("intel","safe_kiosk_intel",10)],
        "bulletin_board": [("read","safe_bb_read",  0)],
    }.get(subtype, [])


# Per-visit catalog cached on the world so prices/items stay stable
# across the player's repeated interactions in the same room.
_BM_BUY_POOL = [
    ("improvised_lockpick", 8,  "zardzewiały wytrych"),
    ("dirty_bandage",       6,  "brudny bandaż"),
    ("snack_bar",           5,  "baton energetyczny"),
    ("duct_tape",           7,  "rolka taśmy klejącej"),
    ("battery",             10, "ogniwo bateryjne"),
    ("suspicious_keycard",  18, "karta dostępu (podejrzana)"),
    ("flashlight",          12, "latarka"),
]

_BM_SELL_BASE = {
    # Item key → base sell price (kredyty). Unknown items go for 2.
    "improvised_lockpick": 4,
    "dirty_bandage":       3,
    "snack_bar":           2,
    "duct_tape":           3,
    "battery":             5,
    "suspicious_keycard":  9,
    "flashlight":          6,
    "plastic_badge":       2,
    "dead_phone":          1,
    "cracked_mug":         1,
    "cheap_knife":         5,
    "broken_camera_lens":  2,
    "map_fragment":        6,
    "floor_map":           15,
}


def _bm_offer(world):
    """Pick 3 items the black-market offers today. Cached per-floor so
    re-entering the room shows the same stock."""
    floor = getattr(world, "current_floor", None)
    if floor is None:
        return _BM_BUY_POOL[:3]
    cache = (floor.state or {}).get("bm_offer") if hasattr(floor, "state") else None
    if cache:
        return cache
    rng = _r.Random(hash(("bm", floor.floor_id)))
    offer = rng.sample(_BM_BUY_POOL, 3)
    if not hasattr(floor, "state") or floor.state is None:
        floor.state = {}
    floor.state["bm_offer"] = offer
    return offer


def perform(action_key: str, world):
    ch = world.character
    if action_key == "coffee" and ch.credits >= 5:
        ch.credits -= 5; ch.heal(3); ch.audience_rating += 1
        return t("safe_cafe_coffee_result", fallback="Pijesz kawę. Smakuje jak metal.")
    if action_key == "food" and ch.credits >= 12:
        ch.credits -= 12; ch.heal(8)
        return t("safe_cafe_food_result", fallback="Jesz coś nazwanego 'posiłkiem'.")
    if action_key == "chat":
        ch.audience_rating += 2
        # Prompt 1: pull a real rumor from the content layer when available
        try:
            from ..content import content_loader
            rumor = content_loader.random_rumor() or {}
        except Exception:
            rumor = {}
        text = rumor.get("text", "")
        if text:
            try:
                key = rumor.get("key")
                if key and world.current_floor and key not in world.current_floor.rumors:
                    world.current_floor.rumors.append(key)
            except Exception:
                pass
            return text
        return t("safe_cafe_chat_result", fallback="Plotki. Niektóre brzmią użytecznie.")
    if action_key == "wash":
        ch.heal(2); ch.conditions[:] = [c for c in ch.conditions if c != "dirty"]
        return t("safe_bath_wash_result", fallback="Myjesz się. Stajesz się tylko trochę gorzej.")
    if action_key == "hide":
        ch.heal(4)
        return t("safe_bath_hide_result", fallback="Oddychasz. Kabina jest cierpliwa.")
    if action_key == "mirror":
        return t("safe_bath_mirror_result", fallback="W lustrze widzisz kogoś, kto przypomina ciebie.")
    if action_key == "drink" and ch.credits >= 8:
        ch.credits -= 8; ch.audience_rating += 5
        return t("safe_lounge_drink_result", fallback="Drink. Widownia notuje.")
    if action_key == "schmooze":
        ch.audience_rating += 3
        return t("safe_lounge_chat_result", fallback="Rozmowa. Krótka, ale błyskotliwa.")
    if action_key == "heal" and ch.credits >= 20:
        ch.credits -= 20; ch.heal(10)
        return t("safe_clinic_heal_result", fallback="Klinika cię zszywa. Tanio nie znaczy bezboleśnie.")
    if action_key == "cure" and ch.credits >= 30:
        ch.credits -= 30; ch.conditions.clear()
        return t("safe_clinic_cure_result", fallback="Stany wyleczone.")
    if action_key == "full" and ch.credits >= 60:
        ch.credits -= 60; ch.hp = ch.max_hp
        return t("safe_clinic_full_result", fallback="Pełne leczenie. Rachunek jeszcze gorszy.")

    # ─────────────────────────────────────────────────────────────────
    # P29.4 — black_market handlers
    # ─────────────────────────────────────────────────────────────────
    if action_key == "buy":
        offer = _bm_offer(world)
        # Print the offer; player commits with `kup <item>` follow-up.
        if not hasattr(world, "_pending_bm_offer"):
            world._pending_bm_offer = {}
        world._pending_bm_offer = {key: (price, name)
                                    for (key, price, name) in offer}
        lines = ["Sprzedawca rzuca na ladę trzy rzeczy:"]
        for key, price, name in offer:
            affordable = "✓" if ch.credits >= price else "✗"
            lines.append(f"  [{affordable}] {name} — {price} kr   (kup {name})")
        lines.append(f"Masz {ch.credits} kr. Wpisz: kup <nazwa>.")
        return "\n".join(lines)

    if action_key == "sell":
        # List sellable items from inventory with prices.
        inv = list(getattr(ch, "inventory_ids", []) or [])
        if not inv:
            return "Pusty plecak. Nic do sprzedania."
        # Build per-id offers.
        offers = []
        for eid in inv:
            ent = world.get(eid)
            if ent is None or not ent.portable:
                continue
            price = _BM_SELL_BASE.get(ent.key, 2)
            offers.append((eid, ent.display_name(), price))
        if not offers:
            return "Nic z plecaka nie ma tu wartości."
        if not hasattr(world, "_pending_bm_sell"):
            world._pending_bm_sell = {}
        world._pending_bm_sell = {name.lower(): (eid, price)
                                   for (eid, name, price) in offers[:6]}
        lines = ["Sprzedawca oferuje:"]
        for eid, name, price in offers[:6]:
            lines.append(f"  • {name} — {price} kr   (sprzedaj {name})")
        if len(offers) > 6:
            lines.append(f"  (+{len(offers) - 6} więcej…)")
        lines.append("Wpisz: sprzedaj <nazwa>.")
        return "\n".join(lines)

    if action_key == "info" and ch.credits >= 15:
        ch.credits -= 15
        # Try to surface a real clue/rumor from the content layer.
        try:
            from ..content import content_loader
            rumor = content_loader.random_rumor() or {}
        except Exception:
            rumor = {}
        body = rumor.get("text", "")
        if body:
            try:
                key = rumor.get("key")
                if (key and world.current_floor
                        and key not in world.current_floor.rumors):
                    world.current_floor.rumors.append(key)
            except Exception:
                pass
            return f"Sprzedawca pochyla się: „{body}” ({15} kr)."
        # Fallback: at least name a sponsor mood as data.
        return (f"Sprzedawca: „Słyszałem, że Sponsor obserwuje. "
                f"Nie wiem który. Ale obserwuje.” (-15 kr)")
    if action_key == "info":
        return f"Sprzedawca: „15 kr za informację. Masz {ch.credits}.”"

    # ─────────────────────────────────────────────────────────────────
    # P29.4 — sponsor_kiosk handlers
    # ─────────────────────────────────────────────────────────────────
    if action_key == "ad":
        # Free promo. Bumps audience, tags spectacle.
        ch.audience_rating += 5
        try:
            from ..engine import sponsors as _sp
            _sp.note_player_tag(world, "spectacle", weight=2)
        except Exception:
            pass
        return ("Włączasz reklamę sponsora. Krótka, głośna, idiotyczna. "
                "Publika klaszczeˇ.")

    if action_key == "intel" and ch.credits >= 10:
        ch.credits -= 10
        # Reveal floor objective if not yet known, else next-room hint.
        f = world.current_floor
        if f and getattr(f, "objective_key", ""):
            obj_title = getattr(f, "objective_title_fallback", "") or f.objective_key
            return (f"Raport sponsorski (-10 kr): cel piętra to "
                    f"„{obj_title}”. Płacisz za to, co prawie wiedziałeś.")
        return ("Raport sponsorski (-10 kr): „Tu jest niebezpiecznie. "
                "Polecam ostrożność.” Pieniędzy nie zwracamy.")
    if action_key == "intel":
        return f"Kiosk: „10 kr za raport. Masz {ch.credits}.”"

    # ─────────────────────────────────────────────────────────────────
    # P29.4 — bulletin_board
    # ─────────────────────────────────────────────────────────────────
    if action_key == "read":
        # Pull up to 3 rumors from the floor.
        rumors = []
        try:
            from ..content import content_loader
            for _ in range(3):
                r = content_loader.random_rumor()
                if r and r.get("text"):
                    rumors.append(r.get("text"))
        except Exception:
            pass
        if rumors:
            lines = ["Tablica ogłoszeń:"]
            for r in rumors:
                lines.append(f"  • {r}")
            return "\n".join(lines)
        return "Tablica ogłoszeń pusta. Ktoś zerwał wszystkie kartki."

    # Catch-all — kept short, no longer the default for everything.
    return t("dialog_too_poor", fallback="Nie stać cię.")


# ─────────────────────────────────────────────────────────────────────
# P29.4 — buy / sell follow-up resolvers (called from game.py when the
# player types `kup X` or `sprzedaj X` after entering a black market).
# ─────────────────────────────────────────────────────────────────────

def try_buy(world, name_hint: str) -> str:
    """Player typed `kup <X>` after entering a black-market. Match X
    against the cached offer and process the purchase."""
    ch = world.character
    offer = getattr(world, "_pending_bm_offer", None) or {}
    if not offer:
        return "Nie wybrałeś jeszcze 'kup' u sprzedawcy."
    needle = (name_hint or "").strip().lower()
    if not needle:
        return "Co kupić? Wpisz `kup X` z listy."
    match_key = None
    for k, (price, name) in offer.items():
        if needle in name.lower() or needle in k.lower():
            match_key = k
            break
    if match_key is None:
        return f"„{name_hint}” — nie ma tego na ladzie."
    price, name = offer[match_key]
    if ch.credits < price:
        return f"Nie stać cię. „{name}” = {price} kr, masz {ch.credits}."
    # Create the item and add to inventory.
    try:
        from ..content.items import make_item
        it = make_item(match_key, location_id="inventory:player")
        world.register(it)
        ch.inventory_ids.append(it.entity_id)
    except Exception as exc:
        return f"(bug w transakcji: {exc})"
    ch.credits -= price
    del offer[match_key]
    return f"Bierzesz „{name}”. Sprzedawca chowa {price} kr w kieszeni."


def try_sell(world, name_hint: str) -> str:
    """Player typed `sprzedaj <X>`. Match X against cached sell offers."""
    ch = world.character
    table = getattr(world, "_pending_bm_sell", None) or {}
    if not table:
        return "Najpierw wybierz 'sprzedaj' u sprzedawcy, żeby zobaczyć stawki."
    needle = (name_hint or "").strip().lower()
    if not needle:
        return "Co sprzedać? Wpisz `sprzedaj X` z listy."
    match_name = None
    for nm in table.keys():
        if needle in nm or nm in needle:
            match_name = nm
            break
    if match_name is None:
        return f"„{name_hint}” — sprzedawca nie chce tego."
    eid, price = table[match_name]
    # Remove from inventory.
    try:
        ch.inventory_ids.remove(eid)
    except ValueError:
        return "Już tego nie masz."
    ch.credits += price
    del table[match_name]
    return f"Sprzedajesz „{match_name}” za {price} kr."
