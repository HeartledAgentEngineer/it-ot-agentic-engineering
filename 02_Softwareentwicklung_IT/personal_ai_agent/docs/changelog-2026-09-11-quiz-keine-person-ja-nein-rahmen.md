# Changelog 2026-09-11 — Quiz: "Keine Person gefunden" Ja/Nein + manueller Rahmen

## Änderung

Verhalten des Gesichter-Quiz bei **0 automatisch erkannten Gesichtern**:

- Vorher: Es wurde gefragt "Wer ist auf diesem Bild?" – unsinnig, wenn nichts
  markiert ist. Die Ja/Nein-Zuordnung war dafür zudem invertiert (Ja → Rahmen,
  Nein → überspringen).
- Jetzt: Kopfzeile **"Keine Person gefunden"** mit klarer Ja/Nein-Frage.
  - **Ja → nächstes Bild** (überspringen, Bild als 'gesehen' abhaken).
  - **Nein → Person per Rahmen ergänzen** (Touch-Drag-Rechteck aufs Bild,
    dann Person benennen/neu anlegen).

Damit ist die 0-Gesichter-Logik identisch zur Einzelgesicht-Variante
"Keine Person gefunden?" (Zeile ~3693), die schon richtig war.

## Technisch

- `frontend/app.js` – `zeigeQuizKarte`: 0-Gesichter-Zweig (`else` bei
  `anzahlGes === 0`) auf Ja=(skip)/Nein=(einzeichnen) gedreht, Kopfzeile
  angepasst. Nutzt die bestehende `zeigeEinzeichnen()` (manueller Rahmen).
- Cache-Bust im `index.html` auf `app.js?v=20260911bA`.

## Zusammengehörige, in diesem Stand enthaltene Feature-Arbeit (manueller Rahmen)

Damit „Nein → Rahmen ergänzen" auch eine nicht von YuNet erkannte Person
anlernen kann, ergänzt dieser Stand zusätzlich (Backend+Frontend):

- `backend/face_infer.py` – neue Operation `embed_crop`: erzeugt ein
  SFace-Embedding für ein selbst gezeichnetes Rechteck in absoluten Pixeln
  (alignCrop über Gesicht+Landmarken im Ausschnitt, Fallback: Quadrat-Crop).
- `backend/app/services/face_service.py` – `embedding_fuer_bbox()` (b64 → infer).
- `backend/app/services/gesicht_quiz.py` – `ergaenze_person_mit_bbox()`:
  legt/findet die Person über `person_speichern(...)` mit dieser neuen Referenz
  (inkl. `jahr` und `bbox`), persistiert Ergebnis-Notiz + Fortschritt.
- `backend/app/router/gesichter.py` – `QuizAntwortBody.manuell_bbox`; Router
  ruft bei `manuell_bbox=True` `ergaenze_person_mit_bbox()` statt `beantworte_runde`.
- `frontend/app.js` – `zeigeEinzeichnen()`: ruft `quizBeantworten(..., manuell=true)`
  mit der gezeichneten bbox auf.

## Verifikation

- `node --check frontend/app.js` → OK.
- `python3 -m ast` (bzw. Syntax-Parse) über die 4 geänderten `.py` → OK.
- Manuell: Server-Neustart erforderlich (uvicorn ohne `--reload`), da Backend
  geändert; Frontend über `index.html?v=20260911bA` neu laden.