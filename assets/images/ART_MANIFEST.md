# Manifest grafik — Dungeon Kraulem (P29.71 + P29.72 per-biome)

**Ten folder (`assets/images/`) to katalog grafik gry.** Gra wczytuje
`assets/images/<klucz>.png`; brak pliku → proceduralny fallback. Wrzucasz
plik o nazwie z tabel → wpada automatycznie, zero zmian w kodzie.

---

## ZASADA NACZELNA: biom = własny styl. Wspólny jest tylko CIENKI „show".

NIE generuj wszystkiego w jednym stylu — biomy mają się RÓŻNIĆ (inaczej
zlewają się w jedno). Spójność daje **cienka warstwa programu**, nie
paleta.

### Warstwa WSPÓLNA (ta sama wszędzie — trzymaj w każdym promptie)
```
reality-show broadcast overlay: subtle neon HUD frame, faint CRT scanlines
and grain, a small sponsor-logo corner, deathgame TV framing; no real
brands, no text, no watermark
```
+ **spójność techniczna**: ten sam poziom kontrastu i głębi czerni (żeby
sceny siadały w tym samym panelu UI), subiekt skomponowany centralnie/
nisko (pod panel), format poziomy ~16:10 (tła) / 1:1 (portrety).

### Warstwa PER BIOM (RÓŻNA — to jej zadanie odróżniać piętra)
Każde tło = warstwa wspólna **+** poniższa tożsamość. Style mają być
odległe (inny gatunek ilustracji, inna paleta, inny nastrój).

| Klucz `bg_<biome>`      | Paleta              | Styl / motyw |
|-------------------------|---------------------|--------------|
| `bg_intake_industrial`  | sodowy pomarańcz + stalowy błękit, beton | zimny brutal-przemysł, taśmociągi, zbrojenia, iskry spawu |
| `bg_zoo_korporacyjne`   | jaskrawe pastele + plamy krwi, plastik | korpo-słodki HORROR, pęknięte maskotki, klatki, neon-cyrk |
| `bg_muzeum_spektakli`   | sepia + zimny reflektor, kurz | wyblakły przepych, woskowe figury, rolki taśmy, barok w rozkładzie |
| `bg_bar_skurczybyk`     | bursztyn/czerwień neon, dym | brudna speluna, mosiężne krany, lepka podłoga, brudny glamour |
| `bg_grzybica_bloom`     | turkus/fiolet bioluminescencja, wilgoć | OBCY organizm, świecące grzyby, zarodniki, mięsiste tekstury |
| `bg_okopy_frontowe`     | błoto-brąz + gazowa zieleń | piekło okopów I-wojny, worki z piaskiem, mgła iperytu, druty |
| `bg_fabryka_pary`       | mosiądz/miedź + biel pary, żar pieca | steampunk, kotły, zawory ciśnieniowe, tłoki, mgła pary |
| `bg_stacja_orbital`     | chłodna biel/cyan, czerń kosmosu | sterylne sci-fi, iluminatory z gwiazdami, panele nawigacyjne |
| `bg_kuznia_polorkow`    | czerń + żar-czerwień, dym | mroczne dark-fantasy, kowadła, lawa, dymny mrok kuźni |
| `bg_biblioteka_miejska` | sepia/głęboki fiolet, blask świecy | OKULTYZM, zakazane tomy, woskowe pieczęcie, kurz i mrok |
| `bg_room_safehouse`     | przygaszony ciepły neon | brudny lounge między piętrami — ulga, antrakt programu |
| `bg_room_boss`          | wg biomu + reflektor i kamery | arena bossa: ostre światło, broadcast, napięcie |
| `bg_default`            | neutralny mrok | zapasowy korytarz (gdy biom bez własnego tła) |

