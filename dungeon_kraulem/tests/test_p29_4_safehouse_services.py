"""Prompt 29.4 — real handlers for black_market / sponsor_kiosk /
bulletin_board services. Player report: 'mam 25 kredytów, nie stać
mnie na informację za 15 kr — to pusta funkcja bez mechanik'.

Covers:
  * black_market.info works when player can afford it (-15 kr,
    returns rumor or stub text)
  * black_market.info refuses gracefully when player can't afford
  * black_market.buy lists 3 items + their prices
  * try_buy actually transfers item + deducts credits
  * black_market.sell lists inventory items with prices
  * try_sell removes item + adds credits
  * sponsor_kiosk.ad bumps audience for free
  * sponsor_kiosk.intel deducts 10 kr
  * bulletin_board.read returns multi-line rumor list
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..systems import safehouses as _sh
from ..content.items import make_item


def _mk_world(credits: int = 25):
    w = WorldState()
    w.character = Character(name="N", background="janitor")
    w.character.credits = credits
    f = FloorState(floor_id="f1", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Bez Paragonu")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    return w


# ── black_market.info ────────────────────────────────────────────────────

def test_info_affordable_deducts_and_returns_text():
    w = _mk_world(credits=25)
    line = _sh.perform("info", w)
    assert w.character.credits == 10, \
        f"info should cost 15 kr; credits={w.character.credits}"
    assert "Sprzedawca" in line or "Słyszałem" in line, line
    print(f"  info (-15 kr): credits 25→10, line: '{line[:50]}…': OK")


def test_info_too_poor_gracefully_refuses():
    w = _mk_world(credits=5)
    line = _sh.perform("info", w)
    assert w.character.credits == 5, "should NOT deduct when too poor"
    assert "15 kr" in line, f"refusal should mention price; got '{line}'"
    print(f"  info too poor: refusal: '{line}': OK")


# ── black_market.buy / try_buy ───────────────────────────────────────────

def test_buy_lists_three_items():
    w = _mk_world(credits=25)
    line = _sh.perform("buy", w)
    # Should mention 3 items + prices.
    assert "kr" in line, line
    # Should leave a pending offer cache.
    assert getattr(w, "_pending_bm_offer", None), "expected pending offer cache"
    assert len(w._pending_bm_offer) == 3
    print(f"  buy lists 3 items: OK ({list(w._pending_bm_offer.keys())})")


def test_try_buy_transfers_item_and_credits():
    w = _mk_world(credits=50)
    _sh.perform("buy", w)
    # Pick the first item in the offer.
    item_key = list(w._pending_bm_offer.keys())[0]
    price, name = w._pending_bm_offer[item_key]
    pre_inv = len(w.character.inventory_ids)
    line = _sh.try_buy(w, name)
    assert w.character.credits == 50 - price, \
        f"credits should drop by {price}; got {w.character.credits}"
    assert len(w.character.inventory_ids) == pre_inv + 1
    assert item_key not in w._pending_bm_offer
    print(f"  try_buy bought '{name}' for {price} kr: OK")


def test_try_buy_too_poor_refuses():
    w = _mk_world(credits=3)
    _sh.perform("buy", w)
    item_key = list(w._pending_bm_offer.keys())[0]
    price, name = w._pending_bm_offer[item_key]
    if price > 3:
        pre_inv = len(w.character.inventory_ids)
        line = _sh.try_buy(w, name)
        assert "Nie stać" in line, line
        assert len(w.character.inventory_ids) == pre_inv
        print(f"  try_buy refuses when too poor: '{line}': OK")
    else:
        print("  (RNG picked cheap item; skip)")


# ── black_market.sell / try_sell ─────────────────────────────────────────

def test_sell_lists_inventory():
    w = _mk_world(credits=0)
    # Seed inventory.
    it = make_item("snack_bar", location_id="inventory:player")
    w.register(it)
    w.character.inventory_ids.append(it.entity_id)
    line = _sh.perform("sell", w)
    assert "snack" in line.lower() or "baton" in line.lower(), line
    assert getattr(w, "_pending_bm_sell", None), "expected sell cache"
    print(f"  sell lists inventory: OK")


def test_try_sell_transfers_credits_and_removes_item():
    w = _mk_world(credits=0)
    it = make_item("snack_bar", location_id="inventory:player")
    w.register(it)
    w.character.inventory_ids.append(it.entity_id)
    _sh.perform("sell", w)
    # Find the cached entry.
    name = list(w._pending_bm_sell.keys())[0]
    eid, price = w._pending_bm_sell[name]
    line = _sh.try_sell(w, name)
    assert w.character.credits == price, \
        f"credits should be +{price}; got {w.character.credits}"
    assert eid not in w.character.inventory_ids
    print(f"  try_sell sold '{name}' for {price} kr: OK")


# ── sponsor_kiosk ────────────────────────────────────────────────────────

def test_kiosk_ad_free_audience_bump():
    w = _mk_world(credits=0)
    pre_aud = w.character.audience_rating
    line = _sh.perform("ad", w)
    assert w.character.audience_rating > pre_aud, \
        "ad should bump audience"
    assert w.character.credits == 0   # free
    print(f"  ad: audience +{w.character.audience_rating - pre_aud}: OK")


def test_kiosk_intel_costs_10_kr():
    w = _mk_world(credits=25)
    line = _sh.perform("intel", w)
    assert w.character.credits == 15, \
        f"intel should cost 10; got credits={w.character.credits}"
    assert "Raport" in line or "raport" in line
    print(f"  intel: -10 kr, credits 25→15: OK")


def test_kiosk_intel_too_poor():
    w = _mk_world(credits=3)
    line = _sh.perform("intel", w)
    assert w.character.credits == 3
    assert "10 kr" in line
    print(f"  intel too poor: '{line}': OK")


# ── bulletin_board ───────────────────────────────────────────────────────

def test_bulletin_read_returns_lines():
    w = _mk_world(credits=0)
    line = _sh.perform("read", w)
    # Either has rumors or "pusta" message.
    assert ("Tablica" in line or "puste" in line.lower()
            or "•" in line), line
    print(f"  bulletin read: OK ('{line[:50]}…')")


# ── Suite ────────────────────────────────────────────────────────────────

def main():
    test_info_affordable_deducts_and_returns_text()
    test_info_too_poor_gracefully_refuses()
    test_buy_lists_three_items()
    test_try_buy_transfers_item_and_credits()
    test_try_buy_too_poor_refuses()
    test_sell_lists_inventory()
    test_try_sell_transfers_credits_and_removes_item()
    test_kiosk_ad_free_audience_bump()
    test_kiosk_intel_costs_10_kr()
    test_kiosk_intel_too_poor()
    test_bulletin_read_returns_lines()
    print("Prompt 29.4 safehouse services smoke: OK")


if __name__ == "__main__":
    main()
