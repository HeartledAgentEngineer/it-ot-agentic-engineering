# Concertify Web — CLAUDE.md

## Was ist das?
Flask-Web-App die automatisch Spotify-Playlists für bevorstehende Konzerte erstellt.
Läuft lokal auf Port 5000. Single-User, kein Auth nötig.
Früher: SetlistMixPrepper.

## Stack
- **Backend**: Python 3.12, Flask, Spotipy, google-genai
- **Frontend**: Vanilla JS + Jinja2 Templates (kein Build-Step)
- **Daten**: `concert_data.json` (atomar schreiben via `_save_concert_data()`)
- **APIs**: Spotify, Gemini (google-genai), Setlist.fm, Songkick, Tavily, Ticketmaster, Eventim

## Kritische Dateien
| Datei | Zweck |
|-------|-------|
| `app.py` | Flask-App, alle Endpunkte |
| `templates/index.html` | Komplette UI (HTML + CSS + JS, ~3000+ Zeilen) |
| `fetch_data.py` | Konzertdaten holen (von /refresh_stream als Subprocess aufgerufen) |
| `festival_client.py` | Festival-Lineups via Tavily (Rock im Park, Hurricane, Southside, Wacken, …) |
| `tavily_concert_client.py` | Hamburg/Stadt-Konzerte via Tavily Web-Search |
| `eventim_client.py` | Eventim-Scraper: Hamburg-Bulk + Einzelsuche deutschlandweit |
| `spotify_client.py` | Spotify API Wrapper |
| `setlist_client.py` | Setlist.fm API Wrapper |
| `rock_im_park.py` | Rock im Park Scraper + Tavily-Supplement |
| `concert_data.json` | Persistente Konzert- und Songdaten |
| `.env` | API-Keys (nie committen) |

## Server starten / neu starten
```bash
# Starten
python app.py

# Neu starten (alten Prozess killen) — Windows:
python -c "
from pathlib import Path; import subprocess
p = Path('server.pid')
if p.exists(): subprocess.run(['taskkill','/F','/PID',p.read_text().strip()], capture_output=True)
"
python app.py
```
Server läuft auf http://localhost:5000 und http://<local-ip>:5000 (Handy).
Auto-Shutdown nach 5 Min Inaktivität.

## Datenstruktur concert_data.json
```json
{
  "hamburg_artists": {
    "Artist": {
      "dates": ["2026-06-01"],
      "venue": "Barclays Arena",
      "venues": {"2026-06-01": "Barclays Arena"},
      "city": "Hamburg"
    }
  },
  "rip_artists": {
    "Artist": {
      "dates": ["2026-06-05"],
      "venue": "Rock im Park, Nürnberg",
      "festival": "Rock im Park"
    }
  },
  "setlist_data": {
    "Artist": {
      "setlist_titles": [],
      "new_titles": [],
      "spotify_uris": {},
      "scores": {},
      "badges": {}
    }
  },
  "last_updated": "2026-05-21"
}
```
**Wichtig**: Immer `_save_concert_data(data)` verwenden — nie direkt `data_file.write_text()`!

## Konzert-Entdeckung (fetch_data.py Pipeline)
Wird via `/refresh_stream?cities=Hamburg,Berlin&festivals=Rock+im+Park,Hurricane` aufgerufen.

1. **Spotify**: Alle gefolgten Künstler holen
2. **Pro Stadt** (Schleife über CONCERT_CITIES):
   - Eventim (nur Hamburg, blockiert Python-Requests häufig)
   - Ticketmaster (nur Hamburg, wenig DE-Daten)
   - Songkick (nur Hamburg)
   - Tavily Web-Search (alle Städte, per-artist)
3. **Pro Festival** (Schleife über ACTIVE_FESTIVALS):
   - Rock im Park: CSS-Scrape + Tavily-Supplement → `rock_im_park.scrape_lineup()`
   - Alle anderen: nur Tavily → `festival_client.get_lineup()`
4. Speichern in concert_data.json

**Tavily-Filter**: `_extract_date_near_hamburg()` / `_extract_date_near_city()` — nimmt nur Daten die räumlich nah (≤400 Zeichen) an einem Stadt/Venue-Keyword stehen. Verhindert Falsch-Positive aus Tour-Seiten die mehrere Städte listen.

