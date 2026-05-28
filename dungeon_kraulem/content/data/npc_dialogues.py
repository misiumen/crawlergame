"""Drzewka dialogowe NPC — Polish-native content.

P29.41 — silnik (engine/dialogue.py).
P29.59 — pierwsze 3 prawdziwe drzewka z treścią:
  * default_crawler — generic dla random crawler spawnowanych przez
    procgen
  * liga_brawurowa_grunt — Kapitan Drużyny, Trener Szkoleniowiec
    (faction:liga)
  * intake_warden — Strażnik Bramy (F1 floor boss)

Każde drzewko ma 4-6 nodów, start + odpowiedzi gracza + minimum 1
mechaniczna konsekwencja (audience / sponsor / item / flag).

Zasada Polish-native (Reguła 8 z feedback_polish_only_imperatyw):
KRYTYCZNE — żadnych kalk z angielskiego. Każde zdanie napisane jak
żywy polski tekst, sprawdzone na głos.

NPC entity ma w state polu `dialogue_tree_key`. Brak → fallback do
starego skill check.
"""
from __future__ import annotations
from ...engine.dialogue import (
    DialogueTree, DialogueNode, DialogueOption, register_tree,
)


# ── default_crawler — generic random crawler (vet/scavenger/runner) ──

def _build_default_crawler_tree() -> DialogueTree:
    """Drzewko dla losowo spawnowanego crawlera bez własnej tożsamości.
    Treść ogólna — pasuje weteranowi, padlinożercy, medycowi. Daje
    graczowi 3 ścieżki: rozeznanie (info), współpracę (alliance),
    siłową dominację (intimidate)."""
    return DialogueTree(
        tree_key="default_crawler",
        start_node="start",
        nodes={
            "start": DialogueNode(
                node_id="start",
                speaker="Zawodnik",
                text=("Mierzy cię od stóp do głów. Zaciska pas, "
                      "patrzy gdzie masz ręce. „Co masz, czego ja "
                      "nie mam?"),
                options=[
                    DialogueOption(
                        label="Spytaj, skąd jest i jak długo tu siedzi.",
                        next_node_id="origin",
                    ),
                    DialogueOption(
                        label="Spytaj o najbliższy bezpieczny pokój.",
                        next_node_id="safehouse_tip",
                    ),
                    DialogueOption(
                        label="Spróbuj wciągnąć go w sojusz. (CHA, TT 11)",
                        skill_check=("CHA", 11),
                        next_node_id="ally_ok",
                        fail_node_id="ally_fail",
                    ),
                    DialogueOption(
                        label="Ostrzeż, że masz lepszą broń. (CHA, TT 13)",
                        skill_check=("CHA", 13),
                        next_node_id="intimidate_ok",
                        fail_node_id="intimidate_fail",
                    ),
                    DialogueOption(
                        label="Skiń głową i idź dalej.",
                        next_node_id=None,
                        consequences=[{"kind": "end"}],
                    ),
                ],
            ),
            "origin": DialogueNode(
                node_id="origin",
                speaker="Zawodnik",
                text=("„Łazienka biurowa, środa po szóstej. Wrzucili "
                      "mnie tu z kubkiem w ręce.” Patrzy na sufit. "
                      "„Trzeci dzień. Nie wiem, czy zegar tu chodzi "
                      "uczciwie.”"),
                options=[
                    DialogueOption(
                        label="Spytaj, czego się tu nauczył.",
                        next_node_id="lesson",
                    ),
                    DialogueOption(
                        label="Wracaj do głównego pytania.",
                        next_node_id="start",
                    ),
                    DialogueOption(
                        label="Zostaw go w spokoju.",
                        next_node_id=None,
                        consequences=[{"kind": "end"}],
                    ),
                ],
            ),
            "lesson": DialogueNode(
                node_id="lesson",
                speaker="Zawodnik",
                text=("„Nie biegnij na bossa głodny. Nie ufaj "
                      "automatom przy ścianach. Sponsor mówiący "
                      "miło to sponsor sprzedający cię niżej.”"),
                on_enter_consequences=[
                    {"kind": "audience", "amount": 1,
                     "source": "dialogue_lesson"},
                ],
                options=[
                    DialogueOption(
                        label="Podziękuj i odejdź.",
                        next_node_id=None,
                        consequences=[{"kind": "end"}],
                    ),
                ],
            ),
            "safehouse_tip": DialogueNode(
                node_id="safehouse_tip",
                speaker="Zawodnik",
                text=("„Drugi korytarz po lewej. Pachnie kawą. "
                      "Tam się sypia. Jeśli kelner pyta, mówisz, "
                      "że jesteś z trzeciej zmiany.”"),
                on_enter_consequences=[
                    {"kind": "audience", "amount": 1,
                     "source": "dialogue_tip"},
                ],
                options=[
                    DialogueOption(
                        label="Skiń i odejdź.",
                        next_node_id=None,
                        consequences=[{"kind": "end"}],
                    ),
                ],
            ),
            "ally_ok": DialogueNode(
                node_id="ally_ok",
                speaker="Zawodnik",
                text=("Wzdycha. „No dobra. Idziesz w lewo, ja "
                      "w prawo. Jak słyszysz krzyk, to nie ja. "
                      "Albo ja, ale i tak nie pomożesz.”"),
                on_enter_consequences=[
                    {"kind": "audience", "amount": 2,
                     "source": "dialogue_ally"},
                    {"kind": "log",
                     "text": "Konferansjer (cicho): „Sojusz. "
                             "Widownia kocha sojusze. Do pierwszej "
                             "zdrady.”",
                     "severity": "normal"},
                ],
                options=[
                    DialogueOption(
                        label="Rozstać się.",
                        next_node_id=None,
                        consequences=[{"kind": "end"}],
                    ),
                ],
            ),
            "ally_fail": DialogueNode(
                node_id="ally_fail",
                speaker="Zawodnik",
                text=("Prycha. „Nie znam cię. Sojusze są dla "
                      "płaczących. Idź swoim.”"),
                on_enter_consequences=[
                    {"kind": "log",
                     "text": "Brzmiało gorzej, niż chciałeś.",
                     "severity": "warn"},
                ],
                options=[
                    DialogueOption(
                        label="Odejść.",
                        next_node_id=None,
                        consequences=[{"kind": "end"}],
                    ),
                ],
            ),
            "intimidate_ok": DialogueNode(
                node_id="intimidate_ok",
                speaker="Zawodnik",
                text=("Robi krok w tył. „Dobra. Tylko nie patrz "
                      "mi na ręce. Ja nie patrzę na twoje.”"),
                on_enter_consequences=[
                    {"kind": "audience", "amount": 2,
                     "source": "dialogue_intimidate"},
                ],
                options=[
                    DialogueOption(
                        label="Pozwolić mu odejść.",
                        next_node_id=None,
                        consequences=[{"kind": "end"}],
                    ),
                ],
            ),
            "intimidate_fail": DialogueNode(
                node_id="intimidate_fail",
                speaker="Zawodnik",
                text=("Śmieje się jednym dźwiękiem. „Lepszą broń? "
                      "Pokaż.” Nie ruszył się o krok."),
                on_enter_consequences=[
                    {"kind": "audience", "amount": -1,
                     "source": "dialogue_intimidate_fail"},
                ],
                options=[
                    DialogueOption(
                        label="Odejść bez słowa.",
                        next_node_id=None,
                        consequences=[{"kind": "end"}],
                    ),
                ],
            ),
        },
    )


