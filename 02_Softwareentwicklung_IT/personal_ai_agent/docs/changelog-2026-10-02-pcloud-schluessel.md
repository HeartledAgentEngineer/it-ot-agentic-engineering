# Änderungsprotokoll 02.10.2026 — pCloud-Schlüssel in allen Startwegen (Issue #3, Punkt 1)

## Befund (Cloud-Sitzung mit Sebastian am Handy, 01./02.10.)

Die Übernahme des pCloud-Schlüssels aus `Download/pcloud_token.txt` nach `backend/.env` stand
**nur** in `start-termux.sh`. Das Widget „agent" startet aber `termux/agent-start` (so legt es
`termux/einrichten.sh` an), die App „Hey Agent" startet `termux/agent-ensure.sh` — keiner der
beiden kam an dem Block vorbei. Der Schlüssel lag seit 27.09. unbenutzt im Download-Ordner, die
Gesichter-Kacheln im 👥-Quiz blieben leer. Die Übergabe vom 01.10. (Punkt 7) nahm fälschlich an,
das Widget laufe über `start-termux.sh`.

## Änderung

- Neu **`termux/pcloud-schluessel-uebernehmen.sh <env-datei> [quelle]`**: die bisherige Logik aus
  `start-termux.sh`, unverändert — nur `PCLOUD_TOKEN`/`PCLOUD_HOST`, zeilenweise ersetzen oder
  anhängen, vorher `<env>.vorher`, Werte werden nie ausgegeben, Windows-Zeilenende und
  Anführungszeichen werden geduldet, leerer Wert löscht nichts, die Übergabedatei wird **nur nach
  erfolgreicher Übernahme** gelöscht (sonst bliebe das Geheimnis im für alle Apps lesbaren
  Download-Ordner). Fehlt die Datei: keine Ausgabe, nichts passiert. Exit immer 0.
- **Alle drei Startwege rufen es auf** (eine Quelle statt dreimal derselbe Block), jeweils nach
  dem Pull und vor dem Serverstart, mit `|| true`: `start-termux.sh` (alter Block ersetzt),
  `termux/agent-start` (Widget), `termux/agent-ensure.sh` (App, Ausgabe ins Log).

## Prüfung

- Neu `backend/tests/test_pcloud_schluessel_uebernahme.py` (9 Tests): jeder Startweg ruft das
  Skript genau einmal, nach dem Pull, vor `python -m uvicorn`, mit `|| true`; die alte Logik steht
  in keinem Startweg mehr; keine `echo`-Zeile gibt einen Wert aus; **Funktionstests mit dem echten
  Skript** (bash, erfundene Werte): anhängen/ersetzen, andere Zeilen bleiben, Sonderzeichen
  `/ + = & |`, CRLF, Übergabedatei weg, Sicherung da, kein Wert in der Ausgabe; ohne Datei passiert
  nichts; ohne gültigen Schlüssel bleibt die Datei liegen. `bash -n` auf allen vier Skripten OK.

## Am Handy

Die Cloud-Sitzung hat den Schlüssel am 02.10. von Hand in `backend/.env` eingetragen;
`pcloud_token.txt` liegt laut Issue noch im Download-Ordner. Beim nächsten Start (Widget oder App)
wird er erneut übernommen (gleicher Wert) und die Übergabedatei entfernt. Hinweis: `agent-start`
holt den neuen Stand erst während des Laufs per `git pull` — die laufende Shell liest noch die
alte Fassung; wirksam ist die Übernahme also ab dem **zweiten** Widget-Tipp (die App über
`agent-ensure.sh` ebenso beim nächsten Kaltstart).
