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
	"aw_poziom_2":  {"name": "Drugi poziom", "desc": "Poziom 2. Awansowałeś. System odnotował, produkcja udaje entuzjazm.", "category": "progression", "hidden": false, "tier": "bronze"},
	"aw_poziom_5":  {"name": "Rozkręcasz się", "desc": "Poziom 5. Widzowie zaczynają zapamiętywać twój numer startowy. Niektórzy nawet kibicują.", "category": "progression", "hidden": false, "tier": "silver"},
	"aw_poziom_10": {"name": "Gwiazda sezonu", "desc": "Poziom 10. Masz własny hashtag i przynajmniej jednego stalkera w innej galaktyce.", "category": "progression", "hidden": false, "tier": "gold"},
	"aw_poziom_15": {"name": "Legenda transmisji", "desc": "Poziom 15. Sponsorzy biją się o prawa do twojej skóry. Dosłownie.", "category": "progression", "hidden": false, "tier": "platinum"},
	"aw_poziom_20": {"name": "Poza skalą", "desc": "Poziom 20 w jednym sezonie. System sprawdza, czy to nie błąd. Nie jest.", "category": "progression", "hidden": true, "tier": "platinum"},
	"pkt_5":  {"name": "Inwestor w siebie", "desc": "Pięć punktów wydanych na siebie. Inwestycja w aktywo o krótkiej żywotności.", "category": "progression", "hidden": false, "tier": "bronze", "stat": "skill_spent", "goal": 5},
	"pkt_15": {"name": "Samodoskonalenie do bólu", "desc": "Piętnaście punktów rozdanych. Samodoskonalenie na arenie śmierci. Urocze.", "category": "progression", "hidden": false, "tier": "silver", "stat": "skill_spent", "goal": 15},
	"cecha_str": {"name": "Tytan", "desc": "Siła 8. Pchasz ściany dla zabawy. Widownia płaci za destrukcję.", "category": "progression", "hidden": false, "tier": "gold"},
	"cecha_dex": {"name": "Wirtuoz noża", "desc": "Zręczność 8. Trafiasz w to, na co nawet nie patrzysz. Kamerzyści cię nienawidzą.", "category": "progression", "hidden": false, "tier": "gold"},
	"cecha_int": {"name": "Szalony konstruktor", "desc": "Spryt 8. Z dwóch śmieci robisz trzeci, gorszy. Sponsorzy techniczni przysyłają próbki.", "category": "progression", "hidden": false, "tier": "gold"},

	# ── Mayhem: kills + damage (lifetime) ────────────────────────────────────
	"kill_10":  {"name": "Pierwsza dziesiątka", "desc": "Dziesięć trupów. System przestał liczyć cię jako statystę.", "category": "combat", "hidden": false, "tier": "bronze", "stat": "kills", "goal": 10},
	"kill_50":  {"name": "Rzeźnik z ramówki", "desc": "Pięćdziesiąt zabitych łącznie. Rzeźnik ramówki. Producent dopisuje cię do plakatu.", "category": "combat", "hidden": false, "tier": "silver", "stat": "kills", "goal": 50},
	"kill_100": {"name": "Setka trupów", "desc": "Setka ciał. Gdzieś powstaje o tobie ballada. W większości jest o krwi.", "category": "combat", "hidden": false, "tier": "gold", "stat": "kills", "goal": 100},
	"kill_250": {"name": "Klęska urodzaju", "desc": "250 zabitych. Nawet System zrobił pauzę. Widzowie nie.", "category": "combat", "hidden": true, "tier": "platinum", "stat": "kills", "goal": 250},
	"dmg_1000": {"name": "Maszyna do mięsa", "desc": "Tysiąc obrażeń łącznie. Maszyna do mięsa działa zgodnie ze specyfikacją.", "category": "combat", "hidden": false, "tier": "silver", "stat": "damage", "goal": 1000},
	"dmg_5000": {"name": "Klęska żywiołowa", "desc": "Pięć tysięcy obrażeń. Klęska żywiołowa z numerem startowym.", "category": "combat", "hidden": false, "tier": "gold", "stat": "damage", "goal": 5000},
	"boss_3":   {"name": "Pogromca finałów", "desc": "Trzech bossów na koncie. Zarząd Lochu prosi o spotkanie. Nie idź.", "category": "combat", "hidden": false, "tier": "gold", "stat": "bosses", "goal": 3},
	"overkill": {"name": "Przesada", "desc": "30+ obrażeń jednym ciosem. Przesada to za mało powiedziane. Widzowie uwielbiają.", "category": "combat", "hidden": false, "tier": "silver"},
	"sever":    {"name": "Kolekcjoner kończyn", "desc": "Odciąłeś komuś kończynę. Kamera zrobiła zbliżenie. Pamiątka z odcinka gotowa.", "category": "combat", "hidden": false, "tier": "silver"},

	# ── Gear: the new equipment layer ────────────────────────────────────────
	"gear_first": {"name": "Ubrany na rozbiórkę", "desc": "Założyłeś coś, co nie jest bronią. System gratuluje instynktu samozachowawczego.", "category": "gear", "hidden": false, "tier": "bronze"},
	"gear_full":  {"name": "Garnitur z areny", "desc": "Głowa, tułów, nogi — komplet ze śmietnika. Wyglądasz jak zwycięzca taniej kategorii.", "category": "gear", "hidden": false, "tier": "gold"},
	"gear_ac":    {"name": "Czołg z recyklingu", "desc": "18 AC ze złomu. Czołg z recyklingu. Wszyscy pudłują, widzowie ziewają.", "category": "gear", "hidden": false, "tier": "silver"},
	"gear_dmg":   {"name": "Uzbrojony po zęby", "desc": "+6 obrażeń z samych ulepszeń. Uzbrojony po zęby, których już połowy nie masz.", "category": "gear", "hidden": false, "tier": "silver"},

	# ── Stealth ──────────────────────────────────────────────────────────────
	"sneak_kill": {"name": "Cichy montaż", "desc": "Zabiłeś coś, zanim się obudziło. Cichy montaż. Widownia woli krzyk, ale liczy się wynik.", "category": "stealth", "hidden": false, "tier": "silver"},
	"flawless":   {"name": "Bez jednego zadrapania", "desc": "Wyczyściłeś pokój bez jednego zadrapania. Podejrzanie czysto. Reżyser sprawdza powtórki.", "category": "stealth", "hidden": false, "tier": "gold"},

	# ── Fortune: lootboxes ───────────────────────────────────────────────────
	"box_5":     {"name": "Otwieracz", "desc": "Pięć skrzynek otwartych. Hazard z gwarancją. Syndykat liczy na nawyk.", "category": "loot", "hidden": false, "tier": "bronze", "stat": "boxes", "goal": 5},
	"box_25":    {"name": "Uzależniony od skrzynek", "desc": "25 skrzynek. Uzależnienie potwierdzone klinicznie. Sponsorzy dosypują.", "category": "loot", "hidden": false, "tier": "silver", "stat": "boxes", "goal": 25},
	"box_100":   {"name": "Hazard to nie problem", "desc": "Setka skrzynek. To już nie loot, to terapia, której Loch ci nie zafunduje.", "category": "loot", "hidden": true, "tier": "gold", "stat": "boxes", "goal": 100},
	"jackpot":   {"name": "Jackpot", "desc": "SZCZĘŚCIE x5. Maszyna zapiszczała, widownia oszalała, a ty i tak stąd nie wyjdziesz bogaty.", "category": "loot", "hidden": false, "tier": "gold"},
	"legend_loot": {"name": "Widziałem legendę (naprawdę)", "desc": "Legenda ze skrzynki. Widziałeś ją naprawdę. Na ekranach pół wszechświata też.", "category": "loot", "hidden": false, "tier": "gold"},

	# ── Craft ────────────────────────────────────────────────────────────────
	"craft_crit": {"name": "Przypadkowy geniusz", "desc": "Pierwszy krytyczny craft. Przypadkowy geniusz. System dopisał gwiazdkę przy słowie przypadkowy.", "category": "craft", "hidden": false, "tier": "bronze"},
	"craft_10":   {"name": "Majsterkowicz", "desc": "Dziesięć rzeczy stworzonych. Majsterkowicz z licencją na desperację.", "category": "craft", "hidden": false, "tier": "silver", "stat": "crafts", "goal": 10},
	"craft_50":   {"name": "Fabryka jednego człowieka", "desc": "Pięćdziesiąt przedmiotów. Fabryka jednego człowieka. Związki zawodowe milczą.", "category": "craft", "hidden": true, "tier": "gold", "stat": "crafts", "goal": 50},
	"recipe_5":   {"name": "Czytelnik instrukcji", "desc": "Pięć receptur odkrytych. Czytasz instrukcje, których nikt ci nie dał.", "category": "craft", "hidden": false, "tier": "silver", "stat": "recipes", "goal": 5},
	"backfire":   {"name": "Eksperyment się udał (prawie)", "desc": "Przeżyłeś backfire. Eksperyment się udał. Prawie. Liczy się, że przeżyłeś.", "category": "craft", "hidden": false, "tier": "bronze"},

	# ── Social: dialogue, audience, sponsors ─────────────────────────────────
	"talk_5":      {"name": "Gaduła", "desc": "Pięć rozmów dobiegło końca. Gaduła areny. Widzowie przewijają, ale liczy się.", "category": "social", "hidden": false, "tier": "silver", "stat": "dialogues", "goal": 5},
	"skillcheck":  {"name": "Słowo jak miecz", "desc": "Krytyczny sukces w teście. Słowo jak miecz, i mniej krwi na kamerze.", "category": "social", "hidden": false, "tier": "gold"},
	"relationship":{"name": "Przyjaciel z areny", "desc": "Zdobyłeś czyjąś przyjaźń na arenie śmierci. Statystycznie to się nie opłaca. Brawo.", "category": "social", "hidden": false, "tier": "gold"},
	"viral":       {"name": "Viralowy trup", "desc": "Poziom VIRAL. Jesteś viralowym trupem w trakcie. Marzenie każdego producenta.", "category": "audience", "hidden": false, "tier": "gold"},
	"sponsor_loyal":{"name": "Markowy faworyt", "desc": "Trzech sponsorów cię uwielbia. Trzy loga, trzy ceny na głowie, jeden ty.", "category": "sponsor", "hidden": false, "tier": "silver"},

	# ── Finale ───────────────────────────────────────────────────────────────
	"reach_final":  {"name": "W finale", "desc": "Dotarłeś do areny finałowej. System otworzył nową kategorię zakładów: czy przeżyje.", "category": "floor", "hidden": false, "tier": "silver"},
	"win":          {"name": "Mistrz sezonu", "desc": "Wygrałeś cały sezon. Mistrz. Syndykat już szuka kogoś, kto cię pobije w następnym.", "category": "floor", "hidden": false, "tier": "gold"},
	"win_pacifist": {"name": "Bez jednego trupa", "desc": "Wygrałeś, nie zabijając nikogo. System nie ma na to przycisku. Widzowie też nie.", "category": "floor", "hidden": true, "tier": "platinum"},
	"win_lowlevel": {"name": "Underdog", "desc": "Wygrałeś poniżej 8 poziomu. Underdog. Bukmacherzy płaczą w trzech układach gwiezdnych.", "category": "floor", "hidden": true, "tier": "platinum"},

	# ── Infamy: the show LOVES a good cancellation ───────────────────────────
	"die_1":      {"name": "Anulowano po pierwszym odcinku", "desc": "Zginąłeś. Anulowano po pierwszym odcinku. Widownia i tak klaszcze — lubi finały.", "category": "infamy", "hidden": false, "tier": "bronze"},
	"die_floor1": {"name": "Krótki sezon", "desc": "Zginąłeś na pierwszym piętrze. Najkrótszy sezon w historii. Sponsorzy żądają zwrotu.", "category": "infamy", "hidden": true, "tier": "bronze"},
	"die_rat":    {"name": "Pożarty przez statystę", "desc": "Zabił cię najsłabszy potwór. Pożarty przez statystę. Klip leci w pętli na Kanale 7.", "category": "infamy", "hidden": true, "tier": "silver"},
	"die_5":      {"name": "Recydywa", "desc": "Pięć zgonów łącznie. Recydywa. System rezerwuje ci stały numer w kostnicy.", "category": "infamy", "hidden": false, "tier": "silver", "stat": "deaths", "goal": 5},
	"die_rich":   {"name": "Nie zdążyłeś otworzyć", "desc": "Zginąłeś z nieotwartą skrzynką. Nie zdążyłeś. Syndykat zatrzymuje zawartość. Regulamin.", "category": "infamy", "hidden": true, "tier": "silver"},

	# ── Meta: chasing the list itself ────────────────────────────────────────
	"narcyz":       {"name": "Narcyz", "desc": "Otworzyłeś listę własnych osiągnięć. Narcyz. Widzowie też lubią patrzeć na siebie.", "category": "meta", "hidden": true, "tier": "bronze"},
	"first_ach":    {"name": "Pierwszy medal", "desc": "Pierwszy medal. System odnotował, że istniejesz. Na razie.", "category": "meta", "hidden": false, "tier": "bronze"},
	"collector_10": {"name": "Kolekcjoner", "desc": "Dziesięć osiągnięć. Kolekcjoner. Trofea ważą tyle, co twoje szanse.", "category": "meta", "hidden": false, "tier": "silver"},
	"collector_25": {"name": "Łowca trofeów", "desc": "25 osiągnięć. Łowca trofeów. Producent zaczyna podejrzewać, że ci się podoba.", "category": "meta", "hidden": false, "tier": "gold"},
	"collector_50": {"name": "Maniak kompletu", "desc": "50 osiągnięć. Maniak kompletu. Nie masz życia poza areną. Areny też długo nie będziesz miał.", "category": "meta", "hidden": false, "tier": "platinum"},
	"platinum_all": {"name": "Sto procent", "desc": "Wszystkie osiągnięcia. Sto procent. System nie ma już czym cię zaskoczyć — zostaje tylko Loch.", "category": "meta", "hidden": true, "tier": "platinum"},
	"classes_3":    {"name": "Kryzys tożsamości", "desc": "Trzy razy przyjąłeś klasę. Kryzys tożsamości na żywej antenie. Widzowie głosują na czwartą.", "category": "meta", "hidden": false, "tier": "silver", "stat": "classes", "goal": 3},
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
