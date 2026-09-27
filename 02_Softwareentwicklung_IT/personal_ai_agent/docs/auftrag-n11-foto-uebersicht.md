# Feinauftrag N11 — Fotos-Übersicht am Handy (Endpunkt + kleine Datendatei)

> **Planer:** Hauptagent (Nachtlauf 27.09.2026) · **Ausführer:** zwei Hermes-Subagenten
> (getrennte Dateimengen, eingefrorene Schnittstelle) · **Prüfer:** `openai/gpt-5.6-luna`
> (andere Modellfamilie). Codex ist bis 15.10.2026 gesperrt (Kontingent).

## Auftrag (Wortlaut des Plans)

> **N11 — Fotos-Fragen am Handy:** Endpunkt `/api/fotos/uebersicht` + kleine
> Datendatei (Zahlen und Event-Namen, **ohne Bilder**).
> **Prüfkriterium:** Endpunkt antwortet **ohne Netz**; Selbsttest zeigt die Quelle.

**Zweck:** Sebastian fragt in der App am Handy „wie viele Events gab's?“ oder
„zeig mir die Urlaube 2021“. Heute unmöglich, weil Sortierschlüssel,
`themen.jsonl` und `kategorien.json` **nur auf dem PC** liegen.

## Harte Regeln (gelten für beide Ausführer)

1. **Kein Git.** Keine `git`-Befehle, kein Commit, kein Push.
2. **NIE löschen.** Keine Löschfunktion, kein `shutil.rmtree`, kein `os.remove`
   außer auf eine **selbst erzeugte** temp-Datei beim atomaren Schreiben.
3. **Kein Netz.** Kein `pcloud_service`, kein `httpx`/`requests`, keine
   LLM-Aufrufe. Alles liest ausschließlich **lokale Dateien**.
4. **Keine Bilder.** Es werden keine Bilddateien gelesen, kopiert oder
   gespeichert (die Übersicht trägt **nur Zahlen und Namen**).
5. **Keine Geheimnisse** in Ausgaben, Dateien oder Logs (kein Token, kein Key).
6. **Keine Namen Dritter** in Repo-Dateien (Code, Tests, Doku): in Tests
   ausschließlich erfundene Beispielnamen (`Beispiel-Ordner`, `Konzert Beispiel`).
   Der **Eigner-Name** darf ebenfalls nicht in **neuen** Zeilen stehen
   (Bestand in `docs/plan-nachtlauf-2026-09-26.md` bleibt unberührt).
7. **Ausgaben nur außerhalb des Repos** (`~/foto_sortierung/`). Ein Zielpfad im
   Repo wird **verweigert** (deutsche Meldung, Exit 2).
8. **Doku auf Deutsch, Kommentare Deutsch.** Keine Emojis in neuen Zeilen.
9. **Fremde Dateien nicht anfassen:** `docs/experimente/live_zahlen.*`,
   `tools/pcloud/pcloud_duplikate.py`, `tools/foto_sortierung/screenshots_triage.py`,
   `docs/changelog-2026-09-27-duplikate-hashes.md`, `backend/tests/test_pcloud_duplikate.py`
   gehören einem **zweiten Agenten** (arbeiten parallel im selben Baum).
10. **Prüfbefehl am Ende selbst fahren** und die Ausgabe in den Bericht schreiben:
    `cd backend && .venv/Scripts/python -m pytest tests/ -q` → muss `passed`, Exit 0.
    Für Frontend: `node --check frontend/app.js` und `node frontend/tests/test_selbsttest.js`.

## Eingefrorene Schnittstelle: die Übersichts-Datei (JSON)

Subagent A **erzeugt** sie, Subagent B **liest** sie. Das Schema ist bindend —
wer es ändert, bricht den anderen Teil.

