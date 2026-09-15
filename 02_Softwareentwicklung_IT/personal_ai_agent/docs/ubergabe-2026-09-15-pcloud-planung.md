# Übergabe: pCloud-Anbindung — Planungsstand

> **Datum:** 15.09.2026 · **Von:** Hermes-Session (Desktop, PC) ·
> **Zweck:** Damit eine weitere Session (Hermes auf dem Handy/Termux, Codex,
> ein anderer Rechner) **ohne neue Recherche** weiterarbeiten kann. Alles unten
> ist **verifiziert** — mit dem Beleg daneben. Diese Datei ersetzt aber nicht das
> Denken: sie liefert die Fakten und die Entscheidungslogik, nicht den Code.

---

## 0. Auf einen Blick (TL;DR)

* **Frage der Session:** pCloud an den Agenten anbinden — vom PC **und** vom
  Handy, Daten ansehen, finden, und über die App routen. **Braucht es die API?**
* **Antwort:** **Am PC nein** — der pCloud-Client liefert die Cloud schon als
  Laufwerk `P:\`. **Am Handy ja** — Android hat kein Mount, und
  `rclone mount` braucht FUSE (in Termux ohne root nicht praktikabel).
  **Fürs Suchen ja** — Metadaten-Listen sind billig, Streaming-Traversierung ist tödlich.
* **Zugang:** **OAuth 2.0** (App registrieren → Browser-Login → `access_token`,
  läuft laut Doku nicht ab). Achtung: **kein Scope** — der Token darf alles.
* **Zielbild:** Explorer in der eigenen App über REST
  (`listfolder` / `getthumbs` / `getfilelink`) — plus optional Upgrade zum
  **eigenen MCP-Server** `pcloud_mcp` (JSON-RPC 2.0 über stdio, kein offener Port).
* **Stand:** Nur **Doku/Plan**, **kein Code**, **kein Token geholt**, **kein Push**
  (Commits liegen lokal — s. §7).

---

## 1. Verifizierte Fakten (bitte NICHT neu recherchieren)

| Befund | Beleg |
|---|---|
| pCloud-Client läuft auf dem PC | `tasklist \| grep -i pcloud` → `pCloud.exe` |
| Cloud liegt als **Laufwerk `P:\`** bereit | `ls -1 /p` → `Bilder & Videos`, `Dokumente`, `Studium`, `Musik`, `RAG_Documents`, `WhatsApp Chats`, `Crypto Folder`, `Automatic Upload`, … |
| Foto-Unterordner fürs Quiz | `/p/Bilder & Videos/` → `Familie`, `Freunde`, `Lieblingsbilder`, `Ausflüge`, `Kochen mit Oma`, `Konzerte_Party`, `BFD 18-19`, `Bilder von Heike` |
| **Einzel-Listing schnell** (alltagstauglich) | `time ls -1 "/p/Bilder & Videos"` → **0,08 s** |
| **Rekursives Scannen = Timeout** | `find "Bilder & Videos" -maxdepth 2` → **Exit 124 nach 180 s** (Streaming-Laufwerk) |
| **Crypto Folder gesperrt** | `ls -1 "/p/Crypto Folder"` → `Permission denied` |
| rclone auf dem PC | **nicht installiert** (`winget` vorhanden) |
| rclone/jq im Termux | laut Blauplan 15.09.: `rclone v1.74.3-termux` + `jq 1.8.2` da, Backend `pcloud` vorhanden, **kein Remote konfiguriert** → im Termux gegenprüfen |
| `datei_suche.py` heute | nur lokale Wurzeln (`~/storage/shared`, `/sdcard`) **hart verdrahtet** (`_STORAGE_BASIS`, `_FALLBACK_WURZELN`), max. Tiefe 3, max. 30 Treffer, nur Namen |
| Abhängigkeiten | `httpx` + `Pillow` stehen in `backend/requirements.txt` → **kein neues Paket** für den REST-Weg |
| **Prüfbefehl des Projekts** | `cd backend && .venv/Scripts/python -m pytest tests/ -q` → **208 passed**, Exit 0 (frisch gelaufen) |
| Track A (PC-Hermes als API-Server) | `hermes config get api_server.enabled` → **„Config key not set"** → exakten Schlüsselnamen prüfen, bevor Track A als „an" gilt |
| Hermes kann MCP-Server | `hermes mcp catalog` → Katalog vorhanden (u. a. Notion, Linear, stripe; n8n als **stdio bridge, kein offener Port**) |

### pCloud-API (an der Quelle verifiziert: offizielles `pCloud/pcloud-sdk-js` + `rclone/backend/pcloud/pcloud.go`)

| Thema | Fakt |
|---|---|
| **Auth (sauber, empfohlen)** | `https://my.pcloud.com/oauth2/authorize?client_id=…&response_type=code` → Code → Tausch gegen Token (`oauth2_token`). **Belegt** in `examples/node/token.js`; Tokens laufen laut Doku **nicht ab** |
| **Auth (Notweg)** | `GET /userinfo?getauth=1&username=…&password=…` → `auth`-Token. Passwort im Klartext im Aufruf → **nur einmalig**, nie speichern |
| **Kein Scope!** | Der belegte OAuth-Ablauf kennt nur `client_id`, `redirect_uri`, `response_type` → der Token darf **alles**. „Nur Lesen" ist eine **Regel im Code**, keine Sperre |
| **Region** | EU-Accounts brauchen `eapi.pcloud.com` (rclone-Option `hostname`), sonst „token error" beim Login. Gegenprobe: `rclone about pcloud:` |
| **Lesen** | `listfolder(folderid)` → `metadata` (Einträge mit `folderid`/`fileid`, `name`, `size`, `created`, `isfolder`) |
| **Bilder** | `getthumbs(fileids, size, type)` (im SDK `32x32` / `120x120`, `png`/`jpg`), `getfilelink(fileid)` → temporäre URL |
| **Schreiben/Ordnen** | `uploadfile(folderid, datei)` (`nopartial=1`), `createfolder`, `renamefile`, `renamefolder`, `movefile`, `movefolder` |
| **Löschen** | `deletefile` / `deletefolder` → **Papierkorb** (rclone-Doku), nichts ist sofort weg |
| **Richtige Adressierung** | pCloud arbeitet mit **IDs** (`folderid`/`fileid`), nicht mit Pfaden — wie ein Explorer: Klick → ID → nächste Liste |
| **rclone-Methoden** | `/listfolder`, `/getfilelink`, `/userinfo`, `/checksumfile`, `/diff`, `/uploadfile`, `/oauth2_token` |

