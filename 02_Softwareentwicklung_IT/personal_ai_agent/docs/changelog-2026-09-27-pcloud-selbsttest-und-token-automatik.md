# Changelog 27.09.2026 — pCloud: Schlüssel-Automatik beim Widget-Start, Selbsttest-Zeile, Anzeige im Blatt

> **Auftrag (N3):** Der pCloud-Schlüssel liegt per Kabel als
> `/sdcard/Download/pcloud_token.txt` auf dem Handy. `start-termux.sh` soll ihn
> beim nächsten Widget-Tipp übernehmen, der Selbsttest soll „pCloud" anzeigen,
> und das Selbsttest-Blatt soll es als Klartext-Zeile zeigen — mit Tests.

## Warum

Der Schlüssel darf **nicht über Git** wandern (öffentliches Repo) und ist bisher
von Hand in die `.env` des Handys getippt worden. Damit der Handy-Stand
**selbstheilend** ist, übernimmt das Startskript die Übergabedatei beim Start und
löscht sie danach (ein Geheimnis soll nicht im freigegebenen Download-Ordner
liegen, den jede App lesen kann). Und weil man unterwegs kein Kabel hat, muss im
Selbsttest-Blatt ablesbar sein, ob der Zugang da ist: eingerichtet, verbunden,
Konto/Quota — ohne je den Schlüssel oder die volle Adresse zu zeigen.

## Die drei Änderungen

| Datei | Art | Inhalt |
|---|---|---|
| `start-termux.sh` | geändert | Block „pCloud-Zugang übernehmen (selbstheilend)" direkt nach dem Archiv-Index-Block |
| `backend/app/router/selbsttest.py` | geändert | Block `pcloud` im Selbsttest-JSON (nur lesend, eigenes Zeitbudget, nie 500) |
| `frontend/app.js` | geändert | neue Klartext-Zeile „pCloud" in `selbsttestText()`; Hinweistext des Blatts korrigiert |
| `frontend/index.html` | geändert | Cache-Bump `app.js?v=20260925G` → **`?v=20260927A`** |
| `backend/.env.example` | geändert | Kommentar: so läuft die Übernahme aufs Handy ab (Weg, Löschung, Rückweg) |
| `.gitignore` | geändert | `*.env.vorher` — die Sicherung enthält dieselben Geheimnisse wie `.env` |
| `backend/tests/test_selbsttest.py` | geändert | +8 Tests für den pCloud-Block, Dienst-Attrappe (kein Netz) — Datei: 21 → 29 |
| `frontend/tests/test_selbsttest.js` | geändert | +8 Prüfungen für die pCloud-Zeile (39 → 47), Cache-Version aktualisiert |
| `frontend/tests/test_sprachaufnahme.js`, `…/test_tastatur_und_textauswahl.js` | geändert | nur die Cache-Versionsprüfung `?v=20260927A` nachgezogen |

### 1. `start-termux.sh` — Übernahme (idempotent, ohne Ausgabe im Normalfall)

Ablauf, wenn `$HOME/storage/downloads/pcloud_token.txt` (sonst
`/sdcard/Download/pcloud_token.txt`) existiert:

1. `backend/.env` wird vorher als **`backend/.env.vorher`** gesichert (`cp -f`) — der Rückweg bleibt offen.
2. Aus der Übergabedatei werden **nur** die Zeilen `PCLOUD_TOKEN=` und `PCLOUD_HOST=` gelesen (alles andere ignoriert, Windows-Zeilenenden `\r` entfernt).
3. Schlüssel in der `.env` vorhanden → Wert **ersetzt** (`sed -i "s|^SCHLUESSEL=.*|…|"` mit `|` als Trenner, weil Token `/`, `+`, `=` enthalten können). Nicht vorhanden → **angehängt**.
4. **Andere Zeilen bleiben unberührt** (z. B. `OPENROUTER_API_KEY`) — es wird nie die Datei neu geschrieben.
5. Ist `PCLOUD_TOKEN=` danach in der `.env` nachweisbar (`grep -q '^PCLOUD_TOKEN='`), wird die Übergabedatei mit `rm -f` **gelöscht** und das gemeldet; scheitert es, bleibt sie liegen und es gibt eine Warnung (erneut starten).
6. **Kein Wert landet je in der Ausgabe** — gemeldet werden nur Schlüsselnamen, Pfade und Zustände (das Startprotokoll liegt auf `/sdcard`).

Fehlt die Datei (Normalfall nach der einmaligen Übernahme), passiert **nichts**:
keine Ausgabe, kein Fehler, der Start läuft unverändert weiter.

Zwei Feinheiten, die im Sandkasten aufgefallen und behoben wurden:

