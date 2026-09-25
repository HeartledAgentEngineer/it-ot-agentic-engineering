# Changelog 2026-09-15 — Gesichter-Quiz stabil (Rahmen, Speichern, Referenzen)

**Projekt:** `personal_ai_agent` (02_Softwareentwicklung_IT)
**Stand:** 20.09.2026, abgeschlossen und verifiziert
**Grundlage:** Sebastians Befunde zum halbfertigen Quiz-Umbau (15.09.2026)
**Prüfbefehle:** siehe Abschnitt „Echte Verifikationsausgaben" — alle Exit-Code 0

---

## 1. Ablauf-Tabelle der 11 Soll-Schritte (vorher → nachher)

Legende: ✅ vollständig · ⚠️ teilweise / greift unter Bedingungen nicht · ➕ in diesem Durchgang ergänzt

| # | Soll-Schritt (Spec) | Vorher | Nachher (belegt) | Greift NICHT, wenn … |
|---|---|---|---|---|
| 1 | Bild lädt | ✅ Bild sofort + Analyse async (`frontend/app.js:4614` `naechsteQuizRunde`, `backend/app/services/gesicht_quiz.py:565` `start_runde`) | ✅ unverändert; Fortschritt jetzt **zusätzlich** je Gesichts-Region gespeichert (`analysiere_bild` → `gesichter[].bestaetigt`) | `_alle_bilder()` leer → „Kein Lieblingsbilder-Ordner" (`gesicht_quiz.py:38`) |
| 2 | „keine Person vorhanden" → nächstes Bild | ✅ `quizUeberspringen` (`app.js:4444`) + `markiere_uebersprungen` (`gesicht_quiz.py:541`) | ✅ unverändert; legt **keine** Person an, markiert das Bild als „gesehen" (getestet) | Bild nicht mehr vorhanden → `{"ok":false,"fehler":"Bild nicht gefunden"}` |
| 3 | Erkennung markiert Gesicht(er) | ⚠️ gelber Kasten **viel zu groß** (28 %-Aufschlag) + verschob sich (native px gegen skalierte Anzeige) | ➕ normalisierte Ankerung (`bboxNormVonPixeln`/Anzeige-Regelwerk, `app.js:2777` `markiereGesichtImBild`, `app.js:2990` `bboxAnzeigeRahmen`: oben 12 %, unten 6 %, seitlich 5 %) | Bild noch nicht geladen (`naturalWidth==0` und keine `bbox_norm`) → kein Rahmen |
| 4 | Gruppenbild: mit EINEM Gesicht starten | ✅ `starteGruppenQuiz` (`app.js:3721`), Gesicht für Gesicht | ✅ unverändert + **Überspringen bereits bestätigter Gesichter** (`app.js:3934` `ueberspringeBestaetigte`) | alle Gesichter bestätigt → Bild wird sofort als erledigt abgeschlossen |
| 5 | Hintergrund-Vergleich, dann „ist das X?" | ⚠️ **kein Hintergrund-Vergleich implementiert.** Die Frage kommt aus der Embedding-Vermutung (`gesicht_quiz.py:170` `_hypothese`, SFace-Cosinus + Alters-Bonus) | ⚠️ unverändert (außerhalb dieses Fixes) — **offener Punkt 5 unten** | kein Katalog / keine Engine → „Keine Person gefunden?"-Gate (`app.js:3785`) |
| 6 | „nein" → Vorschlagsliste möglicher Personen | ✅ `zeigeAntwortZeile` (`app.js:3841`) / `zeigeAntwortEingabe` (`app.js:4286`), 5 Kacheln + „… und N weitere" | ✅ unverändert (Optionen nach Wahrscheinlichkeit sortiert, `gesicht_quiz.py:99`) | weniger als 1 Person im Katalog → leere Kachel-Liste, nur Suche |
| 7 | Suchfeld mit Vorschlägen beim Tippen | ✅ `baueSuchMitVorschlaegen` (`app.js:3662`) | ✅ unverändert (Einzel- und Gruppenbild nutzen dieselbe Funktion) | Eingabe leer → Dropdown bleibt zu (Absicht) |
| 8 | „neue Person" → Hinzufügen-Buttons | ✅ Formular je Karte (Name/Rolle/Infos + ✅ Person speichern) | ✅ unverändert | Name leer → Feld rot, kein Speichern |
| 9 | Abbrechen-Button | ❌ **fehlte** (nur ✕ „Quiz beenden" `app.js:4496`) | ➕ `✖ Abbrechen` in **beiden** Formularen (Einzelbild + Gruppenbild), klappt zu, legt nichts an (Quelltext-Test F) | — |
| 10 | Katalog im Vollbild, überall Referenzbilder, Löschen entfernt auch die Vektoren | ⚠️ Katalog `zeigePersonenVerwaltung` (`app.js:5054`) + Referenz-Vollbild (`app.js:4902`) vorhanden; **Löschen entfernte die Vektoren nur halb** (frisch angelegte Person hatte kein `embedding`-Spiegel) | ➕ Vektor-Spiegelung beim Anlegen + stabile `ref_id` (`gesichter_service.py:130`,`:267`,`:394`), Löschen entfernt Referenz **und** Vektor (getestet) | Referenz ohne `bild_pfad` (alt gelernt) → kein Ausschnitt, nur Text |
| 11 | Rahmen (Bounding-Box) anpassbar | ⚠️ Editor vorhanden, aber: **Pull-to-Refresh lud die Seite neu**, Rahmen in Pixel/Pixel-Skala, Griffe je Auswahl, keine Drehung | ➕ vollständig überarbeitet: `app.js:3027` `zeigeBildVollbild` + `app.js:3452` `speichereEditorRahmen` (normalisiert, geklemmt, Drehung, Speichern in 3 Kontexten) | kein Rahmen ausgewählt → ehrlicher Hinweis im Editor-Status |

---

## 2. Ursachen je Befund (1 Zeile, mit Datei:Zeile)

| Befund (Sebastian) | Ursache | Beleg |
|---|---|---|
| „Kästen viel zu groß" | Rahmen wurde um 28 % der Gesichtshöhe nach oben aufgebläht | `frontend/app.js` vorher `ert = bh * 0.28` (jetzt ersetzt durch `bboxAnzeigeRahmen`, `app.js:2990`) |
| „verrutschen beim Öffnen/Drehen" | Rahmen wurden aus nativen Pixeln gegen die **gerenderte** Größe gerechnet; EXIF-Drehung des angezeigten Bildes war im Koordinatenraum nicht berücksichtigt | `app.js:2777` + `backend/face_infer.py:58` `exif_orientierung`/`deko­diere_bild` (Fix: Detektion auf demselben gedrehten Bild) |
| „beim Runterziehen lädt der Browser neu" | Kein `touch-action:none`, kein `overscroll-behavior`, kein `preventDefault()`; Container war scroll-/pan-bar | `app.js:3027` fr. `touch-action:pinch-zoom` (jetzt `overscroll-behavior:none;touch-action:none` im Editor; `preventDefault` in `touchmove`/`pointermove`, `passive:false`) |
| „Speichern geht die Personen nochmal von vorne durch" | Beim Speichern wurde nur der Rahmen übernommen; es gab **keine** Markierung „diese Region ist für diese Person bestätigt" — ein erneuter Aufbau der Runde fragte alles nochmal | `gesicht_quiz.py:502` `_ist_bestaetigt`, `:461` `_bestaetigte_regionen`, `:518` `_bestaetigung_merken`; `beantworte_runde` prüft **vor** der Detektion (`gesicht_quiz.py:667`); Frontend `app.js:2739` `merkeBestaetigt` + `app.js:3934` `ueberspringeBestaetigte` |
| „Katalog → Referenz → Bild → in der Referenz anpassen → speichern" | Referenz-ID wurde **aus dem Embedding abgeleitet**; beim Rahmen-Anpassen ändert sich das Embedding → neue ID → Dublette / Speichern ins Leere | `gesichter_service.py:130` `_refs_bereinigen` (stabile `ref_id` beim ersten Schreiben), `:267` `_refs_of`, `:394` `referenz_bbox_aktualisieren`; Frontend `app.js:3609` `zeigeReferenzBearbeiten` + `app.js:3452` `speichereEditorRahmen` |
| „Löschen entfernt die Vektoren nicht" | Frisch angelegte Person hatte kein gespiegeltes `embedding`-Feld → Vektor blieb im Legacy-Feld stehen | `gesichter_service.py:221` (Neuanlage spiegelt jetzt die Referenz-Vektoren) |
| „mal so, mal so" (Workflow) | Wechselhafte Detektion + fehlende Bestätigungs-Markierung + Abbruch der Analyse beim Überspringen | `gesicht_quiz.py:21` `_gesichter_robust` (2. Lauf), `analysiere_bild` liefert ehrlich `engine_verfuegbar` (`gesicht_quiz.py:932`), `beendeQuizAktiv` bricht Analyse + Token ab (`app.js:4496`) |

---

## 3. Rahmen beim Öffnen / Zoomen / Drehen / Ziehen / Speichern → vorher/nachher

| Vorgang | Vorher | Nachher |
|---|---|---|
| Öffnen (Vollbild / Quiz-Karte) | Pixel-bbox gegen gerenderte Größe, 28 %-Aufschlag → zu groß, verrutscht | normalisierte Ankerung 0..1 (`bbox_norm` hat Vorrang, sonst aus Pixeln), dezente Kopf-Regel, an den Bildrand geklemmt |
| Zoomen / Skalieren (Fenster/Drehung/Format) | Resync aus nativer Pixel-bbox; Griffe skalierten in Eigenrechnung | Neuberechnung aus `bbox_norm_live` gegen die gerenderten `anzeigeMasse`; Fenster-/Orientierungswechsel lösen `resync()` + Griff-Neuaufbau aus |
| Drehen | keine Drehung; ein falsch orientiertes Bild verschob die Rahmen | `⟳`-Knopf (90°-Schritte) + `bboxNormRotieren` beim Zeichnen; EXIF-Fälle durch `face_infer.exif_orientierung` + `_bbox_zu_norm` (`ImageOps.exif_transpose`) abgedeckt; Anzeige-/Originalraum über `bboxDeltaDrehen` (Zieh-Rückrichtung) |
| Ziehen / Größe ändern | `Math.max(0, …)` auf Position+Größe getrennt, kein Rand-Konzept | `bboxVerschieben` + `bboxSkalieren` **clampen per `bboxClampen`** (Größe bleibt, Position randbündig), Mindestkante 8 px, `setPointerCapture` + `preventDefault` |
| Speichern | nur Quiz-Kontext mit `_aktuelleQuizPerson` (sonst „⚠️ erst Ja/Person wählen"); keine Referenz-Aktualisierung | 3 deterministische Kontexte: (a) Referenz → `POST /api/gesichter/referenzen/{name}/{ref_id}/bbox` + Neu-Laden der Liste, (b) Quiz → Antwort mit `bbox`/`bbox_norm` + Region „bestätigt", (c) ohne Person → ehrlicher Hinweis, Rahmen bleibt erhalten |
| Rahmengröße/Griffe | ✕ 20 px außerhalb des Rahmens, Griffe 12 px | ✕ 22 px **im** Rahmen, Griffe 16 px (fingerfreundlich, nicht riesig) |

---

## 4. Geänderte Dateien

| Datei | Änderung |
|---|---|
| `backend/app/services/gesicht_quiz.py` | Bestätigungs-Regel je Region (`_region_schluessel`, `_bestaetigte_regionen`, `_ist_bestaetigt`, `_bestaetigung_merken`), Skip in `beantworte_runde` (`:667`) und `ergaenze_person_mit_bbox` (`:812`), `analysiere_bild` liefert `bestaetigt` je Gesicht + `bestaetigte_regionen` (`:932`), Fortschritt per `_FORTSCHRITT_OVERRIDE` testbar (`:325`) |
| `backend/app/services/gesichter_service.py` | stabile `ref_id` beim ersten Schreiben (`:130`), effektive ID immer mitführen (`:267`), `referenzen_zu_bild()` (`:343`), Vektor-Spiegelung bei Neuanlage (`:221`) |
| `backend/app/services/face_service.py` | (Vorgänger) Nicht-verfügbar-Cache mit 60 s TTL, damit die Engine ohne Neustart zurückkommt |
| `backend/app/router/gesichter.py` | (Vorgänger) `POST /api/gesichter/referenzen/{name}/{ref_id}/bbox` (`:163`), `DELETE …/{ref_id}` (`:201`) |
| `backend/face_infer.py` | (Vorgänger) EXIF-Orientierung vor der Detektion: `exif_orientierung()` (`:58`), `orientiere_bild()` (`:109`), `dekodiere_bild()` (`:135`) |
| `frontend/app.js` | Geometrie-Funktionen (`:2931`–`:3024`), vollständiger Vollbild-Editor (`:3027`), Speichern-Logik (`:3452`), Referenz-Nachbearbeitung (`:3609`), Bestätigungs-Skip im Gruppenquiz (`:3934`), ✖ Abbrechen in beiden Formularen, normalisierter Kasten (`:2777`) |
| `frontend/index.html` | Cache-Bump `app.js?v=20260920A` (`:204`) — Pflicht bei Frontend-Änderungen |
| `docs/changelog-2026-09-15-quiz-stabil.md` | diese Datei |
| **NEU** `backend/tests/test_gesicht_quiz_fortschritt.py` | 17 Tests (Fortschritt/Skip, Roundtrip, „keine Person", Vektor-Löschung) |
| **NEU** `frontend/tests/test_quiz_geo.js` | 60 reine Logik-Prüfungen der Geometrie |
| **NEU** `frontend/tests/test_quiz_rahmen_quelle.js` | 67 Quelltext-Nachweise (Gesten, Ankerung, Speichern, Referenz-Flow) |

---

## 5. Echte Verifikationsausgaben (frisch ausgeführt, 20.09.2026)

```
$ cd backend && .venv/Scripts/python -m pytest tests/ -q
241 passed, 3 warnings in 22.38s                                  (Exit 0)

$ cd frontend && node --check app.js                              (Exit 0)

$ cd frontend && for f in tests/*.js; do node "$f" app.js; done
tests/test_conv_code_live_stream.js           Exit 0
tests/test_diff_darstellung.js                Exit 0
tests/test_options_assistent.js               Exit 0
tests/test_quiz_ende.js                       Exit 0
tests/test_quiz_geo.js                        Exit 0
tests/test_quiz_rahmen_quelle.js              Exit 0
tests/test_serielles_tippen.js                Exit 0
```

Baseline vor dem Durchgang: **224 passed** → jetzt **241 passed** (224 + 17 neue Python-Tests).
Frontend-Tests neu: `test_quiz_geo.js` (60 Prüfungen, Fehler 0) und `test_quiz_rahmen_quelle.js` (67 Prüfungen, Fehler 0).

Auszug `test_quiz_geo.js` (reine Logik, gegen den echten Quelltext ausgeschnitten):

```
3) Drehen (bboxRotieren / bboxNormRotieren)
  OK   4x = Ausgangslage (= [10,20,30,40])
  OK   Rueckrichtung 1x zurueck (= [10,20,30,40])
  OK   norm 1x hin + 3x zurueck = Original (true)
4) Ziehen: Verschieben wird am Rand begrenzt
  OK   Ziehen ueber den rechten Rand -> ganz im Bild (= [70,20,30,40])
  OK   hin und zurueck = Original (= [10,20,30,40])
```

Auszug `test_quiz_rahmen_quelle.js`:

```
A) Vollbild-Editor loest den Browser NICHT aus (Pull-to-Refresh weg)
  OK   touch-action:none am Editor-Overlay
  OK   preventDefault in touchmove (passive:false)
  OK   setPointerCapture fuer die Maus
D) Speichern fragt bereits Bestaetigtes NICHT erneut ab
  OK   Gruppenquiz liest die backend-Flags je Gesicht
  OK   Einzelantwort merkt die Region
E) Referenz-Nachbearbeitung (Katalog -> Referenz -> Bild -> speichern)
  OK   Speichern geht an die Referenz-Route
  OK   mit neuem Embedding aus dem Ausschnitt
```

---

## 6. Offene Punkte für den Live-Test am Handy

1. **Pull-to-Refresh**: `touch-action:none` am Editor ist gesetzt (Quelltext-Test A grün) — am Gerät bestätigen, dass Ziehen des Kastens nach unten die Seite nicht mehr neu lädt.
2. **Kastengröße/-sitz**: Kasten über dem Gesicht, bei einem **Hochformat-Foto mit EXIF-Drehung** (typisches Handy-Foto) prüfen: sitzt der Kasten ohne Verrutschen?
3. **Drehen**: `⟳` einmal antippen → der Rahmen muss mitwandern; danach „💾 Speichern" → im Katalog/Quiz muss der Rahmen in der **ungedrehten** Bilddatei korrekt liegen (Speichern rechnet die Drehung heraus).
4. **Speichern ohne Wiederholung**: Bild mit 2–3 Gesichtern, eines zuordnen, `💾 Speichern`, dann dasselbe Bild erneut aufrufen → bereits zugeordnete Gesichter dürfen **nicht** erneut gefragt werden. (Voraussetzung: der Live-Katalog hat die Region gespeichert — im Katalog unter „🖼 Referenzen ansehen" nachprüfbar.)
5. **Hintergrund-Vergleich (Spec-Schritt 5)**: ist bewusst **nicht** implementiert — die Vermutung kommt aus dem Gesichts-Embedding. Entscheidung nötig: reicht die Embedding-Vermutung, oder soll zusätzlich ein Hintergrund-/Kontext-Vergleich gebaut werden?
6. **Referenz-Nachbearbeitung**: Katalog → Person → „🖼 Referenzen ansehen / Rahmen anpassen" → Ausschnitt antippen → Originalbild mit Rahmen → verschieben/größer ziehen → 💾 Speichern. Danach prüfen: Rahmen + Miniatur aktualisiert, **Personenzahl im Katalog unverändert**, andere Referenzen noch da.
7. **Alt-Referenzen ohne `bbox_norm`**: deren Rahmen kommt aus dem Pixel-Fallback (bzw. geht beim ersten Speichern in `bbox_norm` über). Falls ein alter Rahmen sichtbar falsch sitzt: einmal über Punkt 6 anpassen.
8. **Zoom-Wunsch**: Das Bild lässt sich im Vollbild-Editor jetzt nicht mehr nativ zoomen (bewusste Folge von `touch-action:none`, das den Reload verhindert). Wenn Zoomen gewünscht ist, wird es als eigene JS-Zoomstufe nachgezogen (Rahmen bleiben dabei normalisiert verankert).
9. **„Quiz fortsetzen" nach Server-Neustart**: offene Frage + bereits bestätigte Regionen müssen konsistent sein (`analysiere_bild` liefert die Flags) — einmal mit laufendem Quiz Server neu starten und prüfen, dass nur offene Gesichter gefragt werden.

---

## 7. Nicht angefasst (bewusst)

* **Keine echten Personendaten** berührt oder gelöscht: Tests biegen `gesichter_service.KATALOG_DATEI` und `gesicht_quiz._FORTSCHRITT_OVERRIDE` auf `tmp_path` um; der Chat-Verlauf wird in Tests stummgeschaltet.
* Keine Git-Operationen (der Hauptagent committet zentral).

---

## 8. Nachtrag 20.09.: Altdaten ohne `ref_id`

**Befund (Sebastian):** „Bei den abgespeicherten Ausschnittbildern waren wieder welche ohne Bild. Und: ich wollte EINS löschen, musste aber ALLE löschen."

**Ursache (belegt, Datei:Zeile):** Zwei getrennte Dinge.

1. **Einzel-Löschen wirkte nur so, als ginge es nicht.** Die API liefert für Altdaten sehr wohl eine `ref_id` (aus dem Embedding abgeleitet: `gesichter_service.py:374` in `_refs_of`, ausgegeben `:403`), und `referenz_entfernen` löschte auch korrekt. Der Fehler saß in der **Anzeige**: der ✕-Knopf im Referenz-Vollbild (`frontend/app.js`) führte die Anfrage aus, **verwarf aber die Antwort** und schrieb immer „✓ gelöscht". Ein 404/500/Netzabbruch blieb unsichtbar → es sah aus, als müsse man „🗑 Alle Referenzen löschen" nehmen. Dasselbe Muster beim Sammel-Löschen (pauschales „✅ alle gelöscht" ohne Prüfung) und ein toter Confirm (`if (!window.confirm && …)`, immer falsch).
2. **Referenzen ohne Ausschnittbild** entstehen im Quiz-Pfad `gesicht_quiz.py:757–761`: hat eine Person noch keinen `referenzen`-Block, werden rohe Alt-Vektoren zu `{"embedding": r, "jahr": None}` **ohne `bild_pfad`** normalisiert und gespeichert (`:768`, ebenso `:897`) — plus Referenzen, deren Originaldatei (pCloud) verschoben ist.

**Fix:** stabile `ref_id` wird für Altbestand **migriert** (nur dieses Feld! `gesichter_service.py:292`/`:316`, Aufruf beim ersten Lesen `:393` und beim Speichern `:220`); Löschen/Rahmen-Anpassen treffen eine Referenz über die effektive **oder** die abgeleitete ID (`_ref_passt`, `:270`, genutzt `:462`/`:496`); im Frontend wird die Serverantwort ausgewertet und ein Fehlschlag sichtbar als **„⚠️ NICHT gelöscht: …"** gemeldet, leere IDs werden nicht gesendet, Zeilen ohne Bild tragen das Abzeichen **„⚠️ ohne Bild"** und bleiben einzeln löschbar (`app.js:5040`–`:5084`). Detail-Dokument: `docs/changelog-2026-09-15-ref-loeschen.md`.

**Neue Tests:** `backend/tests/test_gesichter_ref_loeschen.py` (12) und `frontend/tests/test_ref_loeschen_ui.js` (33 Quelltext-Prüfungen in vier Gruppen).

**Verifikation (frisch):** `pytest tests/ -q` → `253 passed` (Baseline 241 + 12, nicht gesunken); `node --check app.js` Exit 0; alle acht `frontend/tests/*.js` Exit 0. Cache-Bump `index.html` → `app.js?v=20260920B`.
