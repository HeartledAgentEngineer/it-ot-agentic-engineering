# Changelog 2026-09-15 — Coding-Stream live + kein 900s-Abbruch + Coding-Modell

**Anlass (Rückmeldung Sebastian):** „Der Stream im Chat funktioniert noch nicht
richtig: es fängt gut an, streamt nach und nach, dann hört es irgendwann auf und
ich sehe erst nach dem Neuladen wieder etwas — am Ende ein *Timeout nach 900
Sekunden: keine Antwort der aktiven Session*. Außerdem sollen die intern
aufgemachten Hermes-Sessions mit **DeepSeek V4.1 Flash** laufen."

## Symptom → Ursache (3 getrennte Fehler)

### 1. Stream verstummt mitten im Lauf → erst nach F5 wieder etwas
`backend/app/services/sse.py` (`strom_auftrag_live`, die Strecke für
`conv_code`) merkte sich mit einem **absoluten Zähler** (`gesehen = n`), wie
viele Zwischenmeldungen schon gesendet waren, und las `meldungen[n:]`.
`auftrag_service.statusmeldung_hinzufuegen` **kappt** die Liste
(`status_meldungen[-20:]`). Sobals 20 Meldungen erreicht waren, lief der
Zähler dauerhaft **leer**: Der Stream blieb offen, sendete aber nichts mehr,
während Hermes weiterarbeitete → im Frontend „es hat aufgehört", neue Gedanken
erst nach dem Neuladen (über den Verlauf/Status-Poll).

**Fix:** Anschluss über den **Überlapp** der zuletzt gesendeten Einträge statt
über einen Zähler (verträgt Kappung und Längenänderungen). Zusätzlich hält das
Auftragsbuch jetzt **200** statt 20 Zwischenmeldungen.

### 2. „Timeout nach 900s: keine Antwort der aktiven Session"
- `hermes_local.DEFAULT_TIMEOUT`/`stream_auftrag_aktiv` brach den Auftrag nach
  **900 s Gesamtzeit** als `fehler` ab — Coding-Läufe dauern aber länger.
- Der Inbox-Daemon (`hermes_inbox_daemon.py`) las `proc.stdout` in einer
  **direkten for-Schleife**; `proc.wait(timeout=900)` griff erst NACH dem
  Dateiende. Ein hängender Hermes-Lauf blockierte den Daemon dadurch
  **unbegrenzt** (auch alle Folge-Aufträge, der Daemon ist single-threaded).

**Fix:**
- Gesamtbudget aus den Settings: `HERMES_AUFTRAG_TIMEOUT` (Standard **3600 s**).
- Ruhebudget: `HERMES_AUFTRAG_IDLE` (Standard **420 s**) — überschritten kommt
  ein ehrlicher Hinweis „⏳ Seit Ns keine neue Zwischenmeldung — der Auftrag
  läuft weiter (kein Abbruch)", **ohne** Abbruch.
- Jede neue Meldung setzt die Ruhe-Uhr zurück.
- Der Daemon liest in einem **eigenen Thread** (Queue) und beendet den Lauf
  nach dem Gesamtbudget wirklich (`proc.kill()`) und schreibt
  `[Timeout nach Ns] …` als Antwort.

### 3. „Mehrere Nachrichten parallel gestreamt"
Der Daemon schrieb **jede einzelne Ausgabezeile** als eigene Statusmeldung;
im Frontend tippte jede neue Blase **sofort gleichzeitig** los (Typewriter pro
Blase parallel).

**Fix:**
- Daemon **bündelt** Zeilen (Takt ~1,2 s bzw. ab 6 Zeilen) → eine
  zusammenhängende Blase statt vieler Einzelblasen.
- Frontend tippt die Blasen **seriell** über eine Promise-Kette
  (`_gedankenTippKette`); bei Rückstand (>2 wartende Blasen) wird ohne
  Tipp-Animation direkt gesetzt.

### 4. Stream-Abriss erforderte ein Neuladen
Riss die Browser-Verbindung (Android/Doze, Netz), setzte die Fehlerbehandlung
`_laufenderAuftragKurz = null` → der Status-Poll hörte auf, nichts kam mehr an.

