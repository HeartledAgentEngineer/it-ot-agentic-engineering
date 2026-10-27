# Bild-Editor B2 (Backend): Erkennung für eine `fileid` — 27.10.2026

Planschritt B2 von „Bild-Editor für jedes Bild" (nach B1). Nur Backend, **kein Frontend**.
Die neue Route erkennt die Gesichter **eines** Fotos neu, gleicht sie mit den vorhandenen Gesichtern
ab und liefert Namensvorschläge. Sie **speichert nichts** (Übernehmen läuft später über
`POST /api/gruppen/bild-rahmen`, B1).

## Was gebaut ist

### `POST /api/gruppen/bild-erkennen`

Body: `{"fileid": <positive ganze Zahl oder Ziffern-Text, höchstens 20 Stellen>}`. Gleicher Schutz
wie alle `/api/gruppen`-Routen (`main.py` hängt den Router hinter `auth.require_api_key`).

Erfolg (HTTP 200):

```json
{"ok": true, "fileid": "111", "quelle": "original_1600" | "vorschau_800",
 "breite": 1600, "hoehe": 1200, "abgleich": true,
 "gesichter": [
   {"bbox_norm": [x, y, w, h], "status": "bekannt", "gid": "111:0", "name": "…" | null,
    "vorschlaege": [{"name": "…", "abstand": 0.31}]},
   {"bbox_norm": [x, y, w, h], "status": "neu", "vorschlaege": []}]}
```

- `bbox_norm` = `[links, oben, Breite, Höhe]`, normiert (0..1) auf die **verarbeitete** Bildgröße
  (`breite`/`hoehe` der Antwort), 6 Stellen — dasselbe Format wie `bbox_norm` aus B1. Die Erkennung
  liefert Pixel `[x, y, w, h]`; sie werden am Bild begrenzt (ragt ein Rahmen hinaus, wird er
  beschnitten). Rahmen mit weniger als 1 % Breite oder Höhe (`BBOX_MIN`) fallen **still weg**.
- `status`: `bekannt`, wenn der Rahmen mit einem Gesicht der zusammengeführten B1-Sicht
  (`gruppen_quiz.gesichter_auf_bild`, also inkl. verschobener Rahmen, Hand-Gesichter, ohne
  entfernte/ausgeschlossene) eine IoU (Schnitt/Vereinigung) von **mindestens 0,5** hat; dann stehen
  `gid` und `name` (der Name des vorhandenen Gesichts, kann `null` sein) dabei. Sonst `neu`
  (knapp unter 0,5 = neu). Jedes vorhandene Gesicht wird höchstens einmal vergeben, das Paar mit
  der größten Deckung zuerst.
- `abgleich`: `false`, wenn die vorhandene Sicht nicht lesbar war (z. B. Gruppen-Datei fehlt); dann
  ist jedes Gesicht `neu`.
- `vorschlaege`: aus dem Handy-Katalog (`face_service.erkenne_personen`), **nur** `name` und
  `abstand` (Cosinus-Distanz), höchstens 3, sortiert wie der Katalog. **Keine Embeddings** in der
  Antwort, im Log oder auf der Platte; Katalogfehler ergeben `[]`.

### Bildquelle (`bild_erkennen._bild_holen`)

1. **Pillow nutzbar** (Probe `_pillow_nutzbar()`, `from PIL import Image, ImageOps` — Android hat
   oft nur Stubs): Original per `pcloud_service.datei_bytes(fileid, 25 MB)` **nur in den Speicher**,
   `ImageOps.exif_transpose` (Drehung/Spiegelung in die Pixel; die Erkennung erwartet dieselbe
   Ausrichtung wie die Anzeige, `face_infer.py` dreht sonst selbst nach EXIF), auf höchstens
   **1600 px** (längste Seite, nie hochgerechnet) verkleinert, als JPEG (Qualität 90) **ohne EXIF**
   an die Erkennung. JPEGs werden mit `draft` sparsam dekodiert. `quelle = "original_1600"`.
   (Das Muster `datei_suche.py:397` dreht nicht auf diese Weise und wurde nicht übernommen.)
2. **Pillow nicht nutzbar:** `pcloud_service.thumb(fileid, "800x800")` unverändert,
   `quelle = "vorschau_800"`; `datei_bytes` wird dann **nicht** aufgerufen (nie 25 MB ungeschrumpft
   durch proot). Die Maße kommen aus dem Dateikopf (`_masse_aus_kopf`: JPEG `SOFn`, PNG `IHDR`);
   bei JPEG mit EXIF-Orientierung 5–8 sind Breite und Höhe vertauscht, weil die Erkennung selbst
   nach EXIF dreht. Nicht lesbarer Kopf → `bild_unlesbar`.

### Erkennung und `face_service`

- `face_service._infer(payload, timeout_s=None)`: neuer Parameter; `None` = `_INFER_TIMEOUT_S`
  (**30 s**). Alle bisherigen Aufrufer (`embeddings_fuer_pfad`, `embedding_fuer_bbox`) rufen
  unverändert `_infer(payload)` und behalten 30 s.
- `bild_erkennen` ruft `_infer({"op": "embed", "bild_base64": …, "max_faces": 30}, timeout_s=45)`
  (`MAX_GESICHTER = 30`, `ERKENNUNG_TIMEOUT_S = 45`).
