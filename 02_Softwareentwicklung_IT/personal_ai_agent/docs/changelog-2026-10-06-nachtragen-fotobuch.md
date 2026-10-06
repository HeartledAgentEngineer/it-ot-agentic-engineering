# Changelog 06.10.2026 — Fotobuch-Gesichter **nachtragen** statt neu gruppieren

## Anlass

Im Erzählen zeigten die Fotobuch-Seiten (erste Wochen nach der Geburt, mit Vater
und Mutter) „niemand erkannt": Die 842 Fotobuch-Fotos waren nie in der
Gesichtererkennung. Der Nachlauf ist gelaufen (839 geholt, 3 Löcher, 0 Fehler,
110 ohne Gesicht, 39 Mengen → `personen_vektoren_fotobuch.jsonl`, 1.934 nutzbare
Gesichter).

Ein **voller Neu-Lauf** wäre der falsche Weg: der Trockenlauf mit den
Fotobuch-Vektoren (`.hermes/plans/hilfen-2026-10-06/gruppen_stabilitaet.py`)
zeigte, dass die schon **benannten** Gruppen dabei durcheinanderkommen — eine
Gruppe behielt nur 36 von 167 Gesichtern (22 %), andere 74–83 %, zwei kleine 0 %,
und **27 Gesichter wanderten zu einer anderen benannten Person** (falscher Name).

## Was neu ist

**`tools/foto_sortierung/personen_gruppieren.py` — neue Betriebsart
`--nachtragen <datei...>`** (Trockenlauf ist Standard, `--schreiben` schreibt):

1. **Einlesen:** neue Gesichter über dasselbe `gesichter_lesen()` wie der
   große Lauf — Mengen-Regel und Gesichtsbewertung gelten unverändert.
   Gesichter, deren `(bild_id, index)` schon in der Zuordnung steht, werden
   übersprungen (idempotent).
2. **Alte Gruppen bleiben unberührt:** die Zuordnungszeilen werden **wortgleich**
   übernommen, die alten Mittelpunkte aus `kennungen.json` **nicht** verschoben.
3. **Andocken:** je neues Gesicht (nach Qualität `anteil × score` absteigend)
   Cosinus gegen alle alten Mittelpunkte; die ähnlichste Gruppe mit
   Cosinus ≥ `ZUORDNUNG_AEHNLICH` (0,55) bekommt es — **nie zwei Gesichter
   desselben Bildes in dieselbe Gruppe** (cannot-link, inklusive der schon
   vorhandenen Gesichter des Bildes). Nutzer-Ausschlüsse aus
   `personen_vorgaben.json` gelten wie im großen Lauf.
4. **Rest:** nicht angedockte Gesichter gruppieren sich **untereinander**
   (`gruppieren()`, unverändertes Verfahren); Gruppen ab `MIN_GROESSE` bekommen
   **neue** Kennungen hinter der höchsten Nummer (Nummern werden nie
   wiederverwendet), der Rest bleibt Rauschen (`kennung: null`).
5. **Schreiben (nur `--schreiben`, atomar, außerhalb des Repos):**
   `gesicht_zuordnung.jsonl` = alte Zeilen wortgleich + neue; 
   `personen_beispiele.json` = alte Gruppen mit erhöhten
   `groesse`/`bilder`/`videos`/`von`/`bis` (Beispiele dürfen um
   Fotobuch-Gesichter ergänzt werden, max. 8, `beispiele_waehlen`) plus neue
   Gruppen im selben Format; `kennungen.json` = alte Mittelpunkte unverändert +
   neue dazu. **Vorher** werden die drei Dateien als `*.vorher` gesichert
   (Rückweg; eine vorhandene Sicherung wird nicht überschrieben).
6. **Bericht nur Zahlen:** neue Gesichter, angedockt (Gesichter/Gruppen), neue
   Gruppen mit Kennungsbereich, Rauschen, Rechenzeit — keine Namen, keine Pfade.

Neue Funktionen: `zuordnung_zeilen_lesen`, `beispiele_lesen`, `_vorher_sichern`,
`nachtrag_rechnen` (rein, ohne I/O), `nachtrag_schreiben`,
`nachtrag_bericht_text`, `_nachtragen_main`.

## Prüfstand (alles in dieser Sitzung gefahren)

- **Prüfbefehl:** `cd backend && .venv/Scripts/python.exe -m pytest tests/ -q`
  → **3435 passed, 1 skipped, Exit 0** (Grundstand 3418 + 17 neue Tests),
  208 s, 0 FAILED/ERROR.
- **Neu: `backend/tests/test_personen_gruppieren_nachtragen.py`, 17 Tests**
  (erfundene Vektoren, offline, alles in `tmp_path`): Andocken an die eigene
  Gruppe; cannot-link (zwei Gesichter eines Bildes nie in einer Gruppe);
  Schwelle greift; Ausschlussregel beachtet; Rest bildet neue Kennungen mit
  **fortlaufender** Nummer (auch bei zwei neuen Personen); kleine Restgruppe ist
  Rauschen; zweiter Lauf idempotent (0 neue); ohne `--schreiben` byte-gleiche
  Dateien; Schreiben hält die alten Zeilen **wortgleich** und legt drei
  `*.vorher`-Sicherungen an (zweites Schreiben überschreibt sie nicht); alte
  Mittelpunkte unverändert; Beispiele werden ergänzt (nichts geht verloren);
  Kommandozeile trocken/echt; Repo-Ziel `SystemExit(2)`; fehlende Grundlage →
  Exit 2; Bericht ohne Pfade/Namen.
- **Echter Trockenlauf** (`.hermes/plans/hilfen-2026-10-06/nachtragen_stabilitaet.py`,
  nur lesend, nichts geschrieben):
  - Alte Zuordnung: 30.937 Zeilen, 30.937 Gesichter, 1.106 Kennungen — wortgleich übernommen
  - Neue Gesichter: **1.934**, angedockt: **744 in 128 Gruppen**, neue Gruppen:
    **39** (`Person_1111` … `Person_1149`), Rauschen: 663, Rechenzeit 1,4 s
  - Fotobuch-Gesichter: 1.271 in einer Gruppe, davon **155 bei benannten
    Personen**, 527 in neuen Gruppen, 663 Rauschen
  - **Stabilität: 0 von 19.477 alten Gesichtern haben die Gruppe gewechselt;
    alle 17 benannten Kennungen behalten 100 %** (Zuwächse u. a. +83, +34, +18,
    +17, +3) — gegen 22 % Verlust und 27 falsch zugeordnete Gesichter beim
    Neu-Rechnen.

## Was noch aussteht

- **Schreiben** (`--schreiben`) erst nach Sebastians OK auf die Trockenlauf-Zahlen.
- Danach: `tools/handy/gruppen_aufs_handy.py --senden`, Termux neu starten
  (`adb shell am force-stop com.termux` + `am start -a android.intent.action.VIEW -d heyagent://start`),
  Beleg am Handy: Fotobuch-Seiten im Erzählen zeigen Personen.
- Namens-Rückweg Handy→PC bleibt eigener Punkt: die **Namen** liegen weiter nur
  am Handy (`personen_bestaetigt.json` fehlt am PC), bekannt sind hier nur die
  Kennungen.

## Regeln eingehalten

Biometrie (Vektoren, `kennungen.json`) bleibt am PC; Berichte nennen nur Zahlen.
Nichts gelöscht — vor dem Schreiben entstehen Sicherungen. `git commit --only`,
code + docs in einem Commit.
