class_name DialogueTreesExtra
extends RefCounted
## Hand-authored (Godot-native) dialogue trees, layered on top of the ported
## DialogueTrees. New content for the board — deeper branching, multi-stat skill
## checks (CHA/INT/WIS), persistent flags that change later visits, trades, and
## risky options. Same data shape as the generated trees, consumed by Dialogue.
## (Could be back-ported to the Python content pipeline later if desired.)

const EXTRA: Dictionary = {

# ── Złomiarz Bizon — a scrap trader: haggling, a loyalty flag, a betrayal turn ──
"handlarz_szrotu": {
	"start": "start",
	"nodes": {
		"start": {
			"speaker": "Złomiarz Bizon",
			"text": "Siedzi na stercie blachy jak na tronie. „No proszę, świeże mięso z portfelem. Czego szukasz — towaru czy guza?”",
			"options": [
				{"label": "Pokaż, co masz na wymianę.", "next": "wares"},
				{"label": "Potarguj się o lepszy kurs. (CHA, TT 12)", "skill": ["CHA", 12], "next": "haggle_ok", "fail": "haggle_fail", "one_shot": true},
				{"label": "Oszacuj jego towar fachowym okiem. (INT, TT 11)", "skill": ["INT", 11], "next": "appraise_ok", "fail": "appraise_fail", "one_shot": true},
				{"label": "[Stały klient] Poproś o towar spod lady.", "requires": "bizon_regular", "next": "underbar"},
				{"label": "Zostań jego stałym klientem.", "forbids": "bizon_regular", "next": "loyalty", "one_shot": true},
				{"label": "Odejdź.", "cons": [{"kind": "end"}]},
			],
		},
		"wares": {
			"speaker": "Złomiarz Bizon",
			"text": "Rozkłada szmatę. „Złom za przewód, dwa do jednego. Albo bateria za trójkę złomu. Wybieraj, nie filozofuj.”",
			"options": [
				{"label": "Wymień 2 złom na przewód.", "next": "start", "cons": [{"kind": "give_material", "material": "przewód", "qty": 1}, {"kind": "log", "text": "Bizon zgarnia 2 złom. Masz przewód."}]},
				{"label": "Wymień 3 złom na baterię.", "next": "start", "cons": [{"kind": "give_material", "material": "bateria", "qty": 1}, {"kind": "log", "text": "Trzy złom znikają. Bateria twoja."}]},
				{"label": "Wróć.", "next": "start"},
			],
		},
		"haggle_ok": {
			"speaker": "Złomiarz Bizon",
			"text": "Mruży oko. „Gadane masz. Dobra — dziś liczę taniej. Ale komuś powiesz, to ci policzę zęby.”",
			"on_enter": [{"kind": "set_flag", "flag": "bizon_discount", "value": true}, {"kind": "audience", "amount": 2, "source": "dialogue_haggle"}],
			"options": [
				{"label": "Świetnie — pokaż towar.", "next": "wares"},
				{"label": "Wróć.", "next": "start"},
			],
		},
		"haggle_fail": {
			"speaker": "Złomiarz Bizon",
			"text": "Śmieje się sucho. „Targujesz się jak ktoś, kto zaraz umrze. Cena w górę, za fatygę.”",
			"on_enter": [{"kind": "set_flag", "flag": "bizon_markup", "value": true}],
			"options": [
				{"label": "Trudno. Wróć.", "next": "start"},
			],
		},
		"appraise_ok": {
			"speaker": "Złomiarz Bizon",
			"text": "Unosi brew. „Znasz się. Połowa tego badziewia to podróbki sponsorów — ale ta bateria jest prawdziwa.” Podsuwa ci ją.",
			"on_enter": [{"kind": "give_material", "material": "bateria", "qty": 1}, {"kind": "log", "text": "Fachowe oko: wypatrzyłeś dobrą baterię."}],
			"options": [
				{"label": "Dzięki. Wróć.", "next": "start"},
			],
		},
		"appraise_fail": {
			"speaker": "Złomiarz Bizon",
			"text": "„Patrzysz, ale nie widzisz.” Zasłania towar łokciem. „Oglądać za darmo można w telewizji.”",
			"options": [
				{"label": "Wróć.", "next": "start"},
			],
		},
		"loyalty": {
			"speaker": "Złomiarz Bizon",
			"text": "Wyciąga łapę umazaną smarem. „Stały klient, co? Dobra. Ale stały klient nie donosi i nie kradnie. Łapiesz?”",
			"on_enter": [{"kind": "set_flag", "flag": "bizon_regular", "value": true}, {"kind": "relationship", "amount": 2}, {"kind": "audience", "amount": 1, "source": "dialogue_loyalty"}],
			"options": [
				{"label": "Łapię. (uścisk dłoni)", "next": "start"},
			],
		},
		"underbar": {
			"speaker": "Złomiarz Bizon",
			"text": "Zerka na boki, wyciąga zawiniątko. „Dla swoich. Kwas, prosto z laboratorium. Nie pytaj skąd.” Wręcza ci fiolkę.",
			"on_enter": [{"kind": "give_material", "material": "kwas", "qty": 1}, {"kind": "sponsor", "key": "czarny_rynek_plus", "amount": 1}, {"kind": "log", "text": "Towar spod lady: masz kwas."}],
			"options": [
				{"label": "Wróć.", "next": "start"},
				{"label": "Wystarczy. Odejdź.", "cons": [{"kind": "end"}]},
			],
		},
	},
},

# ── Kapłan Polimerów — a cult priest: doctrine (WIS), conversion, blessing/curse ─
"kaplan_polimerow": {
	"start": "start",
	"nodes": {
		"start": {
			"speaker": "Kapłan Polimerów",
			"text": "Stoi w kręgu stopionych butelek. „Wszystko, co trwałe, jest święte. Ty — jesteś jeszcze miękki. Przyszedłeś słuchać czy szydzić?”",
			"options": [
				{"label": "Wysłuchaj doktryny. (WIS, TT 11)", "skill": ["WIS", 11], "next": "doctrine_ok", "fail": "doctrine_fail", "one_shot": true},
				{"label": "Wyśmiej jego polimerowego boga. (CHA, TT 13)", "skill": ["CHA", 13], "next": "mock_ok", "fail": "mock_fail", "one_shot": true},
				{"label": "Przyjmij wiarę polimeru.", "forbids": "polimer_wierny", "next": "convert"},
				{"label": "[Wierny] Poproś o błogosławieństwo.", "requires": "polimer_wierny", "next": "blessing", "one_shot": true},
				{"label": "Odejdź w ciszy.", "cons": [{"kind": "end"}]},
			],
		},
		"doctrine_ok": {
			"speaker": "Kapłan Polimerów",
			"text": "„Ciało gnije. Plastik pamięta. Producent to tylko kolejny bóg, który nie czyta własnego regulaminu.” Coś w tym jest. Widownia kiwa głowami.",
			"on_enter": [{"kind": "audience", "amount": 3, "source": "dialogue_doctrine"}, {"kind": "set_flag", "flag": "polimer_ciekawy", "value": true}],
			"options": [
				{"label": "Wróć z pytaniami.", "next": "start"},
			],
		},
		"doctrine_fail": {
			"speaker": "Kapłan Polimerów",
			"text": "Mówi i mówi, a ty gubisz wątek po trzecim zdaniu o „świętej nieodwracalności wtrysku”. Kiwasz głową, nie rozumiejąc nic.",
			"options": [
				{"label": "Eee… wróć.", "next": "start"},
			],
		},
		"mock_ok": {
			"speaker": "Kapłan Polimerów",
			"text": "Rzucasz żart o bogu, który topi się w słońcu. Trybuny ryczą śmiechem. Kapłan blednie — nawet wierni chichoczą w rękaw.",
			"on_enter": [{"kind": "audience", "amount": 4, "source": "dialogue_mock"}, {"kind": "sponsor", "key": "kanal_7_krawedz", "amount": 1}],
			"options": [
				{"label": "Skłoń się publiczności i odejdź.", "cons": [{"kind": "end"}]},
				{"label": "Wróć (gdy ucichnie).", "next": "start"},
			],
		},
		"mock_fail": {
			"speaker": "Kapłan Polimerów",
			"text": "Żart umiera w ciszy. Kapłan unosi dłoń. „Drwina to też forma modlitwy — do złego boga.” Coś w lochu robi się czujne.",
			"on_enter": [{"kind": "audience", "amount": -2, "source": "dialogue_mock_fail"}, {"kind": "threat", "amount": 3}],
			"options": [
				{"label": "Wycofaj się.", "cons": [{"kind": "end"}]},
			],
		},
		"convert": {
			"speaker": "Kapłan Polimerów",
			"text": "Maluje ci na czole znak roztopionym woskiem. „Odtąd jesteś trwały. Producent cię sprzeda, ale plastik cię zapamięta.”",
			"on_enter": [{"kind": "set_flag", "flag": "polimer_wierny", "value": true}, {"kind": "relationship", "amount": 3}, {"kind": "sponsor", "key": "kaplan_polimerow", "amount": 2}, {"kind": "audience", "amount": 1, "source": "dialogue_convert"}],
			"options": [
				{"label": "Przyjmij znak. (wróć)", "next": "start"},
			],
		},
		"blessing": {
			"speaker": "Kapłan Polimerów",
			"text": "Kreśli nad tobą znak nieskończonej trwałości. „Idź. Niech twoja powłoka nie pęka pierwsza.” Wciska ci w dłoń szmatę nasączoną czymś gryzącym.",
			"on_enter": [{"kind": "give_material", "material": "szmata", "qty": 2}, {"kind": "audience", "amount": 2, "source": "dialogue_blessing"}],
			"options": [
				{"label": "Skłoń głowę i wróć.", "next": "start"},
				{"label": "Odejdź pobłogosławiony.", "cons": [{"kind": "end"}]},
			],
		},
	},
},

}
