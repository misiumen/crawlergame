"""Merchant system for CRAWL PROTOCOL."""
import random
from utils import get_input, get_int_input, press_enter
from items import (Weapon, Armor, Consumable, Trinket,
                   generate_loot, item_to_dict, CONSUMABLE_CATALOG,
                   _copy_consumable, _copy_weapon, WEAPON_CATALOG)
from narrator import get_narrator


_GREETINGS = [
    "A hooded figure emerges from behind a pile of debris.",
    "Someone has set up a folding table in a dungeon corridor. Entrepreneurship.",
    "A merchant materializes from the shadows with impeccable timing.",
    "You find a licensed vendor operating in the death maze. The paperwork is in order.",
]

_FAREWELLS = [
    "The merchant watches you leave. Their eyes don't blink.",
    "Pleasure doing business. Stay alive long enough to spend it.",
    "Come back when you have more to spend and less dignity to protect.",
    "Safe travels. Well. Safer travels.",
]


def _merchant_stock(floor):
    stock = []
    # Always some consumables
    consumable_keys = ["Small Medkit", "Large Medkit", "Antidote", "Fire Flask",
                       "Smoke Bomb", "Focus Injector", "Adrenal Shot"]
    if floor >= 2:
        consumable_keys.extend(["Large Medkit", "Adrenal Shot"])

    num_consumables = random.randint(3, 5)
    seen = set()
    for _ in range(num_consumables):
        k = random.choice(consumable_keys)
        if k not in seen:
            stock.append(_copy_consumable(CONSUMABLE_CATALOG[k]))
            seen.add(k)

    # Chance for weapon
    if random.random() < 0.40:
        from items import _FLOOR_WEAPON_POOLS, _copy_weapon
        pool = _FLOOR_WEAPON_POOLS.get(min(floor, 3), _FLOOR_WEAPON_POOLS[1])
        name = random.choice(pool)
        stock.append(_copy_weapon(WEAPON_CATALOG[name]))

    # Chance for armor
    if random.random() < 0.30:
        from items import _FLOOR_ARMOR_POOLS, _copy_armor, ARMOR_CATALOG
        pool = _FLOOR_ARMOR_POOLS.get(min(floor, 3), _FLOOR_ARMOR_POOLS[1])
        name = random.choice(pool)
        stock.append(_copy_armor(ARMOR_CATALOG[name]))

    return stock


def _item_price(item, player):
    base = item.value
    # Curse Mark mutation: pay 10% more
    for mut in player.mutations:
        if mut.name == "Curse Mark":
            base = int(base * 1.10)
    # Whisper Coin trinket: discount
    for inv_item in player.inventory:
        if isinstance(inv_item, Trinket) and inv_item.effect == "merchant_discount":
            base = int(base * 0.85)
    return max(1, base)


def _sell_price(item):
    return max(1, item.value // 3)


def run_merchant(player, floor=1):
    """Interactive merchant shop. Modifies player in place."""
    n = get_narrator()
    print(f"\n  {'='*56}")
    print(f"  *** MERCHANT ***")
    print(f"  {random.choice(_GREETINGS)}")
    n.say("merchant")

    stock = _merchant_stock(floor)

    while True:
        print(f"\n  {'-'*56}")
        print(f"  Credits: {player.credits}")
        print()
        print("  FOR SALE:")
        if not stock:
            print("    (sold out)")
        else:
            for i, item in enumerate(stock, 1):
                price = _item_price(item, player)
                if isinstance(item, Weapon):
                    print(f"    [{i}] {item.name}  ({item.damage_dice})  -{price} cr")
                elif isinstance(item, Armor):
                    print(f"    [{i}] {item.name}  (AC {item.ac})  -{price} cr")
                elif isinstance(item, Consumable):
                    print(f"    [{i}] {item.name}  -{price} cr")
                else:
                    print(f"    [{i}] {item.name}  -{price} cr")

        print()
        print("  [b] Buy   [s] Sell   [h] Heal   [l] Leave")
        choice = get_input("  Choice: ", ["b", "s", "h", "l"])

        if choice == "b":
            if not stock:
                print("  Nothing left to sell.")
                press_enter()
                continue
            idx = get_int_input("  Item number (0 to cancel): ", 0, len(stock))
            if idx == 0:
                continue
            item = stock[idx - 1]
            price = _item_price(item, player)
            if player.credits < price:
                print(f"  Not enough credits. Need {price}, have {player.credits}.")
                press_enter()
            else:
                player.credits -= price
                player.add_item(item)
                stock.pop(idx - 1)
                print(f"  Bought: {item.name}  (Remaining credits: {player.credits})")
                if player.achievements:
                    player.achievements.check_credits_spent(price)
                    player.achievements.check_merchant_buy()
                press_enter()

        elif choice == "s":
            player.display_inventory()
            if not player.inventory:
                press_enter()
                continue
            idx = get_int_input("  Item number to sell (0 to cancel): ", 0, len(player.inventory))
            if idx == 0:
                continue
            item = player.inventory[idx - 1]
            sp = _sell_price(item)
            player.inventory.pop(idx - 1)
            player.credits += sp
            print(f"  Sold {item.name} for {sp} cr. Credits: {player.credits}")
            press_enter()

        elif choice == "h":
            heal_cost = 15 + floor * 5
            print(f"\n  Emergency medical patch: {heal_cost} cr (+15 HP)")
            if player.credits >= heal_cost:
                confirm = get_input("  Purchase? [y/n]: ", ["y", "n"])
                if confirm == "y":
                    player.credits -= heal_cost
                    healed = player.heal(15)
                    print(f"  Patched up: +{healed} HP ({player.hp}/{player.max_hp})")
                    if player.achievements:
                        player.achievements.check_credits_spent(heal_cost)
            else:
                print(f"  Insufficient credits ({player.credits}/{heal_cost})")
            press_enter()

        elif choice == "l":
            print(f"\n  {random.choice(_FAREWELLS)}")
            press_enter()
            break
