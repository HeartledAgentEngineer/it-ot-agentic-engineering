# Änderungsprotokoll 11.10.2026 — zweite Prompt-Fassung „bildgeschichte" in bild_beschreiben.py

## Anlass

Die Kontaktbogen-Beschreibungen (14 Wörter je Kachel, `bild_beschreiben.py`) sind
für die Textsuche gebaut — knapp, gegenständlich, eine Zeile. Für Erzählungen
fehlt darin das, was eine Bildgeschichte ausmacht: Handlung, Stimmung, Licht und
die Umgebung als zusammenhängender Text. Gewünscht war deshalb eine zweite,
reichhaltige Fassung (englischer Prompt, 2 bis 4 Sätze je Kachel), die man per
Schalter wählen kann — **ohne** das heutige Verhalten zu verändern.

## Änderung

Neuer Schalter `--prompt-variante` in `tools/foto_sortierung/bild_beschreiben.py`:

- **`stichwort`** (Standard, unverändert): der bisherige deutsche Prompt — EIN
  knapper Satz je Kachel, höchstens 14 Wörter. Wort für Wort der Bestand.
- **`bildgeschichte`** (neu): englischer Prompt — je Kachel 2 bis 4 Sätze: wer
  zu sehen ist (OHNE Personennamen, ohne Kennzeichen, ohne Adressen), was
  passiert (Handlung), Umgebung/Ort (drinnen/draußen, Landschaft, Raum),
  Stimmung und Licht, auffällige Gegenstände oder lesbarer Text; höchstens
  70 Wörter. Englisch, weil Modelle in ihrer besten Sprache besser schreiben
  und englischer Text rund 20 % token-sparsamer ist. Die Verbote des
  Bestands-Prompts (keine Namen, keine Kennzeichen, keine Adressen, nichts
  erfinden, nur sicher Erkennbares) gelten unverändert.

Technisch:

- `BESCHREIBUNG_MAX_WOERTER = 14` bleibt unverändert; neu daneben
  `BESCHREIBUNG_MAX_WOERTER_BILDGESCHICHTE = 70` und die Zuordnung
  `PROMPT_VARIANTEN` — einzige Quelle für Prompt **und** Antwort-Normalisierung
  (`max_woerter_fuer(variante)`).
- `prompt_bauen(anzahl, variante='stichwort')` wählt die Fassung.
  `_prompt_stichwort_bauen` (Zeile 465) ist der unveränderte Bestandstext,
  `_prompt_bildgeschichte_bauen` (Zeile 500) der neue englische Prompt.
- `beschreibung_normalisieren(text, max_woerter=14)` kürzt wahlweise bei 14
  oder 70 — Standard 14, damit alle bestehenden Aufrufe und Tests unverändert
  laufen. `beschreibungen_uebernehmen(..., max_woerter=14)` reicht die Grenze
  durch; `bogen_verarbeiten(..., variante='stichwort')` zieht Prompt und
  Wortgrenze aus derselben Variante; die Kommandozeile reicht
  `args.prompt_variante` durch (unbekannter Wert ⇒ argparse-Fehler, Exit 2).
- Unverändert (Auftrag): das JSON-Ausgabeschema (`je_kachel` → JSONL-Felder
  `fileid, datei, jahr, monat, tag, ordner, beschreibung, bogen_id, modell,
  kosten_usd, zeit`), die Kostenrechnung, `--limit`/`--budget`/`--modell`/
  `--kachel`/`--spalten`/`--jsonl` und das Überspringen bereits beschriebener
  Bilder.

## Prüfung (alles offline — kein Vision-Aufruf, kein Netz)

- **Goldtexte des Bestands:** `backend/tests/testdaten/prompt_stichwort_n3.txt`
  (1275 B, sha256 `7009c7848430b85f…`) und `…_n36.txt` (1406 B, sha256
  `4d4a02c350d50006…`) wurden **vor** der Änderung aus dem Werkzeug erzeugt;
  die Tests vergleichen byteweise (`test_prompt_stichwort_ist_wortgleich_zum_bestand`).
- **Vorher/Nachher-Dump aller Stichwort-Prompts n=1..40** (Sonde,
  `prompt_bauen` ist rein): beide 54.462 B, sha256 `361d1ed289f89eb4…`
  identisch, `diff` leer — der Standard ist nachweislich unangetastet.
- `backend/tests/test_bild_beschreiben.py`: **50 passed** (41 Bestand + 9 neue):
  Bestand-Gold, Wortgrenzen/Standard (`max_woerter_fuer`), englischer Prompt
  („exactly N tiles", „2 to 4 sentences", „at most 70 words", Verbote), 
  Normalisierer bei 14 **und** 70, Übernahme bei 14 und 70, Durchreichung über
  `anfrage_bauen`, ganzer Lauf mit `--prompt-variante bildgeschichte`
  (70-Wort-Grenze greift, JSONL-Felder identisch), ganzer Lauf `stichwort`
  (bleibt bei 14), unbekannte Variante ⇒ Exit 2.
- **Voller Prüfbefehl:** `cd backend && .venv/Scripts/python -m pytest tests/ -q`
  → **3628 passed, 2 skipped, Exit 0** (382,78 s).

## Anmerkung (bewusst nicht angefasst)

`MAX_TOKENS_JE_KACHEL = 60` bleibt unverändert (Auftrag: Ausgabe/Kosten nicht
anfassen). Bei vollen 36er-Bögen ergibt das 2.760 Ausgabe-Tokens — für
ausgereizte 70-Wort-Kacheln knapp. Greift die Grenze, bleibt der Bogen ehrlich
offen und wird beim nächsten Lauf wiederholt; am echten Lauf beurteilen und
gegebenenfalls als eigener Schritt nachziehen.
