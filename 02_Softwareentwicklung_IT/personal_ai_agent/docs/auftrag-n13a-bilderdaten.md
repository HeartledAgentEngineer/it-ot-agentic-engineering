# Feinauftrag N13a — Datenfundament „Bilder im Chat" (Galerie-Vorstufe)

> **Auftraggeber:** Planer (Hauptkontext) · **Datum:** 28.09.2026
> **Ausführer:** Hermes-Subagent (`deepseek-v4.1-flash`)
> **Prüfer:** frischer Subagent, andere Modellfamilie (`openai/gpt-5.6-luna`)
> **Übergeordneter Plan:** `docs/plan-nachtlauf-2026-09-26.md`, Schritt **N13**
> („N13a" = Datenfundament, „N13b" = Anzeige im Frontend).
> **Rollenregel:** Der Ausführer fasst **kein** git an, führt **keine** Shell-Kette
> aus und schreibt **keine** Bilddatei. Er lädt keine Archive, keine Fotos.

## Warum dieser Schritt

Der Nutzer will Bilder **im Chat** am Handy sehen: Frage → Trefferliste →
Kacheln → Antippen = groß → Diashow (Plan-Zeile N13). Belegt am 27.09.2026:
das Frontend zeigt **heute keine** Cloud-Bilder (`cloud/thumb` kommt in
`app.js`/`index.html` 0 × vor).

Der Grund, warum die Anzeige nicht einfach gebaut werden kann: die
Fotos-Übersicht aus N11 (`~/foto_sortierung/fotos_uebersicht.json`) enthält
**bewusst keine Datei-Kennungen**. Ohne Kennung kann kein Vorschaubild geladen
werden. Genau diese Lücke schließt dieser Schritt — **ohne** die bestehende
Übersichtsdatei anzufassen.

## Prüfkriterium (das Tor)

1. `cd backend && .venv/Scripts/python -m pytest tests/ -q` → **Exit 0**
   (Baseline: **1687 passed**; die neuen Tests kommen dazu).
2. Das Werkzeug erzeugt die Datei **idempotent**: zweiter Lauf mit
   unverändertem Plan → gleiche Zahlen, keine Doppelungen.
3. Der Endpunkt antwortet **immer HTTP 200** mit **immer denselben Feldern**;
   fehlt die Datei → deutsches `error`, `ok: false` (nie 500).
4. Die Datei-IDs sind **echte** Werte aus dem Plan, keine erfundenen — der
   Planer prüft das live gegen `~/foto_sortierung/sortierplan.json`.

## Teil 1 — Werkzeug `tools/foto_sortierung/foto_dateien.py`

**Aufgabe:** aus dem lokalen `sortierplan.json` (nur lesend) eine kleine,
maschinenlesbare Datei mit den **Datei-Kennungen je Event** bauen.

* Eingabe: `~/foto_sortierung/sortierplan.json` — Feld `zuege` (Liste), je
  Eintrag `fileid` (int), `jahr` (int), `kategorie` (str), `event` (str),
  `von_name` (str), `ziel_pfad` (str). Zusätzlich `stand` (ISO-Text).
  Übersteuerbar per Umgebungsvariable **`FOTO_PLAN_PFAD`** (Tests!).
* Ausgabe: `~/foto_sortierung/fotos_dateien.json`, übersteuerbar per
  **`FOTO_DATEIEN_PFAD`**. Schreiben **atomar** (temp-Datei im Zielordner +
  `os.replace`). Ein Zielpfad **innerhalb des Repos** wird **verweigert**
  (deutsche Meldung, **Exit 2**).
* CLI: `--plan <pfad>`, `--ausgabe <pfad>`, `--trocken` (**Standard**),
  `--schreiben`. `--trocken` zeigt nur Zahlen und schreibt nichts.
