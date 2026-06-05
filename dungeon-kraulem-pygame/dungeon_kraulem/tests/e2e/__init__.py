"""End-to-end test framework — Rule 12d.

Headless `Game` driver pozwalający na scripted-input symulację
flow gracza. Bez tego framework testy jednostkowe pokrywały TYLKO
mechanikę modułu (parser, dialogue engine, etc.) ale NIE faktyczną
ścieżkę user-facing (pogadaj → state opens → log content → etc.).

E2E testy żyją tutaj. Każdy test ma być deterministic, fast (<1s),
i NAPRAWDĘ reprezentować to co gracz wpisuje w grę.
"""