### MCP (Spec-Fassung 2025-06-18, verifiziert)

* Format **JSON-RPC 2.0**, UTF-8.
* Transport **stdio** (stdin/stdout) **oder Streamable HTTP** (POST, optional SSE-Stream).
* Rollen: **Host** (LLM-App) → **Client** (Connector im Host) → **Server** (Tool-Anbieter).
* Server bietet **Tools / Resources / Prompts**, Discovery via `tools/list`, Aufruf via `tools/call`.
* **Auth hängt am Transport** (bei HTTP: OAuth 2.1, `Authorization: Bearer …`; Discovery RFC 9728/8414). Host muss vor Tool-Aufruf/Datenweitergabe **Einwilligung** einholen.

---

## 2. Die Entscheidungslogik (damit sie nicht neu geführt wird)

| Zugriffszweck | PC (`P:\`) | Handy (Termux) |
|---|---|---|
| Auflisten + Ansehen | ✅ sofort, kein Code | ❌ |
| Datei öffnen/weitergeben | ✅ normaler Pfad | ❌ nur über API/rclone |
| Suchen (Name/Jahr) | ⚠️ nur punktuell (kein Index) | ❌ |
| Krypto-Ordner | 🚫 gesperrt | 🚫 |
| Automatisch/Nachtbetrieb | ⚠️ nur bei laufendem Client | ❌ |

* **`rclone mount` scheidet am Handy aus** (FUSE, kein root) → am Handy ist der
  **REST-Client der Explorer**, am PC ist es `P:\`.
* **rclone bleibt wertvoll** fürs Handy: `rclone lsjson pcloud:/… --recursive`
  liefert **Metadaten in Sekunden** (statt Streaming-Traversierung) und kann
  optional einen Ordner spiegeln (dann ist der Spiegel eine zweite Wurzel für
  `datei_suche` — EXIF/Quiz/Embeddings funktionieren ohne Umbau).
* **REST-Client ≠ MCP-Server — aber verwandt:** beide „HTTP + JSON + Token".
  Unterschied ist die **Richtung**: beim REST-Client **rufen wir** pCloud;
  beim MCP-Server **ruft das Modell uns**. Letzteres ist genau das
  Projektziel „**Tool-Enabled statt Button**" (Agent entscheidet selbst).
* **Explorer-Endpunkte (neu, geplant):** `GET /api/cloud/liste?folderid=…`,
  `/api/cloud/thumb?fileid=…`, `/api/cloud/datei?fileid=…`,
  `/api/cloud/suche?q=…&jahr=…`, `/api/cloud/status`.

---

## 3. Sicherheits- und Datenschutzregeln (gesetzt bzw. vorgeschlagen)

1. **Token nur in `backend/.env`** (`PCLOUD_TOKEN=…`) — nie im Frontend, nie im
   Commit, nie in einem Fremd-LLM-Prompt.
2. **Kein Scope vorhanden** → Schreibregeln gehören in den Code:
   **Standard = Lesen**; Schreiben nur, wenn der Auftrag es sagt.
3. **Schreiben zuerst nur in `Agent/`** (eigener Ordner in der pCloud) — nie
   direkt in `Familie`, `Bewerbungen`, `Dokumente`.
4. **Umbenennen / Verschieben / Löschen = Änderung an Sebastians Daten →
   Rückfrage** (Autonomiegrenze: fremdes System). Löschen landet im Papierkorb.
5. **Nichts überschreiben** (`nopartial=1`, vorher Namensgleichheit prüfen).
6. **`P:\` niemals rekursiv scannen** (belegt: 180-s-Timeout).
7. **Crypto Folder ist tabu** (verifiziert gesperrt).
8. **Bilder nur in-memory** für den Vision-Call, danach verwerfen; kein Kopieren
   in `uploads/`, `chroma_data/` oder die Wissensdatenbank.
9. **ZDR-Riegel serverseitig** (nicht nur in der Frontend-Modellauswahl).
10. **Sensible Pfade/Inhalte** (`Bewerbungen`, `Gesundheit_Krankenkasse`,
    `Barclays`, `WhatsApp Chats`, Chat-Verläufe) **nie** an Codex/Claude/OpenAI.
11. **Spiegel + Token außerhalb des Repos** (`~/pcloud_mirror`,
    `~/.config/rclone/`), in `.gitignore` dokumentiert.

---

## 4. Gestufte Umsetzung (Reihenfolge offen — s. §5)

| Stufe | Inhalt | Prüfbefehl / Nachweis |
|---|---|---|
| **S1** | PC-Ansehen über `P:\` (0 Code) | `ls -1 /p`; `time ls -1 "/p/Bilder & Videos"` < 1 s |
| **S2** | rclone im Termux: Remote anlegen (EU → `eapi.pcloud.com`), **erst listen**, dann Spiegel | `rclone about pcloud:` rc 0; `rclone lsjson pcloud:/Familie --recursive`; `rclone size pcloud:/Familie` |
| **S2b (empfohlen)** | OAuth-App registrieren + Token holen | `oauth2_token` liefert Token; `GET /userinfo`-Gegenprobe `result: 0` |
| **S3** | `pcloud_service.py` + `router/cloud.py` (**der Explorer in der App**) | `cd backend && .venv/Scripts/python -m pytest tests/ -q` → **208 passed** |
| **S3b** | Schreiben/Sortieren (`uploadfile`, `createfolder`, `renamefile`/`movefile`) nach §3 | derselbe Prüfbefehl + Testcall |
| **S3c (optional)** | `pcloud_mcp` — MCP-Server über **stdio** mit `cloud_liste`, `cloud_thumb`, `cloud_datei`, `cloud_suche`, `cloud_upload`; nutzt **denselben** `pcloud_service` | `tools/list` zeigt die Tools; Aufruf über einen MCP-Host |
| **S4 (optional)** | Nachtlauf: `rclone copy` + Hinweis im Auftragsbuch | `--dry-run` vorher, echte Zahlen |

---

## 5. Offene Entscheidungen (an Sebastian)

1. **Reihenfolge:** S1 → S2b → S3 wie empfohlen — oder den Explorer (S3) vorziehen?
2. **Testordner für den Spiegel:** `Bilder & Videos/Familie` (passt zum Quiz-Slice)?
3. **Suchen oder Ansehen zuerst?** (Ansehen am PC kostet 0 Code.)
4. **Region:** EU-Account (dann `eapi.pcloud.com`)? Gegenprobe nach dem Login.
5. **Dokumente mitnehmen?** (`P:\Dokumente`; am Handy hängt PDF-zu-Text an ARM-Fragen.)
6. **Schreib-Regeln:** Ist `Agent/` als Schreibordner ok — autonom hochladen/sortieren, aber Umbenennen/Verschieben/Löschen nur nach Rückfrage?
7. **MCP-Variante:** erst interner REST (S3) und MCP später — oder gleich als MCP-Server (S3c)?

---

## 6. Was es noch NICHT gibt (kein Code, keine Credentials)

* `backend/app/services/pcloud_service.py` — **existiert nicht**
* `backend/app/router/cloud.py` — **existiert nicht**
* `pcloud_mcp` (MCP-Server) — **existiert nicht**
* **Kein pCloud-Token** geholt, **kein rclone-Remote** konfiguriert
* Am PC: **kein rclone** installiert

---

## 7. Für die nächste Session — Startpunkt und Fallstricke

1. **Zuerst lesen:**
   * `docs/plan-pcloud-anbindung.md` — Blauplan: Fotos + Quiz (der Kern-Slice)
   * `docs/plan-pcloud-zugang-pc-und-handy.md` — Zugang, `P:\`, OAuth, Explorer, Schreiben, MCP
   * diese Übergabe
2. **Arbeitsweise des Projekts gilt weiter:** eine Änderung pro Antwort, dann
   Rückmeldung; „code + docs" in **einem** Commit; Prüfbefehl **208 passed** als Gate.
3. **Lage der Commits (wichtig!):** Die Plan-Dokumente wurden **lokal** committet —
   `69ab4a8` (Zugangsplan), `395a029` (REST-Client + Schreiben), `d674410` (MCP).
   **Es wurde NICHT gepusht.** Arbeitet die andere Session auf einem **anderen
   Klon oder Gerät** (z. B. Termux), sieht sie diese Commits erst nach einem
   **Push** (bei Sebastian bestätigen lassen — Push ist nie autonom).
4. **Nicht wieder recherchieren:** §1 enthält alle geprüften Fakten inklusive
   der Methodennamen und der Sicherheitskante „kein Scope".
5. **Falle beim Schreiben:** pCloud adressiert über **IDs**, nicht Pfade; und
   `P:\` nie rekursiv durchlaufen.

---

*Diese Übergabe ist Doku, kein Code. Sie fasst eine reine Planungs-Session
zusammen, damit die Denkarbeit nicht zweimal bezahlt wird.*
