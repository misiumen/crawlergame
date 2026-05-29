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

> Łańcuch w grze: `bg_<biome>` → `bg_room_<typ>` → `bg_default`.
> Pokoje walki/lore w danym biomie odziedziczą `bg_<biome>` — nie musisz
> robić osobnych. Boss/treasure/safehouse warto wyróżnić.

---

## Portrety wrogów  (1:1, ~512, popiersie; styl PASUJĄCY do biomu wroga)

Łańcuch: `wrog_<klucz_moba>` → `wrog_<archetyp>`. Portret rób w stylu
biomu, z którego mob pochodzi (zwierzak z zoo ≠ żołnierz z okopów).

| Klucz                 | Subiekt |
|-----------------------|---------|
| `wrog_humanoid`       | hostile humanoid scavenger, makeshift armor |
| `wrog_beast`          | mutated beast, fangs, matted fur |
| `wrog_robot`          | battered security robot, red optic, wiring |
| `wrog_blob`           | amorphous translucent ooze, dripping |
| `wrog_aberration`     | eldritch anomaly, wrong geometry, too many eyes |
| `wrog_undead`         | reanimated crawler corpse, grey flesh |
| `wrog_intake_warden`  | F1 boss: hulking intake warden, riot gear |
| `wrog_boss_panicz_zoo`| F3 boss: pampered show-beast, bear-like, gaudy zoo glam |
| `wrog_tunnel_runt`    | small vicious tunnel rat, wet, red eyes |

(Dla pozostałych bossów: `wrog_<klucz_z_entity_templates>`.)

## Portret gracza  (opcjonalny 1:1): `portret_<origin>` (np.
`portret_bezdomny`). Bez pliku → budowany proceduralnie z EQ.

---
Status: pipeline gotowy. Audio per biom → `assets/audio/AUDIO_MANIFEST.md`.
