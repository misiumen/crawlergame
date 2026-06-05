class_name DialogueTrees
extends RefCounted
## Authored dialogue trees, GENERATED from dungeon_kraulem/content/data/
## npc_dialogues.py by tools/gen_dialogues.py — exact Polish text + branch
## structure ported verbatim. Consumed by sim/dialogue.gd. Re-run the
## generator if the Python trees change.

const TREES: Dictionary = {
	"default_crawler": {
		"start": "start",
		"nodes": {
			"start": {
				"speaker": "Zawodnik",
				"text": "Mierzy cię od stóp do głów. Zaciska pas, patrzy, gdzie masz ręce. „Co masz, czego ja nie mam?”",
				"options": [
					{"label": "Spytaj, skąd jest i jak długo tu siedzi.", "next": "origin", "one_shot": true},
					{"label": "Spytaj o najbliższy bezpieczny pokój.", "next": "safehouse_tip", "one_shot": true},
					{"label": "Spróbuj wciągnąć go w sojusz. (CHA, TT 11)", "next": "ally_ok", "skill": ["CHA", 11], "fail": "ally_fail", "one_shot": true},
					{"label": "Ostrzeż, że masz lepszą broń. (CHA, TT 13)", "next": "intimidate_ok", "skill": ["CHA", 13], "fail": "intimidate_fail", "one_shot": true},
					{"label": "Skończ rozmowę.", "cons": [{"kind": "end"}]},
				],
			},
			"origin": {
				"speaker": "Zawodnik",
				"text": "„Łazienka biurowa, środa po szóstej. Wrzucili mnie tu z kubkiem w ręce.” Patrzy na sufit. „Trzeci dzień. Nie wiem, czy zegar tu chodzi uczciwie.”",
				"options": [
					{"label": "Spytaj, czego się tu nauczył.", "next": "lesson", "one_shot": true},
					{"label": "Wróć do rozmowy.", "next": "start"},
				],
			},
			"lesson": {
				"speaker": "Zawodnik",
				"text": "„Nie biegnij na bossa głodny. Nie ufaj automatom przy ścianach. Sponsor, który mówi miło, to sponsor, który sprzedaje cię niżej.”",
				"on_enter": [{"kind": "audience", "amount": 1, "source": "dialogue_lesson"}],
				"options": [
					{"label": "Wróć do rozmowy.", "next": "start"},
				],
			},
			"safehouse_tip": {
				"speaker": "Zawodnik",
				"text": "„Drugi korytarz po lewej. Pachnie kawą. Tam się sypia. Jeśli kelner pyta, mówisz, że jesteś z trzeciej zmiany.”",
				"on_enter": [{"kind": "audience", "amount": 1, "source": "dialogue_tip"}],
				"options": [
					{"label": "Wróć do rozmowy.", "next": "start"},
				],
			},
			"ally_ok": {
				"speaker": "Zawodnik",
				"text": "Wzdycha. „No dobra. Ty idziesz w lewo, ja w prawo. Jak usłyszysz krzyk, to nie ja. Albo ja — ale i tak nie zdążysz pomóc.”",
				"on_enter": [{"kind": "audience", "amount": 2, "source": "dialogue_ally"}, {"kind": "log", "text": "Konferansjer (cicho): „Sojusz. Widownia kocha sojusze. Aż do pierwszej zdrady.”", "severity": "normal"}],
				"options": [
					{"label": "Wróć do rozmowy.", "next": "start"},
				],
			},
			"ally_fail": {
				"speaker": "Zawodnik",
				"text": "Prycha. „Nie znam cię. Sojusze są dla tych, co się boją. Idź swoją drogą.”",
				"on_enter": [{"kind": "log", "text": "Zabrzmiało gorzej, niż chciałeś.", "severity": "warn"}],
				"options": [
					{"label": "Wróć do rozmowy.", "next": "start"},
				],
			},
			"intimidate_ok": {
				"speaker": "Zawodnik",
				"text": "Robi krok w tył. „Dobra. Tylko nie patrz mi na ręce. Ja nie patrzę na twoje.”",
				"on_enter": [{"kind": "audience", "amount": 2, "source": "dialogue_intimidate"}],
				"options": [
					{"label": "Wróć do rozmowy.", "next": "start"},
				],
			},
			"intimidate_fail": {
				"speaker": "Zawodnik",
				"text": "Śmieje się jednym krótkim dźwiękiem. „Lepszą broń? To pokaż.” Nie ruszył się ani o krok.",
				"on_enter": [{"kind": "audience", "amount": -1, "source": "dialogue_intimidate_fail"}],
				"options": [
					{"label": "Wróć do rozmowy.", "next": "start"},
				],
			},
		},
	},
	"liga_brawurowa_grunt": {
		"start": "start",
		"nodes": {
			"start": {
				"speaker": "Klubowy",
				"text": "Stuk-stuk pałką o własną dłoń. „Witaj w naszym sektorze. Liga przyjmuje wpisowe. Lub trofea. Lub krew. Wybór twój.”",
				"options": [
					{"label": "Spytaj, co to za klub.", "next": "about_klub"},
					{"label": "Zapłać wpisowe (25 kr).", "next": "bribe_paid", "requires": "has_25_credits"},
					{"label": "Wyzwij go na czysty pojedynek. (CHA, TT 13)", "next": "duel_ok", "skill": ["CHA", 13], "fail": "duel_fail"},
					{"label": "Powiedz, że jesteś z innego sektora.", "cons": [{"kind": "log", "text": "Klubowy nie wierzy. Patrzy ci w plecy, kiedy odchodzisz.", "severity": "warn"}, {"kind": "end"}]},
				],
			},
			"about_klub": {
				"speaker": "Klubowy",
				"text": "„Liga Brawurowa, sektor trzeci, sponsor wbity między żebra. Nasi grają w siatę kontaktową. Bez sędziego. Wpis: jeden kawałek ciała przeciwnika, dowolny.”",
				"on_enter": [{"kind": "audience", "amount": 1, "source": "dialogue_klub_lore"}],
				"options": [
					{"label": "Spytaj o sponsora.", "next": "sponsor_hint"},
					{"label": "Wróć do głównego pytania.", "next": "start"},
					{"label": "Odejść.", "cons": [{"kind": "end"}]},
				],
			},
			"sponsor_hint": {
				"speaker": "Klubowy",
				"text": "„Liga ma kontrakt z kanałem. Lubią szybkie starcia, krzywe finały. Jak gracz dasz im show, podpiszą i ciebie. Reszta to kwestia kontuzji.”",
				"on_enter": [{"kind": "sponsor", "key": "liga_brawurowa", "amount": 1}],
				"options": [
					{"label": "Skiń głową i odejdź.", "cons": [{"kind": "end"}]},
				],
			},
			"bribe_paid": {
				"speaker": "Klubowy",
				"text": "Liczy banknoty wolno, kciukiem. „Dobra. Przejście wolne. Nie chwal się tym, kogo minąłeś. Klub nie lubi tematu opłat.”",
				"on_enter": [{"kind": "set_flag", "flag": "liga_passage_paid", "value": true}, {"kind": "audience", "amount": -1, "source": "dialogue_bribe_boring"}, {"kind": "sponsor", "key": "liga_brawurowa", "amount": 1}],
				"options": [
					{"label": "Przejść.", "cons": [{"kind": "end"}]},
				],
			},
			"duel_ok": {
				"speaker": "Klubowy",
				"text": "Uśmiecha się szerzej niż chce. „Jeden na jeden. Bez kolegów. Bez kibiców. Tylko kamera.” Pluje na podłogę między wami. „Pierwszy ruch twój.”",
				"on_enter": [{"kind": "audience", "amount": 5, "source": "dialogue_duel_challenge"}, {"kind": "set_flag", "flag": "liga_duel_accepted", "value": true}, {"kind": "log", "text": "Konferansjer wpada w trans. Pojedynek 1v1 to złota oglądalność.", "severity": "success"}],
				"options": [
					{"label": "Zacznij walkę.", "cons": [{"kind": "end"}]},
				],
			},
			"duel_fail": {
				"speaker": "Klubowy",
				"text": "Robi krok bliżej. „Pojedynek? Tu? Bez wpisowego?” Pałka idzie w górę. „Kup sobie godność, potem przyjdź z propozycją.”",
				"on_enter": [{"kind": "audience", "amount": -2, "source": "dialogue_duel_fail"}],
				"options": [
					{"label": "Cofnąć się i zakończyć.", "cons": [{"kind": "end"}]},
				],
			},
		},
	},
	"intake_warden": {
		"start": "start",
		"nodes": {
			"start": {
				"speaker": "Strażnik Bramy",
				"text": "Mundur leży na nim za luźno. Paralizator trzyma za pasek, nie za rękojeść. Patrzy ponad twoją głowę. „Pan tu w jakiej sprawie, jeśli można.”",
				"options": [
					{"label": "Spytaj, kogo pilnuje.", "next": "what_guarding"},
					{"label": "Spytaj, czy można po prostu zejść.", "next": "passage_question"},
					{"label": "Wsuń mu 30 kr w klapę kombinezonu.", "next": "bribe_paid", "requires": "has_30_credits"},
					{"label": "Powiedz, że bramy nikt nie pilnuje. (CHA, TT 14)", "next": "convince_ok", "skill": ["CHA", 14], "fail": "convince_fail"},
					{"label": "Wyzwij go na walkę.", "cons": [{"kind": "audience", "amount": 3, "source": "dialogue_warden_challenge"}, {"kind": "end"}]},
				],
			},
			"what_guarding": {
				"speaker": "Strażnik Bramy",
				"text": "„Bramy. Bramy do następnego.” Macha ręką w bok. „Nie wiem, czego pilnuje druga strona. Od strony bramy jest tylko brama. Reszty się nauczyłem nie pytać.”",
				"on_enter": [{"kind": "audience", "amount": 1, "source": "dialogue_warden_lore"}],
				"options": [
					{"label": "Wróć do głównego pytania.", "next": "start"},
					{"label": "Zostaw go.", "cons": [{"kind": "end"}]},
				],
			},
			"passage_question": {
				"speaker": "Strażnik Bramy",
				"text": "Spogląda na ciebie pierwszy raz w oczy. „Nie. Albo papier ze sztabu, albo rozstrzygnięcie. Sztabu pan tu nie ma. Zostaje drugie.”",
				"options": [
					{"label": "Wróć do głównego pytania.", "next": "start"},
					{"label": "Spróbuj go odgadać.", "cons": [{"kind": "end"}]},
				],
			},
			"bribe_paid": {
				"speaker": "Strażnik Bramy",
				"text": "Klapę zapina szybko, kciukiem. Nie liczy. „Pan przeszedł godzinę temu. Zapis techniczny. Życzę wszystkiego dobrego w nowym sektorze.”",
				"on_enter": [{"kind": "set_flag", "flag": "warden_bribed", "value": true}, {"kind": "audience", "amount": -2, "source": "dialogue_warden_bribe_boring"}, {"kind": "log", "text": "Konferansjer (znudzony): „Łapówka. Klasyk. Widownia woli krew.”", "severity": "normal"}],
				"options": [
					{"label": "Przejść.", "cons": [{"kind": "end"}]},
				],
			},
			"convince_ok": {
				"speaker": "Strażnik Bramy",
				"text": "Marszczy czoło. Patrzy na bramę. „No fakt. Nikogo nie ma.” Siada przy ścianie, wyjmuje papierosa. „Idź pan, ja sobie ten dzień skreślę.”",
				"on_enter": [{"kind": "set_flag", "flag": "warden_convinced", "value": true}, {"kind": "audience", "amount": 6, "source": "dialogue_warden_meta_win"}, {"kind": "log", "text": "Widownia wybucha śmiechem. To było lepsze niż walka.", "severity": "success"}],
				"options": [
					{"label": "Przejść.", "cons": [{"kind": "end"}]},
				],
			},
			"convince_fail": {
				"speaker": "Strażnik Bramy",
				"text": "Nie reaguje od razu. Potem mówi spokojnie: „Bramy są. Pan jest po tej stronie. Logika trzyma się jak ona, nie jak pan.”",
				"on_enter": [{"kind": "audience", "amount": -1, "source": "dialogue_warden_convince_fail"}],
				"options": [
					{"label": "Cofnąć się.", "cons": [{"kind": "end"}]},
				],
			},
		},
	},
	"placeholder_npc": {
		"start": "start",
		"nodes": {
			"start": {
				"speaker": "Nieznajomy",
				"text": "Stoi przed tobą. Czeka, co powiesz.",
				"options": [
					{"label": "Spytaj kim jest.", "next": "introduce"},
					{"label": "Zastrasz go. (CHA, TT 12)", "next": "intimidate_ok", "skill": ["CHA", 12], "fail": "intimidate_fail"},
					{"label": "Odejdź bez słowa.", "cons": [{"kind": "end"}]},
				],
			},
			"introduce": {
				"speaker": "Nieznajomy",
				"text": "Stoi i milczy. Nie podaje imienia.",
				"options": [
					{"label": "Skończ rozmowę.", "cons": [{"kind": "end"}]},
				],
			},
			"intimidate_ok": {
				"speaker": "Nieznajomy",
				"text": "Robi krok w tył.",
				"on_enter": [{"kind": "audience", "amount": 1}],
				"options": [
					{"label": "Wyjdź.", "cons": [{"kind": "end"}]},
				],
			},
			"intimidate_fail": {
				"speaker": "Nieznajomy",
				"text": "Patrzy chłodno. Nie cofa się.",
				"on_enter": [{"kind": "threat", "amount": 2}],
				"options": [
					{"label": "Cofnij się.", "cons": [{"kind": "end"}]},
				],
			},
		},
	},
}