# ── liga_brawurowa_grunt — Kapitan Drużyny / Trener Szkoleniowiec ───

def _build_liga_brawurowa_tree() -> DialogueTree:
    """Drzewko dla mini-bossów z faction:liga (F2). Sportowy klub,
    teatralny ton. Gracz może: dowiedzieć się o klubie (info), spróbować
    odkupić przejście (kredyty), wyzwać na pojedynek (audience reward),
    albo wyjść (i prawdopodobnie dostać atak)."""
    return DialogueTree(
        tree_key="liga_brawurowa_grunt",
        start_node="start",
        nodes={
            "start": DialogueNode(
                node_id="start",
                speaker="Klubowy",
                text=("Stuk-stuk pałką o własną dłoń. „Witaj w "
                      "naszym sektorze. Liga przyjmuje wpisowe. "
                      "Lub trofea. Lub krew. Wybór twój.”"),
                options=[
                    DialogueOption(
                        label="Spytaj, co to za klub.",
                        next_node_id="about_klub",
                    ),
                    DialogueOption(
                        label="Zapłać wpisowe (25 kr).",
                        next_node_id="bribe_paid",
                        requires_flag="has_25_credits",
                    ),
                    DialogueOption(
                        label="Wyzwij go na czysty pojedynek. "
                              "(CHA, TT 13)",
                        skill_check=("CHA", 13),
                        next_node_id="duel_ok",
                        fail_node_id="duel_fail",
                    ),
                    DialogueOption(
                        label="Powiedz, że jesteś z innego sektora.",
                        next_node_id=None,
                        consequences=[
                            {"kind": "log",
                             "text": "Klubowy nie wierzy. Patrzy ci "
                                     "w plecy, kiedy odchodzisz.",
                             "severity": "warn"},
                            {"kind": "end"},
                        ],
                    ),
                ],
            ),
            "about_klub": DialogueNode(
                node_id="about_klub",
                speaker="Klubowy",
                text=("„Liga Brawurowa, sektor trzeci, sponsor "
                      "wbity między żebra. Nasi grają w siatę "
                      "kontaktową. Bez sędziego. Wpis: jeden "
                      "kawałek ciała przeciwnika, dowolny.”"),
                on_enter_consequences=[
                    {"kind": "audience", "amount": 1,
                     "source": "dialogue_klub_lore"},
                ],
                options=[
                    DialogueOption(
                        label="Spytaj o sponsora.",
                        next_node_id="sponsor_hint",
                    ),
                    DialogueOption(
                        label="Wróć do głównego pytania.",
                        next_node_id="start",
                    ),
                    DialogueOption(
                        label="Odejść.",
                        next_node_id=None,
                        consequences=[{"kind": "end"}],
                    ),
                ],
            ),
            "sponsor_hint": DialogueNode(
                node_id="sponsor_hint",
                speaker="Klubowy",
                text=("„Liga ma kontrakt z kanałem. Lubią szybkie "
                      "starcia, krzywe finały. Jak gracz dasz "
                      "im show, podpiszą i ciebie. Reszta to "
                      "kwestia kontuzji.”"),
                on_enter_consequences=[
                    {"kind": "sponsor", "key": "liga_brawurowa",
                     "amount": 1},
                ],
                options=[
                    DialogueOption(
                        label="Skiń głową i odejdź.",
                        next_node_id=None,
                        consequences=[{"kind": "end"}],
                    ),
                ],
            ),
            "bribe_paid": DialogueNode(
                node_id="bribe_paid",
                speaker="Klubowy",
                text=("Liczy banknoty wolno, kciukiem. „Dobra. "
                      "Przejście wolne. Nie chwal się tym, kogo "
                      "minąłeś. Klub nie lubi tematu opłat.”"),
                on_enter_consequences=[
                    {"kind": "set_flag",
                     "flag": "liga_passage_paid", "value": True},
                    {"kind": "audience", "amount": -1,
                     "source": "dialogue_bribe_boring"},
                    {"kind": "sponsor", "key": "liga_brawurowa",
                     "amount": 1},
                ],
                options=[
                    DialogueOption(
                        label="Przejść.",
                        next_node_id=None,
                        consequences=[{"kind": "end"}],
                    ),
                ],
            ),
            "duel_ok": DialogueNode(
                node_id="duel_ok",
                speaker="Klubowy",
                text=("Uśmiecha się szerzej niż chce. „Jeden na "
                      "jeden. Bez kolegów. Bez kibiców. Tylko "
                      "kamera.” Pluje na podłogę między wami. "
                      "„Pierwszy ruch twój.”"),
                on_enter_consequences=[
                    {"kind": "audience", "amount": 5,
                     "source": "dialogue_duel_challenge"},
                    {"kind": "set_flag",
                     "flag": "liga_duel_accepted", "value": True},
                    {"kind": "log",
                     "text": "Konferansjer wpada w trans. "
                             "Pojedynek 1v1 to złota oglądalność.",
                     "severity": "success"},
                ],
                options=[
                    DialogueOption(
                        label="Zacznij walkę.",
                        next_node_id=None,
                        consequences=[{"kind": "end"}],
                    ),
                ],
            ),
            "duel_fail": DialogueNode(
                node_id="duel_fail",
                speaker="Klubowy",
                text=("Robi krok bliżej. „Pojedynek? Tu? Bez "
                      "wpisowego?” Pałka idzie w górę. „Kup sobie "
                      "godność, potem przyjdź z propozycją.”"),
                on_enter_consequences=[
                    {"kind": "audience", "amount": -2,
                     "source": "dialogue_duel_fail"},
                ],
                options=[
                    DialogueOption(
                        label="Cofnąć się i zakończyć.",
                        next_node_id=None,
                        consequences=[{"kind": "end"}],
                    ),
                ],
            ),
        },
    )


