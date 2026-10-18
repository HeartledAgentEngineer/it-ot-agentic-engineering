# Hermes-Anbindung im Projekt — Bestandsaufnahme

**Stand:** 18.10.2026, am PC **nur lesend** erhoben (Code gelesen, keine Änderung).
**Zweck:** To-do-Punkt 7 („Hermes-Anbindung im Projekt nachsehen — nur lesen").
Grundlage für Sebastians Entscheidung, ob Hermes den reinen LLM-Aufruf ergänzt.

Alle Zahlen und Aussagen unten sind aus dem Code bzw. durch eine ausgeführte Sonde
belegt; die Quellen stehen als Datei:Zeile dabei. Nichts hier ist geschätzt.

---

## 1. Das Zielbild: der Agent kennt seine Grenze

`backend/app/services/faehigkeiten.py` (179 Zeilen) hält das Selbstbild als
**datengetriebenes Manifest**, bewusst ohne LLM (kostenlos, testbar):

- **`FAEHIGKEITEN`** (Z. 19–38) — *kann:* `chat_verstaendnis`, `gedaechtnis`,
  `websuche`, `archiv`, `dokument_text`, `gesichter_merken`, `tts_stt`.
  *kann nicht:* `terminal`, `dateien_schreiben`, `tool_install`, `git`,
  `system_zugriff`.
- **`GRENZE_MARKER`** (Z. 39) — Stichworte, die eine Grenzüberschreitung anzeigen
  (Terminal/Bash, Datei/Repo/Git, installieren, Docker/SPS/OT). Mit
  `stoesst_an_grenze()` (Z. 67) und `soll_hermes_delegieren()` (Z. 163).
- **Reine Lese-Signale** schalten das „datei"-Signal ab: „Lies meine
  Lebenslauf-Datei" ist eine **eigene** Fähigkeit und wird nicht delegiert.

Die Entscheidung fällt **vor** dem Modell, nicht durch das Modell:
`backend/app/services/werkzeuge.py:1040ff` beantwortet einen etwaigen
Modell-Aufruf `hermes` ausdrücklich mit *„Es gibt KEIN aufrufbares Werkzeug
„Hermes" — die Übergabe an Hermes macht das Backend automatisch, bevor eine
Aufgabe zu dir kommt."* Das Modell darf also keine Übergabe behaupten; es kann
selbst nichts an Hermes schicken.

## 2. Die Weiche: drei Wege, eine Reihenfolge

`backend/app/services/chat_routing.py` (218 Zeilen), Funktion `route_auftrag`
(Z. 119), Reihenfolge hart:

1. **Track A — PC-Hermes** (Z. 157). Läuft er, ist Schluss. Der Nutzer kann mit
   `ziel="handy"` (Umlenk-Knopf) Track A überspringen.
2. **Track C — lokaler Hermes auf dem Gerät** (nur wenn A fehlschlug).
3. **Track B — Auftragsbuch** (nur wenn beides fehlt). Seit S7 (Commit
   `84840f6`) mit **ehrlichem** Text: „Liegt bereit — gerade arbeitet niemand
   daran" plus Grund und Ausweg. Die frühere Zeile „Hermes wurde benachrichtigt –
   wartet auf Bearbeitung" behauptete einen Lauf, den es nicht gab.

**Eine Quelle für die Texte:** `statusmeldung_bereit`, `bereit_reply_text`,
`kein_helfer_text` (Z. 25/42/63) — beide Chat-Endpunkte
(`POST /api/chat` und `POST /api/chat/stream` in `router/chat.py`) benutzen sie,
damit die Kopien nicht auseinanderlaufen.

Erkennung vor der Weiche: `llm_service.braucht_hermes()`
(`llm_service.py:1204`, wenige Beispiele als Few-Shot aus
`~/hermes_inbox/klassifikation_lernfaelle.json`, Korrekturen lernbar über
`lerne_klassifikation()`) — zusätzlich zur Wort-Heuristik.

## 3. Track A — PC-Hermes (`hermes_gateway.py`, 218 Zeilen)

- Zugang über die **`.env` des Geräts**: `HERMES_PC_BASE_URL`,
  `HERMES_PC_API_KEY`, `HERMES_PC_TIMEOUT` (Vorgabe 30 s; `config.py:315–317`).
- Protokoll: OpenAI-Format wie ein LLM — `GET {base}/v1/models` als
  Erreichbarkeits-Check (`is_online()`, Z. 52), Arbeit über
  `POST {base}/v1/chat/completions` mit `stream: true` und Modell
  `hermes-agent` (Z. 71–115).
- **Bewusst genau ein Sendeversuch:** den Auftrag schickt nur der
  Hintergrund-Poller (`_start_antwort_poller`, Z. 117); der frühere synchrone
  Erstversuch ist entfernt, weil er den Auftrag **doppelt** an den PC schickte.
  Der Nutzer bekommt sofort die Übergabe-Bestätigung, die Antwort wird
  nachgeholt und per `finish_exchange` in den Verlauf eingespeist.
- Timeout ist **kein** Rückfall: „Der PC-Hermes HAT den Auftrag angenommen" —
  es wird nicht parallel auf dem Handy gearbeitet (Z. 181–193).
- Ein toter PC reißt nie die Anfrage: `sende_auftrag()` liefert dann `None`
  und setzt `letzter_fehler` als Klartext-Grund (Z. 156–165).

## 4. Track C — lokaler Hermes auf dem Gerät (`hermes_local.py`, 1245 Zeilen)

**Voraussetzung (`ist_verfuegbar()`, Z. 323):** die Kommandos **`hermes` UND
`tmux`** müssen im PATH liegen. Fehlt eines, ist Track C nicht verfügbar.

Vier Betriebsarten, alle in dieser einen Datei:

| Kanal | Weg | Kern |
|---|---|---|
| tmux (Standard) | `hermes chat` interaktiv in einer tmux-Pane | `LocalHermesJob` + `HermesRegistry`: Gedanken-/Tool-Boxen per `capture-pane` auslesen, entdoppeln; Abschluss erst nach 10 s stabiler Pane (`_ABSCHLUSS_IDLE_S`); offene Rückfrage zählt **nicht** als Abschluss |
| `query` | Einmal-Subprozess `hermes chat -q … -Q` | deterministisch, kein tmux, keine Registry |
| `aktiv` | Datei-Inbox `~/hermes_inbox/{auftraege,antworten,status}.jsonl` | Server legt ab, **`backend/hermes_inbox_daemon.py`** (581 Zeilen) ist DIE EINE antwortende Instanz, Antwort kommt zurück in den Verlauf; Selbstheilung `sicherstelle_inbox_daemon()` (Z. 255) startet einen toten Daemon neu |
| (Aufräumen) | `raeume_alte_job_sessions_auf()` (Z. 724) | beendet liegengebliebene `hermes_agent_*`-Sessions, **niemals** fremde (`hermes_termux`, `hermes_code`, konfigurierte Session sind geschützt) |

Dazu im selben Dienst: Warteschlangen-Position (`_warteschlange_davor`, Z. 84 —
„noch N Aufträge davor", weil der Daemon streng nacheinander arbeitet),
Ruhebudget als **Hinweis** statt Abbruch (`hermes_auftrag_idle`, Vorgabe 420 s),
hartes Gesamtbudget `hermes_auftrag_timeout` (Vorgabe 3600 s), Modell für den
lokalen Lauf `hermes_local_model` = `deepseek/deepseek-v4.1-flash` (dieselbe
Kennung wie im Chat), Arbeitszeile für den Chat (`arbeits_start_zeile`, Z. 328),
Kommentar-Lernen mit Trivial-Filter (`hat_mehrwert`, Z. 357).

**Weitere Verbraucher außerhalb der Weiche:**

- `backend/app/router/hermes_steuerung.py` (497 Zeilen, **9 Routen**):
  `/api/hermes/aktivieren`, `/status/{id}`, `/beenden`, `/chat`, `/lernfaelle`,
  `/codewort`, `/stream`, `/letzte`, `/chatstream` — damit lässt sich Track C
  auch **explizit** per API in Gang setzen, unabhängig von der Chat-Weiche.
- `backend/app/router/auftraege.py`: Kommentar an einen laufenden Job,
  Daemon-Antwort abholen (`lese_daemon_antwort`), Job beenden.
- `backend/app/main.py:136–152`: **Selbstheilung beim Serverstart** — Inbox-Daemon
  sicherstellen (auch bei leerem Kanal, seit der Befund „Hermes reagiert nicht"
  behoben wurde) und liegengebliebene tmux-Sessions aufräumen.
- `termux-hermes-watcher.sh` (279 Zeilen, Termux): pollt das Auftragsbuch alle
  3 s, claimt den Auftrag, zeigt eine Benachrichtigung, startet die Hermes-App.
  Er liegt **außerhalb** des aktuellen Startwegs (der Watcher-Weg wurde abgelöst).

## 5. Fähigkeiten, Wege und Steuerung auf einen Blick

```
Chat-Nachricht
   │
   ├─ ist_auftrag() ODER soll_hermes_delegieren()   (faehigkeiten.py, llm_service.braucht_hermes)
   │
   └─ route_auftrag()  (chat_routing.py)
         ├─ Track A  hermes_gateway.py ── HTTP ──> PC-Hermes (/v1/chat/completions, OpenAI-Format)
         ├─ Track C  hermes_local.py   ── tmux / query / aktiv-Datei-Inbox ──> lokaler Hermes-CLI auf dem Gerät
         └─ Track B  Auftragsbuch      ── Warteliste + ehrliche Meldung
```
Kein Weg wirft: ein fehlender Helfer führt eine Stufe tiefer, nie in einen
Abbruch des Chats.

## 6. Was am PC gemessen wurde (Sonde, in diesem Lauf ausgeführt)

| Messung | Ergebnis |
|---|---|
| `.env` des PC-Arbeitsbaums (`backend/.env`, 83 B) | enthält **nur** `PCLOUD_HOST` und `PCLOUD_TOKEN` — **keine** `HERMES_PC_*`, **keine** `HERMES_LOCAL_*` |
| `settings.hermes_pc_base_url` / `_api_key` gesetzt | **False / False** |
| `hermes_gateway.ist_konfiguriert` | **False** → Track A liefert `None` mit Grund „nicht konfiguriert" |
| `settings.hermes_local_kanal` / `_session` | leer → tmux-Weg als Standard |
| `hermes_local_model` | `deepseek/deepseek-v4.1-flash` |
| `hermes_auftrag_timeout` / `_idle` | 3600 s / 420 s |
| `hermes_local.ist_verfuegbar()` am PC | **False** — `hermes` ist im PATH, **`tmux` fehlt** (MSYS: „no tmux in …") |
| Lauscht etwas auf Port 8642 (Vorgabe-Port des PC-Hermes) | **nein** (kein LISTENING-Eintrag) |
| Inbox-Verzeichnis `~/hermes_inbox` am PC | **existiert nicht** |
| Hermes-Routing-Tests (11 Dateien) | **75 passed** in 21,24 s |
| Testdateien, die „hermes" erwähnen | 72 |

**Lesart dieser Zahlen (ehrlich):** Auf **diesem** Rechner ist weder Track A
konfiguriert noch Track C verfügbar. Für das Handy ist damit nur so viel
gesagt: `backend/.env` und der PATH liegen **auf dem Gerät** und sind vom PC aus
nicht lesbar — die Frage „hat das Handy `HERMES_PC_*` und ein lauffähiges
`hermes`/`tmux`?" ist am PC **nicht** abschließend messbar. Sebastians Befund
(„Termux-Paket derzeit defekt", „auf dem Handy läuft kein Hermes") ist der
glaubwürdige Stand und passt zum beobachteten Verhalten: erkannte Aufträge
enden mit der S7-Meldung im Buch.

## 7. Entscheidungsgrundlage (offen — Sebastians Wort)

**Weg 1 — PC-Hermes statt Termux (Track A scharf machen).**
Es muss **nichts am Code** gebaut werden: `hermes_gateway.py` ist fertig und
getestet. Nötig sind nur drei Zeilen in der **`.env` des Handys**
(`HERMES_PC_BASE_URL` = LAN-IP des PCs, `HERMES_PC_API_KEY`, optional
`HERMES_PC_TIMEOUT`) und auf dem PC ein laufender Hermes-API-Server.
Passt genau zu Punkt 16 („Termux gar nicht mehr brauchen") — der lokale
CLI-Weg wird dann nicht mehr gebraucht.
*Grenze:* funktioniert nur im selben Netz (WLAN/LAN); unterwegs fällt die Weiche
wie bisher auf Buch zurück.

**Weg 2 — den reinen LLM-Aufruf ergänzen, Delegation schmal halten.**
Der Agent kann Datei lesen, Archiv, Websuche, Dokumente bereits selbst
(`faehigkeiten.py`). Delegiert werden müssten dann nur Terminal, Git,
Installation, System — also die Fälle, die das Manifest schon als „kann nicht"
führt. Das ist **keine neue Technik**, sondern eine Frage der Grenzlinie.

**Weg 3 — nichts tun.** Track C bleibt unerreichbar, erkannte Aufträge landen
ehrlich im Buch (S7). Kostet nichts, liefert aber keine Ausführung.

**Kosten:** alle drei Wege kosten **kein** zusätzliches Geld — Weg 1 nutzt
Hermes am PC, Weg 2 den schon bezahlten Chat-Aufruf. Nur Modellaufrufe fallen
an, wie bisher.

**Kein Umbau ohne Wort:** In diesem Lauf wurde **nichts** am Verhalten
geändert — nur gelesen, gemessen und hier festgehalten.

---

**Grenzen dieser Aufnahme (ehrlich):**
- Die `.env` und das PATH-Umfeld des Handys sind vom PC nicht messbar; dazu
  braucht es das Gerät (Kabel oder Sebastians Blick).
- Ob der PC-Hermes-API-Server überhaupt eingerichtet ist, sagt diese Aufnahme
  **nicht** — nur, dass er gerade nicht lauscht und hier nicht konfiguriert ist.
- `termux-hermes-watcher.sh` wurde gelesen, aber nicht ausgeführt.
