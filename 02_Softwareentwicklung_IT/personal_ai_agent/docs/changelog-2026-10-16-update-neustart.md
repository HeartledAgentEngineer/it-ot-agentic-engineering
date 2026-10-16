# Update und Neustart aus der Oberfläche (16.10.2026)

## Verhalten

- Neuer Kopfzeilenknopf löst `POST /api/system/update` aus und zeigt sofort:
  „Stand wird geholt, Server startet neu — die Seite ist gleich wieder da.“
- Der Endpunkt hat keine Eingabeparameter. Er nutzt beim Einbinden dieselbe
  `require_api_key`-Abhängigkeit wie andere geschützte `/api`-Routen (API-Key oder
  Sitzungscookie), prüft zusätzlich das tatsächliche HTTPS-Schema und ist ohne
  eingerichteten `API_KEY` gesperrt.
- Das feste `termux/update-und-neustart.sh` wird als FastAPI-Hintergrundaufgabe
  erst **nach dem Senden der HTTP-Antwort** mit `Popen` in einer eigenen Sitzung
  gestartet. Es wartet nicht im Anfrageprozess.
- Das Skript protokolliert nach
  `$HOME/storage/downloads/hermes_diag/update-und-neustart.log` (Termux-Verknüpfung
  zum Download-Ordner; falls sie fehlt: `/sdcard/Download/hermes_diag/`). Es führt im
  Projektordner `git pull --ff-only` aus; Zugangsdaten in Git-URLs werden vor
  dem Protokollieren maskiert.
- Ein fehlgeschlagener Pull protokolliert Git-Ausgabe und Exit-Code und beendet
  sich, ohne den Server zu stoppen. Nach erfolgreichem Pull wartet das Skript
  kurz, beendet den Server über `termux/backend-beenden.sh` und ruft danach
  `~/agent-ensure.sh` auf. Bei fehlgeschlagenem Stopp wird nicht neu gestartet.
- Die Oberfläche verwendet `app.js?v=20261016B`; Fehler von HTTP, Anmeldung oder
  Verbindungsabbruch erscheinen ebenfalls in der Statuszeile.

## Tests und Grenzen

`backend/tests/test_system_update.py` deckt Antwort-vor-Prozessstart, festen
Skriptaufruf trotz fremder JSON-Felder, API-Key-/Sitzungsschutz, HTTPS,
fehlende `API_KEY`-Konfiguration sowie erfolgreichen und fehlgeschlagenen
Pull im isolierten Shell-Sandkasten ab. Die Tests beenden keinen echten Server
und führen keinen Netzwerk-Pull aus.

Der Live-Neustart auf einem Android-Gerät mit Termux wurde in dieser Änderung
nicht ausgeführt; dafür muss der neue Stand auf dem Gerät vorhanden sein.