# ── intake_warden — Strażnik Bramy (F1 floor boss) ──────────────────

def _build_intake_warden_tree() -> DialogueTree:
    """Drzewko dla Strażnika Bramy. F1 boss, mundur intake, ostatni
    bastion przed pierwszym zejściem. Gracz może: rozeznanie (info),
    łapówka (kredyty), próba przejścia bez walki (skill check),
    albo wyzwanie."""
    return DialogueTree(
        tree_key="intake_warden",
        start_node="start",
        nodes={
            "start": DialogueNode(
                node_id="start",
                speaker="Strażnik Bramy",
                text=("Mundur leży na nim za luźno. Paralizator "
                      "trzyma za pasek, nie za rękojeść. Patrzy "
                      "ponad twoją głowę. „Pan tu w jakiej "
                      "sprawie, jeśli można.”"),
                options=[
                    DialogueOption(
                        label="Spytaj, kogo pilnuje.",
                        next_node_id="what_guarding",
                    ),
                    DialogueOption(
                        label="Spytaj, czy można po prostu zejść.",
                        next_node_id="passage_question",
                    ),
                    DialogueOption(
                        label="Wsuń mu 30 kr w klapę kombinezonu.",
                        next_node_id="bribe_paid",
                        requires_flag="has_30_credits",
                    ),
                    DialogueOption(
                        label="Powiedz, że bramy nikt nie pilnuje. "
                              "(CHA, TT 14)",
                        skill_check=("CHA", 14),
                        next_node_id="convince_ok",
                        fail_node_id="convince_fail",
                    ),
                    DialogueOption(
                        label="Wyzwij go na walkę.",
                        next_node_id=None,
                        consequences=[
                            {"kind": "audience", "amount": 3,
                             "source": "dialogue_warden_challenge"},
                            {"kind": "end"},
                        ],
                    ),
                ],
            ),
            "what_guarding": DialogueNode(
                node_id="what_guarding",
                speaker="Strażnik Bramy",
                text=("„Bramy. Bramy do następnego.” Macha "
                      "ręką w bok. „Nie wiem, czego pilnuje druga "
                      "strona. Od strony bramy jest tylko brama. "
                      "Reszty się nauczyłem nie pytać.”"),
                on_enter_consequences=[
                    {"kind": "audience", "amount": 1,
                     "source": "dialogue_warden_lore"},
                ],
                options=[
                    DialogueOption(
                        label="Wróć do głównego pytania.",
                        next_node_id="start",
                    ),
                    DialogueOption(
                        label="Zostaw go.",
                        next_node_id=None,
                        consequences=[{"kind": "end"}],
                    ),
                ],
            ),
            "passage_question": DialogueNode(
                node_id="passage_question",
                speaker="Strażnik Bramy",
                text=("Spogląda na ciebie pierwszy raz w oczy. "
                      "„Nie. Albo papier ze sztabu, albo "
                      "rozstrzygnięcie. Sztabu pan tu nie ma. "
                      "Zostaje drugie.”"),
                options=[
                    DialogueOption(
                        label="Wróć do głównego pytania.",
                        next_node_id="start",
                    ),
                    DialogueOption(
                        label="Spróbuj go odgadać.",
                        next_node_id=None,
                        consequences=[{"kind": "end"}],
                    ),
                ],
            ),
            "bribe_paid": DialogueNode(
                node_id="bribe_paid",
                speaker="Strażnik Bramy",
                text=("Klapę zapina szybko, kciukiem. Nie liczy. "
                      "„Pan przeszedł godzinę temu. Zapis "
                      "techniczny. Życzę wszystkiego dobrego "
                      "w nowym sektorze.”"),
                on_enter_consequences=[
                    {"kind": "set_flag",
                     "flag": "warden_bribed", "value": True},
                    {"kind": "audience", "amount": -2,
                     "source": "dialogue_warden_bribe_boring"},
                    {"kind": "log",
                     "text": "Konferansjer (znudzony): „Łapówka. "
                             "Klasyk. Widownia woli krew.”",
                     "severity": "normal"},
                ],
                options=[
                    DialogueOption(
                        label="Przejść.",
                        next_node_id=None,
                        consequences=[{"kind": "end"}],
                    ),
                ],
            ),
            "convince_ok": DialogueNode(
                node_id="convince_ok",
                speaker="Strażnik Bramy",
                text=("Marszczy czoło. Patrzy na bramę. „No fakt. "
                      "Nikogo nie ma.” Siada przy ścianie, "
                      "wyjmuje papierosa. „Idź pan, ja sobie "
                      "ten dzień skreślę.”"),
                on_enter_consequences=[
                    {"kind": "set_flag",
                     "flag": "warden_convinced", "value": True},
                    {"kind": "audience", "amount": 6,
                     "source": "dialogue_warden_meta_win"},
                    {"kind": "log",
                     "text": "Widownia wybucha śmiechem. To było "
                             "lepsze niż walka.",
                     "severity": "success"},
                ],
                options=[
                    DialogueOption(
                        label="Przejść.",
                        next_node_id=None,
                        consequences=[{"kind": "end"}],
                    ),
                ],
            ),
            "convince_fail": DialogueNode(
                node_id="convince_fail",
                speaker="Strażnik Bramy",
                text=("Nie reaguje od razu. Potem mówi spokojnie: "
                      "„Bramy są. Pan jest po tej stronie. "
                      "Logika trzyma się jak ona, nie jak pan.”"),
                on_enter_consequences=[
                    {"kind": "audience", "amount": -1,
                     "source": "dialogue_warden_convince_fail"},
                ],
                options=[
                    DialogueOption(
                        label="Cofnąć się.",
                        next_node_id=None,
                        consequences=[{"kind": "end"}],
                    ),
                ],
            ),
        },
    )


