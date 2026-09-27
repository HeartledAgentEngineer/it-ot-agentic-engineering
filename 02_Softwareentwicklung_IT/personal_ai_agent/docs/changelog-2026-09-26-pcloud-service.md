# pCloud-Service + `/api/cloud`-Routen — nur lesend, mit Tests und echtem Rauchtest

> **Datum:** 26./27.09.2026 · **Auftrag:** Sebastian: nach dem Token-Zugang
> (siehe `docs/changelog-2026-09-26-pcloud-zugang.md`) die dort angekündigte
> nächste Stufe — Dienst + Endpunkte zum **Lesen** der pCloud, „ohne etwas an
> der pCloud zu verändern".

## Warum

Der Agent soll Dateien der pCloud sehen können (Kontostand, Ordnerliste,
Namenssuche, Vorschaubilder, einzelne Dateien), ohne den pCloud-Client auf
dem PC und ohne das Laufwerk `P:\` zu scannen (ein `P:\`-Scan lief nach 180 s
in ein Timeout). Dieser Schritt liefert **nur den Lesezugriff** — der
Explorer/Menüpunkt in der App kommt darauf auf.

## Was neu ist

| Datei | Art | Inhalt |
|---|---|---|
| `backend/app/services/pcloud_service.py` | neu | `PCloudService` — lesender API-Zugriff via httpx |
| `backend/app/router/cloud.py` | neu | `GET /api/cloud/status`, `/liste`, `/suche`, `/thumb`, `/datei` |
| `backend/app/main.py` | geändert | Router registriert — **gleicher Key-Schutz** (`require_api_key`) wie alle /api-Routen |
| `backend/app/config.py` | geändert | Settings `pcloud_token`, `pcloud_host` (aus `.env`: `PCLOUD_TOKEN`, `PCLOUD_HOST`, Standard `eapi.pcloud.com`) |
| `backend/.env.example` | geändert | Abschnitt „pCloud (nur lesend)" mit beiden Variablen |
| `README.md` | geändert | fünf neue Zeilen in der API-Endpunkt-Tabelle |
| `backend/tests/test_pcloud_service.py` | neu | 37 Tests, ohne Netz (httpx gemockt) |
| `backend/tests/test_pcloud_router.py` | neu | 30 Tests, ohne Netz (TestClient + Attrappen) |

### Die Endpunkte

| Endpunkt | Antwort | Besonderheit |
|---|---|---|
| `GET /api/cloud/status` | `verbunden`, `host`, `email` (**maskiert**: erste 2 + letzte 4 Zeichen), `userid`, `premium`, `email_verifiziert`, `quota_gb`, `belegt_gb`, `frei_gb` | GB dezimal wie die pCloud-Anzeige (1 GB = 1e9 Bytes) |
| `GET /api/cloud/liste?folderid=0` | `folderid`, `anzahl`, `eintraege[]` (`name`, `ist_ordner`, `folderid`, `fileid`, `groesse`, `geaendert`) | Ordner zuerst, dann Name (casefold); kein rekursiver Lauf |
| `GET /api/cloud/suche?q=…&folderid=0` | `frage`, `folderid`, `anzahl`, `treffer[]` | Namensfilter in EINEM Ordner, Gross-/Kleinschreibung egal, max. 50 Treffer |
| `GET /api/cloud/thumb?fileid=…&groesse=120x120\|32x32` | Bild-Bytes (live: `image/jpeg`, `Cache-Control: no-store`) | Medientyp aus den ersten Bytes bestimmt |
| `GET /api/cloud/datei?fileid=…` | Datei-Download (`application/octet-stream`, `Content-Disposition: attachment`) | Obergrenze **25 MB** → HTTP 413 mit Klartext |

**Fehlerverhalten** (kein Absturz, keine englischen Stacktraces):

| Lage | Status | Beispieltext |
|---|---|---|
| Kein Token konfiguriert | **503** | „pCloud ist nicht konfiguriert: In der .env des Backends fehlt PCLOUD_TOKEN …" |
| pCloud meldet `result != 0` | **502** | „pCloud meldet Fehler 2005: Directory does not exist." |
| Datei zu gross | **413** | „Datei ist 27.3 MB gross und ueberschreitet die Obergrenze von 26.2 MB. Download abgebrochen." |
| Ungültige Parameter | 422 | FastAPI-Validierung (`q` fehlt, `folderid<0`, fremde `groesse`) |

### Der eine live geprüfte Unterschied (wichtig für Nachbauten)

Die pCloud-Doku lässt offen, was `getthumbs` zurückgibt. **Live geprüft am
27.09.2026 gegen `eapi.pcloud.com`: weder rohe Bildbytes noch JSON**, sondern
**Text, eine Zeile je Datei**:

```
fileid=52643897060, type=jpg  -> 52643897060|0|86x120|data:image/jpeg;base64,/9j/4AAQ…
fileid=52643897060, type=png  -> 52643897060|5002|0
```

- `type=png` antwortet bei diesem Konto grundsätzlich mit Fehlercode **5002**
  (kein PNG-Vorschaubild). Deshalb frägt der Dienst `type=jgp` (JPEG) an.
- Die Masse sind **nicht** die angefragte Grösse, sondern die des Ergebnisses
  (Seitenverhältnis bleibt erhalten: 120x120 → 86x120).
- Der Dienst dekodiert das base64 zu Bytes und gibt sie zurück; `5002`/andere
  Codes werden zu einer klaren Meldung statt als „Bild" durchgereicht.
  Liefert ein Server doch rohe Bildbytes, kommen sie unverändert zurück.

## Regeln, die im Code gelten (nur lesend)

- Es gibt **keine** Schreib-, Umbenenn- oder Löschmethode — der Service endet
  bei `status`/`liste`/`suche`/`thumb`/`datei_bytes`.
- **Kein rekursiver Lauf**: `suche` und `liste` machen genau EIN `listfolder`
  je Aufruf; die App steigt nirgends tiefer von selbst.
- **Der Token steht nur im Request** (`auth`-Parameter) und wird nie geloggt
  oder ausgegeben. Transportfehler melden nur den Klassen-Namen (fremde
  httpx-Meldungen können die volle URL samt Token enthalten); ein
  `_ohne_geheimnis`-Filter entfernt ihn zusätzlich aus durchgereichten
  Fehlertexten. Drei Tests prüfen, dass der Token in keiner Ausgabe,
  Fehlermeldung oder Log-Zeile auftaucht.
- **E-Mail nur maskiert** (`se*******************.com`); drei Tests suchen die
  vollständige Adresse in der gesamten Antwort.
- `Crypto Folder` betritt nichts automatisch (keine Rekursion); der Rauchtest
  überspringt ihn ausdrücklich.

## Belege — ausgeführte Befehle mit echten Zahlen

### Tests (ohne Netz, httpx gemockt)

```
cd backend && .venv/Scripts/python -m pytest tests/test_pcloud_service.py -q
  -> 37 passed, 1 warning in 0.90s

