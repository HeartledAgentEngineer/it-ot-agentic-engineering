# Erkennung für dieses eine Bild neu starten (Schritt I, 18.10.2026)

**Auftrag:** Sebastian, 16.10.2026, Auftragspunkt 3 des Rahmeneditor-Plans
(`.hermes/plans/2026-10-16_rahmeneditor-detailbild.md`, Schritt I): „Erkennung für
dieses eine Bild neu starten (auch übersehene Gesichter finden).“ Ein Knopf, der nur
dieses Bild neu erkennen lässt, **vorhandene Korrekturen nicht überschreibt** und sein
Ergebnis **sichtbar** meldet.

## Befund vorher (gemessen, nicht vermutet)

- Der Server kann die Neu-Erkennung **schon**: `POST /api/gesichter/quiz/analysiere`
  (`backend/app/router/gesichter.py:115`) → `gesicht_quiz.analysiere_bild` (`:1004`) →
  `face_service.embeddings_fuer_pfad` (ganzes Bild, `face_service.py:116`). Antwort je
  Gesicht: `bbox`, `bbox_norm`, `region`, `bestaetigt`, dazu `anzahl_gesichter`,
  `vermutung`, `engine_verfuegbar`.
- **Gefehlt hat die Oberfläche** (kein Knopf im Detailbild-Editor) **und die
  zusammenführende Regel**: die vorhandene `rahmenListeVerschmelzen`
  (`frontend/app.js:4582`) verschmilzt **nach Listenposition** (`vor[i]`). Liefert die
  Engine dieselben Gesichter in **vertauschter Reihenfolge**, wandert die Person damit
  auf einen fremden Rahmen — genau der Befund 3 der Plan-Prüfungen (Fassung 9 und 10).
- **Zusätzlicher Befund aus der Rendermessung:** die Werkzeugleiste war bei 380 px
  Fensterbreite mit den Knöpfen aus Schritt E/G/F/I **664 px breit (links −142)**; schon
  im Stand davor (HEAD) waren es **511 px (links −66)** — die äußeren Knöpfe lagen
  außerhalb des Bildes und waren nicht erreichbar.

## Was gebaut ist (nur Oberfläche, kein Backend-Eingriff)

- **Reine Funktion `rahmenNeuErkennen(gesichter, altNorm, altPersonen, minUeberdeckung)`**
  (`frontend/app.js`): führt die frische Erkennung mit den Rahmen im Editor zusammen.
  Zugeordnet wird über die **Überdeckung** (neue reine Funktion `bboxUeberdeckung`,
  Schnittfläche/Vereinigungsfläche) bzw. über die **gleiche 1-%-Region**; Schwellwert
  standardmäßig 0,5. Ergebnis: `{ bbox_norm_live, personen, behalten, neu }`.
  - gleiche Region/Überdeckung → der vorhandene Rahmen bleibt **wertgleich**
    (Koordinaten **und** Person) — auch bei vertauschter Reihenfolge,
  - zusätzlich gefundene Gesichter kommen **angehängt** dazu, ausdrücklich **ohne
    Person** („unbekannt“) — es wird nichts erfunden,
  - eine leere oder unbrauchbare Antwort ändert **nichts**; gelöschte Plätze (`null`)
    bleiben gelöscht, es wird nie etwas entfernt.
- **Knopf „🔍 Neu erkennen“** in der Werkzeugleiste des Detailbilds (Kennung
  `vollbild-neu-erkennen`), **nicht** in der Referenz-Nachbearbeitung. Klick →
  `erkenneDiesesBildNeu()`:
  - holt die Analyse für **genau dieses** Bild (`_quizEditor.bildPfad`),
  - ist die Engine **nicht gelaufen** (`engine_verfuegbar: false`) oder der Aufruf
    gescheitert, wird **nichts** verändert und das **ehrlich** gemeldet („die N Rahmen
    bleiben unverändert“) — 0 Gesichter wären sonst als „keine Gesichter“
    missverstanden worden,
  - sonst: Zusammenführen, neue Rahmen-Elemente anbauen, `resync()`,
    **Zurück-Schnappschuss** vorher (Undo),
  - Meldung nennt gefundene Gesichter, die **Zahl der Neufunde** und dass die
    vorhandenen Rahmen unverändert bleiben.
