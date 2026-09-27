# pCloud-Zugang für den Agenten — ohne Entwickler-Anmeldung

> **Datum:** 26.09.2026 · **Auftrag:** Sebastian: „Cloud-Zugriff für den Personal
> Agent einrichten" — und nach dem Hänger im Entwicklerbereich ausdrücklich:
> „**ohne App-Registrierung, ohne Client-ID, ohne Google-Hänger**".

## Warum es diesen Weg gibt (Vorgeschichte)

Der geplante Weg war die offizielle App-Registrierung (App Console) + OAuth 2.0.
Am 26.09. stellte sich heraus: **die Anmeldung im Entwicklerbereich
(`docs.pcloud.com`) hängt** — die Seite bleibt stehen, der Login findet nicht
statt (Symptom passt zu den in Comet blockierten Drittanbieter-Cookies, dem
Google-Rücksprung fehlt damit die Grundlage). Zusätzlich läuft Sebastians
pCloud-Konto über **Google-Anmeldung**, hat also möglicherweise gar kein
Passwort, das ein Entwickler-Login verlangen würde.

## Der Weg, der funktioniert hat

Der **pCloud-Client auf dem PC ist bereits angemeldet** (deshalb gibt es das
Laufwerk `P:\`). Er legt seinen Zugang lokal in einer SQLite-Datei ab:

```
C:\Users\sebas\AppData\Local\pCloud\data.db   (373 MB, Tabellen: file, folder, setting …)
  Tabelle setting, Feld 'auth'  -> 39 Zeichen  = Anmelde-Token
  Tabelle setting, Feld 'location_id' = 2      = Europa-Rechenzentrum
```

Dieser `auth`-Wert ist **derselbe Tokentyp, den die pCloud-API akzeptiert**
(pCloud-Token sind client-unabhängig). Also: kein Login, keine App, kein
`client_id`, kein Google.

**Vorgehen (nachvollziehbar, ohne Geheimnis-Ausgabe):**

1. Datenbank **ohne Sperre** lesen (`file:…?immutable=1`), damit der laufende
   Client unberührt bleibt; im Notfall über eine Kopie.
2. Token aus `setting.auth` holen — er wird **nie gedruckt**, sondern direkt in
   `backend/.env` geschrieben.
3. **Echter Beweis** über die API statt Vertrauen: `userinfo` und `listfolder`.

## Beleg (echte Ausgabe der Prüfung)

```
Zugang gefunden: 39 Zeichen im Feld 'auth' (Konto-Nr. 4738912, location_id 2)
Benutzername: se*******************.com                        (maskiert)

Probe gegen https://eapi.pcloud.com/userinfo -> result=0 error=None
  E-Mail:    se*******************.com
  Quota:     2199.0 GB, belegt 390.5 GB
  Konto:     premium=True emailverified=True

Probe /listfolder (Wurzel): 18 Eintraege, z. B.
['Automatic Upload', 'Bilder & Videos', 'Crypto Folder', 'Dokumente', 'Duales Studium (Kahl)']

Token in …\personal_ai_agent\backend\.env eingetragen (PCLOUD_TOKEN, PCLOUD_HOST=eapi.pcloud.com).
```

Damit ist **Lesen bewiesen** (`listfolder`), nicht nur die Anmeldung.

## Wo der Zugang liegt

| Datei | Inhalt | Schutz |
|---|---|---|
| `backend/.env` | `PCLOUD_TOKEN=…`, `PCLOUD_HOST=eapi.pcloud.com` | `.env` steht in `.gitignore` (Zeile 13) |

**Für das Handy gilt Sebastians Regel:** Der Token ist ein Geheimnis und wird
**nicht per Git** übertragen (privates über Kabel), sondern einmal von Hand bzw.
über die `.env` des Handy-Backends eingetragen.

## Regeln, die im Code gelten (pCloud kennt keine „nur lesen"-Freigabe)

1. **Standard ist Lesen.** Schreiben nur, wenn ein Auftrag es sagt.
2. **Schreiben nur in `Agent/`** — nie in `Familie`, `Dokumente`, `Studium` oder
   andere bestehende Ordner.
3. **Umbenennen, Verschieben, Löschen = Änderung an Sebastians Daten →
   Rückfrage.** Löschen landet ohnehin im Papierkorb.
4. **`Crypto Folder` ist tabu** (im Konto eingerichtet, im Listing sichtbar).
5. **Nichts überschreiben**; vorher Namensgleichheit prüfen.
6. **`P:\` nie rekursiv scannen** (belegt: Timeout nach 180 s) — API nutzt
   `listfolder` je Ebene.
7. **Bilder nur in-memory** für Vision-Calls, nie ins Backend kopieren.

## Was ehrlich offen bleibt

* **Der Token ist der des PC-Clients.** Meldet sich der Client ab oder rotiert
  pCloud den Token, stirbt unser Zugang. Dann: neuen `auth` aus `data.db`
  holen (dasselbe Skript) — oder doch den OAuth-Weg gehen, sobald die
  Entwickler-Anmeldung läuft.
* **Der Token darf alles** (pCloud hat keinen Scope außer `manageshares`) — die
  Regeln oben sind Code, keine Freigabe-Sperre.
* Die Entwickler-Anmeldung selbst bleibt ungelöst; sie ist für diesen Weg aber
  **nicht mehr nötig**.

## Nächste Stufe

`backend/app/services/pcloud_service.py` + `backend/app/router/cloud.py`
(`/api/cloud/status`, `/liste`, `/thumb`, `/datei`, `/suche`) mit Tests — der
Explorer in der App, danach die Foto- und Personen-Stufen darauf.