cd backend && .venv/Scripts/python -m pytest tests/test_pcloud_router.py -q
  -> 30 passed, 3 warnings in 5.39s

cd backend && .venv/Scripts/python -m pytest tests/ -q      (voller Prüfbefehl)
  -> 500 passed, 3 warnings in 53.16s
     (vorher 433 -> +67 neue Tests, keine bestehenden gebrochen)
```

Abgedeckt u. a.: fehlender Token → 503 + Klartext, `result != 0` → Fehlertext
durchgereicht, unbekannter Ordner (2005), leere Liste, E-Mail-Maskierung,
50-Treffer-Grenze, Groessen-Obergrenze (laut Link UND beim Laden), Zweit-Host
beim Download, Token nie in Ausgabe/Log, Key-Schutz aller fünf Routen,
Medientyp aus den Bild-Bytes.

### Echter Rauchtest gegen die echte API (nur gelesen)

Skript im Scratch-Verzeichnis (nicht im Repo):
`…\hermes\cache\scratch\pcloud_rauchtest.py`, gestartet mit der venv des
Backends. Ausgabe (gekürzt, exakt so gelaufen):

```
=== 1) Konfiguration ===
konfiguriert: True   Host: eapi.pcloud.com

=== 2) status() ===
email (maskiert): se*******************.com
userid: 4738912   premium: True   email_verifiziert: True
quota_gb: 2199.0   belegt_gb: 390.5   frei_gb: 1808.5        (Dauer 0.48 s)
roh: quota=2199023255552 Bytes (/1e9=2199.0 — die 1024^3-Spalte zeigt 2048.0,
     die Anzeige rechnet dezimal)

