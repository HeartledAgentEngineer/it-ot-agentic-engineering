# Änderungsprotokoll 02.10.2026 — Alle Gesichter eines Vorschlags durchsehen, falsche ausschließen

Wunsch Sebastian (Handytest): „Bei Julian war ein Bild von mir, ich konnte es nicht wegklicken.
Es werden nur acht angezeigt — wenn man alle 300 oder 400 Gesichter durchscrollen und sagen
kann ‚nee, das ist nicht Julian', wird das Ergebnis genauer."

## Was neu ist

- **`gruppen_quiz.gesichter(kennung, seite)`** + `GET /api/gruppen/gesichter?kennung=&seite=`:
  alle Gesichter eines Vorschlags aus `gesicht_zuordnung.jsonl`, nur Fotos (Video-Standbilder
  haben kein Vorschaubild), beste zuerst (Anteil × Score), je Seite 48, ohne ausgeschlossene.
- **`gruppen_quiz.ausschliessen(kennung, gesichter)`** + `POST /api/gruppen/ausschliessen`:
  Regel „dieses Gesicht ist nicht diese Person" in `personen_vorgaben.json` unter
  `"ausgeschlossen": [{"kennung", "bild_id", "index"}]` (höchstens 200 je Aufruf; nur Gesichter,
  die wirklich zu dem Vorschlag gehören; doppelte zählen nicht). Am Handy wirkt sie **sofort**:
  Gesichterliste, Beispielbilder der Karte, Register „Bilder mit …". **Rückgängig** nimmt den
  letzten Ausschluss zurück (Protokoll `art: ausschliessen`).
- **`tools/foto_sortierung/personen_gruppieren.py`**: `vorgaben_lesen` liest `ausgeschlossen`;
  `lauf_rechnen` lässt ein so markiertes Gesicht nie wieder in den Vorschlag mit dieser Kennung
  (Kennung `null`, Bericht „Nach Nutzer-Regel aus einem Vorschlag genommen: N"). Wirksam, sobald
  die Antwort-Dateien vom Handy zurück am PC sind (Rückweg noch offen).
- **Oberfläche** (`gruppen_quiz.js`): Knopf „🔍 Alle N Gesichter ansehen" in der Karte →
  Gesamtansicht: Raster, Antippen markiert (rotes ✕), die Lupe ⤢ öffnet das ganze Foto,
  „Weitere laden" holt die nächsten 48, „🚫 N Gesichter ausschließen" schickt die Markierten;
  Vorschaubilder laden erst beim Sichtbarwerden (IntersectionObserver), damit bei 400 Gesichtern
  nicht 400 Bilder auf einmal kommen. Zurück lädt die Karte neu (Beispiele ohne Ausgeschlossene).
  `gruppen_quiz.js`/`style.css?v=20261002B`.

## Befund beim Bauen (behoben)

`_gemerkt` merkte Ergebnisse nur nach **Dateipfad**. `gesicht_zuordnung.jsonl` lesen jetzt zwei
Funktionen (Register und Gesichterliste) — wer zuerst las, belegte den Speicher, die andere bekam
das falsche Ergebnis (im Test: Ausschluss abgelehnt, „Bilder mit" unverändert). Jetzt je
(Pfad, Lesefunktion).

## Prüfung

- `backend/tests/test_gruppen_quiz.py` +9: seitenweise/beste zuerst/ohne Videos, Ausschluss wirkt
  sofort und **im Format des Gruppierers** (mit dessen `vorgaben_lesen` geprüft), Beispiele,
  „Bilder mit" (Register vor dem Ausschluss gelesen = Zwischenspeicher-Fall), Rückgängig,
  ungültige Eingaben schreiben nichts, Routen.
- `backend/tests/test_personen_gruppieren.py` +2: ausgeschlossenes Gesicht landet beim nächsten
  Lauf nicht mehr im Vorschlag (Größe −1, Bericht), `vorgaben_lesen` mit gültigen und kaputten
  Einträgen.
- `frontend/tests/test_gruppen_quiz.js` erweitert; alle 25 Frontend-Tests Exit 0.
- Browser-Prüfstand (375 px, 60 erfundene Gesichter): Knopf „Alle 60 Gesichter ansehen", 48 dann
  60 Kacheln, Markieren/Entmarkieren, Knopf „🚫 2 Gesichter ausschließen", gesendete Kennungen,
  58 Kacheln danach, Infozeile, Vorschaubilder laden beim Sichtbarwerden; keine waagerechte
  Scroll-Leiste.
