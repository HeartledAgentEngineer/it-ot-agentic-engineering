# pCloud-Zugriff für den Personal AI Agent — Plan (PC + Handy, Finden + Ansehen + Routing)

> **Stand:** 15.09.2026 18:47 · **Status:** Plan/Blauplan, noch kein Code · **Basis:**
> `docs/plan-pcloud-anbindung.md` (Blauplan vom selben Tag — dort geht es um
> **Fotos + Quiz**, und er verweist auf diesen Plan zurück). Dieser Plan hier
> beantwortet die *neue* Frage: **Wie kommt
> der Agent an pCloud-Daten heran — vom PC und vom Handy — und braucht es dafür
> überhaupt die API?** Er ersetzt den Blauplan nicht, sondern schärft ihn.
>
> **Für Hermes:** Nach Sebastians Weg-Entscheidung umsetzen; jeder Schritt
> einzeln vorlegen und mit dem benannten Befehl verifizieren.

---

## 1. Ziel (was am Ende dasteht)

1. **Daten ansehen:** Der Agent kann benannte Dateien/Ordner aus der pCloud
   anzeigen (Bilder als Vorschau in der App, PDFs/Dokumente öffnen) — ohne dass
   Sebastian sie vorher aufs Handy kopiert.
2. **Daten finden:** Der Agent findet Dateien nach Name/Jahr/Ordner in der
   pCloud (`„das letzte Bild aus dem Familien-Ordner"`, `„meine Bewerbungen"`).
3. **Über die App laufen:** Treffer werden über das bestehende Backend an das
   Frontend geroutet (`GET /api/cloud/datei?pfad=…` → Bild/Datei), damit die
   PWA sie darstellen kann — egal ob das Backend auf dem Handy (Termux) oder
   auf dem PC (Track A) läuft.
