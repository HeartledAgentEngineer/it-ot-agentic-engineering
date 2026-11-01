# Änderungsprotokoll 01.11.2026 — Sortierplan hängt nicht mehr an der Uhrzeit

## Befund (Ursache belegt)

Der volle Prüfbefehl brach am 01.11. mit `tests/test_foto_sortieren.py::test_plan_zweiter_lauf_ist_gleich`
ab (1 failed / 6109 passed). Nachgestellt mit 1,2 s Pause zwischen zwei Planläufen: einziger Unterschied ist
`ordner[].createfolder.zeit`. Die **trockene** Ordner-Vorbuchung (`tools/pcloud/pcloud_bewegungen.py`, `_eintrag`)
trägt die aktuelle Uhrzeit; sprang die Sekunde zwischen den beiden Läufen, waren die Pläne verschieden.

Folgen: der Test war zufällig rot, und im Werkzeug griff „Plan unverändert“ (`foto_sortieren.py`, Vergleich über
`_inhalt_ohne_stand`, das nur `stand` ausblendet) bei einem zweiten Lauf praktisch nie.

## Änderung

- `tools/foto_sortierung/foto_sortieren.py` `_trocken_createfolder`: die Vorbuchung kommt **ohne** `zeit` in den
  Plan. Die Planungszeit steht weiter in `stand`. Beim echten Buchen ergänzt `pcloud_bewegungen` eine fehlende
  Zeit selbst (`zeile["zeit"] = _jetzt_iso()`), am Vollzug ändert sich nichts.
- Kein Code liest `createfolder.zeit` (gesucht in `tools/`, `backend/app`).

## Prüfung

- Neu `test_plan_haengt_nicht_an_der_uhrzeit` (Uhr per `monkeypatch` umgestellt): zuerst rot, dann grün.
- `tests/test_foto_sortieren.py` 120 passed; verwandte Tests (Bestand/Handy-Übergabe, pCloud-Bewegungen,
  Rückrollen, Übergabe, Tageslauf) 263 passed.