* **Verbote:** kein Netz, kein pCloud-Aufruf, kein `delete`/`rmtree`, keine
  Bilddatei öffnen, nichts aus dem Repo lesen außer dem eigenen Code,
  keine Löschfunktion (auch nicht „zur Sicherheit"). Tests prüfen die
  Abwesenheit von Lösch- und Netzaufrufen im Quelltext.

### Eingefrorenes Schema der Ausgabedatei (Version 1)

```json
{
  "art": "foto_dateien",
  "version": 1,
  "stand": "2026-09-28T09:40:00+02:00",
  "plan_stand": "2026-09-27T13:49:46+02:00",
  "zahlen": {
    "events": 2098,
    "dateien": 7616,
    "ohne_kennung": 0,
    "kategorien": 11,
    "jahre": 11
  },
  "events": [
    {
      "jahr": 2021,
      "kategorie": "Urlaub",
      "event": "2021_07 Beispielort",
      "anzahl": 42,
      "dateien": [
        {"datei_id": 47110000001, "name": "IMG_20210712_101112.jpg"}
      ]
    }
  ]
}
```

Regeln zum Schema:

* Ein Event = genau ein `(jahr, kategorie, event)`-Tripel — **dieselbe
  Definition wie `events` in der N11-Übersicht** (dort 2.098).
* `dateien` enthält **nur** Züge mit gültiger `fileid`; Züge ohne Kennung
  werden gezählt (`ohne_kennung`) und **nicht** aufgenommen.
* `anzahl` = Länge von `dateien`.
* Sortierung ist **fest**: `events` nach `jahr` absteigend, dann `event`
  aufsteigend; `dateien` nach `name` aufsteigend, bei Gleichstand nach
  `datei_id` aufsteigend. Damit ist die Datei reproduzierbar (Idempotenz
  ist damit prüfbar, nicht nur behauptet).
* `stand` = Zeitpunkt des Schreibens, `plan_stand` = `stand` aus dem Plan
  (oder `null`, wenn dort keiner steht).

## Teil 2 — Dienst `backend/app/services/foto_bilder.py`

Baugleich zu `services/foto_uebersicht.py` (dort abschauen, nicht kopieren —
die Aufteilung ist die Vorlage):

* `DATEIEN_DATEINAME = "fotos_dateien.json"`, `DATEIEN_ORDNER =
  "foto_sortierung"`, `dateien_pfad()` mit Umgebungsvariable
  **`FOTO_DATEIEN_PFAD`** (leerer Wert zählt nicht).
* `ERWARTETE_VERSION = 1`, `ERWARTETE_ART = "foto_dateien"`.
* `dateien_laden()` → `{"existiert": bool, "pfad": str, "stand": str|None,
  "zahlen": dict, "events": list, "error": str|None}` — **nie ein Wurf**;
  unbekannte `version`/`art` → `existiert: False` mit deutschem Text
  (nicht stillschweigend lesen).
* `bilder_finden(jahr=None, kategorie=None, event=None, suche=None,
  limit=5, pro_event=40)` → Liste von Event-Dicts mit gefilterten,
  **gekürzten** Dateilisten. Filter wie in `events_finden` (Umlaut-tolerante
  Teilzeichenkette, Groß/Klein egal); `event` filtert den Event-Namen,
  `suche` dasselbe Feld (ein Feld genügt — beide erlaubt, aber `event` hat
  Vorrang). `limit` auf 1…50 geklemmt, `pro_event` auf 1…200.
* `status_block()` → immer dieselben Schlüssel für das Selbsttest-Blatt:
  `{"ok": bool, "quelle": str|None, "stand": str|None, "events": int,
  "dateien": int, "error": str|None}`.
* **Kein Netz, kein pCloud, keine Bilder, keine Geheimnisse** — nur die
  lokale Datei lesen.

## Teil 3 — Endpunkt `GET /api/fotos/bilder` (in `backend/app/router/fotos.py`)

Der Router existiert; es kommt **eine** Route dazu (keine zweite Datei,
keine Änderung an `main.py` — die Registrierung ist schon da).

Parameter: `jahr: int|None`, `kategorie: str|None (max 200)`,
`event: str|None (max 200)`, `limit: int = 5` (Events),
`pro_event: int = 40` (Dateien je Event).

Antwort (eingefroren, immer HTTP 200, immer dieselben Felder):

```json
{
  "ok": true,
  "quelle": "fotos_dateien.json",
  "stand": "2026-09-28T09:40:00+02:00",
  "zahlen": {"events": 2098, "dateien": 7616},
  "events": [
    {"jahr": 2021, "kategorie": "Urlaub", "event": "2021_07 Beispielort",
     "anzahl": 42,
     "dateien": [{"datei_id": 47110000001, "name": "IMG_20210712_101112.jpg"}]}
  ],
  "anzahl": 1,
  "error": null
}
```

* `anzahl` = Zahl der zurückgegebenen Events.
* Fehlt die Datei: `ok: false`, leere Listen, `error` deutscher Text.
* Jeder Fehler wird gefangen (`logger.error`) — **kein 500er**.
* `pro_event` kürzt die Liste je Event; der Event trägt weiter `anzahl`
  (echte Gesamtzahl) — damit die App „42 Bilder, 40 gezeigt" sagen kann.
* **Keine Bilder im JSON**, keine Bilddaten, kein pCloud-Aufruf im Router.

## Teil 4 — Tests

* `backend/tests/test_foto_dateien.py` — Werkzeug: **mindestens 35**
  Testfunktionen, alles offline (`tmp_path`, erfundene Namen wie
  `Urlaub Beispiel`), inklusive: Idempotenz (2. Lauf byte-gleiche Datei),
  Sortierung, Züge ohne Kennung, kaputter Plan (kein Wurf), Repo-Ziel →
  Exit 2, Quelltext-Abwesenheit von Lösch-/Netzaufrufen, Schema-Felder.
* `backend/tests/test_foto_bilder_endpunkt.py` — Dienst + Endpunkt mit
  `TestClient` und einer **Attrappe** der Datei in `tmp_path` (Umgebungs-
  variable setzen und danach zurücksetzen): Filter, Klemmen von `limit`
  und `pro_event`, fehlende Datei → 200 + `error`, falsche `version`/
  `art`, `anzahl` je Event bleibt die Gesamtzahl, **immer dieselben Felder**.
* Kein Netz in beiden Dateien (Tests dürfen weder Namensauflösung noch
  Verbindungsaufbau zulassen — wie in `test_foto_uebersicht_endpunkt.py`).

## Teil 5 — Doku (im selben Commit wie der Code)

* `docs/changelog-2026-09-28-n13a-bilderdaten.md`: Auftrag, was gebaut
  wurde, die gefahrenen Befehle mit **echten** Zahlen (Prüfbefehl-Ausgabe,
  Zeilen der Dateien, Testfunktionen), das eingefrorene Schema, die
  **offenen** Punkte (Datei liegt nur am PC; Übertragung ans Handy ist
  nicht Teil des Schritts; die Anzeige selbst ist N13b).
* KEINE erfundenen Zahlen. Wenn eine Zahl nicht gemessen wurde, steht das
  als „nicht gemessen" da.
* Keine Personennamen, keine Ortsnamen, keine pCloud-Dateikennungen in der
  Doku — Beispiele sind erfunden.

## Grenzen (hart)

* Nur **reiner Code** — kein Chat-Archiv, keine Fotos, keine Erinnerungen,
  keine `.env`, keine Bewerbungen in Ausgaben oder Dateien.
* **Nichts löschen** — kein `os.remove` außer der **eigenen** temp-Datei
  beim atomaren Schreiben, kein `shutil.rmtree`, nirgends.
* **Keine** schreibende pCloud-Operation, **kein** pCloud-Aufruf überhaupt.
* Keine Schlüsselwerte in Ausgaben oder Dateien.
* Kein git-Befehl, keine `git`-Aufrufe durch den Ausführer.