4. **Von beiden Geräten aus:** PC und Handy nutzen **denselben** Cloud-Bestand,
   ohne zwei Wahrheiten (kein „nur auf dem Handy sichtbar").

**Nicht-Ziel (bleibt, wie im Brainstorming festgehalten):** kein Bulk-Import
der kompletten Fotohistorie, kein Foto-Speicher in der Wissensdatenbank
(Bilder nur in-memory für den Analyse-Call), keine Massen-Gesichtserkennung.

---

## 2. Die Kernfrage: Braucht es überhaupt die API?

**Kurzantwort: für den PC nein, fürs Handy ja — und fürs *Suchen* lohnt sie
auf beiden.**

Der entscheidende Befund von heute: **Auf dem PC läuft der pCloud-Client
bereits und stellt die Cloud als Laufwerk `P:\` bereit.** Damit ist der
PC-Zugriff schon da, ohne eine Zeile API-Code.

| Zugriffszweck | PC (`P:\`) | Handy (Termux) |
|---|---|---|
| Ordner/Dateien **auflisten + ansehen** | ✅ funktioniert sofort (Listing 0,08 s gemessen) | ❌ kein Mount — Android-pCloud-App legt keinen gespiegelten Ordner an |
| Datei **öffnen/weitergeben** | ✅ normaler Pfad `P:\…` | ❌ nur über API/rclone |
| **Suchen** (Name/Jahr/Unterordner) | ⚠️ nur punktuell — rekursives Scannen läuft in den Timeout (belegt, s. §3) | ❌ |
| **Krypto-Ordner** | 🚫 `Permission denied` (E2E-verschlüsselt) | 🚫 über API ebenfalls nicht |
| **Dauerbetrieb/automatisch** | ⚠️ nur wenn Client läuft + eingerastet | ❌ |

Daraus folgt die Aufteilung:
- **Ansehen/Öffnen am PC:** `P:\` reicht → **keine API nötig.**
- **Finden:** Metadaten-Suche gehört in die **API bzw. rclone** (Listings sind
  billig, rekursives Durchlaufen eines Streaming-Laufwerks ist es nicht).
- **Handy:** ohne **API** (rclone-Backend oder pCloud-REST) kommt der Agent
  nicht an die Cloud — es gibt dort schlicht keinen Mount.

---

## 3. Ist-Stand (am 15.09.2026 auf diesem Gerät gemessen, nicht behauptet)

| Prüfung | Ergebnis | Beleg |
|---|---|---|
| pCloud-Client auf dem PC | **läuft** (`pCloud.exe`, PID vorhanden) | `tasklist \| grep -i pcloud` |
| Cloud als Laufwerk | **`P:\` gemountet** — virtuelle Laufwerke erscheinen nicht in `wmic logicaldisk`, sind aber im Shell-Root da | `ls /p` |
| Inhalt `P:\` | `Bilder & Videos`, `Dokumente`, `Studium`, `Duales Studium (Kahl)`, `Musik`, `Meine Hörbücher`, `RAG_Documents`, `WhatsApp Chats`, `Crypto Folder`, `pCloud Backup`, `Automatic Upload`, `Google Exports`, außerdem **`workspace agentic engineering`** (d. h. Teile des Workspace liegen selbst in der Cloud) | `ls -1 /p` |
| Foto-Unterordner (für den Quiz-Slice) | `Familie`, `Freunde`, `Lieblingsbilder`, `Ausflüge`, `Kochen mit Oma`, `Konzerte_Party`, `BFD 18-19`, `Bilder von Heike`, … | `ls -1 "/p/Bilder & Videos"` |
| **Einzel-Listing-Geschwindigkeit** | **0,08–0,19 s** → `P:\` ist alltagstauglich | `time ls -1 …` |
| **Rekursives Scannen** | **Timeout nach 180 s** (`find "Bilder & Videos" -maxdepth 2`) → Streaming-Laufwerk, jede Ebene kostet Netzzugriffe | Timeout-Exit 124 |
| **Crypto Folder** | **`Permission denied`** über `P:\` → für den Agenten unlesbar (richtig so) | `ls -1 "/p/Crypto Folder"` |
| rclone auf dem PC | **nicht installiert** (aber `winget` vorhanden → Installation trivial) | `command -v rclone` |
| rclone/jq auf dem Handy (Termux) | laut Blauplan vom 15.09.: `rclone v1.74.3-termux` + `jq 1.8.2` installiert, Backend `pcloud` vorhanden, **kein Remote konfiguriert** | `docs/plan-pcloud-anbindung.md` §2 — *im Termux gegenprüfen* |
| Backend-Dateisuche heute | `backend/app/services/datei_suche.py` kennt **nur** lokale Wurzeln (`~/storage/shared`, `/sdcard`), hart verdrahtet in `_STORAGE_BASIS`/`_FALLBACK_WURZELN`; max. Tiefe 3, nur Namen, max. 30 Treffer | Code-Read |
| Vorhandene Abhängigkeiten | `httpx` + `Pillow` stehen in `backend/requirements.txt` → **kein neues Paket nötig** für den REST-Weg | Blauplan §2 |
| Prüfbefehl des Projekts | `cd backend && .venv/Scripts/python -m pytest tests/ -q` → **208 passed**, Exit 0 | `02_Softwareentwicklung_IT/CLAUDE.md` |

---

## 4. Die drei Zugangswege

### Weg A — `P:\` am PC (kein neuer Code, sofort verfügbar)

Der Agent (PC-Hermes, Track A) liest `P:\…` wie jeden lokalen Pfad.
**Regel dabei: nur punktuell arbeiten** — ein Listing oder eine Datei, nie
rekursiv (Timeout-Beleg oben). Für „zeig mir Ordner X" und „öffne Datei Y"
ist das der kürzeste Weg.

- **Vorteil:** null Aufwand, volle Datei-Auswahl inkl. Dokumente/PDF.
- **Nachteil/Grenzen:** PC muss an sein und der Client laufen; kein Index,
  daher langsame Suche; **Crypto Folder bleibt gesperrt**; pCloud-Streaming
  darf keine großen Dateien in den Speicher ziehen.
- **Sicherheit:** `P:\` ist **außerhalb** des Repos → nichts wandert per
  Zufall in einen Commit.

### Weg B — rclone auf Termux (`pcloud:`-Remote, Handy-Zugriff)

`rclone` bringt das pCloud-Backend fertig mit und macht OAuth im Browser.
Zwei Betriebsarten:

1. **Spiegel** eines ausgewählten Ordners (`rclone copy pcloud:/Familie
   ~/pcloud_mirror/Familie --max-age 365d --max-size 20M`) → danach ist
   `~/pcloud_mirror` eine zweite Wurzel für die bestehende `datei_suche` →
   EXIF-Jahr, Miniaturen, Quiz, Gesichts-Embeddings funktionieren ohne Umbau.
2. **Ohne Spiegel:** `rclone lsjson pcloud:/… --recursive` liefert eine
   **Dateiliste mit Namen/Größe/Datum in Sekunden** (Netz-Metadaten statt
   Streaming-Traversierung) → genau das, was `P:\` beim Scannen nicht kann.

- **Vorteil:** ein Werkzeug, beide Zwecke (Spiegel + Metadaten-Suche), kein
  Backend-Code, Speicher per `--max-age`/`--max-size` beherrschbar.
- **EU-Region-Pitfall (verifiziert in der rclone-Doku/-Quelle):** Bei einem
  EU-Account muss der Hostname `eapi.pcloud.com` gesetzt sein (Standard ist
  `api.pcloud.com`, US) — sonst „token error" beim Authorisieren. Bei
  deutschen Accounts daher: `rclone config` → *Edit advanced config* →
  hostname = `eapi.pcloud.com`. Gegenprobe: `rclone about pcloud:`.
- **Token-Ablage:** `~/.config/rclone/rclone.conf` liegt außerhalb des Repos —
  nie kopieren, nie committen, nie in einen Fremd-LLM-Prompt geben.

### Weg C — pCloud-REST im Backend (fürs Routing in die App)

`https://eapi.pcloud.com/…` (EU) bzw. `api.pcloud.com` (US), JSON, Token-Auth,
`httpx` ist schon da:

- neu: `backend/app/services/pcloud_service.py` (`listfolder`, `getfilelink`,
  `getthumbs`, Filter nach Name/Jahr),
- neu: `backend/app/router/cloud.py`
  - `GET /api/cloud/status` — erreichbar? Region? Kontingent?
  - `GET /api/cloud/suche?q=…&jahr=…` — Namens-/Datumsfilter, liefert Pfade
    **plus** kleine Thumbnails (`getthumbs`) statt Originale,
  - `GET /api/cloud/datei?pfad=…` — liefert die Datei an das Frontend,
  - `POST /api/cloud/quiz/start` — Quiz aus Cloud-Ordner (deckt sich mit dem
    bestehenden Blauplan),
- Token in `backend/.env` als `PCLOUD_TOKEN=…` → greift in `app/config.py`
  (Settings ohne `env_prefix`), `.env` ist per `.gitignore` draußen,
- Auth: **OAuth 2.0** (App bei pCloud registrieren, `authorize` →
  `oauth2_token`; pCloud-Tokens laufen laut Doku nicht ab) als Endbetrieb;
  `getauth=1` (Passwort im Klartext im Aufruf) **nur einmalig** zum
  Token-Holen, nie speichern.

- **Vorteil:** Handy + PC bekommen **denselben** Endpunkt; nichts wird
  gespiegelt; Thumbnails statt Original-Downloads.
- **Nachteil:** echte Programmierarbeit (Client, Fehlerbehandlung,
  Netzabhängigkeit pro Zugriff) und der Token ist ein weiteres Secret.

---

### 4a. Zugang: wie kommt der Schlüssel her? (an der Quelle verifiziert)

Drei Wege — einer ist der richtige:

| Weg | Ablauf | Bewertung |
|---|---|---|
| **OAuth 2.0 (empfohlen)** | App im Developer-Bereich registrieren (`docs.pcloud.com/my_apps/`, HTTP 200 geprüft) → `client_id` + `app_secret`. Dann Browser-Aufruf `https://my.pcloud.com/oauth2/authorize?client_id=…&response_type=code` → Code anzeigen lassen → Code gegen `access_token` tauschen (`oauth2_token`). **Belegt** im offiziellen JS-SDK `examples/node/token.js`; pCloud-Tokens laufen laut Doku nicht ab | Einmal einrichten, dauerhaft nutzbar, **kein Passwort gespeichert** — das ist die Endbetriebs-Variante |
| **Passwort-Login (`getauth=1`)** | `GET /userinfo?getauth=1&username=…&password=…` → liefert ein `auth`-Token. rclone kann genau das (die Config hat `username`/`password`-Felder, im Quellcode belegt) | Schnellster Test — aber das **pCloud-Passwort steht im Aufruf/Config**: nur **einmalig zum Token-Holen**, nie dauerhaft speichern |
| **Token aus pCloud-Client/App übernehmen** | vorhandenes Geräte-Token weiterverwenden | pragmatisch, aber fremdes Token + Ablaufrisiko (`expire_inactive`) → nicht für den Endbetrieb |

**Angenehmer Nebeneffekt:** rclone nutzt exakt denselben OAuth-Weg (eigener
localhost-Redirect `127.0.0.1:53682`, laut rclone-Doku) — wir können den Token
also **über rclone holen** und danach im eigenen Client verwenden. Kein Zwang,
eine zweite App zu registrieren.

**Sicherheit:** Token ausschließlich in `backend/.env` (`PCLOUD_TOKEN=…`), nie
im Frontend, nie in einem Commit, nie in einem Fremd-LLM-Prompt.

### 4b. Explorer-Mapping: unsere App als Datei-Browser

Das ist die verifizierte Bausteinliste (Methodennamen aus dem offiziellen
`pCloud/pcloud-sdk-js` und aus `rclone/backend/pcloud/pcloud.go` — nicht
geraten):

| Explorer-Funktion | pCloud-Methode | Neuer Backend-Endpunkt |
|---|---|---|
| Ordner öffnen, Baum/Liste zeigen | `listfolder(folderid)` → `metadata` (Einträge mit `folderid`/`fileid`, `name`, `size`, `created`, `isfolder`) | `GET /api/cloud/liste?folderid=0` |
| Vorschaubilder (Galerie/Grid) | `getthumbs(fileids, size, type)` — im SDK `32x32` / `120x120`, Typ `png`/`jpg` | `GET /api/cloud/thumb?fileid=…` |
| Bild/Datei öffnen | `getfilelink(fileid)` → temporäre Download-URL; `downloadfile` | `GET /api/cloud/datei?fileid=…` |
| Wer bin ich? (Region, Kontingent) | `userinfo` | `GET /api/cloud/status` |
| Suchen (Name/Jahr) | `listfolder` rekursiv bzw. rclone `lsjson pcloud:/… --recursive` | `GET /api/cloud/suche?q=…&jahr=…` |

**Zwei Dinge, die man dabei wissen muss:**

1. pCloud adressiert seinen Baum über **IDs** (`folderid`/`fileid`), nicht über
   Pfade — genau wie ein Explorer: Klick auf einen Ordner → dessen `folderid` →
   nächste Liste. Pfad-Zugriff (`path=…`) gibt es zusätzlich, ist aber bei
   Umbenennungen und mehrfachen Namen fehleranfälliger.
2. **Am Handy gibt es kein Mount als Explorer-Ersatz:** `rclone mount` braucht
   FUSE, das ist in Termux ohne root nicht praktikabel. Deshalb gilt:
   - **PC:** `P:\` **ist** der Explorer (Client macht die Arbeit).
   - **Handy/App:** der **REST-Client ist der Explorer** (4b) — deshalb ist
     dieser Weg für „Explorer-Feeling in unserer App" nicht optional.
   - rclone bleibt auf dem Handy das Werkzeug für schnelle **Metadaten-Suche**
     und den optionalen Spiegel — nicht für die Bedienoberfläche.

---

### 4c. Was „REST-Client" konkret heißt (und warum er dein Android-Problem löst)

Ein **REST-Client** ist hier nichts Großes: ein kleines Python-Modul in unserem
Backend (`pcloud_service.py`), das per `httpx` **normale HTTP-Anfragen** an
pCloud schickt — so wie der Browser eine Adresse aufruft. Nur kommt keine
Webseite zurück, sondern **JSON**: ein Datenpaket mit Ordnern, Dateien und ihren
IDs. **Kein Laufwerk, kein Mount, kein Dateisystem-Treiber** — nichts, was
Android einschränken könnte. Es ist Internet + Token.

Genau deshalb passt er zu deinem Fall:

* **Android braucht kein Laufwerk.** Der Client läuft in Termux/Python — dort,
wo das Backend ohnehin läuft. Was Android verbietet (Mounts, Laufwerke über
Apps hinweg), wird gar nicht erst gebraucht.
* **Dein „Share"/Auto-Upload bleibt unberührt.** Der automatische Foto-Upload
(`P:\Automatic Upload`) arbeitet weiter wie bisher — der Agent liest nur
zusätzlich.
* **Ein Client, beide Geräte:** derselbe Code läuft im Handy-Backend (Termux)
und im PC-Hermes.

### 4d. pCloud als flexibler Speicher — was der Agent tun kann (alles belegt)

| Was du willst | Methode | Bedeutung |
|---|---|---|
| Dateien/Ordner **lesen** | `listfolder(folderid)` | Liste + Metadaten, durchklickbar |
| **Bilder ansehen** | `getthumbs(fileids, size)`, `getfilelink(fileid)` | Vorschau-Gitter bzw. Original-Link |
| **Hochladen** | `uploadfile(folderid, datei)` | Datei in einen Cloud-Ordner legen |
| **Schreiben/Ordnen** | `createfolder`, `renamefile`, `renamefolder`, `movefile`, `movefolder` | anlegen, umbenennen, verschieben |
| **Aufräumen** | `deletefile` / `deletefolder` → **Papierkorb** (rclone-Doku) | nichts ist sofort weg |
| Wer bin ich / Platz | `userinfo` | Konto, Region, Kontingent |

**Die ehrliche Sicherheitskante:** Der belegte OAuth-Ablauf kennt **keinen
Scope** — er übergibt nur `client_id`, `redirect_uri`, `response_type`. Der
Token darf also **alles**; „nur Lesen" ist bei pCloud eine **Regel in unserem
Code**, keine technische Sperre. Deshalb gilt für den Client:

1. **Standard = Lesen.** Schreiben nur, wenn der Auftrag es ausdrücklich sagt.
2. **Schreiben zuerst nur in einen eigenen Ordner** (Vorschlag: `Agent/` in der
pCloud) — nie direkt in `Familie`, `Bewerbungen`, `Dokumente`.
3. **Umbenennen/Verschieben/Löschen ändert deine Daten → Rückfrage**
(Autonomiegrenze: fremdes System). Löschen landet im Papierkorb, ist also
umkehrbar — trotzdem Bestätigung.
4. **Nichts überschreiben:** `nopartial=1` im Aufruf (im SDK belegt) und vorher
auf Namensgleichheit prüfen.

---

### 4e. Verwandtschaft mit MCP (und wann daraus ein MCP-Server wird)

Bausteine von MCP (Spec-Fassung 2025-06-18, verifiziert): **JSON-RPC 2.0** in
UTF-8, Transport entweder **stdio** (stdin/stdout) oder **Streamable HTTP**
(POST, optional Server-Sent-Events-Stream). Rollen: **Host** (die LLM-App) →
**Client** (Connector im Host) → **Server** (der Tool-Anbieter). Ein Server
bietet **Tools / Resources / Prompts** an, abfragbar zur Laufzeit
(`tools/list`), aufgerufen über `tools/call`. Auth kennt das Protokoll nicht —
sie hängt am Transport: **OAuth 2.1 / `Authorization: Bearer …`**.

| | pCloud-REST (unser Client) | MCP-Server |
|---|---|---|
| **Richtung** | **wir rufen** — das Backend ist der Client, pCloud der Server | **man ruft uns** — Harness/LLM ist der Host, wir sind der Server |
| **Format** | pCloud-eigenes JSON (`result`-Code + Nutzdaten) | JSON-RPC 2.0 (`method`/`params`/`result`) |
| **Werkzeugliste** | fest und dokumentiert | zur Laufzeit über `tools/list` |
| **Auth** | pCloud-OAuth-Token (läuft nicht ab, **kein Scope**) | am Transport: Bearer/OAuth 2.1 |
| **Wer entscheidet zu rufen** | unser Code | **das Modell** (Tool-Beschreibungen liegen im Kontext) |

Gemeinsam ist beiden: **HTTP + JSON + Token**. Der Unterschied ist die
**Richtung** — und wer die Entscheidung trifft.

**Konsequenz (Upgrade-Pfad):** Derselbe pCloud-Zugriff lässt sich als **eigener
MCP-Server** verpacken (`pcloud_mcp`, JSON-RPC 2.0 über **stdio** — das passt
zu Phone-First: kein offener Port, genau wie die n8n-Bridge in Hermes). Dann
stehen die Cloud-Werkzeuge **jedem MCP-fähigen Host** zur Verfügung (Hermes
kann MCP-Server einbinden), und das Modell entscheidet selbst, wann es
Cloud-Daten zieht — das ist der „Tool-Enabled statt Button"-Gedanke aus dem
Agent-Skill, nur standardisiert.

---

## 5. Empfehlung (gestaffelt, kleinster Schritt zuerst)

**Stufe 1 — PC-Ansehen über `P:\` (heute machbar, 0 Code).**
Nachweis: `ls -1 /p` und `time ls -1 "/p/Bilder & Videos"` (< 1 s) laufen;
der Agent darf in einem Dialog einen Ordnernamen nennen und eine Datei
anzeigen. Dazu die Regel festschreiben: **`P:\` nie rekursiv scannen.**

**Stufe 2 — Handy-Zugriff über rclone** (aus dem Blauplan, jetzt schärfer):
Remote konfigurieren (EU-Hostname beachten), dann **zuerst Listing**
(`rclone lsjson pcloud:/Familie --recursive`), erst danach ein bewusster
**Spiegel** eines Testordners. Ergebnis: `datei_suche` bekommt eine zweite
Wurzel — additive Änderung, kein Umbau.

**Stufe 3 — REST-Client im Backend = der Explorer in unserer App** (§4b),
wenn *Ordner durchklicken*, *Suchen im Chat* und *Routing in die App* kommen
sollen: `pcloud_service` (listfolder/getthumbs/getfilelink) ersetzt/ergänzt die
Streaming-Traversierung, weil Metadaten-Suche über die API in Sekunden geht.
Voraussetzung ist der Token aus Stufe 2. Einzeln vorlegen, Prüfbefehl 208 grün
halten.

**Stufe 3b — Schreiben/Sortieren** (erst nach Stufe 3, weil es dieselben
Endpunkte nutzt): `uploadfile`, `createfolder`, `renamefile`/`movefile` — streng
nach den vier Regeln aus §4d. Reihenfolge: erst **hochladen in `Agent/`**
(harmlos + umkehrbar), dann **sortieren**, Löschen zuletzt und nur mit OK.
Prüfbefehl wie in Stufe 3 (`208 passed`).

**Stufe 3c — pCloud-Tools als MCP-Server** (optional, danach): `tools/list`
liefert `cloud_liste`, `cloud_thumb`, `cloud_datei`, `cloud_suche`,
`cloud_upload`; Transport **stdio**. Sinnvoll erst nach Stufe 3 — der
MCP-Server soll denselben `pcloud_service` nutzen, keine zweite
Implementierung.

**Stufe 4 (optional) — Nachtlauf:** `rclone copy` + Hinweis im Auftragsbuch
(„12 neue Fotos gespiegelt") — deckt „automatisiert Bilder/Urlaube".

---

## 6. Routing in die App (wie „Termux oder PC" zusammenläuft)

Ein Endpunkt-Satz, zwei Gastgeber:

| Gastgeber | Datenquelle | Wann |
|---|---|---|
| Handy-Backend (Termux, `http://127.0.0.1:8080`) | rclone (Listings/Spiegel) bzw. REST | unterwegs, PC aus |
| PC-Hermes (Track A, Port 8642) | `P:\` + REST | PC an, volle Power |

Das Frontend redet **nur** mit dem lokalen Backend (`X-API-Key`), das Backend
holt die Cloud-Datei und liefert sie als Bild/Bytes aus — so bleibt der
API-Key auf dem Gerät (`CLAUDE.md`: „API-Key wird NIE an den Client") und die
Regel „Bilder nur flüchtig anzeigen, nie speichern" bleibt einhaltbar.

---

## 7. Datenschutz — die harten Kanten

1. **ZDR-Riegel serverseitig:** Läuft ein Cloud-Foto durch Vision/Quiz, geht es
   an den Vision-Anbieter. Die ZDR-Prüfung gehört in den Endpunkt, nicht nur in
   die Modell-Auswahl im Frontend.
2. **Bilder nie ablegen:** Analyse nur in-memory, danach verwerfen — kein
   Kopieren in `uploads/`, `chroma_data/` oder die Wissensdatenbank.
3. **Spiegel-Ordner + Token außerhalb des Repos** (`~/pcloud_mirror`,
   `~/.config/rclone/`) und in `.gitignore` dokumentiert.
4. **Crypto Folder ist tabu** — über `P:\` verifiziert gesperrt; nicht
   versuchen, ihn über die API zu öffnen.
5. **`P:\` enthält sensible Ordner** (`Bewerbungen`, `Gesundheit_Krankenkasse`,
   `Barclays`, `WhatsApp Chats`): Der Agent darf dort lesen, aber Pfade/Inhalte
   daraus **nie** an einen Fremd-LLM (Codex/Claude) weitergeben — nur Code
   fließt raus (Skill `ai-datenschutz-regeln`).
6. **Schreiben nur nach Regel (§4d):** Lesen ist der Standard; Hochladen in den
   eigenen `Agent/`-Ordner ist erlaubt; **Umbenennen/Verschieben/Löschen** nur
   nach deiner Bestätigung (fremdes System = Rückfrage).

---

## 8. Risiken

| Risiko | Grad | Gegenmittel |
|---|---|---|
| Rekursives Scannen über `P:\` hängt den Agenten (belegt: 180-s-Timeout) | **Hoch** | Regel „nur punktuell"; Suche über rclone/API-Listings |
| Privates Foto/Token landet im Portfolio-Repo / bei einem Fremd-LLM | **Hoch** | nur ausgewählte Pfade, `git status` vor Commit, Secrets in `.env`, Bilder in-memory |
| Vision-Anbieter erhält Familien-/Urlaubsfotos | Mittel | ZDR-Riegel serverseitig, Thumbnails statt Originale |
| Speicher voll (Handy/256 GB) durch Spiegel | Mittel | `--dry-run`, `--max-age`, `--max-size`, nur Testordner |
| EU/US-Hostname verwechselt → „token error" | Gering | `eapi.pcloud.com` bei EU, Gegenprobe `rclone about pcloud:` |
| pCloud drosselt viele Aufrufe (REST) | Gering | Thumbnails, Ergebnisse cachen, Batch-Listings statt Einzelabrufe |
| PC-Client nicht eingeloggt/Laufwerk weg | Gering | `GET /api/cloud/status` prüft Erreichbarkeit, Stufe 2/3 als Fallback |

---

## 9. Schritt-für-Schritt (jeder Schritt mit Prüfbefehl)

**S1 — PC-Ansehen (0 Code):**
```bash
ls -1 /p                                    # rc 0, Ordnerliste
time ls -1 "/p/Bilder & Videos"             # < 1 s (Streaming-Beweis)
ls -la "/p/Bilder & Videos/Familie" | head  # Ordner punktuell
```
Fertig, wenn die Listings schnell sind und der Agent daraus einen Ordner
benennen/öffnen kann.

**S2 — Handy: Remote prüfen, dann listen, dann spiegeln:**
```bash
# im Termux
rclone listremotes                          # vorher: leer
rclone config                               # Name pcloud, Typ pcloud, EU → hostname eapi.pcloud.com
rclone about pcloud:                        # rc 0 = Token + Region stimmen
rclone lsjson pcloud:/Familie --recursive   # Dateiliste (Metadaten, schnell)
rclone size pcloud:/Familie                 # Datei-/Byte-Zahl statt Bauchgefühl
rclone copy --dry-run pcloud:/Familie ~/pcloud_mirror/Familie --max-size 20M
```
Fertig, wenn `about` rc 0 liefert und `lsjson` eine plausible Anzahl zeigt.

**S3 — `datei_suche` um die zweite Wurzel erweitern (kleine, additive Änderung):**
Erst nach S2; Prüfbefehl danach zwingend:
```bash
cd backend && .venv/Scripts/python -m pytest tests/ -q   # 208 passed, Exit 0
```

**S4 — REST-Client (`pcloud_service.py` + `router/cloud.py`)** — einzeln
vorlegen, gleicher Prüfbefehl zwingend, plus DeepSeek-Testcall der Suche.

---

## 10. Offene Entscheidungen (an Sebastian)

1. **Reihenfolge:** S1 (PC-`P:\` ansehen) → S2 (OAuth-Token holen) → S3
   (REST-Explorer in der App) wie empfohlen — oder den Explorer vorziehen, weil
   genau das dein eigentliches Ziel ist?
2. **Testordner für den Spiegel:** `Bilder & Videos/Familie` (passt zum
   Quiz-Slice) oder ein anderer?
3. **Suchen oder Ansehen zuerst?** Ansehen kostet (am PC) heute 0 Code,
   Suchen kostet den rclone- bzw. REST-Weg.
4. **Region:** Ist der Account EU (dann `eapi.pcloud.com`)? Gegenprobe über
   `rclone about pcloud:` nach dem Login.
5. **Dokumente mitnehmen?** `P:\Dokumente` (PDF/DOCX) ist am PC sofort
   ansehbar; auf dem Handy hängt PDF-zu-Text an ARM-Fragen
   (`docs/stand-2026-08-14.md`) — jetzt oder später?
6. **Schreib-Regeln (§4d) bestätigen:** Eigener `Agent/`-Ordner als erlaubter
   Schreibbereich — und soll der Agent dort **autonom** hochladen/sortieren
   dürfen, während Umbenennen/Verschieben/Löschen immer Rückfrage bleibt?
7. **MCP-Variante (§4e):** erst den internen REST-Weg (Stufe 3) gehen und
   MCP später draufsetzen — oder gleich als MCP-Server bauen, damit auch
   Hermes und andere Harnesses die Cloud-Werkzeuge selbst aufrufen können?

*Dieser Plan ist Doku, kein Code — der Code folgt nach der Weg-Entscheidung,
jeder Schritt einzeln vorgelegt und verifiziert.*
