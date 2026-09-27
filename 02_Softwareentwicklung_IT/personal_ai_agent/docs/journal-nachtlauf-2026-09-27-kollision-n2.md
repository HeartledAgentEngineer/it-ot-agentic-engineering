# Nachtlauf 27.09.2026 — Kollision bei N2, Zustand und nächster Schritt

> **Wer schreibt hier:** der Cron-Lauf des Nachtlaufs (Planer + Committer) um
> 05:20. **Warum diese eigene Datei:** der zweite Agent arbeitet **gleichzeitig**
> im selben Arbeitsbaum und bearbeitet gerade `docs/plan-nachtlauf-2026-09-26.md`;
> ein Eintrag dort hätte **fremde, halbfertige** Zeilen mit in den Commit
> genommen. Deshalb liegt dieser Bericht in einer eigenen Datei.

## Was passiert ist (belegt, mit Uhrzeiten)

1. Um **04:58** gestartet: `git pull --rebase` scheiterte („unstaged changes"),
   `git rev-list --left-right --count origin/main...HEAD` = **0 0** → lokal und
   Remote waren bereits gleich, es war nichts zu holen. Nichts überschrieben.
2. **N2 (Rückroll-Werkzeug)** als Auftrag geschnitten. Ausführer sollte die
   Codex CLI sein (`gpt-5.6-terra`) — **Codex ist ausgefallen**:
   `ERROR: You've hit your usage limit … try again at Oct 15th, 2026 9:32 PM`.
   Ersatzweise lief ein Hermes-Subagent (DeepSeek V4.1 Flash, 462 s, 0,019 $):
   `tools/pcloud/pcloud_manifest.py`, `tools/pcloud/pcloud_rueckrollen.py`,
   +20 Tests, Changelog. Prüfbefehl des Ausführers: **545 passed, Exit 0**.
3. **Prüfer (andere Familie, `openai/gpt-5.6-luna`) → „nicht bestanden"**:
   (a) Changelog behauptete eine „POST-Weiche", der Code nutzt GET;
   (b) im Dokument standen ein echter Dateiname und eine echte `fileid` aus
   Sebastians Konto. Beides ist doc-seitig repariert und die CLI wurde von Hand
   mit **erfundenem** Manifest nachgefahren (`--zeigen` Exit 0, `--trocken`
   Exit 0, fehlendes Manifest Exit 2).
4. Beim zweiten Prüfdurchgang (05:15) kam eine **neue** Abweichung:
   der CLI-Code kenne `--trocken` nicht, sondern `--wirklich`. Ursache war
   **keine** fehlerhafte Doku, sondern eine **Kollision**: ein zweiter Agent hat
   zwischen den Prüfungen genau dieselbe Aufgabe gebaut —
   `tools/pcloud/pcloud_bewegungen.py` (05:10), `pcloud_rueckrollen.py` in einer
   eigenen Fassung (05:15), `backend/tests/test_pcloud_bewegungen.py` und
   `test_pcloud_rueckrollen.py` (05:17). Meine Fassung der CLI und der Testdatei
   existiert damit nicht mehr.

## Entscheidung (selbst getroffen, ohne Rückfrage)

**N2 gehört dem zweiten Agenten — ich fasse es nicht mehr an.** Begründung:

* Sein Werkzeug ist inhaltlich **weiter** als meins: Es prüft vor dem Rückrollen,
  ob das Element noch im Zielordner liegt, schreibt jede echte Rückrollung
  selbst wieder ins Manifest (`art=rueckroll`, „Doppelt-Anfassen" ausgeschlossen)
  und lässt „Ordner anlegen" bewusst stehen statt zu löschen.
* Ein zweites Werkzeug mit derselben Aufgabe wäre **Code-Doppelung** — genau der
  Wildwuchs, den `AGENTS.md` („Tüfteln erlaubt, aber strukturiert") verbietet.
* Ein Commit meiner Reste würde **fremde, halbfertige** Arbeit mitnehmen —
  derselbe Fehler wie Commit `908cf39`. Deshalb: **kein `git add -A`**, hier
  sogar **gar kein Commit** an geteilten Dateien.

**Bewusst NICHT committet** (liegt nur auf der Platte, damit nichts vermischt
wird — nichts gelöscht):

| Datei | Warum liegen gelassen |
|---|---|
| `tools/pcloud/pcloud_manifest.py` | Manifest-Logik, die `pcloud_bewegungen.py` **selbst** mitbringt (Stand 05:10) |
| `backend/app/services/pcloud_service.py` (+`verschiebe_ordner`, `verschiebe_datei`) | das Werkzeug des zweiten Agenten spricht pCloud direkt an — die Methoden wären ungenutzte Doppel-Logik im Backend |
| `backend/tests/test_pcloud_service.py` (+5 Tests) | prüft genau diese ungenutzten Methoden |
| `docs/changelog-2026-09-27-rueckrollwerkzeug.md` | beschreibt eine CLI-Fassung (`--trocken`), die es nicht mehr gibt — **so nicht codgenau** |

## Prüfbefehl (selbst gefahren, 27.09.2026 ~05:18)

```
cd backend && .venv/Scripts/python.exe -m pytest tests/ -q
  -> 530 passed, 3 warnings in 53.53s
     Exit-Code 0
```

Zahlen ehrlich: Baseline dieses Laufs um 04:59 **500** · Zwischenstand mit
meinem (verdrängten) N2-Ausbau **545** · aktueller Stand mit dem Aufbau des
zweiten Agenten **530** (Themen-Stufe N4: 25 Tests; meine 20 sind durch dessen
Fassung ersetzt). Das Tor ist grün — der Lauf hält also nichts Kaputtes.

## Bestandsaufnahme für N9 (Personen-Stufe) — nur gelesen, nichts geändert

Im Backend-venv (`backend/.venv/Scripts/python.exe`, 27.09.2026) vorhanden:
**numpy 2.4.6**, **PIL 12.3.0**. **Nicht installiert:** `cv2` (OpenCV),
`onnxruntime`, `insightface`, `deepface`, `face_recognition`, `scikit-learn`.

Bedeutung für N9: Ein **lokaler** Gesichts-/Embedding-Stapel ist auf diesem
Rechner **nicht** vorhanden — N9 kann nicht „OpenCV-Erkennung über alles" fahren,
sondern muss (a) den Weg über das multimodale Modell nehmen (in-memory, Bilder
nie speichern — Sebastians Datenschutzregel) oder (b) den Paket-Einbau bewusst
als eigenen Schritt mit Kosten/Nutzen vorlegen. Vorhanden ist bereits
`backend/app/services/gesichter_service.py` (581 Zeilen, Personen-Katalog mit
Referenzen + `ref_id`-Kennungen) — daran kann N9 andocken, statt neu zu bauen.

## Nächster Schritt

**N9 (Personen-Stufe vorbereiten)** — kollisionsfrei, weil andere Dateien als
N2/N4/N5: Verfahren festlegen (Modell-Weg statt lokalem CV, Stichprobe messen),
Referenzseiten + Cluster-Verfahren skizzieren. N5–N8 bleiben beim zweiten
Agenten, N3 (Schlüssel aufs Handy) weiterhin **nur** mit Sebastian.