- Das Maskieren der sed-Sonderzeichen (`&`, `\`, `|`) darf **nur** im Ersetzen-Zweig passieren — sonst landen die Masken im Anhängen-Zweig doppelt in der `.env`.
- Eine **leere** Wert-Zeile wird übersprungen: `PCLOUD_TOKEN=` darf einen vorhandenen Schlüssel nicht löschen.

### 2. `selbsttest.py` — Block `pcloud`

```json
"pcloud": {"konfiguriert": true, "host": "eapi.pcloud.com",
           "konto": "se*******************.com",
           "quota_gb": 2199.0, "belegt_gb": 390.5, "error": null}
```

- **Feld ist immer da**, `konfiguriert`/`host`/`konto`/`quota_gb`/`belegt_gb`/`error`.
- Ohne Schlüssel: `konfiguriert: false`, `error: null` — das ist ein **gültiger Zustand**, kein Fehler, und es wird **nichts abgefragt**.
- Mit Schlüssel: **nur lesend** `userinfo` über `pcloud_service`; die E-Mail kommt von dort bereits **maskiert** (erste 2 + letzte 4 Zeichen). Der Schlüssel und die volle Adresse werden nie ausgegeben.
- **Nie ein 500er**: alles in breitem `try/except` mit `logger.warning`; Fehler werden Text (auch ein fremder Fehlertext wird zusätzlich vom Schlüssel befreit). Ins **Log** geht nur der Klassenname der Ausnahme — ein fremder Fehlertext könnte den Schlüssel enthalten (ein Test prüft das ausdrücklich).
- **Eigenes Zeitbudget** `PCLOUD_TIMEOUT_S = 8.0`: Der Aufruf läuft in einem `ThreadPoolExecutor` mit `result(timeout=…)`; bei Überschreitung steht `pCloud nicht erreichbar (Zeitueberschreitung)` im Feld, statt dass das Blatt am 20-s-Timeout des Dienstes hängt. `shutdown(wait=False)` — es wird bewusst **nicht** auf den abgehängten Leseaufruf gewartet (er schreibt nichts).

### 3. Frontend — eine Zeile, gleicher Stil wie die Nachbarn

- nicht eingerichtet → `⚠ pCloud: nicht eingerichtet (kein PCLOUD_TOKEN hinterlegt)`
- Fehler → `⚠ pCloud: <error-Text>`
- verbunden → `✓ pCloud verbunden (Konto se*******************.com, 2199 GB, belegt 390.5 GB)`

Die Kommentare im Blatt und der Hinweistext wurden richtiggestellt: Der Selbsttest
prüft **nicht mehr nur lokal** — er liest zusätzlich das pCloud-Konto (nur lesend,
kein Anbieter/Sprachmodell, kein Schreibzugriff).

## Prüfung — ausgeführte Befehle mit echten Zahlen

```
bash -n start-termux.sh
  -> Exit 0

cd backend && .venv/Scripts/python -m pytest tests/ -q
  -> 665 passed, 3 warnings in 85.27s, Exit 0            (voller Prüfbefehl)

cd backend && .venv/Scripts/python -m pytest tests/test_selbsttest.py -q
  -> 29 passed, 3 warnings in 16.80s, Exit 0             (vorher 21 in der Datei)

cd frontend && node --check app.js
  -> Exit 0

cd frontend && for f in tests/*.js; do node "$f" app.js; done
  -> 15 Dateien, alle Exit 0, zusammen 488 OK-Zeilen, 0 FEHL
```

**Sandkasten-Probe für den neuen Skript-Block** (Skript im Scratch-Verzeichnis,
nicht im Repo — wie beim pCloud-Rauchtest): Der Block wird **aus dem echten
`start-termux.sh` geschnitten** und mit eigenem `HOME`/Projektordner in sechs
Lagen gefahren — **24 Prüfungen, alle grün**:

| Lage | Ergebnis |
|---|---|
| A: vorhandener Schlüssel, Sonderzeichen `/ + = & \|`, CRLF, Fremdzeilen | Wert exakt ersetzt; `OPENROUTER_API_KEY` und weitere Zeilen unberührt; Übergabedatei gelöscht; `.env.vorher` trägt den alten Stand; **kein Wert im Protokoll** |
| B: zweiter Lauf ohne Datei | keine Ausgabe, Wert unverändert (idempotent) |
| C: Übergabedatei ohne PCLOUD-Zeilen | Warnung, Datei bleibt liegen, `.env` unverändert |
| D: nur `PCLOUD_HOST`, kein Token | Host angehängt, Warnung, Datei bleibt liegen |
| E: `.env` ohne pCloud-Zeilen | beide Schlüssel angehängt, Backslash/`&`/`\|` exakt, keine CR-Zeilenenden |
| F: nur leere `PCLOUD_TOKEN=`-Zeile | alter Wert bleibt, Warnung, Datei bleibt liegen |

## Was NICHT geprüft wurde

- **Kein Lauf auf dem Handy.** Die Wirkung zeigt sich beim **nächsten Widget-Tipp**
  (der laufende Durchgang führt noch den alten Skripttext aus — deshalb zweimal
  tippen). Erst dann ist belegbar: Zeile „übernommen/Übergabedatei gelöscht" im
  Protokoll und `pcloud` im Selbsttest am Gerät.
- **Kein Live-Aufruf der Selbsttest-Zeile** gegen einen echten Schlüssel: Die
  Backend-Tests ersetzen den Dienst durch eine Attrappe (kein Netz, kein Verbrauch);
  die Frontend-Prüfungen rechnen mit Beispielwerten.
- **Die Zeitüberschreitung** ist mit verkleinertem Budget (0,05 s) getestet, nicht
  mit echten 8 s gegen einen hängenden Server.
- **`/sdcard/Download/pcloud_token.txt`** liegt weiterhin auf dem Handy (Stand vor
  dem Widget-Tipp) — die Löschung ist vor Ort noch nicht beobachtet.

## Was unsicher bleibt

- Ist `HOME/storage/downloads` auf dem Handy nicht eingerichtet, greift der
  zweite Pfad `/sdcard/Download/…` (Muster des Archiv-Index-Blocks) — geprüft ist
  das im Sandkasten, nicht auf dem Gerät.
- Der Selbsttest macht jetzt **einen** externen Leseaufruf. Ist das Handy offline,
  steht nach spätestens 8 s ein ⚠-Text im Blatt (statt eines Hängers).
