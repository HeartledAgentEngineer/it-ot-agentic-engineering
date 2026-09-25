# Changelog 25.09.2026 — Selbsttest: Zustand des Systems ohne Kabel ablesbar

## Warum

Das Backend läuft auf Sebastians Android-Handy in Termux, die Oberfläche ist eine
installierte Web-App. **Unterwegs hat er kein Kabel (kein ADB)** und kann nicht in die
Termux-Konsole sehen — er sieht nur, was die App selbst anzeigt. Bisher gab es dafür
**keinen Ort**: Commit-Stand, Archiv-Index, Inbox-Daemon, letzte Protokollzeilen,
Erinnerungen, Sprachmodelle und Serverzeit waren nur über die Konsole prüfbar.

Der Selbsttest macht den Systemzustand in der App ablesbar — als Klartext-Zeilen mit
✓/⚠/✗, damit er sich als **Bildschirmfoto per Telegram** teilen lässt.

Zusätzlich war der Auslöser die gemeldete Auffälligkeit, dass **Zeitstempel vor dem
Text** erschienen. Der Selbsttest liefert dafür die aktuelle **Serverzeit** mit, sodass
sich Vergleiche nachvollziehbar machen lassen.

## Was

### 1. Backend: `GET /api/selbsttest`

**Neu:** `backend/app/router/selbsttest.py` (APIRouter, Präfix `/api`, Tag `selbsttest`),
registriert in `backend/app/main.py` **mit demselben API-Key-Schutz wie alle `/api`-Routen**.

Antwort-JSON — **jedes Feld ist immer vorhanden**; fehlt eine Quelle, trägt das Feld einen
`error`-Text. **Nie ein 500er** (jeder Block hat sein eigenes try/except mit Logging):

