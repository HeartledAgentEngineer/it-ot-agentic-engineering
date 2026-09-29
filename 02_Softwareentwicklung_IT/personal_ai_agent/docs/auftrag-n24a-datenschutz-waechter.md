# Auftrag N24 Teil A — Datenschutz-/IT-Sicherheits-Wächter (Nachtlauf 29./30.09.2026)

> **Rolle:** Planer = Hauptagent. Ausführer = Hermes-Subagent (`deepseek-v4.1-flash`).
> Prüfer = frischer Kontext, **andere Modellfamilie** (`z-ai/glm-5.2`), prüft gegen
> diesen Auftrag und führt den Prüfbefehl selbst aus.
> **Codex ist gesperrt** (live gemessen: „You've hit your usage limit … try again
> at Oct 15th, 2026") → Bauweg über Subagenten.

## 0. Warum (gemessene Ausgangslage, Planer)

Der Plan-Schritt **N24** („Datenschutz-/IT-Sicherheits-Prüfung: App, Android,
Verschlüsselung, Widerruf") ist bisher **nur geplant, nie gebaut**. Beim Nachsehen
wurden drei belegte Widersprüche gefunden:

| # | Fund | Beleg (Datei:Zeile) |
|---|---|---|
| F1 | `backend/app/main.py:329-334` erklärt als **eigentlichen** Schutz „`HOST_BIND=127.0.0.1` in der .env (nur lokal erreichbar)" — aber **zwei Startskripte binden hart auf `0.0.0.0`** und lesen `HOST_BIND` überhaupt nicht | `termux/agent-ensure.sh:76`, `start-termux.sh:353` |
| F2 | Nur ein Skript liest `HOST_BIND` (Muster ist also vorhanden und erprobt) | `termux/neu-start-nach-lauf.sh:69-75` |
| F3 | In `backend/.env` stehen **weder** `HOST_BIND` **noch** `API_KEY` (nur die Namen geprüft, nie Werte) — damit greift der Key-Schutz der `/api`-Routen gar nicht, und der Server lauscht auf allen Schnittstellen | gemessen: `grep -o '^HOST_BIND='` / `'^API_KEY='` → beide leer |
| F4 | Der Key selbst wird offen ausgeliefert — **gewollt**, damit das Frontend ihn holen kann, aber nur bei Loopback-Bindung unschädlich | `main.py:324-341` |
| F5 | 85 `/api`-Routen, **5** ohne Key-Schutz: `auth/token`, `auth/check`, `health`, `hello`, `konfig`. Nur `health` und `auth` sind als Ausnahme dokumentiert (`main.py:166-167`) — `hello` und `konfig` sind **undokumentiert offen** (eigene Messung des Planers über `app.routes`) | Sonde des Planers |
| F6 | `CORS allow_origins=["*"]` + `--reload` im Startbefehl des Handys | `main.py:155-162`, `agent-ensure.sh:76` |

**Kein bestehender Wächter-Test deckt eine dieser Regeln ab** (`ls backend/tests |
grep -i -E "sicher|datenschutz|security|privacy|waechter"` → **0 Treffer**). Genau
das ist die Lücke: die Regeln stehen in Prosa, niemand prüft sie maschinell.

## 1. Auftrag Teil 1 — die eine Änderung am Code (klein, rücknehmbar)

**`HOST_BIND` wirksam machen** — die dokumentierte Sicherung existiert, greift
aber nicht:

1. `termux/agent-ensure.sh` und `start-termux.sh`: vor dem uvicorn-Aufruf
   `HOST_BIND` aus `backend/.env` lesen, **genau mit dem vorhandenen Muster** aus
   `termux/neu-start-nach-lauf.sh:69-71` (`grep -E "^HOST_BIND=" .env | tail -1 |
   cut -d= -f2- | cut -d'#' -f1 | tr -d '[:space:]\r"'`), Standardwert bleibt
   **`0.0.0.0`** — **keine Verhaltensänderung**, solange `HOST_BIND` nicht gesetzt
   ist. Aufruf dann mit `--host "$HOST_BIND"`.
2. `termux/neu-start-nach-lauf.sh`: Standardwert auf `0.0.0.0` **belassen** (das
   Skript verhält sich schon so) — nur die Zeile im Kommentar/Log, die den
   Standard nennt, angleichen, falls sie fehlt. Kein Umbau.
3. `backend/app/config.py`: **reine Funktion** (testbar, kein Netz, kein IO):
   `bindung_hinweis(host: str, hat_api_key: bool) -> Optional[str]` — gibt einen
   deutschen Warnsatz zurück, wenn `host` **nicht** Loopback ist und **kein**
   API-Key gesetzt ist; sonst `None`. Loopback = `127.0.0.1`, `::1`, `localhost`
   (auch `127.0.0.x`). Beispielsatz: „Server lauscht auf <host> ohne API-Key —
   im gleichen Netz kann jeder den Archiv-Index lesen. Schutz: HOST_BIND=127.0.0.1
   und API_KEY in backend/.env setzen."
4. `backend/app/main.py`: beim Start `logger.warning(hinweis)`, wenn die Funktion
   etwas liefert; `/api/health` bekommt das Feld **`bindung_warnung`** (Text oder
   `null`) — `health` ist ohnehin offen, der Text enthält **kein** Geheimnis,
   **keinen** Key-Wert, **keine** IP des Geräts.
   **Regel:** `/api/health` und `/api/konfig` bleiben inhaltlich sonst unverändert,
   alle anderen Antwortfelder unverändert.

**Verboten:** die Bindung umstellen (`127.0.0.1` erzwingen) — die Entscheidung
darüber trifft Sebastian über die `.env`; jeder Umbau von `/api/konfig`, der das
Frontend den Key nicht mehr holen lässt; Netz-Aufrufe in Tests.

## 2. Auftrag Teil 2 — die Wächter-Tests (der eigentliche Wert)

Neu: `backend/tests/test_datenschutz_waechter.py`, **alles offline**, keine
persönlichen Daten, keine echten Namen/Nummern/Orte, **mindestens 35
Testfunktionen**. Geprüft werden **Regeln des Repos**, nicht Verhalten des Netzes:

1. **Lebende Ausnahmeliste:** über `app.routes` (nur `APIRoute`) alle Pfade mit
   Präfix `/api` sammeln; Routen **ohne** `require_api_key` müssen **genau**
   `{/api/auth/token, /api/auth/check, /api/health, /api/hello, /api/konfig}`
   sein. Eine **neue** offene Route lässt den Test rot werden (das ist gewollt).
   Dazu: Gesamtzahl der `/api`-Routen ist > 50 und jede der Ausnahmen ist
   tatsächlich vorhanden (keine Liste, die ins Leere zeigt).
2. **Startskripte:** in `start-termux.sh`, `termux/agent-ensure.sh`,
   `termux/neu-start-nach-lauf.sh` darf **kein** hart codiertes
   `--host 0.0.0.0` mehr stehen; jedes der drei Skripte muss `HOST_BIND`
   erwähnen und `--host` mit einer **Variablen** aufrufen.
3. **`bindung_hinweis`:** Loopback-Varianten (`127.0.0.1`, `127.0.0.5`, `::1`,
   `localhost`, Groß-/Kleinschreibung) → `None`; `0.0.0.0` **ohne** Key → Text;
   `0.0.0.0` **mit** Key → `None`; eine LAN-Adresse ohne Key → Text; der Text
   nennt `HOST_BIND` und `API_KEY`, ist deutsch und enthält **keinen** Key-Wert.
4. **Frontend ohne Fremde:** in `frontend/*.html|js|css` (Tests ausgenommen) kommt
   **keine** fremde Adresse vor — erlaubt sind `localhost`, `127.0.0.1` und die
   dokumentierte Beispiel-Adresse aus `app.js` (Zeile mit `api_base`); kein
   `cdn.`, `gstatic`, `googleapis`, `unsplash`, kein `sk-or-`.
5. **`.env` geschützt:** `.gitignore` enthält eine `.env`-Zeile; `backend/.env`
   ist per `git check-ignore` ignoriert und **nicht** in `git ls-files`.
6. **Löschregel:** `deletefile|deletefolder` kommt in `tools/` **nur** in
   `tools/pcloud/pcloud_duplikate_loeschen.py` vor; in `backend/app/` **gar nicht**
   (`__pycache__` ausgenommen). Damit ist „nie löschen außer beweisbaren
   Duplikaten" maschinell verankert.
7. **Medien ohne Zwischenspeicher:** `Cache-Control: no-store` steht im Quelltext
   von `router/fotos.py`, `router/cloud.py`, `router/speak.py` bzw. der
   Bildauslieferung in `main.py` (Fundstelle zulässig: `main.py` `NoCache…`).
8. **Wächter über sich selbst:** die Testdatei enthält **keine** Netz-Aufrufe
   (`requests.`, `urlopen`, `httpx`, `socket.`) und liest `backend/.env` **nicht**
   (kein Wert kann in Ausgaben geraten).

Jede Testfunktion prüft eine benannte Regel; bei Verletzung nennt die Meldung die
Regel und die Datei, **keinen** Inhalt aus `.env`.

## 3. Auftrag Teil 3 — Doku (folgt dem Code, keine Behauptung ohne Beleg)

1. Neu `docs/changelog-2026-09-29-n24a-datenschutz-waechter.md`: die Funde F1–F6
   mit Datei:Zeile, was gebaut wurde, **welche Entscheidung offen bleibt**
   (nämlich: `HOST_BIND`/`API_KEY` in `backend/.env` setzen — Sebastians Griff,
   zwei Zeilen), Prüfbefehl mit Zahl, Prüfer-Befund.
2. `CLAUDE.md` (Projekt): die Zeile „Backend läuft NUR lokal
   (localhost/127.0.0.1) – kein öffentlicher Port" ist **nicht mehr codegenau** —
   sie wird auf den echten Stand gezogen: Bindung kommt aus `HOST_BIND`
   (Standard `0.0.0.0`), Skripte lesen sie jetzt, Warnung im Log und in
   `/api/health`, wenn ohne API-Key auf allen Schnittstellen gelauscht wird.
   Dazu eine Protokollzeile im Änderungsprotokoll (Datum 29.09.2026).
3. Der Ausführer **committet nicht** und ruft **kein** git auf.

## 4. Prüfkriterium (das Tor)

```bash
cd backend && .venv/Scripts/python -m pytest tests/ -q     # Exit 0, Baseline 3058 (+28 N23)
bash -n start-termux.sh termux/agent-ensure.sh termux/neu-start-nach-lauf.sh   # Exit 0
```
Erwartung: **Baseline + die neuen Testfunktionen**, alles grün, `1 skipped` bleibt
(der übersprungene Test ist Bestand). Der Prüfer führt beide Befehle **selbst**
aus und meldet „bestanden" oder die Abweichungen mit Beweis.

## 5. Grenzen (hart)

* Keine persönlichen Daten, keine Namen/Nummern/Orte, kein Foto, kein Chat-Archiv,
  keine `.env`-Werte in Dateien, Ausgaben oder Commit-Texten.
* Kein Netz-Aufruf in den Tests, kein pCloud-Aufruf, keine Löschfunktion.
* Keine Änderung an `/api/konfig`-Semantik, keine erzwungene Loopback-Bindung.
* Nichts außerhalb des Repos schreiben; `N8` (echtes Sortieren) bleibt gesperrt.
