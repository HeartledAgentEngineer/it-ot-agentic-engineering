# 12.10.2026: Der Nachweis kennt jetzt das Chat-/WhatsApp-Archiv

## Warum

Der Bestandsnachweis (`tools/foto_sortierung/bestand_pruefen.py`, „fertig ist,
was verifiziert ist") zaehlt die gebauten Stufen selbst nach: Plaene, Gesichter,
Beschreibungen, Gruppen, OSM, Bildindex, Neuausrichtung, Anlaesse, Ortsnamen,
Erzaehl-Quellen, Beziehungen, Personen, App-Uebersicht, Doppelten, Sebastians
eigene Erzaehl-Stufen und die Uebergabe.

**Nicht gezaehlt war die Stufe, aus der JEDE Archiv-Antwort im Chat ihre
Fundstellen zieht:** das Chat-/WhatsApp-Archiv (Rohdaten
`normalized/messages.jsonl`, Textschicht `db/memory.db`, voller Index
`db/archiv_index.db`). Genau an dieser Stufe ist am 10.10. ein echter Fehler
aufgefallen — der Chat suchte in einer alten Kopie, WhatsApp kam gar nicht an
(Plan, Abschnitt „WhatsApp: Bestandsaufnahme"). Gefunden wurde das **von Hand**;
eine Pruefzeile gab es nicht.

## Was geaendert wurde

Nur Werkzeug, Test und Doku — **kein Betriebs- oder Anzeigecode**. Nichts
geloescht, nichts verschoben, kein Netzaufruf.

1. **Neuer Abschnitt „Archiv (Chat/WhatsApp)"** in `bestand_pruefen.py` mit drei
   Lesern, die **nie werfen**: `archiv_jsonl_zaehlen(pfad)` (Rohdaten
   zeilenweise), `archiv_index_lesen(pfad, heute=None)` (voller Index),
   `archiv_memory_lesen(pfad)` (Textschicht des alten Weges), dazu
   `archiv_vektordatei_stand(ordner)` und die Helfer `_ro_verbindung`,
   `_zaehle_sql`, `_je_quelle`, `_jahr`, `_dimensionen`, `_meta_lesen`,
   `_archiv_kopf`, `_quellen_kurz`. Neue Konstanten `STANDARD_ARCHIV_ORDNER`,
   `ARCHIV_MESSAGES`, `ARCHIV_INDEX_DB`, `ARCHIV_MEMORY_DB`,
   `ARCHIV_VEKTORDATEI`, `ARCHIV_FRUEHESTES_JAHR`, Modul-Docstring nachgezogen.
2. **Zwei neue Schalter:** `pruefen(..., archiv=None, archiv_heute=None)` und
   `--archiv` / `--archiv-heute`. **Voreinstellung `None`** (die Stufe wird nur
   geprueft, wenn sie ausdruecklich gewaehlt ist), die Kommandozeile setzt den
   Archivordner neben dem Projekt; `--archiv ""` schaltet sie ab. So bleiben die
   uebrigen Tests offline und schnell.
3. **Gezaehlt wird nur, was nachpruefbar ist.** Rohdaten: Zeilen, nicht lesbare
   Zeilen, Zeilen ohne Quelle/Text, Quellen als Zahl. Index: Nachrichten,
   Gespraeche, Chunks, davon mit Vektor, Vektoren (je Modell, Dimension, Waisen
   ohne Chunk), Volltextindex (`chunks_fts_docsize`) und die Selbstauskunft aus
   `meta`. Textschicht: Nachrichten, Chunks, davon mit Vektor. Zeitstempel nur
   als **Jahresspanne** plus die Zahl vor 1990 und in der Zukunft.
4. **Ehrlich statt still — jede Abweichung wird eine Luecke:**
   Zeilen in `messages.jsonl` gegen Nachrichten im Index (und die Textschicht
   gegen beide), eine **Quelle ohne Nachricht im Index**, **Chunks ohne Vektor**,
   **Vektoren != Chunks mit Vektor**, **verwaiste Vektoren**, ein
   **unvollstaendiger Volltextindex** (die Volltextsuche liefert dann still zu
   wenig) und eine **Selbstauskunft**, die der Zaehlung widerspricht
   („nicht reproduzierbar" — dieselbe Strenge wie bei den Doppelten).
   Ein fehlender Ordner/Index und eine nicht lesbare SQLite-Datei sind eigene
   Luecken, keine stillen Nullwerte.
5. **Nur Zahlen und Quellen-NAMEN** (Apps wie `whatsapp`, `chatgpt`) — **kein
   Nachrichtentext, kein Titel, kein Gespraechsname, kein Pfad** (im Test mit
   einem Fantasiewort und `str(tmp_path) not in text` festgehalten).

## Belege

* Testdatei `backend/tests/test_bestand_und_handy_uebergabe.py` **67 → 71
  Testfunktionen** (4 neue: Zaehlung/„stimmiges Archiv ist kein Befund",
  jede Abweichung als Luecke, fehlender Ordner/Index + Abschaltbarkeit, alle
  Leser tolerant bei kaputter JSONL/keiner SQLite/leerer DB). Lauf der Datei
  **71 passed**.
* Pruefbefehl (siehe Commit) frisch und vollstaendig, Exit 0.
* **Messung am echten Bestand (nur lesend, Exit 0)** — Zeilen des neuen
  Abschnitts:

```
Archiv (Chat/WhatsApp): messages.jsonl: 282.029 Zeilen, 68 ohne Text - 7 Quellen
  Quellen: whatsapp 241.402, chatgpt 19.057, claude-code 13.328, gemini 4.734,
           claude-ai 3.088, google-kalender 405, google-notizen 15
  archiv_index.db: 282.029 Nachrichten, 1.590 Gespraeche, 52.679 Chunks,
                   52.679 mit Vektor, 52.679 Vektoren
  Modell openai/text-embedding-3-small, Dimension 1536, Speicher float16;
  gebaut 2026-09-25, ergaenzt 2026-09-28; Token 16.035.838, Kosten 0,32 USD
  Volltextindex: 52.679 von 52.679 Chunks indexiert
  Vektor-Dimensionen: 1 (1.536)
  Zeitstempel: 0 ohne, Jahre 1940-2026; vor 1990: 5; in der Zukunft: 2
  Rueckfallweg memory.db: 282.029 Nachrichten, 52.679 Chunks, davon 33.312 mit
  Vektor (alter Stand)
  Vektordatei des Rueckfallwegs (memory.vektoren.f32): fehlt
```

  Alle Abgleiche stimmen: 282.029 Rohdatenzeilen = 282.029 Nachrichten im Index
  = 282.029 Nachrichten in `memory.db`; 0 Chunks ohne Vektor, 0 verwaiste
  Vektoren, Volltextindex vollstaendig, keine Quelle ohne Nachricht im Index,
  `meta` deckt sich mit der Zaehlung. **Kein Befund** — die Stufe ist stimmig.
  Die Ergebnisliste bleibt bei **5 Luecken** (vier kosten-/geraetebunden, die
  fuenfte aus Journal 23).

## Ehrliche Neben-Befunde (gemessen, nicht geaendert)

1. **68 Nachrichten ohne Text** in den Rohdaten (von 282.029). Das ist
   plausibel (Bilder/Anhaenge ohne Text) und **keine** Luecke — benannt, weil
   die Zeile es zeigt.
2. **Zeitstempel 1940–2026.** 5 Nachrichten liegen vor 1990, 2 nach dem
   heutigen Tag — alle aus `google-kalender`, also Kalendereintraege mit alten
   beziehungsweise kuenftigen Jahren (Geburtstage/Termine), keine Chat-Aussage.
   `zeitraum_von`/`-bis` in `meta` behaupten genau diese Spanne. **Keine
   Luecke**, aber ein Hinweis: wer nach Datum zitiert, sieht hier Kalenderdaten
   mit alten Jahren.
3. **Die Vektordatei des alten Weges fehlt unter ihrem erwarteten Namen.**
   `db/memory.db` nennt als `vektordatei` `memory.vektoren.f32`; im Ordner liegt
   nur eine Fassung mit **abweichendem Namen** (`memory.vektoren
   [conflicted].f32`, ein Git-Konflikt-Rest, 136 MB) und die Vor-WhatsApp-Fassung.
   Der alte Weg oeffnet die Vektoren ueber den festen Namen — er findet also
   keine Vektoren, und seine Bedeutungssuche schweigt still. Auf dem PC ist das
   folgenlos (der Standardweg ist der volle Index), deshalb als Zeile benannt,
   **nicht** als Luecke und **nicht** umgebaut: die Datei umzubenennen waere ein
   Eingriff in ein Datenarchiv und damit Sebastians Entscheidung.

## Ehrlich offen (unveraendert)

5 Luecken: 8 Fotos ohne Beschreibung und 25 Videos ohne Gesichter-Lauf (bezahlte
Netzaufrufe, Sebastians Entscheidung), WhatsApp-Verdrahtung (Geraet) und die
2 Kennungen ohne Gruppe (Journal 23). Nichts geloescht, kein Bild- oder
Gesichtsdienst aufgerufen, keine Geraeteeingaenge, keine kostenpflichtigen
Massenlaeufe.