> Łańcuch w grze (P29.74 — WSZYSTKO per biom, zero bleedu między biomami):
> `bg_<biome>_<typ>` → `bg_<biome>` → gradient w tincie biomu.
> Pokoje walki/lore dziedziczą `bg_<biome>` — nie musisz robić osobnych.
> Warto wyróżnić: `bg_<biome>_boss`, `bg_<biome>_safehouse`,
> `bg_<biome>_treasure`, `bg_<biome>_start`.
> (Nie ma już `bg_room_<typ>` ani `bg_default` — były wspólne dla
> wszystkich biomów → powodowały „zlewanie się".)

---

## Portrety wrogów  (CAŁA SYLWETKA, pion ~2:3 np. 512×768; styl biomu wroga)

**Konwencja BIOME-FIRST (P29.75).** Każdy mob należy do JEDNEGO biomu —
nie ma „mobów generycznych". Nazwa pliku = `wrog_<biom>_<reszta>`, gdzie
`<biom>` to KRÓTKI człon klucza biomu (`intake_industrial` → **`intake`**,
`zoo_korporacyjne` → **`zoo`**). Łańcuch rozwiązywania (pierwszy istniejący
plik wygrywa):
```
wrog_<biom>_<klucz_moba>           # np. wrog_intake_tunnel_runt  (per mob)
wrog_<klucz_moba>                  # gdy klucz moba już zawiera biom (wrog_intake_warden)
wrog_<biom>_<archetyp>_<ogon>      # np. wrog_intake_humanoid_industrial (per archetyp)
wrog_<biom>_<archetyp>             # np. wrog_intake_humanoid
wrog_<archetyp>                    # ostatni ratunek (zwykle brak — proceduralny fallback)
```
`<ogon>` = drugi człon klucza biomu (`intake_industrial` → `industrial`).
Styl wg biomu moba (zwierzak z zoo ≠ żołnierz z okopów).

Pliki Sortowni już wrzucone: `wrog_intake_tunnel_runt`,
`wrog_intake_freezer_carver`, `wrog_intake_biotech_inspector`,
`wrog_intake_warden`, `wrog_intake_humanoid_industrial`,
`wrog_intake_beast_industrial`.

**KRYTYCZNE — całe ciało, nie popiersie.** VATS targetuje strefy:
głowa / tors / ramiona / **nogi**. Popiersie ucina nogi → nie da się ich
celować. Wymagania:
- **pełna postać head-to-feet**, front, stojąca, kończyny ROZDZIELONE
  (nie skrzyżowane) — żeby strefy ciała siadały na realnych członkach,
- **tło proste/ciemne lub przezroczyste (PNG alpha)** — bez gęstej sceny
  za postacią (kłóci się z nakładką stref VATS),
- format pionowy ~2:3 (głowa u góry, stopy na dole).

| Klucz                 | Subiekt (zawsze FULL-BODY, stojąca postać) |
|-----------------------|---------|
| `wrog_humanoid`       | full-body hostile humanoid scavenger, makeshift armor, standing |
| `wrog_beast`          | full-body mutated beast on all-fours/standing, fangs, matted fur |
| `wrog_robot`          | full-body battered security robot, red optic, exposed wiring |
| `wrog_blob`           | full-body amorphous translucent ooze, dripping, upright mass |
| `wrog_aberration`     | full-body eldritch anomaly, wrong geometry, too many limbs |
| `wrog_undead`         | full-body reanimated crawler corpse, grey flesh, shambling |
| `wrog_intake_warden`  | boss Sortowni: full-body hulking intake warden, riot gear |
| `wrog_intake_tunnel_runt` | full-body small vicious tunnel rat, wet, red eyes |
| `wrog_intake_freezer_carver` | full-body butcher in frost-rimed apron, cleaver |
| `wrog_intake_biotech_inspector` | full-body NovaChem hazmat inspector, clipboard |
| `wrog_intake_nadzorca_sortowni` | miniboss: full-body hi-vis foreman, stun baton, clipboard, shoulder armor |

> Wiersze `wrog_<archetyp>` powyżej = OSTATNI ratunek (gdy biom nie ma
> własnego pliku). Realne pliki per biom: `wrog_<biom>_<archetyp>_<ogon>`
> lub `wrog_<biom>_<klucz_moba>`. Bossy biomów: `wrog_<biom>_<klucz_moba>`.

## Portret gracza  (opcjonalny 1:1): `portret_<origin>` (np.
`portret_bezdomny`). Bez pliku → budowany proceduralnie z EQ.

---
Status: pipeline gotowy. Audio per biom → `assets/audio/AUDIO_MANIFEST.md`.