# ── Rejestracja ──────────────────────────────────────────────────────

def _build_placeholder_tree() -> DialogueTree:
    """Minimalne drzewko-szkielet używane przez engine tests
    (test_p29_41_dialogue_engine). Trzymane dla wstecznej zgodności
    testów — nie jest wpięte do żadnego gameplay-spawn."""
    return DialogueTree(
        tree_key="placeholder_npc",
        start_node="start",
        nodes={
            "start": DialogueNode(
                node_id="start",
                speaker="Nieznajomy",
                text="Stoi przed tobą. Czeka, co powiesz.",
                options=[
                    DialogueOption(
                        label="Spytaj kim jest.",
                        next_node_id="introduce",
                    ),
                    DialogueOption(
                        label="Zastrasz go. (CHA, TT 12)",
                        skill_check=("CHA", 12),
                        next_node_id="intimidate_ok",
                        fail_node_id="intimidate_fail",
                    ),
                    DialogueOption(
                        label="Odejdź bez słowa.",
                        next_node_id=None,
                        consequences=[{"kind": "end"}],
                    ),
                ],
            ),
            "introduce": DialogueNode(
                node_id="introduce",
                speaker="Nieznajomy",
                text="Stoi i milczy. Nie podaje imienia.",
                options=[
                    DialogueOption(
                        label="Skończ rozmowę.",
                        next_node_id=None,
                        consequences=[{"kind": "end"}],
                    ),
                ],
            ),
            "intimidate_ok": DialogueNode(
                node_id="intimidate_ok",
                speaker="Nieznajomy",
                text="Robi krok w tył.",
                on_enter_consequences=[
                    {"kind": "audience", "amount": 1},
                ],
                options=[
                    DialogueOption(
                        label="Wyjdź.",
                        next_node_id=None,
                        consequences=[{"kind": "end"}],
                    ),
                ],
            ),
            "intimidate_fail": DialogueNode(
                node_id="intimidate_fail",
                speaker="Nieznajomy",
                text="Patrzy chłodno. Nie cofa się.",
                on_enter_consequences=[
                    {"kind": "threat", "amount": 2},
                ],
                options=[
                    DialogueOption(
                        label="Cofnij się.",
                        next_node_id=None,
                        consequences=[{"kind": "end"}],
                    ),
                ],
            ),
        },
    )


def register_all_trees() -> None:
    """Wywoływane raz przy starcie gry (lub lazy przed pierwszym
    użyciem)."""
    register_tree(_build_default_crawler_tree())
    register_tree(_build_liga_brawurowa_tree())
    register_tree(_build_intake_warden_tree())
    register_tree(_build_placeholder_tree())


# Idempotent register at import time.
register_all_trees()