=== 3) liste(0) ===
Anzahl: 18 (17 Ordner, 1 Datei), Dauer 0.20 s — sortiert:
  [D] Automatic Upload / Bilder & Videos / Crypto Folder / Dokumente
      / Duales Studium (Kahl) / Google Drive …

=== 3b) suche('bild', 0)  (Zusatzprobe) ===
1 Treffer ("Bilder & Videos"); 'BILD' liefert dieselbe Zahl (Gross/Klein egal)

=== 4) thumb() ===
Bild: 059956_2024-08-09_17-14-43_96.jpg (fileid=52643897060, 2 144 391 Bytes)
thumb(120x120): 4185 Bytes, image/jpeg, 0.17 s, erste Bytes ffd8ffe0
thumb(32x32):   1004 Bytes, image/jpeg, 0.23 s, erste Bytes ffd8ffe0

=== 5) Zusatzprobe: unbekannter Ordner ===
pCloudFehler wie erwartet: pCloud meldet Fehler 2005: Directory does not exist.

Fertig. Es wurde nichts geschrieben, nichts umbenannt, nichts geloescht.
```

Damit ist **Lesen live bewiesen**: Kontostand (2199,0 GB / belegt 390,5 GB),
18 Wurzel-Einträge, echte Vorschaubilder als JPEG, ehrlicher Fehlertext.

## Was NICHT geprüft wurde

- **`datei_bytes()` (echter Download)** — nur mit Attrappen getestet
  (`getfilelink` → `hosts`/`path`, Streaming, Zweit-Host, 25-MB-Grenze).
  Es wurde **keine echte Datei heruntergeladen** (kein Verbrauch, keine
  Wartezeit). Die 413-Antwort ist live ebenfalls ungeprüft.
- **Schreiben ist nirgends implementiert und daher auch nicht getestet** —
  es gibt keine Schreib-/Umbenenn-/Löschfunktion, auch nicht versteckt.
- **Die HTTP-Endpunkte wurden nicht live über einen laufenden Server
  aufgerufen** (nur über `TestClient` mit gemocktem httpx + live über den
  Service). Frontend hat noch keine Cloud-Seite.
- **Die 50-Treffer-Grenze wurde live nicht ausgelöst** — die Wurzel hat nur
  18 Einträge; die Grenze ist per Test belegt, nicht per Live-Daten.
- **Kein Live-Test auf dem Handy/Termux.** Dort fehlt der Token bis zur
  manuellen Übertragung (Regel: Geheimnisse nicht per Git).
- **Bedeutung von Fehlercode 5002** ist nicht dokumentiert; statt zu raten
  frägt der Dienst `type=jgp` an (funktioniert live) und meldet 5002 als Text.

## Was unsicher bleibt

- **Der Token gehört zum PC-Client.** Meldet der Client sich ab oder rotiert
  pCloud, stirbt der Zugang — Selbstheilung: `tools/pcloud/pcloud_token_erneuern.py`.
- **Vorschaubilder sind langsam** (0,17–0,23 s je Bild, kein Cache — bewusst
  `Cache-Control: no-store`). Für Bildlisten in der App sollte später über
  einen kleinen Zwischenspeicher entschieden werden.
- **`datei_bytes` liefert `application/octet-stream` ohne Dateinamen** —
  `getfilelink` liefert keinen verlässlichen Namen; die Oberfläche müsste ihn
  aus der `liste`-Antwort nachreichen.
- Die pCloud-Doku nennt `jgp` als Typ; live verhalten sich `jpg`/`jpeg`/`jgp`
  identisch. Falls pCloud das ändert, bricht nur `thumb()` — nicht `liste`/`status`.
