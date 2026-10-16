# Kachelbedienung der Gesichterliste: langer Druck wählt aus, kurzer Klick öffnet (S4)

**Datum:** 16.10.2026 · **Schritt:** S4 der To-do-Liste („Kacheln klein + Gruppen-Filter +
Klick-Bedienung", Punkt 2c) · **Auftrag:** `.hermes/plans/2026-10-16_kachelgroesse-und-gruppen-filter.md`
(Fassung 2, Abschnitte „Kachelbedienung" und „Zweiter Nachtrag — Auswahlmodus")

## Ausgangslage

In der Ansicht **Alle Gesichter** eines Vorschlags (`#gruppen-alle-raster` der Gruppenkarte)
hat **jeder kurze Klick sofort markiert** — gemeint war aber das Öffnen des Bildes. Zum
Ansehen des ganzen Fotos gab es deshalb auf jeder Kachel ein **Vergrößerungs-Symbol** (⤢,
`.gruppen-lupe`) in der Ecke. Video-Gesichter waren davon ausgenommen (der Server lehnt
Ausschließen/Zuordnen für sie ab) und öffneten per kurzem Klick.

## Jetzt

- **Langer Druck (500 ms)** auf eine Kachel startet den **Auswahlmodus** und wählt genau
  diese Kachel; solange er läuft, **schaltet jeder kurze Klick** die Auswahl um.
- **Außerhalb des Modus öffnet der kurze Klick das Bild** — die Vergrößerungs-Symbole auf
  den Kacheln sind deshalb entfallen (Markup und CSS-Regel `.gruppen-lupe` entfernt).
- Der Modus endet, wenn die **letzte markierte Kachel abgewählt** wird, über den neuen Knopf
  **„✕ Auswahl beenden"** in der Werkzeugzeile der Ansicht, beim Verlassen der Ansicht und
  bei jedem Neuaufbau der Liste (Sortierwechsel, anderes Gesichtsfeld). Danach öffnen kurze
  Klicks wieder Bilder.
- **Auswahlsteuerung bleibt wie sie war:** `Ausschließen` und `Zuordnen` arbeiten auf der
  Markierung, markierte Kacheln tragen weiterhin roten Rahmen und Kreuz, jede Kachel meldet
  ihren Zustand über `aria-pressed`. Die synthetische Klickfolge, die ein Browser nach dem
  Loslassen nachschiebt, wird verworfen — sie darf die Auswahl nicht sofort wieder aufheben.
- **Abbruchbedingungen des Timers:** Bewegung ab 8 px (Scrollen/Ziehen), `pointerup`,
  `pointercancel` und `lostpointercapture`; der Browser-Langdruck (Kontextmenü) wird während
  des Haltens unterdrückt. Tastaturklicks (Enter/Leertaste) bleiben funktionsfähig.

## Code

| Datei | Änderung |
|---|---|
| `frontend/gruppen_quiz.js` | `kachel()` kennt `ohneKlick` (der Aufrufer verdrahtet selbst) und baut kein Vergrößerungs-Symbol mehr; neu `AUSWAHL_LANGDRUCK_MS = 500`, `AUSWAHL_BEWEGUNG_PX = 8`, `alleAuswahlModusSetzen`, `alleKachelMarkeSetzen`, `alleAuswahlBeenden`, `alleKachelKlick`, `alleKachelVerdrahten`; Raster-Verdrahtung in `alleSeiteLaden`, Rücksetzen in `alleVonVorn`/`alleSchliessen`, Knopf-Verdrahtung |
| `frontend/index.html` | neuer Knopf `#gruppen-alle-auswahl-ende` in der Werkzeugzeile; Cache-Schlüssel `gruppen_quiz.js?v=20261016C`, `style.css?v=20261016D` |
| `frontend/style.css` | Regel `.gruppen-lupe` entfernt; `.gruppen-alle-werkzeuge` bricht jetzt um (`flex-wrap`, `gap`) |
| `frontend/tests/test_gruppen_auswahl.js` | **neu** — Laufzeitprüfung des ganzen Modus (siehe unten) |
| `frontend/tests/test_gruppen_liste.js` | die vier Stellen, die bisher per kurzem Klick markiert haben, starten die Auswahl jetzt per langem Druck (`langdruck()`-Helfer) — die Assertions bleiben |
| `frontend/tests/test_gruppen_quiz.js` | Quelltext-Wächter an die neue Form angepasst: Video-Gesicht **ohne** Verdrahtung, nur Gesichter ohne Video bekommen `alleKachelVerdrahten` |
| `backend/tests/test_frontend_node.py` | neuer Test in der Zuordnungstabelle (`test_gruppen_auswahl.js` → `gruppen_quiz.js`) |

## Belege

- **Neuer Laufzeittest** `frontend/tests/test_gruppen_auswahl.js` (führt die echten Funktionen
  in einer DOM-Umgebung aus, nur HTTP-Antworten sind Attrappen; Exit 0):
  langer Druck startet und markiert · die Klickfolge danach hebt die Auswahl nicht auf und
  öffnet nichts · kurzer Klick schaltet im Modus um · letzte Kachel abgewählt beendet den
  Modus, danach öffnet der kurze Klick wieder (Beleg: Vollbild-Abruf `groesse=800x800`) ·
  „Auswahl beenden" leert die Auswahl und lässt den Klick wieder öffnen · Bewegung ab 8 px
  und `pointercancel` brechen den Timer ab · **Video-Kachel ohne Pointer-Verdrahtung** (öffnet
  per kurzem Klick) · eine neu geladene Liste startet ohne Modus. Dazu Quelltext-Wächter:
  kein `gruppen-lupe` in JS und CSS, 500 ms / 8 px fest, Knopf und Cache-Schlüssel vorhanden
  und jung genug.
- **Rendermessung im echten Browser** (Edge, Belegskript außerhalb des Repos
  `…/cache/scratch/s4_auswahl_messen.js`, das die Markup-Struktur aus der **echten**
  `index.html` schneidet und die **echte** `style.css` lädt, mit sichtbarem Auswahlmodus):
  1400 px Werkzeugzeile **eine** Zeile, Überlauf 0, Raster 8 Spalten × 166 px, Dokument
  ohne Überlauf; 768 px eine Zeile, 4 × 180 px; **380 px eine Zeile** (Knöpfe 130 px + 152 px),
  kein Überlauf, Raster unverändert 4 × 83 px (Handy-Baseline aus S3). Standbilder
  `s4_auswahl_1400.png`, `_768.png`, `_380.png` angesehen: Knöpfe ohne Überlappung, Text hell
  auf dunklem Grund, markierte Kacheln klar am roten Rahmen mit Kreuz erkennbar.
- **Prüfbefehl** `cd backend && .venv/Scripts/python -m pytest tests/ -q` → siehe Protokoll
  im Commit-Log (Tor im pre-commit-Haken).

## Ehrliche Grenzen

- **Video-Gesichter bleiben nicht auswählbar** (weiterhin nur per kurzem Klick zu öffnen).
  Das ist Absicht und steht so in der geprüften Auftragsfassung 2: die Serverfunktionen
  `ausschliessen`/`zuordnen` lehnen Video-Kennungen mit `VIDEO_GESPERRT` ab
  (`backend/app/services/gruppen_quiz.py:993/1132/1210`), weil deren Kennungen nicht in der
  Zuordnungsdatei stehen — eine Markierung würde dort also nichts bewirken. Sebastians Wunsch
  „Bilder aus Videos markierbar" (To-do Punkt 11, Schritt S2) braucht deshalb zuerst einen
  eigenen Schreib-/Auswertungsweg für Video-Kennungen (offener Schritt, nicht Teil dieses
  Commits).
- **Gemessen wurde gerendert, nicht getippt:** die Laufzeitprüfung fährt die echten Handler,
  die Rendermessung prüft die Werkzeugzeile und das Raster; eine Finger-Bedienung auf einem
  echten Touchgerät ist in diesem Durchlauf **nicht** erfolgt.
- Einzelkacheln in Quiz-/Personenansichten behalten ihren kurzen Öffnungsklick — nur das
  auswählbare Raster `#gruppen-alle-raster` hat den Auswahlmodus.
