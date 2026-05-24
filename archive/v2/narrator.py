"""CRAWL PROTOCOL v2 - The Syndicate broadcast voice."""
import random

_LINES = {
    "enter_floor": [
        "Welcome to Floor {floor}. The Syndicate hopes you find it educational.",
        "Floor {floor} is live. Ratings are being tracked. Don't waste the airtime.",
        "Descending to Floor {floor}. Your audience has been notified.",
        "Floor {floor} access confirmed. Sponsor message incoming in 3... 2...",
    ],
    "enter_room": [
        "New room. New opportunity to disappoint everyone watching.",
        "The Protocol logs your position. The audience logs their expectations.",
        "A room. Whether it kills you is, frankly, good for ratings either way.",
        "Entering unknown space. The Syndicate finds your bravery statistically unusual.",
        "Another room. The crawler persists. Sponsors are cautiously optimistic.",
    ],
    "combat_start": [
        "Engagement detected. Ratings spike in 3, 2, 1.",
        "Combat initiated. The Syndicate has alerted premium subscribers.",
        "A fight! Finally. The last three rooms were a ratings disaster.",
        "Violence detected. This is what the audience came for.",
        "Hostile contact. Try not to make it boring.",
    ],
    "critical_hit": [
        "Critical hit! That was BRUTAL. Ratings through the ceiling.",
        "Natural 20. The crowd goes absolutely feral.",
        "Maximum damage. A sponsor just paid extra for that replay.",
        "That's going in the highlight reel. Incredible.",
    ],
    "critical_miss": [
        "Natural 1. The Syndicate is embarrassed on your behalf.",
        "Critical miss. A child watching just turned it off.",
        "You have fumbled in spectacular fashion. The Protocol notes this.",
        "That was painful to watch. And we broadcast pain professionally.",
    ],
    "player_death": [
        "Contestant eliminated. The Syndicate thanks you for your service.",
        "Signal terminated. Your slot will be filled within the hour.",
        "You have died. The audience has already moved on. Brutal, but fair.",
        "Flatline confirmed. The Protocol recycles its resources efficiently.",
        "Game over. Your personal effects will be auctioned for ratings.",
    ],
    "level_up": [
        "Level increase detected. The crawler grows stronger. Unfortunate for the dungeon.",
        "Leveled up. The Syndicate is adjusting difficulty accordingly.",
        "Growth logged. You are becoming a problem. The audience loves it.",
        "New level achieved. Sponsors are bidding on your next encounter.",
    ],
    "loot_found": [
        "Loot acquired. The Syndicate reminds you that all items are sponsor-approved.",
        "Item found. Your net worth has increased by a number the dungeon resents.",
        "Acquisition logged. The Protocol calculates your improved survivability.",
        "Loot secured. The dungeon is filing a complaint with management.",
    ],
    "box_opened": [
        "Box opened. The audience holds its breath. Mostly.",
        "Contents revealed. The Syndicate takes a small finder's fee.",
        "A box, opened. Whatever is inside, you earned it. Statistically.",
        "Box contents logged. A sponsor has already branded them.",
    ],
    "class_earned": [
        "Class designation confirmed. You are no longer Unclassified. Congratulations.",
        "Class Box opened. The dungeon has formally categorized your threat level.",
        "Class assigned. The Syndicate updates your official contestant profile.",
        "You have a Class now. The audience cheers. Primarily for entertainment value.",
    ],
    "rest": [
        "Short rest logged. The Syndicate notes you are still breathing.",
        "Recovery detected. Try not to need this so often.",
        "Resting. The audience is watching you breathe. Make it interesting.",
        "Downtime. The Protocol uses this to recalibrate nearby threats.",
    ],
    "merchant": [
        "Merchant contact established. The Syndicate takes 15% of all transactions.",
        "A vendor. In a dungeon. Somehow this makes perfect sense here.",
        "Commerce detected. The Protocol approves. Sort of.",
        "Merchant located. Their prices reflect the local danger premium.",
    ],
    "flee": [
        "Retreat logged. The Syndicate is disappointed but understands.",
        "Fleeing. Strategically. That's the official story.",
        "You ran. The audience is split on whether that was cowardly or smart.",
        "Escape confirmed. The Protocol will note this in your profile.",
    ],
    "boss_death": [
        "Floor boss eliminated. The Syndicate was not expecting that.",
        "Boss defeated. A production assistant just got fired for not betting on you.",
        "Major threat neutralized. Audience engagement: unprecedented.",
        "The floor boss is dead. The Protocol is recalculating everything.",
    ],
    "checkpoint": [
        "Checkpoint reached. The Syndicate grants you a moment of safety. A moment.",
        "Safe zone accessed. The dungeon isn't allowed to kill you here. Technically.",
        "Checkpoint logged. Sponsors are refreshing their bids for the next floor.",
        "Safe zone. Breathe. The cameras are still rolling, but they're polite cameras.",
    ],
    "audience_up": [
        "Ratings increase! The audience is engaged. Keep it up.",
        "Viewer count rising. You are becoming a phenomenon.",
        "Audience approval detected. A sponsor just doubled their investment.",
        "The crowd loves you right now. Don't waste it.",
    ],
    "audience_down": [
        "Ratings dip. The audience grows bored. Do something.",
        "Viewer count falling. The Protocol is considering intervention.",
        "Audience losing interest. May we suggest more violence?",
        "Engagement dropping. The Syndicate is concerned.",
    ],
    "trap_triggered": [
        "Trap activated. The audience winced. Some of them, anyway.",
        "You have triggered a trap. The Protocol designed it specifically for people like you.",
        "Trap sprung. This is why contestants are warned to look down.",
        "Hazard contact logged. The dungeon smiles, metaphorically.",
    ],
    "trap_disarmed": [
        "Trap disabled. Impressive. The dungeon is annoyed.",
        "Hazard neutralized. The Protocol will install a better one next time.",
        "Trap disarmed. A sponsor just sent you a gift. It's also a trap.",
        "Nice work. The audience approves of competence.",
    ],
    "mutation": [
        "Mutation event logged. Your DNA is filing a complaint.",
        "Physical alteration detected. The Syndicate updates your threat rating.",
        "Mutation acquired. You are now 12% less human. The audience loves it.",
        "Genetic variance confirmed. You are becoming something the dungeon hasn't seen before.",
    ],
    # Step 12 — new categories
    "env_kill": [
        "Środowisko zrobiło robotę za ciebie. Widownia bije brawo.",
        "Kreatywne. Bestialskie. Wysoka oglądalność.",
        "Loch sam się skarży na ciebie do działu prawnego.",
        "Sponsor ledwo nadążył z reklamą. Bardzo zadowolony.",
        "Niewybredna metoda. Widownia kocha niewybredne metody.",
    ],
    "creative_solution": [
        "Syndykat zapisuje. To było zaskakująco eleganckie.",
        "Widownia: 'znowu to zrobi?' Syndykat: 'lepiej dla wszystkich, jeśli tak.'",
        "Twoja kreatywność zmienia plany scenarzystów na następny tydzień.",
    ],
    "race_pick": [
        "Loch zarejestrował twoją nową formę. To go zaintrygowało.",
        "Twoja klasyfikacja gatunkowa: zaktualizowana. Klucz zmieniony.",
        "Sponsor zmienił kontrakt w połowie zdania. To dobry znak.",
    ],
    "class_suggested": [
        "Syndykat sugeruje klasę. Widownia już głosuje.",
        "Twój styl gry został rozpoznany. Loch ma propozycje.",
        "Analiza behawioralna: gotowe. Wybór klasy: czeka na ciebie.",
    ],
    "crawler_encountered": [
        "Inny zawodnik. Widownia podwaja zakłady.",
        "Spotkanie zawodników. Liczba widzów rośnie skokowo.",
        "Statystycznie: jeden z was nie wyjdzie. Tym bardziej ciekawie.",
    ],
    "safehouse_visit": [
        "Safehouse. Reklamy sponsorów aktywne. Kamery uprzejme.",
        "Bezpieczna strefa. To znaczy, że jest tylko trochę niebezpiecznie.",
        "Loch zawiesza wrogi tryb. Tylko tu. Tylko teraz.",
    ],
    "language_switched": [
        "Język transmisji zmieniony. Sponsorzy obu rynków zadowoleni.",
        "Transkrypcja zaktualizowana w 47 językach jednocześnie.",
    ],
    "achievement_unlock": [
        "Osiągnięcie. Widownia notuje. Sponsor wpłaca premię.",
        "Loch zarejestrował twoje osiągnięcie. Algorytm cię polubił.",
    ],
    "dialog_tense": [
        "Słychać kliknięcie bezpiecznika. Widownia wstrzymuje oddech.",
        "Rozmowa zaczyna pachnieć krwią. Wskaźnik widowni rośnie.",
    ],
    "dialog_friendly": [
        "Ktoś tu komuś ufa. Loch nie wie, jak to obsłużyć.",
        "Współpraca zawodników: rzadkie. Audytoryjne. Zyski sponsorów.",
    ],
}


class Narrator:
    def get(self, category, **kwargs):
        # Prefer localized variants: narrator_<category>_1 .. _6
        from lang import tr, has_key
        candidates = []
        for i in range(1, 7):
            key = f"narrator_{category}_{i}"
            if has_key(key):
                candidates.append(tr(key))
        if not candidates:
            # Fall back to inline English/PL pool
            candidates = _LINES.get(category, ["..."])
        line = random.choice(candidates) if candidates else "..."
        try:
            return line.format(**kwargs)
        except (KeyError, ValueError, IndexError):
            return line

    def say(self, category, **kwargs):
        return self.get(category, **kwargs)


_NARRATOR = None


def get_narrator():
    global _NARRATOR
    if _NARRATOR is None:
        _NARRATOR = Narrator()
    return _NARRATOR