**Fix (`frontend/app.js`):** Bricht der Stream ab, während noch ein Auftrag
läuft, wird er **nicht** als Fehler behandelt und **nicht** neu gesendet
(kein Doppel-Auftrag), sondern per `starteAuftragResumePoll()` weiterverfolgt:
neue Zwischengedanken als Blasen, beim Status `fertig`/`fehler` wird das
Ergebnis in einer frischen Blase angezeigt. Der Status-Poll
(`pollHermesLetzte`) läuft jetzt für **jeden** Chat, wenn ein Auftrag offen ist
(vorher nur `conv_code`).

## Coding-Modell (DeepSeek V4.1 Flash)
Neue Einstellung `hermes_local_model` (Standard `deepseek/deepseek-v4.1-flash`,
`.env`-Schlüssel `HERMES_LOCAL_MODEL`). Sie geht an **alle** lokal gestarteten
Hermes-Läufe:
- Inbox-Daemon (`hermes chat -m <modell> -q …`),
- tmux-Session (`sichere_persistente_tmux_session`, `LocalHermesJob.starten`),
- `query`-Zweitweg (`stream_auftrag_query`).
Der Server reicht Modell + Zeitbudgets beim Selbstheilen des Daemons per
Umgebung durch (`sicherstelle_inbox_daemon`) — eine Quelle: die Settings.

## Aufräumen
- Technische CLI-Zeile `session_id: …` (`-Q`-Abschluss) wird verworfen, sie
  landete vorher im Ergebnis-Text.
- Neues Skript `termux/neu-start-nach-lauf.sh`: startet Server + Inbox-Daemon
  **erst nach dem Ende eines laufenden Hermes-Auftrags** neu (beide Prozesse
  laden Code ohne `--reload`; ein Neustart mitten im Lauf hätte die laufende
  Antwort verworfen). Log: `termux/neu-start-nach-lauf.log`.

## Verifikation (Befehle + Ausgabe)
```bash
# 1) Syntax/Parse
node --check frontend/app.js                     # JS_OK
python -m py_compile backend/hermes_inbox_daemon.py \
  backend/app/services/hermes_local.py backend/app/config.py   # PYCOMPILE_OK

# 2) Tests der Live-Strecke (Kappung darf den Strom nicht abwürgen)
python -m pytest backend/tests/test_sse_live_strom.py -q       # 4 passed

# 3) Daemon isoliert (eigene Inbox): Modell, Bündelung, Antwort
HERMES_INBOX_DIR=$TMPDIR/htest python backend/hermes_inbox_daemon.py --einmal
#   [daemon] start … modell=deepseek/deepseek-v4.1-flash timeout=3600s
#   [daemon] beantwortet test-koa: PONG      → RC=0
#   status.jsonl: "💬 session_id…\n💬 PONG"-gebündelt (2 Zeilen in EINER Blase)

# 4) Watchdog: Gesamtbudget greift wirklich
HERMES_INBOX_DIR=$TMPDIR/htest2 HERMES_AUFTRAG_TIMEOUT=12 \
  python backend/hermes_inbox_daemon.py --einmal
#   → antworten.jsonl: "[Timeout nach 12s] Der Hermes-Lauf wurde beendet."

# 5) Voller Testlauf
python -m pytest backend/tests -q   # 175 passed, 6 failed
```
Die 6 Fehlschläge liegen in **unveränderten** Modulen und hängen an echten
Gerätedaten (`test_datei_suche` findet reale Dateien unter `/sdcard`,
`test_kontext_delegation` liest den echten Chat-Verlauf) — sie sind
vorbestehend, nicht Folge dieser Änderung.

## Betroffene Dateien
- `backend/app/services/sse.py`, `backend/app/services/auftrag_service.py`
- `backend/app/services/hermes_local.py`, `backend/app/config.py`
- `backend/hermes_inbox_daemon.py`
- `frontend/app.js`, `frontend/index.html` (Cache-Bust `v=20260915bZ`)
- `backend/tests/test_sse_live_strom.py` (neu)
- `termux/neu-start-nach-lauf.sh` (neu)
