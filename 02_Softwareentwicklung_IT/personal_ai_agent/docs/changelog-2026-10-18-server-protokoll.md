# Server-Protokoll und Steuerung in der Oberfläche (To-do Punkt 16)

18.10.2026, Hermes-Dauerlauf. Wunsch Sebastian (16.10.2026):

> „Früher war es so, dass in Termux der Server gesteuert wurde und ich den
> Verlauf sehen konnte — die Prompts, eine Liste mit Verbindungen, so ein Log.
> Das ist nicht mehr möglich."

**Ziel:** Termux wird für den Alltag nicht mehr gebraucht — alles, was dort zu
sehen und zu tun war, steht in der Oberfläche.

## Ursache (gemessen, nicht vermutet)

Der Server läuft seit dem Umbau **abgekoppelt im Hintergrund**
(`termux/backend-starten.sh --abloesen`, `setsid`/`nohup`), damit er das
Schließen von Termux überlebt. Seine Ausgaben gingen dabei **ins Leere**: die
Startwege `termux/agent-start` und `start-termux.sh` starteten ihn ohne
Ausgabedatei, also verschwand alles mit der Sitzung. Angezeigt wurde es
nirgends — genau der Befund.

## Was gebaut wurde

### 1. Der Server schreibt ein Protokoll (mit Zeitstempel und Rotation)

* **`termux/server-protokoll.sh`** (neu) — **eine** Stelle für den Pfad:
  `AGENT_SERVER_PROTOKOLL`, Vorgabe `$HOME/agent-server.log`, per Umgebung
  überschreibbar. Eingebunden von **`termux/backend-starten.sh`** (der einzigen
  Startstelle) und dort **exportiert**; damit erben alle Startwege (Widget
  `agent-start`, App `agent-ensure.sh`, Terminal `start-termux.sh`,
  `neu-start-nach-lauf.sh`) denselben Wert, ohne ihn viermal zu nennen.
* **`backend/app/services/protokoll.py`** (neu) — `einrichten()` hängt einen
  `RotatingFileHandler` (256 kB je Datei, 2 Sicherungen) an Wurzel-Logger und
  die uvicorn-Logger (`uvicorn`, `uvicorn.error`, `uvicorn.access`). Zeitstempel
  (`2026-10-18 09:00:01 INFO uvicorn.access: …`) und Rotation kommen aus der
  Standardbibliothek.
* Aufgerufen wird es in der `lifespan` von `backend/app/main.py`.

**Warum kein Umleiten der Ausgabe (`| tee`):** eine Pipe würde die Abkopplung
zerstören — der Server hinge wieder an der Sitzung, die er überleben soll.
Deshalb schreibt der Server selbst.

**Warum nur mit gesetztem Pfad:** `einrichten()` tut **nichts**, wenn
`AGENT_SERVER_PROTOKOLL` fehlt. Auf einem Rechner ohne diesen Startweg (beim
Entwickeln oder im Test) entsteht deshalb **keine** Datei in einem fremden
Heimverzeichnis.

### 2. Die Oberfläche zeigt ihn — Bereich „Server"

* `frontend/index.html`: Knopf **„Protokoll"** im Zustandsstreifen
  (`#server-protokoll-btn`, mit `aria-expanded`) und darunter der zugeklappte
  Bereich `#server-protokoll` mit Kopfzeile (`#server-protokoll-stand`), einem
  `<pre id="server-protokoll-zeilen">` und den Knöpfen **„Aktualisieren"** und
  **„Neu starten"**.
* `frontend/app.js`: reine Funktionen `serverProtokollStand(antwort)` und
  `serverProtokollZeilenText(antwort)` plus Laufzeit (Auf-/Zuklappen, Erneuerung
  alle 5 s **nur solange offen**, Laden beim Sichtbarwerden).
* `frontend/style.css`: flach im Fluss (kein Kasten über dem Chat — Punkt 9),
  `<pre>` mit eigenem Rollbereich (`max-height: 40vh`, `overflow: auto`,
  `white-space: pre-wrap`), umbruchfähige Kopfzeile, 28 px hohe Knöpfe.
* **„Neu starten"** nutzt den **vorhandenen** Weg `POST /api/system/update`
  (holt den Stand und startet den Server neu, mit Rückmeldung wie beim
  Update-Knopf). Es wurde bewusst **kein** zweiter Neustartweg gebaut.
* Cache: `app.js?v=20261018N`, `style.css?v=20261018D`.

### 3. Die Route

`GET /api/system/protokoll?zeilen=200` in `backend/app/router/system_update.py`
— **nur lesend**. Schutz wie beim Update: das Gerät selbst (Loopback) darf
immer; fremde Geräte nur über HTTPS. Gelesen wird höchstens das Dateiende
(256 kB); eine angeschnittene erste Zeile fällt weg; ANSI-Farbschlüssel werden
entfernt. Ist nichts da, sagt die Antwort das ehrlich (`vorhanden: false`,
`hinweis`) — es wird nichts erfunden und nichts angelegt.

## Belege (in diesem Lauf selbst ausgeführt)

