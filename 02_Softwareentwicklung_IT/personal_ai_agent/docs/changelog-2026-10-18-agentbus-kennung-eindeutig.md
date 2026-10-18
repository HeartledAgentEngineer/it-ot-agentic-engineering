# 18.10.2026 — Agentenbus: Nachrichten-Kennung ist jetzt eindeutig (flakiger Prüfbefehl behoben)

## Der Befund (gemessen, nicht vermutet)

Der volle Prüfbefehl fiel in einem Tor-Lauf rot, mit **einem** Fehler:

```
FAILED tests/test_agentbus.py::test_gelesen_vermerk_ueberlebt_weiteren_send
E  assert [] == ['zwei']
```

Allein ausgeführt war dieselbe Datei **grün** (30 passed, Exit 0), und an den Dateien des
Agentenbusses war seit dem 29.09.2026 nichts geändert — also ein **flakiger** Test, nicht Folgen einer
Änderung. Ursache am Code gemessen:

`tools/agentbus/agentbus.py`, `send`: die Kennung war

```python
"id": f"m{int(time.time() * 1000)}",
```

**Millisekunden-Auflösung — zwei Nachrichten in derselben Millisekunde bekommen dieselbe Kennung.**
Die Lese-Vermerke liegen in `gelesen-<agent>.txt` und sind Mengen von Kennungen (`_ungelesen`:
`schon = m.get("id") in gelesen …`). Fällt die Kennung zusammen, markiert der Vermerk der ersten
Nachricht **auch die zweite** als gelesen — genau die gemessene Ausgabe (`[]` statt `['zwei']`).
Ob es passiert, hängt davon ab, ob die beiden Schreibvorgänge in dieselbe Millisekunde fallen; allein
läuft der Test ohne Last und damit fast immer in zwei verschiedene Millisekunden.

## Die Änderung

Neu in `tools/agentbus/agentbus.py`: `_neue_kennung(d)` — Basis bleibt die Millisekunde, bei einer
Kollision kommt ein Zähler dahinter, geprüft gegen die Kennungen, die schon in `messages.jsonl`
stehen (`m1750000000123`, `m1750000000123-1`, …). Deterministisch, ohne Zufall, ohne neue Abhängigkeit;
`sent` verhält sich unverändert (Kennung, Reihenfolge, anhängendes Log).

## Belege (in diesem Lauf selbst ausgeführt)

- Neuer Test `backend/tests/test_agentbus.py::test_kennung_bleibt_eindeutig_bei_gleicher_millisekunde`
  mit **eingefrorener Uhr** (`monkeypatch.setattr(bus.time, "time", …)`):
  zwei Nachrichten in derselben Millisekunde haben **verschiedene** Kennungen; Lesen liefert beide,
  ein zweites Lesen nichts; eine **dritte** Nachricht in derselben Millisekunde wird gelesen, obwohl
  die ersten beiden schon gelesen sind.
  **Gegenprobe im selben Test:** mit der alten Regel (`_neue_kennung` auf die Millisekunden-Kennung
  zurückgesetzt) liefert Lesen `[]` — der gemessene Fehler tritt also reproduzierbar auf. Ohne diese
  Gegenprobe wäre der Test nicht scharf.
- `pytest tests/test_agentbus.py -q` → **31 passed**, Exit 0 (30 vorher + 1 neuer Test).

## Ehrlich dazu

Der Agentenbus wird **seit 14.10.2026 nicht mehr benutzt** (siehe `AGENTS.md`, Hermes-Arbeit läuft über
eigene Hermes-Sitzungen). Diese Änderung schaltet **keine** Funktion frei — sie nimmt einem flakigen
Test die Zufälligkeit, der den gemeinsamen Prüfbefehl und damit jeden Commit blockieren konnte.
Ein Bus, der Nachrichten verschluckt, ist außerdem genau die Art Fehler, die man später sucht, wenn
er doch wieder benutzt wird.
