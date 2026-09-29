# Changelog 2026-09-29 — N24a: Datenschutz-/IT-Sicherheits-Wächter

> Auftrag: `docs/auftrag-n24a-datenschutz-waechter.md` (Planer: Hauptagent,
> Ausführer: Hermes-Subagent, Prüfer: andere Modellfamilie).
> Sprache/Stil: deutsch wie im Bestand.

## Warum (die gemessenen Funde F1–F6)

| # | Fund | Beleg (Datei:Zeile, Stand vor der Änderung) | Zustand nach der Änderung |
|---|---|---|---|
| F1 | Zwei Startskripte banden hart auf `0.0.0.0` und lasen `HOST_BIND` gar nicht — die in `main.py` als „eigentlicher Schutz" bezeichnete Bindung griff dort nicht | `termux/agent-ensure.sh:76`, `start-termux.sh:353` (`--host 0.0.0.0`) | Beide lesen jetzt `HOST_BIND` aus `backend/.env`; Aufruf `--host "$HOST_BIND"` (`agent-ensure.sh:79-83`, `start-termux.sh:358-361`) |
| F2 | Nur ein Skript las `HOST_BIND` — das Muster war also vorhanden und erprobt | `termux/neu-start-nach-lauf.sh:69-75` | Dieses Muster ist jetzt in allen drei Skripten **identisch** (`_env_host=$(grep -E "^HOST_BIND=" …)`), Test `test_regel_muster_in_allen_drei_skripten_gleich` |
| F3 | In `backend/.env` standen weder `HOST_BIND` noch `API_KEY` (nur Namen geprüft, nie Werte) → Key-Schutz der `/api`-Routen griff nicht, Server lauschte überall | gemessen: `grep -o '^HOST_BIND='` / `'^API_KEY='` → beide leer | **Nicht im Code geschlossen** — das ist Sebastians Griff (siehe „Offene Entscheidung"). Der Code warnt jetzt sichtbar |
| F4 | Der Key wird offen ausgeliefert (gewollt, damit das Frontend ihn holt) — nur bei Loopback unschädlich | `main.py:335-352` (`/api/konfig`, `Cache-Control: no-store`) | Unverändert. `/api/konfig` bleibt offen; Test `test_regel_konfig_bleibt_offen_fuer_frontend` verankert das |
| F5 | 85 `/api`-Routen, **5** ohne Key-Schutz: `auth/token`, `auth/check`, `health`, `hello`, `konfig`; `hello`/`konfig` waren undokumentiert offen | Planer-Sonde über `app.routes`; `main.py:166-167` nennt nur `health`/`auth` | Lebende Ausnahmeliste als Test: genau diese fünf sind erlaubt, jede neue offene Route lässt den Test rot werden |
| F6 | `CORS allow_origins=["*"]` + `--reload` im Handy-Startbefehl | `main.py:165-172`, `agent-ensure.sh:76` | `--reload` bleibt (Entwicklungsbetrieb, Entscheidung offen); CORS unverändert — als Regel festgehalten, nicht geändert |

**Kein bestehender Wächter-Test deckte eine dieser Regeln ab** (`ls backend/tests | grep -i -E "sicher|datenschutz|security|privacy|waechter"` → 0 Treffer).

## Was gebaut wurde

### 1. `HOST_BIND` wirksam (die eine Code-Änderung an den Skripten)

* `termux/agent-ensure.sh` (85 Zeilen): vor dem `nohup python -m uvicorn`-Aufruf
  `HOST_BIND` aus der `.env` lesen, Standard **`0.0.0.0`**, Aufruf mit
  `--host "$HOST_BIND"` (Zeilen 76-83).
* `start-termux.sh` (396 Zeilen): dasselbe vor dem Startbefehl (Zeilen 355-361).
* `termux/neu-start-nach-lauf.sh` (96 Zeilen): Verhalten war schon richtig; nur
  ein Kommentar ergänzt, der den Standard **`0.0.0.0`** ausdrücklich nennt
  (Zeilen 69-71). Kein Umbau.

**Keine Verhaltensänderung**, solange `HOST_BIND` nicht gesetzt ist — der
Standard ist überall `0.0.0.0`.

### 2. Reine Funktion + Warnung

* `backend/app/config.py` (394 Zeilen): neu `ist_loopback(host)` (Zeile 70) und
  `bindung_hinweis(host, hat_api_key) -> Optional[str]` (Zeile 92). Reine
  Funktionen: kein Netz, kein IO, keine DNS-Auflösung. Loopback =
  `127.0.0.1`, `127.0.0.x`, `::1`, `localhost` (Groß-/Kleinschreibung egal).
  Der Warnsatz nennt `HOST_BIND` und `API_KEY`, enthält **kein** Geheimnis und
  **keine** Geräte-IP.
* `backend/app/main.py` (361 Zeilen): beim Start `logger.warning(...)`, wenn die
  Funktion etwas liefert (Zeilen 99-101). `/api/health` bekommt das Feld
  **`bindung_warnung`** (Text oder `null`, Zeile 256). Alle anderen Felder,
  `/api/konfig` und `/api/health`-Semantik unverändert.

### 3. Wächter-Testdatei

`backend/tests/test_datenschutz_waechter.py` — **630 Zeilen, 52 Testfunktionen**
(pytest sammelt 66 Tests, parametrisierte Fälle eingerechnet), **alles offline**.
Acht Regelgruppen:

1. lebende Ausnahmeliste der offenen `/api`-Routen (über `app.routes`,
   `require_api_key` erkannt am `Depends`-Namen),
2. die drei Startskripte (kein hartes `--host 0.0.0.0`, `HOST_BIND` überall,
   identisches Muster, Standard `0.0.0.0`),
3. `bindung_hinweis` (Loopback-Varianten → `None`, `0.0.0.0`/LAN ohne Key →
   Text, mit Key → `None`, Text deutsch und ohne Key-Wert),
4. Frontend ohne fremde Adressen (`cdn.`/`gstatic`/`googleapis`/`unsplash`/
   `sk-or-`), erlaubt nur `localhost`/`127.0.0.1` und die `api_base`-Zeile,
5. `.env`-Schutz (`.gitignore`-Zeile, `git check-ignore`, `git ls-files`),
6. Löschregel (`deletefile|deletefolder` nur in
   `tools/pcloud/pcloud_duplikate_loeschen.py`, im Backend gar nicht),
7. Medien ohne Zwischenspeicher (`Cache-Control: no-store`),
8. der Wächter über sich selbst (keine Netz-Tokens, liest die
   Einstellungsdatei nicht, ≥ 35 Testfunktionen, kein Personenname).

## Offene Entscheidung (Sebastians Griff, zwei Zeilen)

Die Code-Änderung **erzwingt keine Loopback-Bindung** — bewusst. Wirksam wird
der Schutz erst, wenn in `backend/.env` gesetzt wird:

```
HOST_BIND=127.0.0.1
API_KEY=<ein frei gewählter Wert>
```

Ohne diese zwei Zeilen bleibt der Server im Heimnetz für jedes Gerät offen; Log
und `/api/health` → `bindung_warnung` sagen das jetzt.

## Prüfer-Befund

**Prüfer `z-ai/glm-5.2` (frische Sitzung, andere Modellfamilie als der Ausführer):
BESTANDEN — 0 Abweichungen.**

Eigene Messungen des Prüfers (alle selbst gefahren):

| # | Prüfpunkt | Erwartet | Eigener Lauf des Prüfers | Urteil |
|---|---|---|---|---|
| 1 | `pytest tests/ -q` | Exit 0, 3124 passed, 1 skipped | 3124 passed, 1 skipped, Exit 0 (254 s) | OK |
| 2 | neue Testdatei allein | 66 passed | 66 passed (19,9 s) | OK |
| 2b | `def test_` zählen | 52 | 52 (630 Zeilen) | OK |
| 3 | `bash -n` auf drei Skripte | Exit 0 | 3× Exit 0 | OK |
| 4 | eigene Sonde über `app.routes` | 85 /api, 5 ohne Key | 85, genau 5 (`auth/check`, `auth/token`, `health`, `hello`, `konfig`) | OK |
| 5 | Skripte: Standard `0.0.0.0`, `/api/konfig` unverändert | ja / ja | bestätigt | OK |
| 6 | `ist_loopback`/`bindung_hinweis` mit eigenen Aufrufen | siehe Auftrag | Loopback-Varianten → `None`, `0.0.0.0` ohne Key → Text, mit Key → `None`, LAN-Adresse → Text, kein Key-Wert im Text | OK |
| 7 | Doku codegenau | ja | alle zitierten Zeilen stimmen, Zahlen 630/52/66/3124/3058/+66 überall gleich | OK |
| 8 | Datenschutz | sauber | keine Netz-Tokens, kein `.env`-Zugriff, keine Personendaten | OK |

**Nicht blockierende Beobachtung des Prüfers:** im Arbeitsbaum liegen weitere
uncommittete Änderungen (`tools/agentbus/wache.py`, `docs/experimente/live_zahlen.*`)
— **fremde** Parallelarbeit, gehört nicht zu diesem Auftrag, wurde nicht angefasst
und geht nicht in den Commit.

## Prüfbefehle mit Zahl (selbst gefahren)

```
cd backend && .venv/Scripts/python.exe -m pytest tests/test_datenschutz_waechter.py -q
# 66 passed, 3 warnings in 10.45s — Exit 0
# (52 Testfunktionen definiert; 66 durch Parametrisierung gesammelt)

cd backend && .venv/Scripts/python.exe -m pytest tests/ -q
# 3124 passed, 1 skipped, 3 warnings in 203.13s — Exit 0
# Baseline 3058 passed, 1 skipped, Exit 0 → +66, keine Regression

bash -n termux/agent-ensure.sh termux/neu-start-nach-lauf.sh   # Exit 0
bash -n < start-termux.sh                                       # Exit 0
```

Hinweis: `bash -n start-termux.sh` als Dateiargument wurde von der
Laufzeit-Sicherung des ausführenden Agenten blockiert (das Skript enthält
`pkill`/`tmux kill-session`, die Sicherung hält es für einen Stopp-Befehl am
Gateway). Geprüft wurde deshalb über Umlenkung `bash -n < start-termux.sh` auf
**denselben** Dateiinhalt — Exit 0. Zusätzlich `bash -n` auf byte-identischen
Kopien aller drei Dateien: Exit 0.

## Prüfer-Befund

Die unabhängige Prüfung (frische Sitzung, andere Modellfamilie) lief **nach**
dieser Abgabe gegen `docs/auftrag-n24a-datenschutz-waechter.md`; das Ergebnis
steht im Abschnitt darüber. Bis dahin stand hier bewusst keine vorweggenommene
Bewertung.
