# A3: Der gesendete Rahmen liegt wirklich im Datenbestand (16.10.2026)

Schritt **A3** zum Punkt 0 des Auftrags „Gesichtskorrektur im Detailbild"
(`.hermes/plans/2026-10-16_rahmeneditor-detailbild.md`, Abschnitt 9; freigegeben
nach der Planprüfung der Fassung 13 am 16.10. um 13:18, **Urteil FREI**, Protokoll
`.hermes/pruefkreis/rahmeneditor-detailbild-plan-fassung13.md`).

## Der behobene Fehler

Sebastians Feldbefund: „Rahmen verschieben, speichern — die Position ist nicht im
Datenbestand." Ursache war `beantworte_runde` (`backend/app/services/gesicht_quiz.py`):
der **Normalzweig** übernahm Rahmen **und** Vektor des **Detektors**

```python
dom = _gesicht_zu_bbox(gesichter, bbox)
if dom and dom.get("embedding"):
    neue_emb = dom["embedding"]      # Vektor des DETEKTOR-Ausschnitts
    neue_bbox = dom.get("bbox") or []  # Koordinaten des DETEKTORS
```

und meldete trotzdem `ok`. Der vom Nutzer bestätigte Rahmen kam nur im
**Ausweichzweig** zum Zug (wenn die Detektion gar kein Gesicht fand). Schritt A
hatte das nur in der **Anzeige** entschärft — dort stand seit A, dass dieser Weg
„nicht meldet, ob ein neuer Vektor entstand"; gespeichert wurde weiter der
Detektor-Rahmen.

## Was jetzt gilt

- **Der gesendete Rahmen gewinnt.** Ist ein `bbox` mitgesendet, wird der Vektor
  für **genau diesen Ausschnitt** gerechnet (`embed_crop` über
  `face_service.embedding_fuer_bbox`) und die Referenz trägt **numerisch die
  gesendeten Koordinaten**. Ein Test mit unterschiedlichen Vektoren für `embed`
  (Detektor) und `embed_crop` (Ausschnitt) belegt beides.
- **Rückfall bleibt Rückfall.** Findet die Detektion ein Gesicht, lässt sich der
  gesendete Ausschnitt aber nicht einbetten, wird der Detektor-Rahmen gespeichert
  — und **ehrlich als Rückfall gemeldet** (`grund`), nicht als „gesendet".
- **Neu in beiden Wegen**: die Antworten von `beantworte_runde` **und**
  `ergaenze_person_mit_bbox` tragen jetzt

  | Feld | Bedeutung |
  |---|---|
  | `referenz_geschrieben` | `true` nur, wenn in diesem Aufruf wirklich eine Referenz geschrieben wurde (Wahrheit aus der Speicherung) |
  | `rahmen_gespeichert` | `"gesendet"` (Nutzer-Rahmen) · `"erkannt"` (Detektor-Rahmen) · `null` (keine Referenz) |
  | `grund` | Klartext, wenn **keine** Referenz entstand oder ein Rückfall nötig war |
  | `cosinus_distanz` | **Nachtrag 16.10. (Schritt B):** Distanz des neuen Vektors zur nächsten vorhandenen Referenz derselben Person, auf 4 Stellen gerundet; `null`, wenn nicht verglichen wurde (erste Referenz, Frühausstieg, Fehler) |

  Gründe, die vorher „still" waren: Region bereits bestätigt (Frühausstieg),
  Cosinus-Distanz unter 0,05, Face-Engine nicht verfügbar, Ausschnitt-Einbettung
  liefert keinen Vektor.
- **Oberfläche** (`frontend/app.js`, Funktion `speichereEditorRahmen`, Quiz-Weg):
  eine Referenz wird **nur** behauptet, wenn `referenz_geschrieben` **und**
  `rahmen_gespeichert === 'gesendet'`. Der Detektor-Rückfall wird ausdrücklich als
  „Referenz mit dem ERKANNTEN Rahmen" benannt, der Fall ohne Referenz als „KEINE
  neue Referenz: <Grund>". Die A-Formulierung („… meldet dieser Weg nicht") ist
  damit weg — der Weg meldet es jetzt.
- Cache-Bump: `app.js?v=20261016D` → **`?v=20261016E`** in `frontend/index.html`.

## Tests (in diesem Lauf selbst ausgeführt)

- Neu: `backend/tests/test_gesicht_quiz_gesendeter_rahmen.py` — 11 Tests:
  Koordinaten **und** Vektor des gesendeten Rahmens, Gegenprobe ohne gesendeten
  Rahmen (`erkannt`), Rückfall-Meldung, die vier ehrlichen Gründe, derselbe
  Nachweis für `ergaenze_person_mit_bbox`. Ergebnis:
  `11 passed` (mit den Nachbardateien `60 passed`).
- Neu: `frontend/tests/test_quiz_referenz_meldung.js` — führt die **echte**
  Funktion gegen drei Antwortformen aus und liest den Text, der beim Nutzer
  ankommt; dazu die Verdrahtungsprüfung im Quelltext. Ergebnis: **Exit 0**,
  „Alle Pruefungen bestanden."
- Nachgezogen: `frontend/tests/test_quiz_rahmen_referenz_ehrlich.js` prüft jetzt
  den A3-Zustand (statt der A-Formulierung), inklusive Gegenprobe auf die alte
  Fassung; `frontend/tests/test_gesicht_quiz_fortschritt.py` liefert in der
  Engine-Attrappe **je Rahmen verschiedene** Vektoren (vorher lieferte die
  Attrappe für jeden Rahmen denselben Vektor — mit A3 wäre der Test sonst aus
  dem falschen Grund rot geworden).
- Alle Frontend-Tests zusammen (`backend/tests/test_frontend_node.py`):
  **37 passed, Exit 0**.

## Grenzen (ehrlich)

- Die **Wirkung am Gerät** ist am PC nicht abnehmbar: ob Sebastians verschobener
  Rahmen nach dem Neuladen wirklich sitzt, zeigt erst das Handy. Der Test belegt
  die **gespeicherten Daten**, nicht die Anzeige.
- **Nicht** Teil von A3: das Anlegen **mehrerer** gleicher Referenzen
  („Variante 2" im Plan — jedes Speichern erzeugt eine neue Referenz). Diese
  Variante wartet auf Sebastians Entscheidung und ist derzeit **nicht** gebaut;
  ihre Auflagen (Kennungen, Mehrdeutigkeit beim Adressieren) stehen im Plan,
  Abschnitt 4.
- Die Schritte **B–I** des Plans (Rahmen neu vektorisieren, Mehrfachbearbeitung,
  PC-Weg, Rahmen von Hand, Bedienfeld überall, Ziel-Personen-Menü, Umbenennen,
  Neuerkennung) sind weiterhin **nicht** gebaut.
  **Nachtrag 16.10.:** **Schritt B** ist inzwischen gebaut (die Cosinus-Distanz
  steht im Antwort-Protokoll, siehe `changelog-2026-10-16-rahmen-distanz-protokoll.md`)
  — offen sind **C–I**.
