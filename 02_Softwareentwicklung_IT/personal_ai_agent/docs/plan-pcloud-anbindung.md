# Implementierungsplan: pCloud als Datenanbindung

> **Stand:** 15.09.2026 · **Status:** Blauplan (noch kein Code) · **Anlass:**
> Sebastian möchte die pCloud als Datenquelle an den persönlichen KI-Assistenten
> anbinden, damit Fotos (Urlaube, Leben) automatisiert und das Gesichter-Quiz
> unterstützend mit Cloud-Bildern arbeiten können.
> Grundlage der Wunschliste: `brainstorm-foto-kontext.md` (Abschnitt
> „pCloud-Anbindung … eigener Slice") und `brainstorm.md` (Nice-to-have
> „Cloud-Zugriff (pCloud API)").

---

## 1. Ziel (was am Ende dasteht)

1. **Quiz aus der Cloud speisen:** Das Gesichter-Quiz soll Bilder aus einem
   pCloud-Ordner durchgehen können (Urlaubs-/Familienfotos), ohne dass Sebastian
   sie vorher aufs Handy kopiert.
2. **Bilder im Chat finden (Cloud-Suche):** „Zeig mir das Foto mit Julian bei
   den Sonnenfinsternisbrillen" → Suche in der pCloud nach Name/Datum, Anzeige
   der Treffer als Bild (Vorschau), Analyse nur auf ausdrücklichen Anhang.
3. **Zeitstufen für Gesichter erweitern:** Ältere Cloud-Fotos liefern
   zusätzliche Referenz-Embeddings (`referenzen:[{embedding,jahr}]`) — genau
   das, was der Alters-/Dekaden-Weg heute braucht (vgl. Skill-Abschnitt
   „Gesichter: Zeitstufen").
4. **Später automatisiert:** Ein Nacht-Spiegel holt neue Cloud-Fotos in einen
   lokalen Ordner, den die bestehende Pipeline schon versteht.

**Nicht-Ziel (bewusst, wie im Brainstorming festgehalten):** kein Bulk-Import
der ganzen Fotohistorie, kein Foto-Speicher in der Wissensdatenbank, keine
automatische Gesichtserkennung als Massensuchfunktion.

---

## 2. Ist-Stand (verifiziert am 15.09.2026 auf diesem Gerät)

| Prüfung | Ergebnis |
|---|---|
| Vorhandene Cloud-Anbindung | **keine** — pCloud ist bisher nur Wunsch in `brainstorm.md` / `specification.md` („MVP kann NICHT: Cloud-Zugriff") |
| Dateisuche heute | `backend/app/services/datei_suche.py` durchsucht **nur** `~/storage/shared` bzw. `/sdcard` (max. Tiefe 3, nur lesen, nur Namen) — keine Netzquelle |
| pCloud-Ordner auf dem Gerät | **kein** `/sdcard/*loud*` o. ä. Der Android-pCloud-Client legt keinen kontinuierlich gespiegelten Ordner an |
| Python | 3.13.13; `httpx` und `Pillow` stehen bereits in `backend/requirements.txt` — ein API-Client braucht **keine neue Abhängigkeit** |
| rclone / jq | **installiert am 15.09.2026**: `rclone v1.74.3-termux` + `jq 1.8.2` (`pkg install -y rclone jq`), Backend `pcloud` vorhanden. Noch **kein** Remote konfiguriert (`rclone listremotes` ist leer, `/data/data/com.termux/files/home/.config/rclone/rclone.conf` fehlt) |
| ffmpeg | vorhanden (für Miniaturen/Video-Sonderfälle nutzbar) |
| Sicherheitsnetze, die bleiben | `X-API-Key` auf allen `/api/*`-Routen, `HOST_BIND` in `.env`, `.gitignore` führt `uploads/`, `chroma_data/`, `gesichter_katalog.json`, `.env` |

**Wichtig für den Aufwand:** Nicht der Login ist die Arbeit, sondern (a) Bilder
überhaupt an den Vision-Kanal zu bekommen und (b) die vorhandene lokale
Pipeline (EXIF-Jahr, Miniaturen, Quiz, Embeddings) auf Cloud-Dateien
anzuwenden. Genau dafür gibt es zwei saubere Wege.

---

## 3. Die zwei Wege

### Weg A — rclone-Spiegel (empfohlener Einstieg)

`rclone` bringt einen fertigen pCloud-Backend mit und macht die komplette
OAuth-Prozedur im Browser für uns. Wir spiegeln **nur ausgewählte Ordner**
(z. B. `Fotos/Urlaub`) in einen lokalen Ordner.

```bash
# 1) Werkzeug holen (Termux, kein root nötig)
pkg install -y rclone jq

# 2) pCloud-Zugang anlegen (OAuth im Browser, kein Passwort in einer Datei)
rclone config create pcloud pcloud
#   → fragt nach Nutzer/Passwort bzw. öffnet den Browser-Login-Token
rclone lsd pcloud:                      # Ordner auflisten
rclone lsjson pcloud:/Fotos --recursive  # Struktur prüfen

# 3) Spiegel (nur Neues, Größen begrenzen, Papierkorb-Schutz)
rclone copy pcloud:/Fotos ~/pcloud_mirror/Fotos --max-age 365d --max-size 20M --progress
```

* **Vorteil:** fast kein neuer Code. Danach wird `~/pcloud_mirror` einfach eine
  zweite Wurzel der bestehenden `datei_suche` — **EXIF-Aufnahmejahr, Miniaturen
  (`exif_transpose` in-memory), Quiz, Gesichts-Embeddings und Zeitstufen-Refs
  funktionieren ohne Änderung.**
* **Nachteil:** es liegt eine Kopie auf dem Gerät (Speicherplatz — 256-GB-SSD
  bzw. Handy-Speicher). Mit `--max-age`/`--max-size`/Ordner-Auswahl beherrschbar.
* **Automatisierbar:** derselbe Befehl als Cron (z. B. nachts, wie der
  bestehende Nachtjob) — dann „automatisiert Bilder/Urlaube".
* **Token-Ablage:** `~/.config/rclone/rclone.conf` liegt **außerhalb** des
  Repos; trotzdem nie kopieren/committen (enthält den Cloud-Zugang).

### Weg B — pCloud-REST-API direkt im Backend (zweite Stufe)

pCloud bietet eine HTTP-JSON-API (`https://api.pcloud.com/…`) mit
Token-Authentifizierung. `httpx` ist schon da, also:

* neu: `backend/app/services/pcloud_service.py` (Client: `listfolder`,
  `getfilelink`, `getthumbs`, Namens-/Datumsfilter),
* neu: `backend/app/router/cloud.py` (`GET /api/cloud/suche`,
  `GET /api/cloud/datei?pfad=…` als Bild-Auslieferung, `GET /api/cloud/status`),
* `POST /api/cloud/quiz/start` für „Quiz aus Cloud-Ordner X",
* Token in `backend/.env` (`PCLOUD_TOKEN=…`) → greift automatisch in
  `app/config.py` (Settings ohne `env_prefix`), Schlüssel bleibt per
  `.gitignore` draußen.

Auth-Varianten (offizielle Doku, `docs.pcloud.com/methods/intro/authentication.html`):

| Variante | Ablauf | Bewertung |
|---|---|---|
| OAuth 2.0 | App bei pCloud registrieren (`client_id`/`client_secret`), `authorize` → `oauth2_token`; laut Doku **laufen Access-Tokens nicht ab** | sauberste Variante für den Endbetrieb |
| `getauth=1` (Passwort-Login) | `GET /userinfo?getauth=1&username=…&password=…` → liefert `auth`-Token | schnellster Test, aber pCloud-Passwort im Klartext im Aufruf — **nur einmalig zum Token-Holen**, nie dauerhaft speichern |
| Token aus dem pCloud-Client | `listtokens` / vorhandenes Geräte-Token | pragmatisch, Ablauf (`expire_inactive`) beachten |

* **Vorteil:** nichts wird auf dem Gerät gespiegelt; Live-Suche im ganzen
  Konto, Thumbnails „on demand" (getthumbs liefert kleine Vorschaubilder — ideal
  fürs Quiz-Cover, ohne das Original zu laden).
* **Nachteil:** echte Programmierarbeit (Client, Endpunkte, Fehlerbehandlung),
  Netzabhängigkeit bei jedem Zugriff, und der „Original nie überschreiben / nur
  Pfad"-Grundsatz braucht hier eine bewusste Regel für die Ablage.

---

## 4. Empfehlung (gestaffelt)

**Stufe 1 = Weg A** (rclone-Spiegel eines Testordners, z. B. 3–5 GB Fotos).
Begründung: kleinstes Risiko, sofort im Quiz nutzbar, keinerlei neuer
Backend-Code — und es beweist die Datenschutz-Kette mit **echten** Fotos.
Verifikation: `rclone lsjson` zeigt N Dateien, `~/pcloud_mirror/Fotos` ist im
`datei_suche`-Korridor, Quiz läuft über diese Bilder, Referenzen bekommen ein
`jahr`.

**Stufe 2 = Weg B** (REST-Client) für „Cloud-Suche im Chat + Thumbnails ohne
Download" und damit für den automatisierten Betrieb (Nachtsichtung neuer
Ordner). Erst nach Stufe 1, weil die Bild-Weiterverarbeitung dann schon
bewiesen ist.

**Stufe 3 (optional)** = Nacht-Cron: `rclone copy` + anschließender Hinweis im
Auftragsbuch („12 neue Fotos gespiegelt, 3 fürs Quiz vorbereitet").

---

## 5. Datenschutz — die harte Kante (bitte bewusst entscheiden)

Das Projekt hat einen ZDR-Riegel für Vision-Modelle
(`brainstorm-foto-kontext.md`, Entscheidung 1: „Bilddaten verlassen das Gerät
nur über Modelle mit Zero Data Retention"). Für pCloud-Fotos gilt:

* **Der pCloud-Zugang selbst ist nur Lesen** — es wird nichts hochgeladen,
  umbenannt oder gelöscht.
* **Kritischer Punkt:** Sobald ein Cloud-Foto durch das Quiz/Vision läuft,
  geht das **Bild an den Vision-Anbieter** (OpenRouter/Gemini). Private Fotos
  aus der Cloud sind damit weiter gereist als heute. Konsequenzen:
  1. Quiz/Cloud-Analyse nur mit **als ZDR gekennzeichneten** Modellen; die
     Prüfung gehört **serverseitig** in den Cloud-Endpunkt, nicht nur in die
     Frontend-Modellauswahl.
  2. Der Spiegel-Ordner gehört ausdrücklich in `.gitignore` (er liegt außerhalb
     des Repos — Regel trotzdem dokumentieren).
  3. Originaldatei-Regel bleibt: nur Pfad + kleine eingebettete Miniatur
     (bewusste Ausnahme, vgl. Referenz „pCloud-Ausnahme zur nur-der-Pfad-Regel").
* **Was unverändert bleibt:** lokale Suche, Verlauf append-only, bestehende
  Endpunkte, `X-API-Key`-Schutz, kein Push von Daten.

---

## 6. Risiken

| Risiko | Grad | Gegenmittel |
|---|---|---|
| Speicher voll (256-GB-/Handy-Speicher) | Mittel | nur Testordner spiegeln, `--max-age`, `--max-size`, `--dry-run` vorher |
| Versehentliches Veröffentlichen privater Bilder/Tokens | Hoch (Portfolio-Repo!) | nur ausgewählte Dateien stagen, `git status` prüfen, Spiegel außerhalb des Repos, Token in `.env` |
| Vision-Anbieter erhält private Urlaubsfotos | Mittel | ZDR-Riegel serverseitig erzwingen (Abschnitt 5) |
| Abgelaufenes/ungültiges Token | Gering | `rclone lsd pcloud:` als Prüfbefehl; bei REST: `GET /userinfo` muss `result:0` liefern |
| pCloud drosselt viele Aufrufe (REST-Weg) | Gering | Thumbnails statt Originale, Ergebnisse cachen |

---

## 7. Nächste konkrete Schritte (so würde ich anfangen)

1. `pkg install -y rclone jq` und `rclone config create pcloud pcloud`
   (Sebastian loggt sich einmal im Browser ein).
2. `rclone lsd pcloud:` → Ordnerstruktur zeigen; **Sebastian wählt den
   Testordner** (z. B. `Fotos/Urlaub 2024`).
3. `rclone copy --dry-run` → Größe/Anzahl prüfen (echte Zahlen statt Bauchgefühl).
4. Echter `copy` nach `~/pcloud_mirror/<Ordner>`.
5. `datei_suche` um diese zweite Wurzel erweitern (kleine, additive Änderung) →
   Quiz-Test mit echten Cloud-Fotos, Prüfung: Referenz bekommt `jahr`, Erkennung
   greift.
6. Erst danach Stufe 2 (REST-Client) bauen.

**Verifikationsbefehle der Stufe 1:**
```bash
rclone lsd pcloud:                                   # rc 0 + Ordnerliste
rclone size pcloud:/<Testordner>                     # Datei-/Byte-Zahl
rclone copy --dry-run pcloud:/<Testordner> ~/pcloud_mirror/<Testordner>
ls -R ~/pcloud_mirror/<Testordner> | head -20
curl -s localhost:8080/api/health                    # rc 200 (Server läuft)
```

---

## 8. Offene Entscheidungen (an Sebastian)

1. **Weg-Reihenfolge:** A zuerst (empfohlen) oder direkt B?
2. **Testordner** in der pCloud (welcher, wie groß)?
3. **Auth-Weg für Stufe 2:** OAuth-App bei pCloud registrieren (sauber) oder
   zuerst pragmatisch ein Token aus dem pCloud-Client?
4. **Spiegel-Regel:** nur Fotos, oder auch PDFs/Dokumente (dann greift die
   PDF-zu-Text-Frage auf ARM — laut `stand-2026-08-14.md` der eigentliche
   Aufwand)?

*Dieser Plan ist Doku, kein Code — der Code folgt nach der Entscheidung, jeder
Schritt einzeln vorgelegt und verifiziert.*