```json
{
  "version": 1,
  "art": "foto_uebersicht",
  "stand": "2026-09-27T22:30:00+02:00",
  "quelle": {"plan_stand": "2026-09-27T13:49:46", "trocken": true},
  "zahlen": {
    "zeilen": 9430, "anlaesse": 2127, "zuege": 7616,
    "events": 2098, "events_neu": 2088, "events_wiederverwendet": 39,
    "ordner_neu": 2108, "ordner_vorhanden": 82,
    "themen": 48, "kategorien": 11,
    "doppelung_gesamt": 1534, "doppelung_ohne_anlass": 866,
    "doppelung_uebersprungen": 668, "ohne_thema": 0, "ohne_jahr": 0,
    "ohne_datum": 1146, "jahre": 11
  },
  "jahre": [{"jahr": 2014, "anlaesse": 1, "dateien": 1, "events": 1}],
  "themen": [{"thema": "Haus und Garten", "anlaesse": 3, "dateien": 3}],
  "kategorien": [{"kategorie": "WG", "anlaesse": 9, "dateien": 12, "events": 9}],
  "events": [{"jahr": 2014, "kategorie": "WG",
              "name": "2014-03-30 Haus und Garten", "dateien": 1, "quelle": "neu"}]
}
```

**Pflicht-Felder (B verlässt sich darauf):** `version`, `art`, `stand`,
`quelle.plan_stand`, `quelle.trocken`, `zahlen.*` (alle oben genannten Schlüssel),
die vier Listen `jahre`/`themen`/`kategorien`/`events` mit **genau den genannten
Schlüsseln** (Typen: `jahr` int, `anlaesse`/`dateien`/`events` int, `name`/
`kategorie`/`thema`/`quelle` str).
Sortierung: `jahre` aufsteigend nach `jahr`; `themen`/`kategorien` absteigend nach
`anlaesse`, bei Gleichstand alphabetisch; `events` aufsteigend nach `jahr`, dann
alphabetisch nach `name`; `zahlen.jahre` = `len(jahre)`.

Quellen (nur lesend, keine Struktur ändern): `~/foto_sortierung/sortierplan.json`
(Schlüssel `trocken`, `anlaesse`, `ordner`, `zuege`, `zusammenfassung`, `stand`).
Ein Anlass-Eintrag hat u. a. `thema_quelle`, `jahr`, `kategorie`, `event`,
`event_quelle`, `thema`, `datum`, `dateien`.

## Teil A — Werkzeug `tools/foto_sortierung/foto_uebersicht.py` (Subagent A)

Neue Datei, Aufbau wie die Nachbarn (`foto_sortieren.py` als Vorbild: Modulkopf-
Docstring auf Deutsch mit „Warum“, reine Funktionen, CLI mit `--trocken`-Logik).

Pflichtfunktionen:

* `UEBERSICHT_VERSION = 1`
* `plan_laden(pfad: str) -> dict` — `json.load`, nur lesend.
* `uebersicht_bauen(plan: dict, *, stand: str | None = None) -> dict` — **reine**
  Funktion, keine Datei-/Netzzugriffe, kein `datetime.now()` ohne `stand`
  (für Tests injizierbar). Bei fehlendem/ungültigem `plan` deutsche
  `ValueError`-Meldung (kein stiller Rückfall).
* `uebersicht_laden(pfad: str) -> dict` — liest die **Übersichtsdatei**.
* `uebersicht_schreiben(pfad: str, daten: dict) -> str` — **atomar** (temp-Datei
  im Zielordner + `os.replace`), verweigert Ziele **im Repo** mit deutscher
  `ValueError`-Meldung; Rückgabe: geschriebener Pfad.
* `uebersicht_text(daten: dict) -> str` — deutsche Zusammenfassung (mehrzeilig),
  inkl. Stand, Anlässe, Events, Dateien, Jahre, Themen, Kategorien, Doppelungen,
  Zeilen ohne Datum.
* `haupt(argv) -> int` (CLI): `--plan`, `--ausgabe`, `--schreiben`; **ohne**
  `--schreiben` reiner Trockenlauf (nur Ausgabe auf der Konsole). Ziel im Repo
  → deutsche Meldung auf `stderr`, **Exit 2**.

Zählregeln (exakt so, mit Kommentar):

* `zahlen.zeilen`, `anlaesse`, `zuege`, `doppelung_*`, `ohne_thema`, `ohne_jahr`,
  `events_neu`, `events_wiederverwendet`, `ordner_neu`, `ordner_vorhanden` kommen
  aus `plan["zusammenfassung"]` (fehlender Wert → `0`, **nie** ein Absturz);
  `anlaesse` zusätzlich gegen `len(plan["anlaesse"])` geprüft (Abweichung → der
  echte Listenwert gewinnt, kein stiller Widerspruch).
* `events` = Anzahl **verschiedener** `(jahr, kategorie, event)`-Kombinationen.
* `dateien` je Jahr/Thema/Kategorie/Event = Summe der `dateien`-Felder der
  Anlässe dieser Gruppe.
