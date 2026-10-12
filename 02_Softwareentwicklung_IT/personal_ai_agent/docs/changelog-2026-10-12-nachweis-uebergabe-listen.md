# Nachtrag 12.10.2026: Der Nachweis kennt jetzt die Uebergabe-LISTEN

## Warum

Der Bestandsnachweis (`tools/foto_sortierung/bestand_pruefen.py`, „fertig ist,
was verifiziert ist\") zaehlt die gebauten Stufen selbst nach. Seit dem 11.10.
kennt er auch die **Uebergabe-Stufe** (Ketten-Schritt 9, `uebergabe_manifest.jsonl`)
— also das, was tatsaechlich uebertragen wurde. **Nicht geprueft war die
Katalogleiste selbst**, die sagt, WAS ueberhaupt uebertragen wird. Der
vorherige Journal-Eintrag hatte sie als „zwei Wege, zwei Listen\" von Hand
benannt, nicht gemessen.

Der Fehlerfall ist derselbe wie bei der alten `bild_index.db` vom 10.10.: Eine
gebaute Ergebnisdatei, die **auf keiner Liste steht**, kommt nie ans Geraet —
und es merkt niemand, weil kein Nachweis die Liste gegen das stellt, was die
Dienste wirklich lesen. Die Startskripte nennen dieselbe Liste uebrigens
**zweimal** (einmal mit, einmal ohne `|| true`) — zwei Stellen, die
auseinanderlaufen koennen.

## Was geaendert wurde

Nur Werkzeug, Test und Doku — **kein Betriebs- oder Anzeigecode**.

1. **Neuer Leser `uebergabe_listen_lesen(pfad)`** liest die `--dateien`-Zeilen
   eines Startskripts: je Aufrufstelle die Zeilennummer und die Dateinamen,
   dazu die Vereinigung. Erkannt werden nur einfache Dateinamen mit einer der
   Endungen `.json`, `.jsonl`, `.db`, `.csv` — Platzhalter (`"$DATEIEN"`) und
   Endungs-Reste (`".csv"`) zaehlen nicht mit. Wirft nie.
2. **Neuer Leser `dienst_dateinamen(ordner)`** sammelt per **AST** die
   Zeichenketten-Literale in `backend/app`, die wie ein Dateiname aussehen
   (`__pycache__` bleibt aussen vor, `SyntaxError` wird uebersprungen). Ein
   **Kommentar ist kein Literal** und zaehlt damit nicht mit — dieselbe
   Begruendung wie beim repo-weiten Archiv-Waechter (Journal 18).
3. **Neue Prueffunktion `uebergabe_deckung_pruefen(...)`** stellt beides
   zusammen: je Skript Namen und Aufrufstellen, dazu die vom Dienst gelesenen
   Namen gegen die Liste. Neue Konstanten `STANDARD_UEBERGABE_LISTEN`
   (`termux/start-vorbereiten.sh`, `start-termux.sh`),
   `STANDARD_UEBERGABE_LISTE_PFLICHT` (der gemeinsame Startweg fuer App-Knopf
   und Widget), `STANDARD_DIENST_ORDNER`, `DIENST_DATEI_MUSTER`,
   `_LISTEN_MUSTER` und `UEBERGABE_GERAETESEITIG`.
4. **`UEBERGABE_GERAETESEITIG` — die begruendete Ausnahmeliste.** Dateien, die
   das **Geraet selbst erzeugt** (Quiz: `personen_bestaetigt.json`,
   `personen_vorgaben.json`, `personen_profile.json`, `gruppen_quiz_stand.json`,
   `gruppen_antworten.jsonl`, `quiz_fortschritt.json`; App: `geschichten.jsonl`,
   `anlass_umbenennung.jsonl`), **Geraetespeicher** (`gesichter_katalog.json`,
   `memory_store.json`, `klassifikation_lernfaelle.json`), **Postfach/Steuerung
   am Geraet** (`auftraege.json`, `auftraege.jsonl`, `antworten.jsonl`,
   `status.jsonl`, `conversations.json`, `letzte_nachricht.json`,
   `ueberlauf.jsonl`) und das **Archiv** (`archiv_index.db`, eigener Weg ueber
   `/sdcard/Download`). **Jede Aufnahme traegt ihren Grund im Quelltext**;
   ohne Grund gehoert die Datei auf die Liste — dann ist ihr Fehlen dort ein
   echter Befund (sonst waere jede Quiz-/Postfach-Datei ein Dauerfehlalarm).
5. **Ehrlich statt still, jede stille Abweichung wird eine Luecke:**
   * die mehrfachen **Aufrufstellen** derselben Liste stimmen nicht ueberein,
   * eine vom Dienst **gelesene Datei steht auf keiner Liste** (und ist nicht
     begruendet geraeteseitig) — sie kaeme nie ans Geraet,
   * die **Pflichtliste fehlt** ganz (dann ist die Uebergabe nicht pruefbar).
   Eine **uebergebene Datei, die kein Dienst liest**, wird dagegen nur
   **benannt** (Zeile, keine Luecke) — genau wie der Neben-Befund der
   Uebergabe-Stufe.
6. **Schalter:** `pruefen(..., uebergabe_listen=None, projekt=None)` und die
   Kommandozeile `--uebergabe-listen` (mit Komma getrennt, leer = nicht
   pruefen). **Voreinstellung `None`** — die uebrigen Pruefungen und alle
   bestehenden Tests bleiben dadurch unveraendert und schnell; die
   Kommandozeile prueft die zwei bekannten Skripte. Modul-Docstring und die
   Beschreibung des Berichts sind nachgezogen.
7. **Nur Zahlen und die eigenen Ergebnis-Dateinamen** — kein Pfad, kein
   Inhalt, kein Kommentar. (Im Test mit `tmp_path` und `.py` in den
   Uebergabe-Zeilen festgehalten.)

## Belege

* **Tests:** `backend/tests/test_bestand_und_handy_uebergabe.py` **71 → 75
  Testfunktionen** (4 neue: Zaehlung/Aufrufstellen an einem stimmigen
  Mini-Projekt, auseinanderlaufende Stellen + ungelistete Datei als Luecken,
  fehlende Pflichtliste als Luecke + Abschaltbarkeit, beide Leser tolerant bei
  fehlender/kaputter/fremdformatiger Quelle mit Platzhaltern, Endungs-Resten,
  Pfaden, Leerzeichen, `__pycache__` und kaputtem Python). Lauf der Datei:
  **75 passed**.
* **Pruefbefehl** (vom Hook erzwungen, `cd backend && .venv/Scripts/python -m
  pytest tests/ -q`): siehe Commit (`Exit 0`).
* **Messung am echten Bestand** (`bestand_pruefen.py`, Exit 0, nur lesend):

  ```
  Uebergabe-Listen (Deckung): termux/start-vorbereiten.sh: 12 Namen, 2 Stellen (gleich);
                             start-termux.sh: 12 Namen, 2 Stellen (gleich)
    Dienst liest 31 Datendateinamen; auf einer Liste 12, geraeteseitig 19, ohne Liste 0
    Uebergeben, aber von keinem Dienst gelesen (4): bild_beschreibungen_papa_reich.jsonl,
                                                    bild_beschreibungen_reich.jsonl,
                                                    bild_index.db, orte.jsonl
  ```

  Die Ergebnisliste bleibt damit **5 Luecken** (vier kosten-/geraetebunden, die
  fuenfte = 2 Kennungen ohne Gruppe). Die Listen sind stimmig, und **keine**
  vom Dienst gelesene Datei fehlt auf einer Liste — der Befund ist die
  Gegenrichtung.

## Ehrlicher Neben-Befund (gemessen, nicht geaendert)

**Vier Dateien reisen zum Geraet, ohne dass sie dort jemand liest:**
`bild_index.db` (der Bildindex), `bild_beschreibungen_reich.jsonl`,
`bild_beschreibungen_papa_reich.jsonl` und `orte.jsonl`. Gemessen (nicht
vermutet): keines dieser vier Namen kommt in `backend/app`, `frontend/` oder
`android/` vor; `orte.jsonl` wird ausschliesslich von den PC-Werkzeugen
`orte_zuordnen.py`/`anlass_namen.py` gelesen, die auf dem PC laufen. Das
verlaengert den Neben-Befund der Uebergabe-Stufe („kein Backend-Dienst liest
die reichen Beschreibungen\") um den Bildindex und die Ortsnamen. **Nicht
umgebaut** — ob die reichen Beschreibungen den knappen Altspeicher ersetzen
sollen und ob die Bildsuche verdrahtet wird, ist ausdruecklich Sebastians
Entscheidung (der Plan haelt sie offen).

**Korrektur einer eigenen Notiz (codegenau statt vermutet):** Der vorherige
Journal-Eintrag nannte `~/foto_sortierung/whatsapp_zuordnung.json` als „von
`archiv_standard`/Chat genutzt\". Gemessen ist das **falsch**: in `backend/app`
gibt es **keinen** Leser dieser Datei; sie wird nur vom PC-Werkzeug
`tools/foto_sortierung/chat_andocken.py` gelesen (und von Tests). Sie ist damit
**kein** Kandidat fuer eine Uebergabe-Pruefzeile im Backend — die Notiz ist
hier berichtigt.

## Ehrlich offen

Nichts geloescht, kein Bild-/Gesichtsdienst, keine Geraeteeingaenge, keine
kostenpflichtigen Massenlaeufe. Nur eigene Pfade committet (nie `git add -A`).
Am Geraet ist nichts gegengeprueft (kein Handy am Kabel in dieser Runde).