| Feld | Inhalt |
|---|---|
| `commit` | `ok`, `zeile` (letzter Commit), `error` — aus `git log --oneline -1` im Repo (`subprocess`, abgesichert) |
| `index` | `pfad` (`~/archiv_index.db`), `existiert`, `groesse_mb`, `nachrichten`, `chunks`, `error` — SQLite **nur mit `mode=ro`** geöffnet, COUNT auf `nachrichten`/`chunks` |
| `daemon` | `laeuft` (True/False/**null = nicht feststellbar**), `log_pfad`, `log_groesse_bytes`, `log_alter_s`, `log_letzte_zeilen` (letzte 3), `error` — Prozess erkennbar über `pgrep -f hermes_inbox_daemon.py`, sonst `/proc/*/cmdline` |
| `letzte_antwort` | `antworten` und `status` — je `pfad`, `existiert`, `zeilen`, `laenge`, `auszug`, `error` aus `~/hermes_inbox/antworten.jsonl` / `status.jsonl` |
| `gedaechtnis` | `anzahl` (derselbe Zählweg wie `/api/memory/count`), `error` |
| `sprache` | `modelle` (die Kette aus `TRANSCRIBE_MODELS`), `transcribe_registriert`, `speak_registriert` (gegen die echten Routen geprüft), `error` |
| `uhrzeit` | `iso`, `lokal`, `zeitzone` — aktuelle Serverzeit |

Sicherheit:

* **Auszüge bewusst gekürzt** auf **200 Zeichen** (`AUSZUG_LAENGE`) — ein Screenshot soll
  lesbar bleiben; `laenge` nennt die volle Länge der Zeile.
* **Keine Geheimnisse** im JSON: nur Modell-Namen, Pfade, Größen, Zähler und gekürzte
  Logzeilen — nie ein API-Key, nie ein Token.
* **Nur lesend**: Der Archiv-Index wird mit `mode=ro` geöffnet, nichts wird geschrieben.
* Kein Netz-Aufruf, kein externer Anbieter.
* Der Endpunkt ist **synchron** (`def`), damit SQLite/`git`/`pgrep` nicht den Event-Loop
  und damit laufende Chat-Streams aufhalten.

### 2. Frontend: Blatt „Selbsttest“ (Kopfzeilen-Knopf)

* `frontend/index.html`: Knopf `#selbsttest-btn` in der Kopfzeile (neben dem Zahnrad) und
  Blatt `#selbsttest-sheet` mit `#selbsttest-text`, Knopf **„Aktualisieren“** und `#selbsttest-hint`.
  Aufbau wie die bestehenden Blätter (`.sheet-panel`, `.sheet-head`, `.sheet-list`, `.sheet-note`).
* `frontend/app.js`:
  * **`selbsttestText(daten) -> string`** — **reine Funktion** (kein DOM, kein Zustand),
    wandelt das JSON in deutsche Klartext-Zeilen mit ✓/⚠/✗. Sie ist damit ohne Browser
    testbar und wirft auch bei fehlenden Feldern nicht.
  * `ladeSelbsttest()` holt `GET /api/selbsttest`, `zeigeSelbsttest()` schreibt per
    **`textContent`** (kein `innerHTML` → keine Injektion).
  * Öffnen über den Kopfzeilen-Knopf, Schließen über ×, Hintergrund oder **Esc**.
  * **Reine Anzeige, kein Auto-Polling** — geladen wird beim Öffnen und nur auf Knopfdruck.
  * Fehlschlag wird ehrlich gemeldet („✗ Selbsttest nicht abrufbar“), nicht leer gelassen.
* `frontend/style.css`: `#selbsttest-sheet` in die gemeinsamen Blatt-Selektoren aufgenommen,
  dazu `.sheet-refresh` (Aktualisieren-Knopf) und `.selbsttest-text` (Monospace, Umbruch).
* **Cache-Bump:** `app.js?v=20260925F`, `style.css?v=20260925E`.

### 3. Tests

* **`backend/tests/test_selbsttest.py` — 21 Tests** (echtes HTTP gegen die echte App, Pfade
  auf `tmp_path` umgebogen, kein Netz-Call, eine Stolperfalle lässt jeden echten
  LLM-Zugriff auffliegen): Route + Key-Schutz, alle Felder vorhanden, fehlende Dateien →
  `error`-Text statt 500, `git`-Ausfall, Auszug-Grenze **≤ 200 Zeichen bei voller Länge**,
  echte SQLite-Zähler, Datei ohne Tabellen, Daemon-Log (Größe/Alter/letzte 3 Zeilen),
  Daemon unklar = `null`, Gedächtnis-Zahl und -Fehler, Sprachkette + registrierte Wege,
  Serverzeit, **kein Schlüssel im JSON**, Feldsatz exakt.
* **`frontend/tests/test_selbsttest.js` — 39 Prüfungen** (rein, ohne DOM): schneidet
  `selbsttestText` aus dem echten `app.js` und führt sie aus — vollständige Daten, leeres
  Objekt/`null`/Text als Eingabe, ⚠-Warnzeichen (Daemon aus, Zählfehler), ✗-Fälle
  (fehlende Dateien, Zählfehler im Gedächtnis, nicht registrierter Sprachweg), kein `NaN`
  und kein `undefined`, Blatt-Verdrahtung, **kein Auto-Polling**, Cache-Bump, kein CDN,
  kein Schlüssel.

## Prüfbefehle und Ergebnisse

```
cd backend && .venv/Scripts/python -m pytest tests/test_selbsttest.py -q
→ 21 passed, Exit 0 (4,69 s)

cd backend && .venv/Scripts/python -m pytest tests/ -q
→ 388 passed, Exit 0   (vor der Änderung, Baseline)
→ 422 passed, Exit 0   (nach der Änderung, 95,8 s)

cd frontend && node --check app.js
→ OK (Exit 0)

cd frontend && for t in tests/*.js; do node "$t" app.js; done
→ alle 14 Testdateien Exit 0, darunter test_selbsttest.js „alle Prüfungen grün"
```

Der Anstieg **388 → 422** sind **+21 Tests aus dieser Änderung**; die restlichen
**+13** stammen aus einem parallel laufenden Arbeitsstrang im selben Arbeitsverzeichnis
(`tests/test_daemon_ausgabe.py` erweitert, neu `tests/test_verlauf_persistenz_daemon.py`,
10 Tests) — nicht aus dieser Änderung.

## Was NICHT geprüft werden konnte / offen bleibt

* **Auf dem Gerät ist der Selbsttest nicht erprobt.** Auf dem PC existieren
  `~/archiv_index.db` und `~/hermes_inbox/` nicht, und `pgrep` gibt es unter Windows nicht —
  dort meldet der Endpunkt ehrlich `error`-Texte bzw. `laeuft: null`. Ob Daemon-Erkennung,
  SQLite-Zähler und Log-Auszüge auf **Termux/Android** wie erwartet greifen, zeigt erst der
  Blick in der App auf dem Handy.
* Der Bildschirmfoto-Fall (Teilen per Telegram) ist reine Anzeige — die Darstellung ist nur
  quelltext-nah geprüft (Klassen/Umbruch), nicht optisch am Gerät.
* Die Zeitstempel-Frage selbst ist damit **nicht behoben**, nur **prüfbar gemacht**
  (Serverzeit steht im Selbsttest).