* `jahre` = Anzahl verschiedener Jahre; `themen` = Anzahl verschiedener
  `thema`-Werte; `kategorien` = Anzahl verschiedener `kategorie`-Werte.
* `ohne_datum = max(0, zeilen - zuege - doppelung_uebersprungen)` **mit**
  Kommentar, dass das die Zeilen ohne Datum im Namen sind (N7: 9.430 − 7.616 −
  668 = **1.146**).

Tests A — `backend/tests/test_foto_uebersicht_werkzeug.py` (alles offline,
`tmp_path`, kein Netz, kein Bild):
**mindestens 30 Testfunktionen**, u. a.: reine Funktion ohne Dateizugriff;
leerer/minimaler Plan; fehlende `zusammenfassung`-Schlüssel → 0; ungültiger Plan
→ `ValueError`; Gruppen-Zählung (Jahre/Themen/Kategorien/Events, inkl.
Event-Wiederverwendung `events_wiederverwendet`); Sortierungen; `ohne_datum`
(Invariante 9.430/7.616/668 → 1.146); atomares Schreiben (temp-Datei weg,
Zielinhalt lesbar); Repo-Ziel verweigert (`ValueError`, Exit 2 über CLI);
idempotenter zweiter Lauf (gleiche Bytes bei gleichem `stand`); `uebersicht_text`
nennt alle Zahlen; **Quelltext-Prüfung**: keine Lösch-, Netz- oder
pCloud-Funktion im Modul (AST oder Textsuche, wie in den Nachbartests).
Doku A: `docs/changelog-2026-09-27-n11-uebersicht-datei.md`.

## Teil B — Endpunkt, Chat-Anschluss, Selbsttest (Subagent B)

### B1 Service `backend/app/services/foto_uebersicht.py`

* `def uebersicht_pfad() -> str` — Standard `~/foto_sortierung/fotos_uebersicht.json`,
  übersteuerbar per Umgebungsvariable `FOTO_UEBERSICHT_PFAD` (für Tests).
* `def uebersicht_laden(pfad: str | None = None) -> dict` — **wirft nie**;
  bei Fehler `{"existiert": False, "error": "…deutsch…"}`.
* `def status_block() -> dict` — **immer dieselben Schlüssel**:
  `{"quelle": str|None, "pfad": str|None, "existiert": bool, "stand": str|None,
   "anlaesse": int|None, "events": int|None, "dateien": int|None, "jahre": int|None,
   "error": str|None}`. „Quelle“ = **Dateiname ohne Verzeichnis** (`basename`).
* `def events_finden(jahr=None, kategorie=None, suche=None, limit: int = 25) -> list`
  — `suche` als Teilzeichenkette **ohne Groß/Klein-Unterschied** (Umlaute
  tolerieren: `ae/oe/ue` gegen `ä/ö/ü`), `kategorie` exakt ohne Groß/Klein;
  `jahr` exakt; `limit` auf 1…200 begrenzt; bei fehlender Datei leere Liste.
* `def text_antwort(jahr=None, kategorie=None, suche=None, limit: int = 25) -> str`
  — deutsche Notiz für die Chat-Anhängung; **leerer String**, wenn die Datei
  fehlt (der Chat bleibt dann still, statt zu raten). Nennt immer die Gesamtzahl
  aus der Datei und die gezeigten Treffer.

### B2 Router `backend/app/router/fotos.py` (neu)

`GET /api/fotos/uebersicht`, Query-Parameter `jahr: int | None`,
`kategorie: str | None`, `suche: str | None`, `limit: int = 25`.
Antwort **immer HTTP 200**, alle Felder immer vorhanden:
`{"ok": bool, "quelle": str|None, "stand": str|None, "zahlen": dict, "jahre": list,
  "themen": list, "kategorien": list, "events": list, "error": str|None}`.
Fehlt die Datei: `ok: false`, `error` mit deutlichem Text, Listen leer — **nie 500**.
Registrierung in `backend/app/main.py` mit
`app.include_router(fotos.router, dependencies=[Depends(auth.require_api_key)])`
+ Kommentarzeile im Stil der Nachbarn.

### B3 Chat-Anschluss `backend/app/router/chat.py`