- **Werkzeugleiste bricht jetzt um** (`flex-wrap: wrap`, `max-width: 96vw`,
  `left:0;right:0;margin:0 auto;width:fit-content`): bei breiten Fenstern unverändert
  **eine Zeile**, auf dem Handy mehrere Zeilen **mittig im Fenster** statt aus dem Bild
  heraus.
- Cache-Schlüssel `app.js?v=20261018L` → **`20261018M`** (`frontend/index.html`).
  Am CSS (`style.css`) nichts geändert, kein Backend-Eingriff, keine neue Abhängigkeit.

## Belege (in diesem Lauf selbst ausgeführt)

| Beleg | Ergebnis |
|---|---|
| neu `frontend/tests/test_quiz_rahmen_neu_erkennen.js` (echte Funktionen im Sandkasten + Quelltext-Wächter) | **Exit 0**, 40 Prüfungen |
| Gegenprobe gegen die **HEAD**-Fassungen (`app.js`, `index.html`, `style.css` außerhalb des Repos, dieselbe Prüfdatei) | **Exit 1, 40 von 40 rot** (Hinweis: `bboxUeberdeckung`, `rahmenNeuErkennen` fehlten) — die Fähigkeit gab es vorher nicht |
| `pytest tests/test_frontend_node.py -q` | **48 passed** (47 + dieser Test) |
| Rendermessung im **echten Browser** (Edge headless, echte `index.html` + `app.js`, echter `zeigeBildVollbild`-Aufruf): 1400 px | Leiste **990 px breit, 56 px hoch (eine Zeile)**, links 205, rechts 1195, **kein Überlauf** (0) |
| dasselbe bei 380 px | Leiste **365 px breit, 174 px hoch (drei Zeilen)**, links 8, rechts 373 — **ganz im Fenster**, kein Überlauf; **vorher** (HEAD): links −66, 511 px breit |
| Klick auf den echten Knopf mit gestellter Antwort (dieselben zwei Gesichter **vertauscht** + ein neues) | Rahmen **2 → 3**; Namen bleiben an ihren Rahmen: Rahmen 0 **Anna**, Rahmen 1 **Tim**, Neufund Rahmen 2 **„unbekannt“**; die Meldung nennt „1 neue(s) Gesicht(er)“ und „die 2 vorhandenen bleiben unveraendert“; kein JS-Fehler |
| dasselbe mit **scheiterndem** `fetch` (kein Server) | Rahmenzahl und Namen **unverändert** (3 / Anna / Tim), Meldung „🔍 Erkennung nicht erreichbar — die 3 Rahmen bleiben unveraendert.“ |
| volles Tor über den Commit-Haken | siehe Commit (`pytest tests/ -q`, Exit 0) |

## Ehrliche Grenzen

- Gemessen ist die **Verschmelzungsregel** (echte Funktionen, vertauschte Reihenfolge,
  verschobene und entfernte Gesichter) und der **echte Oberflächenweg** im Browser mit
  **gestellten** Antworten. Ein **echter** Engine-Lauf über ein echtes Bild ist am PC
  nicht gemessen (kein Server/Engine im Messaufbau) — die Abnahme mit dem Finger am
  Gerät bleibt Sebastians Schritt.
- Der Neufund steht als **„unbekannt“** und wird **nicht** gespeichert; die Person setzt
  das Menü aus Schritt G. Ohne Person gibt es weiterhin keinen Speicherweg.
- Video-Standbilder sind in dieser Ansicht nicht neu erkennbar (der Editor arbeitet auf
  Bildpfaden), der Gruppierlauf am PC kennt Standbilder ebenfalls nicht (offener Punkt
  aus Schritt S2).
- Die Umstellung der Werkzeugleiste betrifft **alle** Knöpfe des Editors (Schritt
  E/G/F/I); gemessen sind zwei Fensterbreiten (1400 px, 380 px), nicht jedes Gerät.

## Nicht angefasst

Kein fremder Pfad, kein `git add -A`, nichts gelöscht, keine Geräteschritte, keine
`.env`, kein Bild an ein fremdes Modell, keine echten Personennamen (nur erfundene wie
„Anna“/„Tim“). Kosten: **0 USD**.
