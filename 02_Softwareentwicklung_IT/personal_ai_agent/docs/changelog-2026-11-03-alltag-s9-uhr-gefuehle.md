# Changelog 03.11.2026 — Alltagsprotokoll S9: Ekman-Gefühle, Diktat in jedem Feld, Schlaf von der Uhr

Baut auf S8 auf. Sebastians Wünsche vom 03.11.:

1. Nur wissenschaftlich begründete Gefühle.
2. An jedem Textfeld auch Sprache.
3. Die Schlafknöpfe fallen weg, weil der Schlaf von der Uhr kommt.

## Gefühle: die sechs Grundemotionen nach Ekman

- `GRUNDGEFUEHLE` sind jetzt nur noch Freude, Trauer, Angst, Ärger, Ekel und Überraschung (Ekman 1992, „An argument for basic emotions").
  - Weggefallen sind Scham, Schuld, Ruhe und Erschöpfung.
  - Ruhe und Erschöpfung sind eher Körperzustände. Wie angespannt du warst, erfasst weiter der Regler für die Anspannung.
- Das Sprachmodell darf nur noch aus dieser Liste wählen. Wörter, die nicht passen, fallen weg; vorher galt „sonst ein eigenes kurzes Wort".
- `_gefuehl` bildet gängige Wörter für dasselbe Gefühl ab (Wut, Zorn → Ärger; Furcht → Angst; Glück → Freude; Traurigkeit → Trauer; Abscheu → Ekel; Erstaunen → Überraschung). Alles andere verwirft es, auch beim vorherrschenden Gefühl.
- In der Oberfläche ist das Feld für eigene Gefühlsworte weg. Wählbar sind nur noch die sechs Knöpfe, und `alltagGefuehle` lässt nur Wörter aus der Liste durch.
- **Alte Einträge** mit „Ruhe" oder eigenen Worten bleiben gespeichert und sichtbar.
  - Das Chat-Werkzeug behandelt sie wie Freitext: Sie gehen nur geschwärzt hinaus.
  - Ohne Namensliste gehen sie gar nicht hinaus.
  - In den Tageskennzahlen zählen sie nicht als Grundgefühl.

## 🎙 an jedem Textfeld

- Neben dem großen Textfeld (Tastatur) und neben „Was hast du gemacht?" steht ein runder 🎙-Knopf.
  - Erster Tipp startet die Aufnahme, zweiter beendet sie.
  - Der verstandene Text wird an das Feld **angehängt** (`alltagAnhaengen`) und lässt sich vor dem Speichern korrigieren.
- Dafür wird derselbe Rekorder wie bei „Sprechen" verwendet: ein Rekorder mit Ziel. Ohne Ziel wird der Text ein Eintrag, mit Ziel landet er im Feld.
- Es läuft immer nur eine Aufnahme.
- Das Mikrofon wird in jedem Weg freigegeben: bei Stopp, bei einem Fehler, beim Schließen des Blatts und wenn die Rückfrage wechselt, während ihr Feld noch aufnimmt.
- Ist das Feld beim Eintreffen des Texts schon weg, wird nichts eingetragen.

## Schlaf nur noch von der Uhr

- Die vier Knöpfe (schlafen, aufwachen, wach liegen, wieder schlafen) sind aus Blatt, Skript und Stil entfernt.
- Der Endpunkt `POST /api/alltag/ereignis` bleibt bestehen, damit alte Aufrufe nicht brechen.
- Auch ein gesprochenes „Ich gehe schlafen" wird weiter als Schlaf-Ereignis erkannt.
- `letzter_stand` zählt jetzt das Ende einer Uhr-Nacht (`schlafnacht.ende`) als letzten Stand. Die Nachtstunden gelten damit nicht als „offen".
  - Ein späterer Stundeneintrag schlägt die Nacht.
  - Eine Nacht ohne Ende oder mit einem Ende in der Zukunft zählt nicht.
  - `/api/alltag/offen` liest dafür auch die Uhr-Nächte.
- **Grenze:** Die Uhr liefert die Nacht erst nach dem Aufwachen (Health Connect). Bis zum Abgleich am Morgen zählt das Pop-up noch ab dem letzten Abendeintrag. Eine Ruhezeit für die Nacht entscheidet Sebastian.

## Prüfung

- Neue oder geänderte Tests, vorher rot:
  - `test_alltag_struktur.py`: Ekman-Liste, Synonyme, Aufforderung ohne eigene Worte; die strenge Prüfung erwartet jetzt „Wut → Ärger, Neid weg".
  - `test_alltag_rechnen_s2.py`: `test_uhr_nacht_deckt_die_schlafstunden`.
  - `test_alltag_router_s5.py`: `test_offen_zaehlt_ab_dem_aufwachen_laut_uhr`.
  - `frontend/tests/test_alltag.js`: nur Listengefühle, `alltagAnhaengen`, 🎙-Knöpfe, keine Schlafknöpfe, kein `/api/alltag/ereignis` mehr.
- In `test_alltag_auswertung.py` ersetzt „Freude" das frühere Grundgefühl „Ruhe".
- Vorschau im Browser mit erfundenen Daten bei 390 px:
  - Rückfragen bis zu den Gefühlen durchgeklickt; PATCH sendet `{"gefuehle":["Ärger"]}`.
  - Feld-Diktat mit nachgebautem Mikrofon geprüft: Der Text wird angehängt, es entsteht kein Eintrag, und das Mikrofon wird freigegeben.
  - Ein Diktat ins Textfeld überlebt „Überspringen".
- Cache-Bump `style.css` und `alltag.js` auf `?v=20261103D`.
- Volle Suite auf `56f16d9`: 6431 grün, 3 übersprungen.

## Nachtrag nach Hermes (Runde 1: FREI, ein Hinweis)

- Hinweis von Hermes: `PATCH /api/alltag/eintrag/{id}` prüfte Gefühle nicht serverseitig. Über die
  Oberfläche war das nicht erreichbar, ein direkter Aufruf hätte aber jedes Wort speichern können.
- Jetzt läuft jede Korrektur durch `alltag_struktur.gefuehle_pruefen`, mit denselben Regeln wie die
  Modellantwort:
  - Synonyme werden abgebildet.
  - Doppelte und unbekannte Wörter fallen weg.
  - Text statt Liste ergibt eine leere Liste.
  - Ein unbekanntes `vorherrschend` wird `null`.
- Neuer Test `test_korrigieren_nimmt_nur_grundgefuehle` (vorher rot).

## Nachtrag nach Hermes (Runde 2: EINWAND, Mikrofon blieb an)

- **Fehler (seit S6):** Scheiterte nach der Mikrofon-Freigabe ein Schritt (AudioContext,
  `addModule`, AudioWorkletNode), war `zustand.aufnahme` noch leer. `aufnahmeFreigeben` stoppte dann
  nichts, und das Mikrofon blieb an. Mit den 🎙-Knöpfen aus S9 gibt es mehr Wege dorthin.
- **Jetzt:** `alltagMikrofonOeffnen` öffnet Mikrofon und Worklet in einem Schritt. Scheitert ein
  Teil, gibt `alltagMikrofonSchliessen` alles schon Geöffnete frei, auch teilweise Geöffnetes. Erst
  danach wird der Fehler gemeldet.
- **Mitbehoben, gleiche Art:**
  - Wird das Blatt geschlossen, während der Freigabe-Dialog noch offen ist, wird das danach
    geöffnete Mikrofon sofort wieder freigegeben. Dasselbe gilt, wenn das Zielfeld verschwunden ist.
  - Ein Doppeltipp während des Öffnens wird ignoriert (`zustand.oeffnet`).
- **Prüfung:**
  - Test 8b in `test_alltag.js` (vorher rot): Fehler an drei Stellen stoppt jeweils die Spur und
    schließt den AudioContext. Im Normalfall bleibt alles offen.
  - Im Browser mit nachgebautem Mikrofon geprüft: Fehler, Schließen während der Freigabe mit
    Doppeltipp, danach ein normaler Start.
- Cache-Bump `alltag.js` auf `?v=20261103E`.