## Wichtige Endpunkte
| Route | Methode | Zweck |
|-------|---------|-------|
| `/` | GET | Haupt-UI |
| `/refresh_stream?cities=…&festivals=…` | GET (SSE) | Konzerte suchen (startet fetch_data.py) |
| `/quick_refresh` | GET | Nur Spotify-Follows aktualisieren, nicht-gefolgten entfernen |
| `/search_artist` | POST | Manuell Künstler in Stadt suchen (TM + SK + Eventim + Tavily) |
| `/search_concert` | POST | Einzelkonzert-Suche: Artist + Stadt oder deutschlandweit + Zeitraum (TM + Tavily + Eventim parallel, speichert NICHT in JSON) |
| `/more_songs` | POST | Songs per Setlist.fm + Gemini laden |
| `/create_playlist` | POST | Spotify Playlist erstellen/updaten |
| `/search_tracks` | GET | Spotify Autocomplete (ClientCredentials) |
| `/remove_artist` | POST | Künstler aus JSON entfernen |
| `/add_song_to_artist` | POST | Song manuell hinzufügen |
| `/add_artist_manual` | POST | Künstler mit Datum+Venue manuell eintragen |

## UI-Struktur (index.html)
- **3 Tabs** (CSS-only via Radio + `:checked ~ panel`):
  - 🎵 Mix — Haupt-Tab: Einstellungen + Künstler + Songs + Playlist
  - 🌙 Abend — Platzhalter (noch nicht gebaut)
  - 📋 Playlists — vorhandene Spotify-Playlists (lazy via `/get_playlists`)
- **Action-Bar** (🚀) — per JS `change`-Event auf Radios ein-/ausgeblendet

### Einstellungen-Panel (Mix-Tab)
- Songs pro Künstler (Dropdown 3–20)
- Konzerte von/bis (Datepicker)
- **Konzert-Städte** — Pill-Buttons (Toggle + × Entfernen) für Hamburg, Lübeck, Hannover, Berlin, Kiel + freies Textfeld (Enter = neue Stadt hinzufügen); gespeichert in `localStorage` unter `gp_cities` (aktiv) + `gp_city_presets` (alle)
- **Festivals** — Pill-Buttons (Toggle + × Entfernen) für Rock im Park, Rock am Ring, Hurricane, Southside, Wacken, Download DE + Textfeld mit **Autocomplete-Dropdown** (60+ Festivals); gespeichert unter `gp_festivals` + `gp_festival_presets`
- 🔍 Konzerte suchen — startet SSE-Stream, Hint zeigt aktuelle Konfiguration live

### Manuell Künstler suchen (aufklappbar unter Künstler-Liste)
- Künstler-Input + **Stadt-Input** (Default: Hamburg) + 🔍 Suchen
- Datum + Venue + ＋ Manuell (für manuellen Eintrag ohne API)
- Suche nutzt Ticketmaster + Songkick + Eventim + Tavily parallel

### Einzelkonzert / Konzertreise suchen (aufklappbar)
- Künstler + Stadt (optional) + Zeitraum + Checkbox "Deutschlandweit"
- Suche via `/search_concert`: TM + Tavily + Eventim parallel
- Ergebnis: Tabelle mit Datum, Venue, Stadt, Quelle
- Speichert NICHT automatisch — "Als Konzertreise hinzufügen"-Button noch offen (TODO)

## EventimClient — zwei Modi
```python
# Hamburg-Bulk (für fetch_data.py / refresh_stream)
client.get_hamburg_artists(followed_artists)          # locationIds=63, paginiert

# Einzelsuche deutschlandweit (für /search_concert und /search_artist)
client.search_artist_any(artist_name, city="")        # kein locationIds-Filter
# city="" → alle deutschen Konzerte
# city="Braunschweig" → filtert: "braunschweig" in venue.lower() OR city_field.lower()
```
`_parse_group()` extrahiert jetzt auch `city` aus `place.city` oder `place.address.city` — wichtig für den Stadtfilter bei nicht-Hamburg-Venues (z.B. "Volkswagen Halle" → city: "Braunschweig").

## run_config / _build_env
`_run_config` (global dict in app.py) wird via `_build_env()` als Umgebungsvariablen an Subprozesse (fetch_data.py, main.py, preview_run.py) weitergegeben. Gesetzt via `/run` (Playlist-Config) und `/refresh_stream` (Suchkonfig).

