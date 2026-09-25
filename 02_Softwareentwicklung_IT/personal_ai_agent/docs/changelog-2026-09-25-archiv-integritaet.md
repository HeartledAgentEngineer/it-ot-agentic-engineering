# Archiv-Integrität: Zeiger, Zeilennummern und die Anfüge-Regel

**Datum:** 25.09.2026 · **Anlass:** Vorbereitung des WhatsApp-Imports
**Status:** untersucht und gemessen (keine Code-Änderung in diesem Schritt)

## Anlass

Vor dem Anschluss der WhatsApp-Exporte musste geklärt werden, ob ein weiterer
Lauf der Normalisierung die bestehenden Daten gefährdet. Zwei Fragen standen im
Raum: (1) überschreibt die Normalisierung die vorhandenen Nachrichten, und
(2) bleibt die Verknüpfung zwischen Index-Zeiger und Originaltext stabil?

## Befund 1 — die Normalisierung überschreibt (gemessen)

`src/normalisieren.py` sammelt die gewählten Quellen und ruft
`schreibe_jsonl(args.ziel, nachrichten)`; `src/normalform.py:118-126` öffnet die
Zieldatei mit dem Modus `"w"` — also **überschreibend**, und zwar vollständig.

`normalized/messages.jsonl` enthält **40.627 Zeilen / 46,8 MB**. Ein Aufruf

    python -m src.normalisieren --nur whatsapp

hätte diese Datei durch **nur** die WhatsApp-Nachrichten ersetzt. Die anderen
Quellen wären aus der normalisierten Datei verschwunden (aus `raw/` neu
erzeugbar, aber der Index hätte dann veraltete Verweise).

**Regel:** Für neue Quellen immer `--ziel <Nebendatei>` benutzen und das
Ergebnis anschließend **anhängen**. Die echte Datei wird vorher gesichert
(`messages.jsonl.bak-<Datum>`).

## Befund 2 — die Zeilennummer im Index ist 0-basiert (gemessen)

Der Index (`db/archiv_index.db`) trägt in `nachrichten.id` die Zeilennummer der
JSONL — laut Schema-Kommentar (`archiv_suche.py:141`). Gemessen am echten
Bestand gilt:

| Index-ID | Inhalt | JSONL-Zeile mit demselben Inhalt |
|---|---|---|
| 1 | 1965-08-16 (Kalender) | **2** |
| 2 | 1968-04-19 (Kalender) | 3 |
| 40.626 | 2026-12-28 (Kalender) | **40.627** |

Höchste Index-ID = **40.626**, Datei hat **40.627** Zeilen → der Versatz beträgt
**genau 1**. Ursache: Die Datei wurde nach dem Index-Bau einmal **neu sortiert**
(die Kalender-Einträge von 1940 kamen später hinzu und rutschten nach vorn).

## Befund 3 — Treffer und Nachlese zeigen trotzdem auf dieselbe Stelle (gemessen)

Drei echte Fragen, jeweils bester Treffer, danach die Nachlese
(`ArchivSuche.original`) gegen die Datei gestellt:

| Frage | Zeiger-`ordinal` | Nachlese-Text deckt sich exakt mit Zeile | Chat-Zuordnung |
|---|---|---|---|
| „Yoga Hamburg" | 16.154 | **16.155** (93/93 Wörter) | Zeile 16.154 = falscher Chat, 16.155 = richtig |
| „Zahnarzt Prophylaxe Termin" | 22 | **23** (1/1) | 22 falscher Chat, 23 richtig |
| „Bachelorarbeit" | 11.951 | **11.952** (2/2) | 11.952 richtig |

**Ergebnis:** Treffer und Nachlese**stimmen überein** — beide zeigen auf dieselbe
Nachricht. Der Grund: Das Nachlesen läuft über die **Originaldatei**
(`quelldatei` aus dem Zeiger, z. B. `raw/chatgpt/conversations-000.json`); die
JSONL ist nur der **Rückfallweg** (`archiv_suche.py:679, 992-996`). Der
Zeilenversatz wirkt sich dort nicht aus.

**Offene Grenze:** Wird der Index mit `--ohne-quelldateien` gebaut, zeigt der
Zeiger ausschließlich auf `normalized/messages.jsonl` — dann trifft der
0-basierte `ordinal` die Zeile um eins daneben. Das ist bisher **nicht** der Fall
(alle 1.109 Gespräche haben eine aufgelöste Quelldatei), aber der Rückfallweg
bleibt damit unzuverlässig. Vorschlag für einen eigenen Schritt: den Zeiger um
eine **Inhalts-Prüfsumme** (z. B. SHA-1 des Nachrichtentexts) erweitern und beim
Lesen prüfen — dann kann kein Versatz mehr stillschweigend danebengreifen.

## Regel für alle künftigen Importe

1. `normalized/messages.jsonl` wird ab jetzt **nur angehängt**, nie neu
   sortiert. Jede Neusortierung verschiebt **alle** Zeiger stillschweigend.
2. Neue Quellen (wie WhatsApp) laufen über `--ziel <Nebendatei>` → Prüfsumme
   → **anhängen** an das Ende.
3. Vor jedem Import: Sicherung `messages.jsonl.bak-<Datum>` anlegen.
4. Nach jedem Import: Stichprobe „Zeiger → Originaltext" (Muster dieses
   Dokuments) und Zählung (Zeilen vorher/nachher) dokumentieren.

## Belege

- `src/normalisieren.py:64-93` (Ablauf), `src/normalform.py:118-126` (Modus `"w"`)
- `normalized/messages.jsonl`: 40.627 Zeilen, 46,8 MB
- `db/archiv_index.db`: 40.627 Zeilen in `nachrichten`, höchste ID 40.626
- Messungen: Zeilenvergleich ID↔Zeile (4 Stichproben), Wortüberlappung und
  Exaktvergleich Nachlese↔Datei (3 Fragen), alles am 25.09.2026 ausgeführt
