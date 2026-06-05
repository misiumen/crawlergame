# Manifest audio — Dungeon Kraulem (P29.72)

Format: **SFX** → `assets/audio/sfx/<klucz>.ogg|.wav` (44.1kHz/16-bit/
stereo, krótkie, znormalizowane, przycięta cisza). **Muzyka** →
`assets/audio/music/<klucz>.ogg` (OGG loopuje czyściej w pygame; rób
bezszwowe pętle). Brak pliku → cisza (fallback). Podmieniasz → gra.

---

## ZASADA NACZELNA (jak w grafice): biom = własny styl muzyczny.
Wspólna jest tylko CIENKA warstwa „show", nie gatunek.

### Warstwa WSPÓLNA (ta sama pod każdym trackiem)
- cichy podkład **broadcast static / „station ident"** (ledwie słyszalny
  szum eteru + krótki motyw-sygnał programu) — spina wszystko w jeden show,
- stałe **`sponsor_chime`** (jingiel sponsora) + **UI chiptune blipy**
  (confirm/cancel/tab/error) — te NIE zmieniają się per biom.

### Warstwa PER BIOM (RÓŻNA — gatunek + instrumentarium mają odróżniać)
Pliki `explore_<biome>.ogg` (eksploracja danego piętra). Style odległe:

| Klucz `explore_<biome>`       | Gatunek + instrumentarium |
|-------------------------------|---------------------------|
| `explore_intake_industrial`   | opresyjny industrial drone, łomot blachy, sub-bas |
| `explore_zoo_korporacyjne`    | wykrzywiona karuzela / muzak, calliope, dziecięce dzwonki w mollu |
| `explore_muzeum_spektakli`    | zakurzona pozytywka, kwartet smyczkowy lekko rozstrojony |
| `explore_bar_skurczybyk`      | pijacki lounge-jazz / synth-sleaze, jukebox zza ściany |
| `explore_grzybica_bloom`      | eteryczny dron BEZ rytmu, oddychające pady, obco |
| `explore_okopy_frontowe`      | militarny dread, werble wojenne, dalekie ostrzały |
| `explore_fabryka_pary`        | rytmiczny steam-mechanical, perkusja z trybów, blacha |
| `explore_stacja_orbital`      | sterylny sci-fi ambient, bipy, poczucie ogromu |
| `explore_kuznia_polorkow`     | ciężkie plemienne bębny, rytm kowadła, niski chant |
| `explore_biblioteka_miejska`  | złowieszczy chór-szepty, organy, szelest kart |

### Tracki stanu (ponad biomami)
| Plik | Charakter |
|---|---|
| `menu.ogg`      | tytuł: pulsujące arpeggio, gwar tłumu w tle, groza |
| `safehouse.ogg` | antrakt: spokojne lo-fi, ulga, ciepły hum |
| `combat.ogg`    | walka: napędzający dark-synth, pilna perkusja, adrenalina |
| `boss.ogg`      | boss: dread, łomot bębnów, chór-stabs, broadcast-hype |
| `victory.ogg`   | krótki sting: tryumf + zryw tłumu |
| `defeat.ogg`    | krótki sting: ponure opadanie, statyka, buczenie widowni |

> Boss/combat warianty per biom (`combat_<biome>`, `boss_<biome>`) =
> opcjonalnie później; na start wystarczy jeden combat + jeden boss.

---

## SFX świata/walki (ElevenLabs) — podmień istniejące + dorób systemowe
- istniejące do podbicia: `hit_landed` (mokry cios), `hit_crit`/
  `player_crit_hit` (chrupnięcie kości), `attack_miss` (świst),
  `attack_fumble` (klekot upuszczenia), `enemy_death` (bulgot zgonu),
  `player_hit` (jęk+impakt), `player_death` (ostatni oddech+upadek),
  `limb_broken` (trzask kości), `floor_descent` (zjazd, zgrzyt maszyn),
  `sponsor_chime` (jingiel sponsora).
- **systemowe (NOWE — dorób, wzmacniają mechanikę):** `sys_fire`
  (whoomph+trzask), `sys_zap` (łuk elektryczny), `sys_acid` (syk żrący),
  `sys_freeze` (szklisty lód), `sys_shatter` (rozbicie szkła), `cast`
  (ładowanie+uwolnienie czaru), `panic` (panika stwora).

## UI (chiptune — Bfxr/jsfxr): `ui_confirm`, `ui_cancel`, `ui_tab`,
`ui_error` — krótkie 8-bit. (Te zostają wspólne, „terminalowe".)

---
## Wymaga mojego kroku kodu (powiedz, zrobię):
- wybór muzyki per biom (`explore_<biome>`) + przełączanie na
  `combat`/`boss`/`safehouse` (teraz gra leci tylko menu/explore/victory/
  defeat),
- wpięcie `play_sfx` dla `sys_*`/`cast`/`panic` w efekty silnika.