Relevante Keys:
- `CONCERT_CITIES` — kommagetrennt, z.B. `"Hamburg,Berlin"`
- `ACTIVE_FESTIVALS` — kommagetrennt, z.B. `"Rock im Park,Hurricane"`
- `PLAYLIST_NAME`, `DATE_FILTER_FROM`, `DATE_FILTER_TO`, `TRACK_LIMIT_PER_ARTIST`, `EXCLUDE_ARTISTS`, `EXCLUDE_SONGS`

## Gemini
- Library: `from google import genai` (nicht `google.generativeai` — deprecated!)
- Modell: `gemini-2.0-flash-lite`
- Fallback: wenn rate-limited → nur Setlist.fm
- Quota: 1500 RPD, Reset Mitternacht Pacific Time

## Spotify Scopes
```
user-follow-read playlist-read-private playlist-modify-public
playlist-modify-private ugc-image-upload user-modify-playback-state
user-read-playback-state streaming user-read-email user-read-private
user-library-read user-library-modify
```
Scope-Konstante: `_SPOTIFY_SCOPE` in `app.py` (ganz oben definiert).
Token-Cache: `.cache` (nicht committen). Bei neuen Scopes: `.cache` löschen → neu auth.
**Liked-Songs-Endpoints**: Verwenden `_get_spotify_with_library_scope()` — öffnen KEINEN Browser, geben
sofort `{error: "scope"}` zurück wenn Token fehlt (kein Hängen).

## Festival-Unterstützung (festival_client.py)

Bekannte Festivals mit optimierten Tavily-Queries:
`Rock im Park` (Scraper), `Rock am Ring`, `Hurricane`, `Southside`, `Wacken`, `Download DE`, `Hellfest`, `Copenhell`, `Elbriot`, `Impericon Festival`

Unbekannte Festivals (z.B. Wutzrock): generischer Fallback `"{name} 2026 lineup artists list"` — funktioniert, aber niedrigere Trefferquote.

Festival-Autocomplete in der UI: `FESTIVAL_SUGGESTIONS`-Array (60+ Einträge) in index.html — client-seitig gefiltert, kein API-Call.

## Bekannte Stolperfallen
- **JSON-Korruption**: Nur `_save_concert_data()` verwenden (Lock + atomic write)
- **Spotify-Suche hängt**: `SpotifyOAuth` startet Browser-Auth → für Suche `SpotifyClientCredentials` nutzen
- **Gemini deprecated warning**: `google.generativeai` nicht verwenden
- **Dropdown geclipped**: Song-Autocomplete nutzt `position:fixed` global div (`#global-song-dropdown`)
- **Tab-Konflikt**: BroadcastChannel verhindert mehrere Browser-Tabs
- **Server-Neustart Windows**: `os.kill(pid, SIGTERM)` funktioniert nicht → `subprocess.run(['taskkill', '/F', '/PID', str(pid)])` verwenden
- **PLAYLIST_NAME**: In `.env` gesetzt — überschreibt Code-Default
- **Unicode Windows**: Keine `→`, `…`, `🎸`, `✅` in Python-Print-Statements in fetch_data.py / tavily_concert_client.py (cp1252-Encoding im subprocess)
- **Tavily falsche Städte**: Nicht `_extract_date()` direkt verwenden — immer `_extract_date_near_hamburg()` oder `_extract_date_near_city()` aus tavily_concert_client.py
- **Eventim Stadtfilter**: Venue-Name enthält oft nicht die Stadt (z.B. "Volkswagen Halle" ohne "Braunschweig") → `_parse_group()` extrahiert `city` separat aus `place.city`; Filter prüft beide Felder

## Song-Typ-Logik (more_songs)
Künstler-Typ wird automatisch erkannt:
- `hamburg_artists` → Hauptact → `konzert_songs` (Default 22)
- `rip_artists` → Festival-Act → `festival_songs` (Default 10)
Frontend schickt beide Werte bei jedem `/more_songs`-Aufruf mit (`getTypeSongCounts()`).
localStorage-Keys: `gp_konzert_songs`, `gp_festival_songs`.

## Support Acts
Datenstruktur: `concert_data["support_acts"]["Linkin Park"]["2026-06-01"] = ["Band1", "Band2"]`
Songs: wie reguläre Künstler in `setlist_data`, werden lazy via `more_songs` geladen (max 8).
- `/search_support_acts` POST: TM-Attractions + Tavily-Fallback
- `/add_support_act` POST / `/remove_support_act` POST
- UI: `.support-acts-section` am Ende jeder nicht-RiP Künstler-Karte (innerhalb `.song-list`)
- Support Act Songs kommen am Ende der Playlist (`startRun()` → `supportUris` Array)
- Spotify-Autocomplete nutzt vorhandenen `/search_artists`-Endpoint

