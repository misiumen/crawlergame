class_name AchievementsExtra
extends RefCounted
## HAND-AUTHORED achievements (Godot-only — the systems they track, like leveling,
## equipment, lifetime tallies and the show's darker running gags, don't exist in
## the pygame source, so they aren't generated). DCC in spirit, Vampire-Survivors
## in presentation: tiered (bronze→platinum), many with lifetime progress goals.
##
## Entry: {name, desc, category, hidden, tier, [stat, goal]}
##   tier  — "bronze" | "silver" | "gold" | "platinum"  (frame color + point value)
##   stat  — a LIFETIME counter key (see Achievements.bump); presence makes it a
##           progress achievement that auto-unlocks when the counter hits `goal`.
## Achievements with no stat are STATE-based: BoardView unlocks them on an event.

const EXTRA: Dictionary = {
	# ── Progression: the level track DCC runs on ─────────────────────────────
	"aw_poziom_2":  {"name": "Drugi poziom", "desc": "Awansowałeś. Produkcja udaje, że to robi wrażenie.", "category": "progression", "hidden": false, "tier": "bronze"},
	"aw_poziom_5":  {"name": "Rozkręcasz się", "desc": "Poziom 5. Widzowie zaczynają zapamiętywać twój numer.", "category": "progression", "hidden": false, "tier": "silver"},
	"aw_poziom_10": {"name": "Gwiazda sezonu", "desc": "Poziom 10. Masz już własny hashtag.", "category": "progression", "hidden": false, "tier": "gold"},
	"aw_poziom_15": {"name": "Legenda transmisji", "desc": "Poziom 15. Sponsorzy biją się o twoją skórę.", "category": "progression", "hidden": false, "tier": "platinum"},
	"aw_poziom_20": {"name": "Poza skalą", "desc": "Poziom 20 w jednym sezonie. To nie powinno być możliwe.", "category": "progression", "hidden": true, "tier": "platinum"},
	"pkt_5":  {"name": "Inwestor w siebie", "desc": "Rozdaj 5 punktów umiejętności.", "category": "progression", "hidden": false, "tier": "bronze", "stat": "skill_spent", "goal": 5},
	"pkt_15": {"name": "Samodoskonalenie do bólu", "desc": "Rozdaj 15 punktów umiejętności.", "category": "progression", "hidden": false, "tier": "silver", "stat": "skill_spent", "goal": 15},
	"cecha_str": {"name": "Tytan", "desc": "Siła 8. Pchasz ściany dla samej przyjemności.", "category": "progression", "hidden": false, "tier": "gold"},
	"cecha_dex": {"name": "Wirtuoz noża", "desc": "Zręczność 8. Trafiasz w to, na co nawet nie patrzysz.", "category": "progression", "hidden": false, "tier": "gold"},
	"cecha_int": {"name": "Szalony konstruktor", "desc": "Spryt 8. Z dwóch śmieci robisz trzeci, gorszy.", "category": "progression", "hidden": false, "tier": "gold"},

	# ── Mayhem: kills + damage (lifetime) ────────────────────────────────────
	"kill_10":  {"name": "Pierwsza dziesiątka", "desc": "Ubij 10 przeciwników (łącznie).", "category": "combat", "hidden": false, "tier": "bronze", "stat": "kills", "goal": 10},
	"kill_50":  {"name": "Rzeźnik z ramówki", "desc": "Ubij 50 przeciwników (łącznie).", "category": "combat", "hidden": false, "tier": "silver", "stat": "kills", "goal": 50},
	"kill_100": {"name": "Setka trupów", "desc": "Ubij 100 przeciwników (łącznie).", "category": "combat", "hidden": false, "tier": "gold", "stat": "kills", "goal": 100},
	"kill_250": {"name": "Klęska urodzaju", "desc": "Ubij 250 przeciwników (łącznie).", "category": "combat", "hidden": true, "tier": "platinum", "stat": "kills", "goal": 250},
	"dmg_1000": {"name": "Maszyna do mięsa", "desc": "Zadaj 1000 obrażeń (łącznie).", "category": "combat", "hidden": false, "tier": "silver", "stat": "damage", "goal": 1000},
	"dmg_5000": {"name": "Klęska żywiołowa", "desc": "Zadaj 5000 obrażeń (łącznie).", "category": "combat", "hidden": false, "tier": "gold", "stat": "damage", "goal": 5000},
	"boss_3":   {"name": "Pogromca finałów", "desc": "Ubij 3 bossów (łącznie).", "category": "combat", "hidden": false, "tier": "gold", "stat": "bosses", "goal": 3},
	"overkill": {"name": "Przesada", "desc": "Zadaj 30+ obrażeń jednym ciosem.", "category": "combat", "hidden": false, "tier": "silver"},
	"sever":    {"name": "Kolekcjoner kończyn", "desc": "Odetnij komuś kończynę. Pamiątka z odcinka.", "category": "combat", "hidden": false, "tier": "silver"},

	# ── Gear: the new equipment layer ────────────────────────────────────────
	"gear_first": {"name": "Ubrany na rozbiórkę", "desc": "Załóż swój pierwszy pancerz.", "category": "gear", "hidden": false, "tier": "bronze"},
	"gear_full":  {"name": "Garnitur z areny", "desc": "Głowa, tułów i nogi — komplet ze śmietnika.", "category": "gear", "hidden": false, "tier": "gold"},
	"gear_ac":    {"name": "Czołg z recyklingu", "desc": "Dobij do 18 AC. Wszyscy pudłują.", "category": "gear", "hidden": false, "tier": "silver"},
	"gear_dmg":   {"name": "Uzbrojony po zęby", "desc": "+6 do obrażeń z samych ulepszeń.", "category": "gear", "hidden": false, "tier": "silver"},

	# ── Stealth ──────────────────────────────────────────────────────────────
	"sneak_kill": {"name": "Cichy montaż", "desc": "Ubij przeciwnika, zanim się obudził.", "category": "stealth", "hidden": false, "tier": "silver"},
	"flawless":   {"name": "Bez jednego zadrapania", "desc": "Wyczyść pokój, nie tracąc HP.", "category": "stealth", "hidden": false, "tier": "gold"},

	# ── Fortune: lootboxes ───────────────────────────────────────────────────
	"box_5":     {"name": "Otwieracz", "desc": "Otwórz 5 skrzynek (łącznie).", "category": "loot", "hidden": false, "tier": "bronze", "stat": "boxes", "goal": 5},
	"box_25":    {"name": "Uzależniony od skrzynek", "desc": "Otwórz 25 skrzynek (łącznie).", "category": "loot", "hidden": false, "tier": "silver", "stat": "boxes", "goal": 25},
	"box_100":   {"name": "Hazard to nie problem", "desc": "Otwórz 100 skrzynek (łącznie).", "category": "loot", "hidden": true, "tier": "gold", "stat": "boxes", "goal": 100},
	"jackpot":   {"name": "Jackpot", "desc": "Trafiłeś SZCZĘŚCIE ×5 przy otwieraniu skrzynki.", "category": "loot", "hidden": false, "tier": "gold"},
	"legend_loot": {"name": "Widziałem legendę (naprawdę)", "desc": "Wyjmij legendarny przedmiot ze skrzynki.", "category": "loot", "hidden": false, "tier": "gold"},

	# ── Craft ────────────────────────────────────────────────────────────────
	"craft_crit": {"name": "Przypadkowy geniusz", "desc": "Pierwszy krytyczny sukces w warsztacie.", "category": "craft", "hidden": false, "tier": "bronze"},
	"craft_10":   {"name": "Majsterkowicz", "desc": "Stwórz 10 przedmiotów (łącznie).", "category": "craft", "hidden": false, "tier": "silver", "stat": "crafts", "goal": 10},
	"craft_50":   {"name": "Fabryka jednego człowieka", "desc": "Stwórz 50 przedmiotów (łącznie).", "category": "craft", "hidden": true, "tier": "gold", "stat": "crafts", "goal": 50},
	"recipe_5":   {"name": "Czytelnik instrukcji", "desc": "Odkryj 5 receptur (łącznie).", "category": "craft", "hidden": false, "tier": "silver", "stat": "recipes", "goal": 5},
	"backfire":   {"name": "Eksperyment się udał (prawie)", "desc": "Przeżyj backfire w warsztacie.", "category": "craft", "hidden": false, "tier": "bronze"},

	# ── Social: dialogue, audience, sponsors ─────────────────────────────────
	"talk_5":      {"name": "Gaduła", "desc": "Zakończ 5 rozmów (łącznie).", "category": "social", "hidden": false, "tier": "silver", "stat": "dialogues", "goal": 5},
	"skillcheck":  {"name": "Słowo jak miecz", "desc": "Zalicz krytyczny sukces w teście rozmowy.", "category": "social", "hidden": false, "tier": "gold"},
	"relationship":{"name": "Przyjaciel z areny", "desc": "Zdobądź czyjąś przyjaźń (relacja 3+).", "category": "social", "hidden": false, "tier": "gold"},
	"viral":       {"name": "Viralowy trup", "desc": "Osiągnij poziom widowni VIRAL.", "category": "audience", "hidden": false, "tier": "gold"},
	"sponsor_loyal":{"name": "Markowy faworyt", "desc": "Miej trzech sponsorów na maksymalnej uwadze.", "category": "sponsor", "hidden": false, "tier": "silver"},

	# ── Finale ───────────────────────────────────────────────────────────────
	"reach_final":  {"name": "W finale", "desc": "Dotrzyj do areny finałowej.", "category": "floor", "hidden": false, "tier": "silver"},
	"win":          {"name": "Mistrz sezonu", "desc": "Wygraj cały sezon.", "category": "floor", "hidden": false, "tier": "gold"},
	"win_pacifist": {"name": "Bez jednego trupa", "desc": "Wygraj, nie zabijając nikogo.", "category": "floor", "hidden": true, "tier": "platinum"},
	"win_lowlevel": {"name": "Underdog", "desc": "Wygraj poniżej 8 poziomu.", "category": "floor", "hidden": true, "tier": "platinum"},

	# ── Infamy: the show LOVES a good cancellation ───────────────────────────
	"die_1":      {"name": "Anulowano po pierwszym odcinku", "desc": "Zgiń. Widownia i tak klaszcze.", "category": "infamy", "hidden": false, "tier": "bronze"},
	"die_floor1": {"name": "Krótki sezon", "desc": "Zgiń na pierwszym piętrze.", "category": "infamy", "hidden": true, "tier": "bronze"},
	"die_rat":    {"name": "Pożarty przez statystę", "desc": "Daj się zabić najsłabszemu potworowi.", "category": "infamy", "hidden": true, "tier": "silver"},
	"die_5":      {"name": "Recydywa", "desc": "Zgiń 5 razy (łącznie).", "category": "infamy", "hidden": false, "tier": "silver", "stat": "deaths", "goal": 5},
	"die_rich":   {"name": "Nie zdążyłeś otworzyć", "desc": "Zgiń z nieotwartą skrzynką w plecaku.", "category": "infamy", "hidden": true, "tier": "silver"},

	# ── Meta: chasing the list itself ────────────────────────────────────────
	"narcyz":       {"name": "Narcyz", "desc": "Otworzyłeś tę listę. Widzowie też lubią patrzeć na siebie.", "category": "meta", "hidden": true, "tier": "bronze"},
	"first_ach":    {"name": "Pierwszy medal", "desc": "Zdobądź pierwsze osiągnięcie.", "category": "meta", "hidden": false, "tier": "bronze"},
	"collector_10": {"name": "Kolekcjoner", "desc": "Odblokuj 10 osiągnięć.", "category": "meta", "hidden": false, "tier": "silver"},
	"collector_25": {"name": "Łowca trofeów", "desc": "Odblokuj 25 osiągnięć.", "category": "meta", "hidden": false, "tier": "gold"},
	"collector_50": {"name": "Maniak kompletu", "desc": "Odblokuj 50 osiągnięć.", "category": "meta", "hidden": false, "tier": "platinum"},
	"platinum_all": {"name": "Sto procent", "desc": "Wszystkie osiągnięcia. Nie masz życia poza areną.", "category": "meta", "hidden": true, "tier": "platinum"},
	"classes_3":    {"name": "Kryzys tożsamości", "desc": "Przyjmij klasę 3 razy (łącznie, różne podejścia).", "category": "meta", "hidden": false, "tier": "silver", "stat": "classes", "goal": 3},
}

## Stable display order (the dict above keeps insertion order, but be explicit).
const EXTRA_ORDER: Array = [
	"aw_poziom_2", "aw_poziom_5", "aw_poziom_10", "aw_poziom_15", "aw_poziom_20",
	"pkt_5", "pkt_15", "cecha_str", "cecha_dex", "cecha_int",
	"kill_10", "kill_50", "kill_100", "kill_250", "dmg_1000", "dmg_5000", "boss_3", "overkill", "sever",
	"gear_first", "gear_full", "gear_ac", "gear_dmg",
	"sneak_kill", "flawless",
	"box_5", "box_25", "box_100", "jackpot", "legend_loot",
	"craft_crit", "craft_10", "craft_50", "recipe_5", "backfire",
	"talk_5", "skillcheck", "relationship", "viral", "sponsor_loyal",
	"reach_final", "win", "win_pacifist", "win_lowlevel",
	"die_1", "die_floor1", "die_rat", "die_5", "die_rich",
	"narcyz", "first_ach", "collector_10", "collector_25", "collector_50", "platinum_all", "classes_3",
]