* **Neu `backend/tests/test_server_protokoll.py` — 23 passed, Exit 0.** Enthält:
  letzte Zeilen und Kappung (angeschnittene Zeile fällt weg), ANSI-Entfernung,
  ehrliche Meldungen (fehlende Datei, leere Datei, Datei ohne Protokoll-Startweg),
  Begrenzung der Zeilenzahl, **ohne Startweg entsteht keine Datei**,
  Zeitstempel-Form der Zeilen, Idempotenz (genau **ein** Anhang je Logger),
  Rotationsgrenzen, die Route (Loopback 200 ohne Anmeldung, fremd ohne Schluessel
  401, fremd über HTTP 403, fremd über HTTPS 200), die Gegenprobe „Loopback
  öffnet nur `/api/system/`", die Startstelle (Setzen des Pfads aus `$HOME`,
  eigener Pfad gewinnt, `backend-starten.sh` bindet die Datei ein, der
  Serverstart selbst bleibt unverändert) und die Oberfläche (Kennungen,
  zugeklappt, Route im `app.js`, **kein `.innerHTML`** im Protokollblock,
  Cache-Schlüssel, Umbrüche im Stil).
* **Neu `frontend/tests/test_server_protokoll.js` — Exit 0, 44 Prüfungen**
  (Kopfzeile in allen Zuständen, Null-/Unsinns-Antworten ohne Absturz,
  Klartext ohne Symbole, Verdrahtung, Stil).
* **Gegenprobe gegen den HEAD-Stand** (Kopien außerhalb des Repos, dieselbe
  Prüfdatei): **Exit 1** — „Funktion nicht gefunden: serverProtokollStand";
  die Fähigkeit gab es vorher nachweislich nicht. Ebenso: `git show HEAD:…/system_update.py`
  enthält **0** Treffer für „protokoll" (die Route war neu).
* `pytest tests/test_frontend_node.py -q` → **49 passed** (48 + dieser).
* Vorprobe der berührten Bereiche: `test_backend_start_stopp.py`,
  `test_system_update.py`, `test_ein_startweg.py`, `test_widget_agent_start.py`,
  `test_agent_ensure_app.py`, `test_datenschutz_waechter.py`,
  `test_server_protokoll.py` → **184 passed, Exit 0**.
* **Rendermessung im echten Browser** (Edge headless, echte `index.html` +
  `style.css`, gestellte Antworten; Skript außerhalb des Repos
  `…/hermes/cache/scratch/p16_protokoll_messen.js`):
  * **1400 px:** zugeklappt → Klick → offen (`aria-expanded` auf `true`), **7**
    Protokollzeilen sichtbar, Kopfzeile
    „/data/…/agent-server.log · 4,0 kB · 7 Zeilen"; Dokument-Überlauf **0**,
    kein überbreites Kind, **keine Überlappung** mit dem Chat, Protokollkasten
    187 px; zweiter Klick → wieder zu.
  * **380 px:** dasselbe, Protokollkasten 360 px mit **eigenem Rollbereich**
    (`scrollt: true`), Bereich 380 = Fenster 380, Überlauf **0**, kein
    überbreites Kind, keine Überlappung.
  * Die absichtlich eingebaute 400-Zeichen-Zeile ohne Leerzeichen schiebt die
    Seite **nicht** (Umbruch greift).
  * **Sichtprüfung** des Standbilds (380 px): Kopfzeile, Pfadzeile, beide
    Knöpfe und die Protokollzeilen stehen sauber untereinander, nichts
    abgeschnitten oder verdeckt.
* **Ein Befund der Messung — kein Fehler dieser Änderung, aber wichtig zu
  wissen:** der erste Messlauf öffnete den Bereich nicht. Ursache gemessen: die
  **Anmelde-Hülle** (`#anmelden`, z-Index 2000, ganzes Fenster) lag über dem
  Knopf — und ebenso über den **bestehenden** Knöpfen `#system-update-btn`,
  `#selbsttest-btn`, `#gruppen-btn`. Sie ist nur offen, solange die
  Sitzungsprüfung nicht „frei" meldet; im Messaufbau (gestellte Antworten)
  fehlte die Antwort auf `/api/auth/sitzung`. Nach Stellung dieser Antwort
  (angemeldeter Zustand) messen alle vier Knöpfe sauber. Die Messung wurde
  entsprechend korrigiert — kein Produktfehler.

## Ehrliche Grenzen

* **Geprüft sind Mechanismus, Route und Darstellung.** Die **Abnahme am Gerät**
  (Knopf drücken, Protokollzeilen sehen, „Neu starten" auslösen) bleibt
  Sebastians Schritt — ein echter Serverstart am Handy wurde hier nicht gefahren.
* Das Protokoll enthält, was der Server über `logging` schreibt (Start, Zugriffe,
  Fehler). **Nicht** enthalten sind Ausgaben, die ein Skript per `echo` auf
  stdout schreibt, und die Ausgabe des TLS-Zugangs wird nicht doppelt geführt.
* „Neu starten" ist der **Update-Weg** (git pull + Neustart), nicht ein reiner
  Neustart ohne Pull — die Rückmeldung sagt das.
* Die Protokolldatei wächst nicht endlos (Rotation ab 256 kB, zwei Sicherungen),
  ist aber **kein Archiv**: ältere Zeilen fallen weg.
* Die Anmeldung bleibt für fremde Geräte unverändert; die Loopback-Ausnahme gilt
  weiterhin **nur** für `/api/system/`.

Kein fremder Pfad angefasst, kein `git add -A`, nichts gelöscht, `status.json`
nicht angefasst, kein Bild/Vision-/pCloud-Schreibzugriff, keine Geräteeingriffe,
keine `.env`, keine echten Personennamen. **Kosten: 0 USD.**
