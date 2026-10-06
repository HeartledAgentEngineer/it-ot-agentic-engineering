# Änderungsprotokoll 06.10.2026 — Erzählen: wer ist auf den Bildern (Schritt 11a)

Wunsch Sebastian: schon beim Erzählen sehen und angesagt bekommen, welche Personen auf den
Bildern erkannt wurden — die Verknüpfung liegt ja schon in den Daten. Später sollen diese Stellen
auch zum Anlernen dienen (Schritt 11b: unbenannte Gesichter direkt benennen, „ist nicht X";
11c: Erzählung auswerten, „das ist mein Papa und ich").

## Ausgangslage

- Am Handy liegen `gesicht_zuordnung.jsonl` (je Bild/Video die Gesichter mit Gruppen-Kennung) und
  `personen_bestaetigt.json` (Kennung → Name) — daraus beantwortet `gruppen_quiz.bilder_mit` schon
  „Bilder mit Leon und/oder Tim". Das Erzählen nutzte das nicht.

## Änderung

- **Backend:** `gruppen_quiz.personen_auf_bildern(fileids)` (nur lesend, nie ein Wurf): je Bild die
  Namen (mehrere Vorschläge mit demselben Namen zählen einmal) und die Kennungen ohne Namen;
  dazu die Zusammenfassung (Name → Zahl der Bilder, häufigste zuerst) und die Zahl der Personen
  ohne Namen. Wie im Register fehlen ausgeschlossene Gesichter; als „kenne ich nicht" markierte
  Gruppen (fremde Menge) zählen nicht mit; Videos laufen über ihre Video-Kennung. Höchstens 2.000
  Bilder je Anfrage.
- **Route:** `GET /api/erzaehlen/ereignisse/{kennung}/personen` — eigener Aufruf, damit die
  Übersicht sofort steht und die Personen nachkommen; immer HTTP 200, Fehler als deutscher Text
  (keine Ereignisdatei, unbekanntes Ereignis, keine Gesichter-Zuordnung am Gerät).
- **Frontend:** Übersicht zeigt z. B. „Erkannt: A (12 Bilder), B (8 Bilder) · 3 Personen noch
  ohne Namen" (höchstens 8 Namen, Rest „und N weitere"); das Einzelbild „Auf diesem Bild: A und B
  · 1 Person noch ohne Namen" bzw. „Auf diesem Bild wurde niemand erkannt." Namen nur per
  `textContent`. Veraltete Antworten (Ereignis inzwischen gewechselt) werden verworfen.
- **🔊 Vorlesen** nur auf ausdrücklichen Tipp: zuerst die Browser-Stimme (bleibt auf dem Gerät,
  am PC vorhanden). **Die App am Handy hat keine** — am 06.10.2026 in der laufenden App gemessen:
  `speechSynthesis` fehlt in der Android-WebView. Dort nimmt 🔊 dieselbe Strecke wie das Vorlesen
  im Chat: `POST /api/speak` über OpenRouter. Der Satz mit den Namen verlässt dann das Handy (wie
  jede vorgelesene Chat-Antwort); kein neuer Anbieter.
- Neue reine Funktionen in `frontend/erzaehlen.js`: `erzaehlPersonenUebersicht`,
  `erzaehlPersonenBild`, `erzaehlSprechtext` (+ Helfer `_erzaehlAufzaehlen`, `_erzaehlOhneNamen`).
- Cache-Bump: `style.css?v=20261006C`, `erzaehlen.js?v=20261006B`.

## Prüfung

- Neu `backend/tests/test_erzaehlen_personen.py` (11 Tests, erfundene Daten): Namen/Unbenannte je
  Bild, gleicher Name aus zwei Vorschlägen einmal, Ausschluss, „kenne ich nicht", Rauschen, Video,
  Zusammenfassung, doppelte/kaputte Kennungen, fehlende Zuordnung (nichts angelegt), nur lesend
  (Prüfsummen vorher/nachher gleich), kaputte Namensdatei; Route: Treffer, unbekanntes Ereignis,
  fehlende Zuordnung, fehlende Ereignisdatei — jeweils HTTP 200.
- `frontend/tests/test_erzaehlen.js` Abschnitte 9–10 (Texte, Sprechtext, Verdrahtung, Vorlesen nur
  auf Tipp, kein `innerHTML`, `[hidden]`-Regel); alle 25 Frontend-Testdateien Exit 0.
- Prüfstand Edge headless 375 px, echter Code, Attrappe mit erfundenen Personen: Übersicht
  „Erkannt: Testperson A (2 Bilder), Testperson B (1 Bild) · 1 Person noch ohne Namen"; Bild 3
  „Auf diesem Bild: Testperson A und Testperson B · 1 Person noch ohne Namen", Bild 4 „… 1 Person
  noch ohne Namen", Bild 5 „… niemand erkannt"; 🔊 spricht über die Browser-Stimme (Sprechtext mit
  Satzpause statt „·"); ohne Browser-Stimme geht derselbe Satz an `/api/speak`.
- Prüfbefehl: siehe Commit.
