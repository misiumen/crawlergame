# Manifest grafik — Dungeon Kraulem (P29.71, workstream C/2)

Gra wczytuje PNG z `assets/images/<klucz>.png`. Jeśli pliku brak →
proceduralny fallback (gradient/sylwetka), więc gra działa bez grafik.
Wrzucasz pliki o nazwach z tabel poniżej → wpadają automatycznie.

**Jak używać:** generujesz obraz w swoim modelu (Midjourney / SDXL / itp.)
promptem ze wspólną dyrekcją (niżej), zapisujesz jako `<klucz>.png` w tym
folderze. Gra skaluje do panelu, więc dokładny rozmiar nie jest krytyczny
— trzymaj proporcje z kolumny „format".

---

## Wspólna dyrekcja artystyczna (wklej na początek KAŻDEGO promptu)

```
dark neon dungeon reality-show, gritty cyber-industrial, painterly concept
art, moody volumetric lighting, magenta-and-cyan neon glow, wet grimy
metal, high detail, cinematic, desaturated shadows with saturated neon
accents, 35mm, no text, no watermark, no logos
```

Trzymaj jeden **seed/styl** dla spójności całej serii. Bez napisów i
realnych marek (gra unika brandów i bezpośrednich odniesień do prozy).

---

## Tła pokojów  (format poziomy ~16:10, np. 1024×640)

Łańcuch: `bg_<biome>` → `bg_room_<typ>` → `bg_default`.

| Klucz pliku            | Subiekt do promptu |
|------------------------|--------------------|
| `bg_default`           | generic dungeon corridor, pipes and grates |
| `bg_intake_industrial` | industrial intake hall, conveyor, rebar, sparks |
| `bg_zoo_korporacyjne`  | corporate zoo, cages, feeding troughs, animal stink |
| `bg_muzeum_spektakli`  | museum of spectacles, wax figures, film reels, plaster |
| `bg_bar_skurczybyk`    | dive bar, brass taps, neon booze signs, sticky floor |
| `bg_grzybica_bloom`    | fungal bloom cavern, glowing mushrooms, spores, mycelium |
| `bg_okopy_frontowe`    | trench warfare tunnels, mud, sandbags, gas haze |
| `bg_fabryka_pary`      | steam factory, boilers, pressure valves, coal glow |
| `bg_stacja_orbital`    | orbital cargo station, viewport stars, nav panels |
| `bg_kuznia_polorkow`   | half-orc forge, anvils, molten iron, charcoal smoke |
| `bg_biblioteka_miejska`| occult city library, forbidden tomes, wax seals, dust |
| `bg_room_safehouse`    | grimy safehouse lounge, vending, reception, dim neon |
| `bg_room_boss`         | boss arena, ominous spotlight, broadcast cameras |
| `bg_room_treasure`     | loot vault, sponsor crates, glinting credits |

## Portrety wrogów  (format kwadrat ~1:1, np. 512×512, popiersie)

Łańcuch: `wrog_<klucz_moba>` → `wrog_<archetyp>`.
Archetypy (fallback dla każdego moba): humanoid · beast · robot · blob ·
aberration · undead.

| Klucz pliku           | Subiekt do promptu |
|-----------------------|--------------------|
| `wrog_humanoid`       | hostile humanoid scavenger, makeshift armor, bust |
| `wrog_beast`          | mutated dungeon beast, fangs, matted fur, bust |
| `wrog_robot`          | battered security robot, red optic, exposed wiring |
| `wrog_blob`           | amorphous ooze creature, translucent, dripping |
| `wrog_aberration`     | eldritch anomaly, wrong geometry, too many eyes |
| `wrog_undead`         | reanimated crawler corpse, grey flesh, dead eyes |
| `wrog_intake_warden`  | floor-1 boss: hulking intake warden in riot gear |
| `wrog_boss_panicz_zoo`| floor-3 boss: pampered show-beast, bear-like, gaudy |
| `wrog_tunnel_runt`    | small vicious tunnel rat, wet, red eyes |

(Dla pozostałych bossów dodawaj `wrog_<klucz_z_entity_templates>`.)

## Portret gracza  (opcjonalny, kwadrat ~1:1)

Łańcuch awatara można nadpisać: `portret_<origin>` (np.
`portret_bezdomny`). Bez pliku → budowany proceduralnie z EQ (ui/avatar).

---

## Status
Pipeline gotowy (P29.71). Brak plików = fallback proceduralny. Każdy
wrzucony PNG działa od ręki, bez zmian w kodzie.