- Vor dem Laden aus der pCloud wird `face_service.verfuegbar()` geprüft (kein Download, wenn die
  Erkennung nicht läuft).

### Fehler (ehrlich, mit echtem HTTP-Status)

Abweichend von der sonst üblichen Regel der Gruppen-Routen („immer 200 + `ok`") antwortet diese
Route bei Fehlern mit dem passenden Status. Der Körper ist immer
`{"ok": false, "grund": "<schlüssel>", "fehler": "<deutscher Text>"}` (Tabelle:
`bild_erkennen.STATUS_JE_GRUND`):

| Status | `grund` | `fehler` |
|---|---|---|
| 400 | `fileid_ungueltig` | Ungültige Bildkennung. (kein Ziffern-Text/Zahl, ≤ 0, > 20 Stellen, `true`, Liste, `null` …) |
| 413 | `bild_zu_gross` | Bild zu groß (über 25 MB). (auch Pillow-Dekompressionsbombe) |
| 422 | `bild_unlesbar` | Bild nicht lesbar. (Pillow öffnet es nicht / Kopf ohne Maße) — **422 auch**, wenn das Feld `fileid` im Body ganz fehlt (FastAPI-Validierung, anderer Körper) |
| 502 | `pcloud_nicht_erreichbar` | pCloud nicht erreichbar. (`PCloudFehler`, leere Antwort) |
| 502 | `erkennung_fehlgeschlagen` | Die Erkennung ist fehlgeschlagen. (innere Meldung nur im Log, gekürzt) |
| 503 | `pcloud_nicht_konfiguriert` | pCloud ist nicht konfiguriert. |
| 503 | `erkennung_nicht_verfuegbar` | Erkennung nicht verfügbar. (`verfuegbar()` False oder Engine verschwindet zwischen Prüfung und Lauf) |
| 504 | `zeitgrenze` | Zeitgrenze der Erkennung (45 s) erreicht — die Erkennung hat zu lange gebraucht. (`_infer` meldet `timeout`; die 45 s gelten nur für den Erkennungs-Subprozess, nicht für Verfügbarkeitsprobe, Download oder Vorschau davor) |

Ein unbekannter `grund` würde als 500 gemeldet (kommt im Code nicht vor).

### Speichern: nichts

Kein Schreibzugriff: weder Original noch Verkleinerung noch Ergebnis landen auf der Platte
(Bytes nur im Speicher; Embeddings nur während des Aufrufs).

## Entscheidungen

- **Eigenes Modul** `backend/app/services/bild_erkennen.py` statt Funktion in `gruppen_quiz.py`:
  `gruppen_quiz` ist laut Kopf „nur lokale Dateien, kein Netz, kein Modellaufruf" und hat bereits
  ~2.870 Zeilen; B2 braucht pCloud (Netz) und den Erkennungs-Subprozess. `bild_erkennen` nutzt
  `gruppen_quiz` nur lesend (`gesichter_auf_bild`, `_bbox_norm`).
- `fileid` im Pydantic-Modell als `Any` (wie B1), damit ungültige Werte HTTP 400 mit dem
  einheitlichen Körper ergeben statt FastAPI-422.
- Höchstens 3 Namensvorschläge je Gesicht (der Plan nennt keine Zahl).
- Beim Abgleich zusätzlich `name` des vorhandenen Gesichts in der Antwort (nur Name, den es in der
  Sicht ohnehin gibt).

## Geänderte und neue Dateien

- `backend/app/services/face_service.py` — `_infer(payload, timeout_s=None)`.
- `backend/app/services/bild_erkennen.py` — neu.
- `backend/app/router/gruppen.py` — Route `bild-erkennen`, Docstring-Liste, Eingabemodell.
- `backend/tests/test_bild_editor_b2.py` — neu, **56 Tests** (14 davon die Parametrisierung der
  ungültigen `fileid`), offline: pCloud und Erkennung sind Attrappen, nur erfundene Kennungen/Namen.
- `docs/changelog-2026-10-27-bild-editor-b2.md` — diese Datei.

## Prüfung

`cd backend && .venv/Scripts/python -m pytest tests/test_bild_editor_b2.py -q` — alle 56 Tests grün.
Bestehende Tests: `tests/test_gruppen_quiz.py tests/test_bild_editor_b1.py` — 171 grün.

## Offen

- Oberfläche (B4/B5) ruft die Route noch nicht auf.
- HEIC/AVIF-Originale kann Pillow ohne Zusatzmodul nicht öffnen → `bild_unlesbar` (kein Rückfall auf
  die Vorschau; so im Plan nicht vorgesehen).
- Echter Handy-Lauf (proot, echte pCloud) steht aus; getestet ist nur mit Attrappen.
- Unbelegt: ob die pCloud-Vorschau 800×800 das EXIF-Orientierungstag (274) behält, obwohl die Pixel
  schon gedreht sind. Dann würden die Maße vertauscht und `face_infer` dreht ein zweites Mal → Rahmen
  falsch. Beim ersten Handy-Lauf an einem Hochkantbild Tag und Maße der Vorschau prüfen (Hermes-Befund 1).