## Player-Popup (Spotify Embed Controller API)
`_showSpotifyEmbed(trackId, uri)` verwendet jetzt die Spotify IFrame API (`window.onSpotifyIframeApiReady`):
- Erster Aufruf: `IFrameAPI.createController(container, {uri}, callback)` → erstellt iframe in `#spotify-embed-container`
- Folgeaufrufe: `controller.loadUri(uri)` + `controller.play()` — kein iframe-reload
- `playback_update`-Listener: trackt `_embedPlaying` → Button-Text live
- Leertaste: `_embedController.pause()` / `.resume()` — nur wenn Player sichtbar
- Fallback: direktes iframe wenn API noch nicht geladen
- ❤️-Button: `/liked_songs/check` + `/liked_songs/toggle` — erfordert neue Scopes → `.cache` löschen

## Session-Start Protokoll (PFLICHT — vor jeder Arbeit)

Claude führt dies zu Beginn jeder Session aus, bevor Code angefasst wird:

1. **Status zeigen**: Letzten Git-Commit + offene TODOs ausgeben sowie **aktuelle API-Quotas verifizieren**.
   * *Grund:* Verhindert Informationsverlust nach Kontext-Resets, sichert den exakten mentalen und technischen Arbeitsstand ab, warnt vor abgelaufenen Limits/Tokens und vermeidet redundante Arbeiten.
2. **Vorgehensweise (Dual Engineering System)**:
   Wir arbeiten immer in den folgenden 4 Phasen. **OBERSTE REGEL: Es gibt KEINEN Wechsel in die nächste Phase ohne das konkrete Okay des Users!**
   Jeder Phasenwechsel muss explizit mit dem Auswahldialog (`ask_question` Tool) durch den User freigegeben werden. Vor dem Dialog erfolgt eine kurze Einführung in die nächste Phase (Was steht an? Was möchte ich tun?).

   1. **Phase 1: Brainstorming (To-Do / Ideenfindung)**
      - Neue Aufgaben werden *nur* besprochen und in `TASKS.md` dokumentiert. Keine Ausführung!
   2. **Phase 2: Alignment (Architektur & Planung)**
      - Erstellung des `implementation_plan.md`. Kapselung, DI und Architektur werden geklärt.
      - Der Plan muss vom User (Wächter-Rolle) abgenommen werden (Auswahldialog!).
   3. **Phase 3: Implementation (Clean Code)**
      - Erst nach Freigabe aus Phase 2 wird Code geschrieben, streng testgetrieben (TDD).
   4. **Phase 4: Verifikation (Tests & UI)**
      - Ausführung der Tests (`pytest`), manuelle UI-Checks. Erstellung eines `walkthrough.md`.

3. **Ziele abstimmen**: "Was möchtest du heute erreichen?" — max. 3 Punkte.
   * *Grund:* Fokussiert die Session auf konkrete, kleine, lieferbare Inkremente statt unkoordiniert an zu vielen Fronten gleichzeitig zu arbeiten.
4. **Workflow benennen**: In welcher Phase des 4-Phasen-Zyklus sind wir? Was kommt als nächstes?
   * *Grund:* Schafft Klarheit über die aktuelle Phase (z.B. Alignment, Plan, Code oder Test), damit alle Schritte der Qualitätssicherung eingehalten werden.
5. **Erst dann** Code lesen oder ändern.
   * *Grund:* Verhindert voreilige, blinde Codeänderungen ("Trial and Error"), die zu unvorhersehbaren Fehlern führen.

Falls Sebastian direkt mit einer Aufgabe startet ohne Check-in → kurz pausieren, 1-Satz-Status geben, dann fortfahren.

## Coding-Konventionen
- **Duales Engineering-System**: Jede Änderung durchläuft Planung (Modul-Hierarchie), Review (Wächter-Check gegen Spaghetti-Code/Globals) und Implementierung (saubere DI + 100% testbar).
- Antworten auf Deutsch.
- Kein Trailing-Summary nötig.
- Keine Tasks für triviale Aktionen.
- Server nach Code-Änderungen automatisch neu starten.
- Vor jeder Änderung: Konzept hinter der Änderung in 1 Satz benennen (Lernmodus).
