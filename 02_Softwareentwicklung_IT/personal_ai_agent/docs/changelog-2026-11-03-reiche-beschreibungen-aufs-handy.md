# 03.11.2026 — Reiche Bildbeschreibungen kommen aufs Handy

## Befund
Am Handy hatten die Fotobuch-Bilder keine Beschreibung; die KI-Anlassgeschichte hatte darum kaum Stoff.

## Zählung (nur Zahlen, `tools/foto_sortierung/beschreibung_abdeckung.py`)
| | PC (alle Quellen) | wie am Handy (nur `bild_beschreibungen.jsonl` + `life_archive.db`) |
|---|---|---|
| Fotobuch (842 Bilder) | 840 beschrieben (99,8 %) | **0** |
| Ereignisse (7.616 Bilder) | 7.613 | 7.613 |
| Beschreibungen gesamt | 26.241 | 19.065 |

## Ursache
`erzaehl_service.beschreibungen_alle_pfade()` liest neben `bild_beschreibungen.jsonl` vier
`*_reich.jsonl`-Dateien. Die Fotobuch-Beschreibungen stehen nur dort. Die Übernahmeliste in
`termux/start-vorbereiten.sh` (und im alten `start-termux.sh`) nannte sie nie, also blieben sie
im Download-Ordner liegen bzw. wurden nie übertragen. Der Wächtertest leitet die erwarteten
Namen aus Dienst-Konstanten ab — die vier Namen waren aber nur fest im Code, ohne Konstante.

## Änderung
- `erzaehl_service.py`: neue Konstante `REICHE_BESCHREIBUNGEN_DATEINAMEN`, von
  `beschreibungen_alle_pfade()` genutzt.
- `termux/start-vorbereiten.sh`, `start-termux.sh`: die vier Namen in allen Übernahmelisten.
- `test_uebergabe_uebernehmen.py`: Wächter kennt 16 statt 12 Dateien (rot → grün).
- Daten: die vier Dateien per `tools/handy/gruppen_aufs_handy.py --senden` in den Download-Ordner
  des Handys (Größen am Handy gleich).

## Hinweis Neustart
Beim ersten Neustart holt `git pull` das neue Skript, Bash liest aber die schon geöffnete alte
Fassung weiter. Erst der **zweite** Neustart übernimmt die Dateien.
