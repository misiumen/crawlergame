"""Safehouse subtype catalog + services."""
from .lang import t


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
    return t("dialog_too_poor", fallback="Nie stać cię.")