Neue Funktion `_fotos_uebersicht_tool(frage: str) -> str` **nach** dem
Gesichts-Tool in die Werkzeugkette einhängen (Muster von
`_gesicht_suche_tool`, Zeilen ~1116 und ~377-379). **Enge Auslöseregel** (keine
Fehltreffer, sonst leerer String):
* mindestens ein Foto-Wort: `foto`, `fotos`, `bild`, `bilder`, `event`, `events`,
  `anlass`, `anlaesse`, `anlässe`, `urlaub`, `konzert`
* **und** ein Frage-/Listen-Wort: `wie viele`, `wieviele`, `wie oft`, `anzahl`,
  `wieviel`, `zeig`, `zeige`, `welche`, `liste`, `übersicht`, `uebersicht`,
  `gibts`, `gibt es`, `gab`
* Jahreszahl `20\d\d` wird als `jahr` erkannt, Wörter wie `urlaub`/`konzert`
  werden als `suche` übergeben.
Antwort ist die Notiz aus `foto_uebersicht.text_antwort(...)`; bei fehlender
Datei leer. **Kein** zusätzlicher LLM-Aufruf, kein Netz.

### B4 Selbsttest

* `backend/app/router/selbsttest.py`: neuer Block `_fotos_info()` (nutzt
  `foto_uebersicht.status_block()`), im Ergebnis-Dict unter `"fotos"` und in der
  Bauer-Schleife; jeder Fehler bleibt ein `error`-Text — **nie 500**.
* `frontend/app.js`: in `selbsttestText(daten)` eine Zeile ergänzen, im Stil der
  Nachbarblöcke: `✓ Fotos: <anlaesse> Anlässe · <events> Events · <dateien>
  Dateien · <jahre> Jahre (Stand <stand>, Quelle <quelle>)`; fehlende Datei →
  `✗ Fotos: <error>`; Teilangaben → `⚠`. Fehlende Felder dürfen **nicht** abstürzen.
* `frontend/index.html`: Cache-Bump für `app.js` — **vom Planer auf
  `?v=20260927B` gesetzt** (der vorherige Wert `20260927A` stammt aus Commit
  `6b08e67` und war älter als diese Änderung; Regel §5). Die Token-Prüfung in
  `frontend/tests/test_selbsttest.js` ist mitgezogen.
* `frontend/tests/test_selbsttest.js`: Prüfungen für den neuen Block ergänzen
  (vorhanden/fehlend/Teilangaben/`error`), bestehende Prüfungen bleiben gültig.

Tests B — `backend/tests/test_foto_uebersicht_endpunkt.py` (alles offline,
`tmp_path`, kein Netz): **mindestens 30 Testfunktionen**, u. a. Service lädt
Datei; fehlende Datei → `existiert False` + `error`, kein Wurf; `status_block`
hat **immer** alle Schlüssel; Filter (Jahr, Kategorie, Suche mit Umlaut-Toleranz,
`limit`-Grenzen); `text_antwort` leer ohne Datei; Endpunkt über `TestClient`
(HTTP 200 im Erfolgs- und Fehlerfall, `ok` wahr/falsch, Filter greifen);
Selbsttest-Block enthält `fotos`; Selbsttest-Fehlerfall → `error` statt Ausnahme;
**kein Netz** (Monkeypatch, der jeden Ausgeh-Versuch scheitern lässt);
**Quelltext-Prüfungen**: Router/Service ohne Lösch- und ohne pCloud-Aufrufe.
Doku B: `docs/changelog-2026-09-27-n11-uebersicht-endpunkt.md`.

## Prüfkriterium des Schritts (der Prüfer fährt es selbst)

1. `cd backend && .venv/Scripts/python -m pytest tests/ -q` → **Exit 0**, Anzahl
   **≥ Baseline 1503** (Planer-Lauf 27.09. 22:2x: `1503 passed, Exit 0`, 149,7 s —
   die Suite enthält auch die Dateien eines parallel arbeitenden zweiten Agenten),
   ohne Fehler.
2. `node --check frontend/app.js` und `node frontend/tests/test_selbsttest.js` → Exit 0.
3. Werkzeug auf den echten Plan angewandt **ohne Netz**: `fotos_uebersicht.json`
   entsteht außerhalb des Repos; die Zahlen stimmen mit
   `sortierplan.json`/`zusammenfassung` überein (Prüfer rechnet nach).
4. Endpunkt liefert im Test **ohne jeden Netzaufruf** HTTP 200; Selbsttest-Block
   nennt die **Quelle** der Daten.
