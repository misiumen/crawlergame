"""P29.27 — handler modules extracted from engine/game.py.

The 6900-line Game class was a maintenance bomb. This package
breaks individual handler clusters out as free functions that
take a Game instance + intent, keeping game.py as a thin
dispatcher. The Game class still owns state; handlers just
operate on it.

P29.27 ships:
  credit_sinks — _attempt_train_stat / bribe / call_pod /
                 upgrade_loadout (P29.19)

Future passes can extract:
  combat       — _combat_attack and friends
  inventory    — wield/wear/consume/use
  social       — memetic/exploit/invoke
"""
