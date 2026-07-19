"""
Concertify — Web UI
====================
Run:  python app.py
Open: http://localhost:5000  (or on phone: http://<your-IP>:5000)
"""

import json
import os
import sys
import subprocess
from datetime import date as _date
from pathlib import Path

from dotenv import dotenv_values
from flask import Flask, Response, render_template, request, jsonify

BASE_DIR = Path(__file__).parent
app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True

# ─── Neue Architektur-Schicht (Slice 1 + 3) ──────────────────────────────────
# Blueprints mit der neuen Layered Architecture (domain/ → repositories/ →
# services/ → routes/). Laufen parallel zu den alten Routen unten.
# URL-Prefix: /api/v2/... — alte Routen bleiben unveraendert.
from routes import imports_bp, playlists_bp, songs_bp  # noqa: E402
app.register_blueprint(songs_bp)
app.register_blueprint(playlists_bp)
app.register_blueprint(imports_bp)

from services.support_order_service import reorder_support_acts as _reorder_support_acts  # noqa: E402
from services.song_state_service import toggle_song_excluded as _toggle_song_excluded, reorder_songs as _reorder_songs  # noqa: E402

_WEEKDAYS_SHORT = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']

@app.template_filter('wd')
def _wd_filter(date_str: str) -> str:
    """Gibt zweistelligen Wochentag zurück: Mo Di Mi Do Fr Sa So"""
    try:
        from datetime import date as _d
        return _WEEKDAYS_SHORT[_d.fromisoformat(str(date_str)[:10]).weekday()]
    except Exception:
        return ''

# Vollständige Spotify Scopes (inkl. Liked Songs)
_SPOTIFY_SCOPE = (
    "user-follow-read playlist-read-private playlist-modify-public "
    "playlist-modify-private ugc-image-upload user-modify-playback-state "
    "user-read-playback-state streaming user-read-email user-read-private "
    "user-library-read user-library-modify"
)

# Stores the most recent run config (single-user local app)
_run_config: dict = {}

# ── Atomares JSON-Schreiben mit Lock ──────────────────────────────
import threading as _threading_json
_json_lock = _threading_json.Lock()

# ── Gemini Request-Zähler (RPD) ───────────────────────────────────
from datetime import datetime as _dt, timezone as _tz, timedelta as _td

GEMINI_RPD_LIMIT = 1500  # Gemini 1.5 Flash free tier

def _gemini_reset_ts() -> float:
    """Nächste Mitternacht Pacific Time (UTC-8) als Unix-Timestamp."""
    pt_offset = _td(hours=-8)
    now_pt = _dt.now(_tz.utc).astimezone(_tz(pt_offset))
    midnight_pt = (now_pt + _td(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight_pt.timestamp()

_gemini_counter: dict = {"date_pt": "", "count": 0}
_gemini_counter_lock = _threading_json.Lock()

def _gemini_tick() -> None:
    """Jeden Gemini-API-Call mit diesem Aufruf mitzählen."""
    pt_offset = _td(hours=-8)
    today_pt = (_dt.now(_tz.utc).astimezone(_tz(pt_offset))).strftime("%Y-%m-%d")
    with _gemini_counter_lock:
        if _gemini_counter["date_pt"] != today_pt:
            _gemini_counter["date_pt"] = today_pt
            _gemini_counter["count"] = 0
        _gemini_counter["count"] += 1

# ── API-Health-Cache (in-memory, wird bei Fehlern passiv aktualisiert) ────
import time as _time
_api_health: dict = {}

def _update_api_health(api_id: str, ok: bool, error: str = "", retry_after: int = 0) -> None:
    """Speichert letzten bekannten Status einer API im Memory-Cache."""
    _api_health[api_id] = {
        "ok":          ok,
        "checked":     int(_time.time()),
        "retry_after": retry_after,
        "error":       error[:120] if error else "",
    }


def _seconds_until_midnight_utc() -> int:
    """Sekunden bis 00:00 UTC — Reset-Zeitpunkt der setlist.fm-Quota.

    Wird als Fallback genutzt wenn die API keinen Retry-After-Header schickt.
    """
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return int((midnight - now).total_seconds())


def _save_concert_data(data: dict) -> None:
    """Write concert_data.json atomically: write temp → rename."""
    data_file = BASE_DIR / "concert_data.json"
    tmp_file  = BASE_DIR / "concert_data.tmp"
    with _json_lock:
        tmp_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_file.replace(data_file)

# -- Snapshot-DB (SQLite-Keimzelle) --
from db.connection import create_connection
from repositories.snapshot_repository import SnapshotRepository
from services.snapshot_service import SnapshotService, diff_setlists

_snapshot_conn    = create_connection(BASE_DIR / "concertify.db")
_snapshot_repo    = SnapshotRepository(_snapshot_conn)
_snapshot_service = SnapshotService(_snapshot_repo)


def _load_concert_data() -> dict:
    """Liest concert_data.json (oder {} wenn nicht vorhanden)."""
    f = BASE_DIR / "concert_data.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


# ── Auto-Shutdown bei Inaktivität ─────────────────────────────────
import time as _time
import threading as _threading

IDLE_TIMEOUT_MINUTES = 5  # Server fährt nach 5 Min ohne Request herunter
_last_request = _time.time()

def _idle_watchdog():
    while True:
        _time.sleep(60)
        idle = (_time.time() - _last_request) / 60
        if idle >= IDLE_TIMEOUT_MINUTES:
            print(f"\n⏰ Keine Aktivität seit {IDLE_TIMEOUT_MINUTES} Minuten — Server wird beendet.")
            os._exit(0)

_threading.Thread(target=_idle_watchdog, daemon=True).start()

@app.before_request
def _touch():
    global _last_request
    _last_request = _time.time()


@app.route("/")
def index():
    env = dotenv_values(BASE_DIR / ".env")

    concert_data: dict = {}
    data_file = BASE_DIR / "concert_data.json"
    if data_file.exists():
        concert_data = json.loads(data_file.read_text(encoding="utf-8"))

    hamburg = concert_data.get("hamburg_artists", {})
    rip = concert_data.get("rip_artists", {})

    today_str = _date.today().isoformat()

    # Build a sorted list — nur zukünftige Konzerte
    artists = []
    for name, info in hamburg.items():
        dates = sorted(d for d in info.get("dates", []) if d[:10] >= today_str)
        if not dates:
            continue  # alle Konzerte vorbei → überspringen
        city_single = info.get("city", "Hamburg") or "Hamburg"
        cities = info.get("cities") or {d: city_single for d in dates}
        rip_info  = rip.get(name, {})
        rip_dates = rip_info.get("dates", [])
        rip_date  = rip_dates[0] if rip_dates else ""
        also_rip  = bool(rip_info) and (rip_date >= today_str if rip_date else False)
        artists.append({
            "name":       name,
            "source":     "Hamburg",
            "also_rip":   also_rip,
            "date":       dates[0],
            "extra_dates": len(dates) - 1,
            "venue":      info.get("venue", "Hamburg"),
            "venues":     info.get("venues", {}),
            "cities":     cities,
            "dates_all":  dates,
            # RiP-Details (nur wenn auch_rip)
            "rip_date":   rip_date,
            "rip_day":    rip_info.get("day",   "") if also_rip else "",
            "rip_stage":  rip_info.get("stage", "") if also_rip else "",
            "rip_start":  rip_info.get("start", "") if also_rip else "",
            "rip_end":    rip_info.get("end",   "") if also_rip else "",
        })
    for name, info in rip.items():
        if name not in hamburg:
            fest_date = info.get("dates", ["2026-06-05"])[0]
            if fest_date[:10] < today_str:
                continue
            fest_name  = info.get("festival", "Rock im Park")
            fest_venue = info.get("venue", f"{fest_name}, Nürnberg")
            artists.append({
                "name":       name,
                "source":     fest_name,
                "also_rip":   False,
                "date":       fest_date,
                "extra_dates": 0,
                "venue":      fest_venue,
                "venues":     {fest_date: fest_venue},
                "cities":     {fest_date: info.get("city", "Nürnberg")},
                "dates_all":  [fest_date],
                "day":        info.get("day", ""),
                "stage":      info.get("stage", ""),
                "tt_start":   info.get("start", ""),
                "tt_end":     info.get("end", ""),
            })
    def _sort_key(a):
        date  = a.get("date", "")
        start = a.get("tt_start", "")
        if start:
            h, m = map(int, start.split(':'))
            if h < 12:   # nach Mitternacht → auf nächsten Tag legen
                h += 24
            mins = h * 60 + m
        else:
            mins = 0
        return (date, mins)
    artists.sort(key=_sort_key)

    gemini_key = env.get("GEMINI_API_KEY", "")
    has_gemini = bool(gemini_key and gemini_key != "dein-key-hier")
    has_anthropic = bool(env.get("ANTHROPIC_API_KEY"))
    has_tavily = bool(env.get("TAVILY_API_KEY"))

    setlist_data = concert_data.get("setlist_data", {})

    # Date defaults: today → latest Hamburg concert date
    last_updated = concert_data.get("last_updated", "")
    max_date = ""
    for info in hamburg.values():
        for d in info.get("dates", []):
            d_clean = d[:10] if d else ""
            if d_clean > max_date:
                max_date = d_clean

    support_acts = concert_data.get("support_acts", {})

    # Spotify-Statistiken für Banner
    followed_count        = concert_data.get("followed_count", 0)
    spotify_display_name  = concert_data.get("spotify_display_name", "")
    # Künstler mit Konzerten gefunden (unique, egal ob Hamburg oder Festival)
    artists_on_tour = len(set(hamburg.keys()) | set(rip.keys()))

    resp = render_template(
        "index.html",
        artists=artists,
        followed_count=followed_count,
        spotify_display_name=spotify_display_name,
        artists_on_tour=artists_on_tour,
        playlist_name=env.get("PLAYLIST_NAME", f"Setlist-Mix {max_date[8:10]}.{max_date[5:7]}.{max_date[0:4]}" if max_date else "Setlist-Mix 2026"),
        has_gemini=has_gemini,
        has_anthropic=has_anthropic,
        has_tavily=has_tavily,
        setlist_data=setlist_data,
        support_acts=support_acts,
        today=today_str,
        max_date=max_date,
        last_updated=last_updated,
    )
    from flask import make_response
    r = make_response(resp)
    r.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return r


@app.route("/run", methods=["POST"])
def run():
    global _run_config
    exclude_raw = request.form.get("exclude_artists", "")
    exclude_lines = [a.strip() for a in exclude_raw.replace(",", "\n").splitlines() if a.strip()]

    _run_config = {
        "PLAYLIST_NAME":         request.form.get("playlist_name", "Setlist-Mix 2026"),
        "DATE_FILTER_FROM":      request.form.get("date_from", ""),
        "DATE_FILTER_TO":        request.form.get("date_to", ""),
        "EXCLUDE_ARTISTS":       ",".join(exclude_lines),
        "EXCLUDE_SONGS":         request.form.get("exclude_songs", ""),
        "USE_CLAUDE_SETLIST":    "1" if request.form.get("use_claude") else "",
        "TRACK_LIMIT_PER_ARTIST": request.form.get("track_limit", "10"),
    }
    return jsonify({"ok": True})


def _build_env() -> dict:
    """Merge OS env + .env file + current run config."""
    env = os.environ.copy()
    env.update(dotenv_values(BASE_DIR / ".env"))
    for key, val in _run_config.items():
        if val:
            env[key] = val
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    return env


_fetch_data_proc: "subprocess.Popen | None" = None

def _stream_script(script: str, done_msg: str):
    """SSE generator that streams stdout of a Python script."""
    def generate():
        global _fetch_data_proc
        # Doppelstart verhindern
        if script == "fetch_data.py" and _fetch_data_proc and _fetch_data_proc.poll() is None:
            yield "data: ⚠️ Konzertsuche läuft bereits — bitte warten bis sie abgeschlossen ist.\n\n"
            yield "data: __done__\n\n"
            return
        proc = None
        try:
            proc = subprocess.Popen(
                [sys.executable, str(BASE_DIR / script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=_build_env(),
                cwd=str(BASE_DIR),
            )
            if script == "fetch_data.py":
                _fetch_data_proc = proc
            for raw in iter(proc.stdout.readline, b""):
                line = raw.decode("utf-8", errors="replace").rstrip()
                if line:
                    yield f"data: {line}\n\n"
            proc.wait()
            if proc.returncode == 0:
                yield f"data: \n\n"
                yield f"data: {done_msg}\n\n"
            else:
                yield f"data: ❌ Fehler (exit code {proc.returncode})\n\n"
        except GeneratorExit:
            # Browser hat Verbindung getrennt → Subprocess sofort beenden
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
            if script == "fetch_data.py" and _fetch_data_proc is proc:
                _fetch_data_proc = None
            return
        except Exception as e:
            yield f"data: ❌ Fehler: {e}\n\n"
        finally:
            if script == "fetch_data.py" and _fetch_data_proc is proc:
                _fetch_data_proc = None
        yield "data: __done__\n\n"
    return generate


@app.route("/stream")
def stream():
    pname = _run_config.get("PLAYLIST_NAME", "Setlist-Mix 2026")
    done  = f"✅ Fertig! Playlist «{pname}» in Spotify aktualisiert."
    return Response(
        _stream_script("main.py", done)(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/preview_stream")
def preview_stream():
    return Response(
        _stream_script("preview_run.py", "✅ Vorschau abgeschlossen.")(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/refresh_stream")
def refresh_stream():
    global _run_config
    cities = request.args.get("cities", "").strip() or "Hamburg"
    festivals = request.args.get("festivals", "Rock im Park").strip() or "Rock im Park"
    date_from = request.args.get("date_from", "").strip()
    date_to   = request.args.get("date_to", "").strip()
    _run_config["CONCERT_CITIES"] = cities
    _run_config["ACTIVE_FESTIVALS"] = festivals
    if date_from:
        _run_config["DATE_FILTER_FROM"] = date_from
    if date_to:
        _run_config["DATE_FILTER_TO"] = date_to
    return Response(
        _stream_script("fetch_data.py", "✅ Konzertdaten aktualisiert!")(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/abort_search", methods=["POST"])
def abort_search():
    """Bricht die laufende Konzertsuche ab (z.B. wenn Browser geschlossen wird)."""
    global _fetch_data_proc
    if _fetch_data_proc and _fetch_data_proc.poll() is None:
        _fetch_data_proc.terminate()
        try:
            _fetch_data_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _fetch_data_proc.kill()
        _fetch_data_proc = None
        return jsonify({"ok": True})
    return jsonify({"ok": False})


@app.route("/quick_refresh")
def quick_refresh():
    """Holt aktuelle Spotify-Follows, updated concert_data.json und gibt neue Künstlerliste zurück."""
    today = _date.today().isoformat()
    env = dotenv_values(BASE_DIR / ".env")

    try:
        from spotipy import Spotify
        from spotipy.oauth2 import SpotifyOAuth
        sp = Spotify(auth_manager=SpotifyOAuth(
            client_id=env.get("SPOTIFY_CLIENT_ID", ""),
            client_secret=env.get("SPOTIFY_CLIENT_SECRET", ""),
            redirect_uri=env.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
            scope="user-follow-read playlist-read-private playlist-modify-public playlist-modify-private ugc-image-upload user-modify-playback-state user-read-playback-state streaming user-read-email user-read-private",
            cache_path=str(BASE_DIR / ".cache"),
        ))
        # Spotify-User-Profil holen
        try:
            me = sp.me()
            spotify_display_name = me.get("display_name") or me.get("id", "")
        except Exception:
            spotify_display_name = ""

        # Alle gefolgten Künstler holen
        followed_names: set[str] = set()
        after = None
        while True:
            result = sp.current_user_followed_artists(limit=50, after=after)
            page = result["artists"]
            for a in page["items"]:
                followed_names.add(a["name"])
            after = page["cursors"]["after"]
            if not after:
                break
    except Exception as e:
        return jsonify({"error": str(e), "artists": []})

    # concert_data.json laden und nicht-gefolgten Künstler entfernen
    data_file = BASE_DIR / "concert_data.json"
    concert_data: dict = {}
    if data_file.exists():
        concert_data = json.loads(data_file.read_text(encoding="utf-8"))

    hamburg = concert_data.get("hamburg_artists", {})
    rip = concert_data.get("rip_artists", {})

    # Nicht mehr gefolgte entfernen
    hamburg_new = {k: v for k, v in hamburg.items() if k in followed_names}
    rip_new = {k: v for k, v in rip.items() if k in followed_names}
    concert_data["hamburg_artists"] = hamburg_new
    concert_data["rip_artists"] = rip_new
    concert_data["last_updated"] = today
    concert_data["followed_count"] = len(followed_names)
    if spotify_display_name:
        concert_data["spotify_display_name"] = spotify_display_name
    _save_concert_data(concert_data)

    # Gefilterte Künstlerliste zurückgeben
    artists = []
    for name, info in hamburg_new.items():
        dates = sorted(d for d in info.get("dates", []) if d[:10] >= today)
        if not dates:
            continue
        artists.append({"name": name, "source": "Hamburg", "date": dates[0], "extra_dates": len(dates) - 1})
    for name in rip_new:
        if name not in hamburg_new and "2026-06-05" >= today:
            artists.append({"name": name, "source": "Rock im Park", "date": "2026-06-05", "extra_dates": 0})
    artists.sort(key=lambda a: a["date"])
    return jsonify({"artists": artists, "last_updated": today, "followed_count": len(followed_names), "display_name": spotify_display_name})


@app.route("/artists_json")
def artists_json():
    """Gibt die aktuelle Künstlerliste aus concert_data.json zurück."""
    today = _date.today().isoformat()
    concert_data: dict = {}
    data_file = BASE_DIR / "concert_data.json"
    if data_file.exists():
        concert_data = json.loads(data_file.read_text(encoding="utf-8"))

    hamburg = concert_data.get("hamburg_artists", {})
    rip = concert_data.get("rip_artists", {})

    artists = []
    for name, info in hamburg.items():
        dates = sorted(d for d in info.get("dates", []) if d[:10] >= today)
        if not dates:
            continue
        artists.append({"name": name, "source": "Hamburg", "date": dates[0], "extra_dates": len(dates) - 1})
    for name, info in rip.items():
        if name not in hamburg:
            fest_date = info.get("dates", ["2026-06-05"])[0]
            if fest_date[:10] < today:
                continue
            artists.append({
                "name":        name,
                "source":      "Rock im Park",
                "date":        fest_date,
                "extra_dates": 0,
                "festival":    info.get("festival", "Rock im Park"),
                "day":         info.get("day", ""),
                "stage":       info.get("stage", ""),
                "start":       info.get("start", ""),
                "end":         info.get("end", ""),
            })
    artists.sort(key=lambda a: a["date"])
    return jsonify({"artists": artists, "last_updated": concert_data.get("last_updated", "")})


@app.route("/search_artist", methods=["POST"])
def search_artist():
    """Sucht einen Künstler manuell auf Ticketmaster (Hamburg) und fügt ihn zu concert_data.json hinzu."""
    data = request.get_json(force=True) or {}
    artist_name = data.get("artist", "").strip()
    city        = data.get("city", "").strip()
    date_from   = data.get("date_from", "").strip()
    date_to     = data.get("date_to",   "").strip()
    nosave      = data.get("nosave", False)              # True = nicht in concert_data.json speichern
    if not artist_name:
        return jsonify({"error": "Kein Künstlername angegeben"})

    env = dotenv_values(BASE_DIR / ".env")
    today = _date.today().isoformat()
    data_file = BASE_DIR / "concert_data.json"
    concert_data = json.loads(data_file.read_text(encoding="utf-8")) if data_file.exists() else {}

    city_lower  = city.lower()
    is_hamburg  = "hamburg" in city_lower
    # Zeitraum: Standard ist ab heute ohne Oberschranke
    search_from = date_from or today
    search_to   = date_to   or ""

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _search_ticketmaster():
        tm_key = env.get("TICKETMASTER_API_KEY")
        if not tm_key:
            return []
        import requests as _req
        params = {
            "apikey": tm_key, "keyword": artist_name,
            "countryCode": "DE",
            "classificationName": "Music", "size": 10,
            "sort": "date,asc", "locale": "*",
            "startDateTime": search_from + "T00:00:00Z",
        }
        if city:
            params["city"] = city
        if search_to:
            params["endDateTime"] = search_to + "T23:59:59Z"
        resp = _req.get(
            "https://app.ticketmaster.com/discovery/v2/events.json",
            params=params, timeout=10,
        )
        events = []
        for event in resp.json().get("_embedded", {}).get("events", []):
            date_str = event.get("dates", {}).get("start", {}).get("localDate", "")
            if not date_str or date_str < search_from:
                continue
            if search_to and date_str > search_to:
                continue
            venues = event.get("_embedded", {}).get("venues", [])
            venue = venues[0].get("name", city) if venues else city
            event_city = venues[0].get("city", {}).get("name", "").lower() if venues else ""
            if event_city and city_lower not in event_city:
                continue
            events.append({"date": date_str, "venue": venue})
        return events

    def _search_songkick():
        from songkick_client import SongkickClient
        sk_events = SongkickClient()._get_hamburg_shows(artist_name) if is_hamburg else []
        return [{"date": e.get("datetime", e.get("date", ""))[:10],
                 "venue": e.get("venue", city)}
                for e in sk_events if e.get("datetime", e.get("date", ""))[:10] >= today]

    def _search_eventim():
        if not is_hamburg:
            return []
        from eventim_client import EventimClient
        return [{"date": e["date"], "venue": e.get("venue", city)}
                for e in EventimClient().search_artist_hamburg(artist_name)]

    def _search_tavily():
        tavily_key = env.get("TAVILY_API_KEY")
        if not tavily_key:
            return []
        from tavily_concert_client import TavilyConcertClient
        events = TavilyConcertClient(api_key=tavily_key)._search_artist(artist_name, city=city)
        return [{"date": e.get("datetime", ""), "venue": e.get("venue", city)}
                for e in events if e.get("datetime", "") >= today]

    # Alle Quellen parallel starten
    found_events = []
    seen_dates = set()
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {
            ex.submit(_search_ticketmaster): "Ticketmaster",
            ex.submit(_search_songkick):     "Songkick",
            ex.submit(_search_eventim):      "Eventim",
            ex.submit(_search_tavily):       "Tavily",
        }
        for fut in as_completed(futures):
            try:
                for e in (fut.result() or []):
                    if e["date"] and e["date"] not in seen_dates:
                        seen_dates.add(e["date"])
                        found_events.append(e)
            except Exception:
                pass

    if not found_events:
        return jsonify({"found": False, "message": f"Keine Konzerte fuer '{artist_name}' in {city} gefunden (Ticketmaster + Songkick + Eventim + Tavily)."})

    sorted_dates = sorted(set(e["date"] for e in found_events))
    date_venue = {e["date"]: e["venue"] for e in found_events}

    if not nosave:
        concert_data.setdefault("hamburg_artists", {})[artist_name] = {
            "dates": sorted_dates,
            "venue": date_venue.get(sorted_dates[0], city),
            "venues": date_venue,
            "city": city,
        }
        _save_concert_data(concert_data)

    return jsonify({
        "found": True,
        "name": artist_name,
        "date": sorted_dates[0],
        "venue": date_venue.get(sorted_dates[0], city),
        "extra_dates": len(sorted_dates) - 1,
        "all_dates": [{"date": d, "venue": date_venue.get(d, city)} for d in sorted_dates],
    })


@app.route("/search_festival_stages", methods=["POST"])
def search_festival_stages():
    """Sucht automatisch Bühne + Zeiten für Festival-Künstler ohne Stage-Daten via Tavily."""
    data_file = BASE_DIR / "concert_data.json"
    concert_data: dict = {}
    if data_file.exists():
        concert_data = json.loads(data_file.read_text(encoding="utf-8"))
    rip = concert_data.get("rip_artists", {})
    missing = [name for name, info in rip.items()
               if not info.get("stage") or not info.get("start") or not info.get("day")]
    if not missing:
        return jsonify({"ok": True, "updated": 0, "slots": {}})

    tavily_key = os.getenv("TAVILY_API_KEY", "")
    if not tavily_key:
        return jsonify({"ok": False, "error": "Kein TAVILY_API_KEY"})

    try:
        from rock_im_park import scrape_timetable
        timetable = scrape_timetable(missing, tavily_key)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

    _RIP_DATE_MAP = {"Freitag": "2026-06-05", "Samstag": "2026-06-06", "Sonntag": "2026-06-07"}
    updated = 0
    for name, slot in timetable.items():
        if name in rip:
            for k in ("day", "stage", "start", "end"):
                if slot.get(k):
                    rip[name][k] = slot[k]
            if slot.get("day") and slot["day"] in _RIP_DATE_MAP:
                rip[name]["dates"] = [_RIP_DATE_MAP[slot["day"]]]
            updated += 1

    concert_data["rip_artists"] = rip
    _save_concert_data(concert_data)
    return jsonify({"ok": True, "updated": updated, "slots": {k: v for k, v in timetable.items()}})


@app.route("/search_concert", methods=["POST"])
def search_concert():
    """Einzelkonzert-Suche: Artist + Stadt (oder deutschlandweit) + Zeitraum.
    Speichert NICHT in concert_data.json — gibt nur Treffer zurueck."""
    req = request.get_json(force=True) or {}
    artist_name = req.get("artist", "").strip()
    city        = req.get("city", "").strip()
    date_from   = req.get("date_from", _date.today().isoformat())
    date_to     = req.get("date_to", f"{_date.today().year + 1}-12-31")
    nationwide  = req.get("nationwide", False) or not city

    if not artist_name:
        return jsonify({"error": "Kein Kuenstlername angegeben"})

    env = dotenv_values(BASE_DIR / ".env")
    results: list[dict] = []
    seen_keys: set = set()

    def _add(events: list[dict], source: str):
        for e in events:
            d = e.get("date") or e.get("datetime", "")
            d = d[:10] if d else ""
            if not d or d < date_from or d > date_to:
                continue
            # Dedup per Datum + Venue/Stadt — gleicher Tag, andere Stadt = kein Duplikat
            venue_raw = (e.get("venue") or e.get("city") or "").lower().strip()[:40]
            dedup_key = f"{d}|{venue_raw}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)
            results.append({
                "date":   d,
                "venue":  e.get("venue", city or ""),
                "city":   e.get("city", city or ""),
                "source": source,
            })

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _ticketmaster():
        tm_key = env.get("TICKETMASTER_API_KEY")
        if not tm_key:
            return []
        import requests as _r
        params = {
            "apikey": tm_key, "keyword": artist_name,
            "countryCode": "DE", "classificationName": "Music",
            "size": 20, "sort": "date,asc", "locale": "*",
            "startDateTime": f"{date_from}T00:00:00Z",
            "endDateTime":   f"{date_to}T23:59:59Z",
        }
        if not nationwide and city:
            params["city"] = city
        try:
            resp = _r.get("https://app.ticketmaster.com/discovery/v2/events.json",
                          params=params, timeout=10)
            events = []
            for ev in resp.json().get("_embedded", {}).get("events", []):
                d = ev.get("dates", {}).get("start", {}).get("localDate", "")
                if not d:
                    continue
                venues = ev.get("_embedded", {}).get("venues", [])
                v = venues[0].get("name", "") if venues else ""
                c = venues[0].get("city", {}).get("name", "") if venues else ""
                # Stadtfilter bei city-Suche
                if not nationwide and city and c.lower() and city.lower() not in c.lower():
                    continue
                events.append({"date": d, "venue": v, "city": c})
            return events
        except Exception:
            return []

    def _tavily():
        tk = env.get("TAVILY_API_KEY")
        if not tk:
            return []
        import requests as _rq
        from tavily_concert_client import TavilyConcertClient
        client = TavilyConcertClient(api_key=tk)

        # Nationwide-Suche gibt die meisten Ergebnisse
        evs = client._search_nationwide(artist_name, date_from, date_to)
        results = [{"date": e["datetime"], "venue": e.get("venue",""), "city": e.get("city","")}
                   for e in evs]

        # Wenn eine Stadt angegeben: zusaetzlich city-spezifische Eventim-Suche
        if city and not nationwide:
            years = sorted(set([date_from[:4], date_to[:4]]))
            year_str = " ".join(years)
            try:
                payload = {
                    "api_key": tk,
                    "query": f'"{artist_name}" {city} {year_str} Konzert Ticket',
                    "search_depth": "basic",
                    "max_results": 8,
                    "include_domains": ["eventim.de", "ticketmaster.de"],
                }
                r = _rq.post("https://api.tavily.com/search", json=payload, timeout=12)
                import re as _re
                pat_de  = _re.compile(r'\b(\d{1,2})[./](\d{1,2})[./](20\d{2})\b')
                city_lower = city.lower()
                for res in r.json().get("results", []):
                    text = res.get("content", "") + " " + res.get("title", "")
                    for m in pat_de.finditer(text):
                        d, mo, yr = m.group(1).zfill(2), m.group(2).zfill(2), m.group(3)
                        iso = f"{yr}-{mo}-{d}"
                        if iso < date_from or iso > date_to:
                            continue
                        # Pruefen ob Stadt im Snippet vorkommt
                        start = max(0, m.start() - 150)
                        snippet = text[start: m.end() + 150]
                        if city_lower not in snippet.lower():
                            continue
                        results.append({"date": iso, "venue": city, "city": city, "source_hint": "Eventim"})
            except Exception:
                pass

            # Nur Ergebnisse behalten die zur Stadt passen (kein city = rausfiltern)
            results = [e for e in results
                       if e.get("city") and city.lower() in e["city"].lower()]

        return results

    def _eventim():
        try:
            from eventim_client import EventimClient
            client = EventimClient()
            evs = client.search_artist_any(artist_name, city="" if nationwide else city)
            return [{"date": e["date"], "venue": e.get("venue", ""), "city": e.get("city", "")}
                    for e in evs]
        except Exception:
            return []

    def _songkick():
        try:
            from songkick_client import SongkickClient
            evs = SongkickClient().search_artist_any(
                artist_name, city="" if nationwide else city
            )
            return [{"date": e["date"], "venue": e.get("venue", ""), "city": e.get("city", "")}
                    for e in evs]
        except Exception:
            return []

    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(_ticketmaster): "Ticketmaster",
                ex.submit(_tavily):       "Tavily",
                ex.submit(_eventim):      "Eventim",
                ex.submit(_songkick):     "Songkick"}
        for fut in as_completed(futs):
            try:
                _add(fut.result() or [], futs[fut])
            except Exception:
                pass

    results.sort(key=lambda x: x["date"])
    return jsonify({
        "found":    len(results) > 0,
        "artist":   artist_name,
        "concerts": results,
        "message":  f"{len(results)} Konzert(e) gefunden" if results
                    else f"Keine Konzerte fuer '{artist_name}' gefunden ({date_from} – {date_to})",
    })


@app.route("/research_setlist", methods=["POST"])
def research_setlist():
    """Gemini recherchiert typische Live-Setlist für einen Künstler."""
    data = request.get_json(force=True) or {}
    artist = data.get("artist", "").strip()
    if not artist:
        return jsonify({"error": "Kein Künstler angegeben"})

    env = dotenv_values(BASE_DIR / ".env")
    gemini_key = env.get("GEMINI_API_KEY", "")
    if not gemini_key or gemini_key == "dein-key-hier":
        return jsonify({"error": "Kein Gemini API Key in .env"})

    # Bereits vorhandene Songs laden um Duplikate zu vermeiden
    data_file = BASE_DIR / "concert_data.json"
    concert_data = json.loads(data_file.read_text(encoding="utf-8")) if data_file.exists() else {}
    existing = set()
    sl = concert_data.get("setlist_data", {}).get(artist, {})
    existing.update(sl.get("setlist_titles", []))
    existing.update(sl.get("new_titles", []))

    try:
        from google import genai as _genai_sdk
        _gc = _genai_sdk.Client(api_key=gemini_key)
    except Exception as e:
        return jsonify({"error": f"Gemini Fehler: {e}"})

    prompt = (
        f'Liste die 15 Songs auf die "{artist}" am häufigsten live gespielt hat (2023-2025). '
        f'Nur echte Songtitel, keine Live-Versionen, keine Intros/Outros. '
        f'Antworte NUR mit einer JSON-Liste: ["Song 1", "Song 2", ...]'
    )
    try:
        _gemini_tick()
        resp = _gc.models.generate_content(model="gemini-2.0-flash-lite", contents=prompt)
        text = resp.text.strip()
        # JSON aus Antwort extrahieren
        import re as _re
        m = _re.search(r'\[.*?\]', text, _re.DOTALL)
        if not m:
            return jsonify({"error": "Gemini hat kein verwertbares Format zurückgegeben", "raw": text})
        import json as _json
        songs = _json.loads(m.group(0))
        songs = [s for s in songs if isinstance(s, str) and s.strip() and s not in existing]
        return jsonify({"songs": songs, "existing_count": len(existing)})
    except Exception as e:
        return jsonify({"error": f"Fehler: {e}"})


@app.route("/fill_venues", methods=["POST"])
def fill_venues():
    """Sucht via Gemini fehlende Venues (='Hamburg') und verifiziert per Datum."""
    env = dotenv_values(BASE_DIR / ".env")
    gemini_key = env.get("GEMINI_API_KEY", "")
    if not gemini_key or gemini_key == "dein-key-hier":
        return jsonify({"error": "Kein Gemini API Key"})

    data_file = BASE_DIR / "concert_data.json"
    concert_data = json.loads(data_file.read_text(encoding="utf-8")) if data_file.exists() else {}
    hamburg = concert_data.get("hamburg_artists", {})

    # Künstler mit unbekannter Venue finden
    missing = {
        name: info for name, info in hamburg.items()
        if info.get("venue", "Hamburg") == "Hamburg"
    }
    if not missing:
        return jsonify({"updated": [], "message": "Alle Venues bereits bekannt."})

    try:
        from google import genai as _genai_sdk2
        _gc2 = _genai_sdk2.Client(api_key=gemini_key)
    except Exception as e:
        return jsonify({"error": f"Gemini Init Fehler: {e}"})

    import re as _re
    updated = []

    for name, info in missing.items():
        dates = info.get("dates", [])
        if not dates:
            continue
        date_str = dates[0]  # Erstes/nächstes Konzertdatum
        # Datum für die Suche formatieren: DD.MM.YYYY
        date_fmt = f"{date_str[8:10]}.{date_str[5:7]}.{date_str[0:4]}"

        prompt = (
            f'Wie heißt die Konzertlocation für "{name}" in Hamburg am {date_fmt}? '
            f'Antworte NUR mit dem Venue-Namen, ohne weitere Erklärung. '
            f'Wenn du dir nicht sicher bist oder das Datum nicht übereinstimmt, antworte mit "unbekannt".'
        )
        try:
            _gemini_tick()
            resp = _gc2.models.generate_content(model="gemini-2.0-flash-lite", contents=prompt)
            venue_raw = resp.text.strip().strip('"\'').strip()
            # Plausibilitäts-Check: kurzer Name, kein "unbekannt", kein langer Satz
            if (venue_raw
                    and venue_raw.lower() not in ("unbekannt", "unknown", "hamburg")
                    and len(venue_raw) < 80
                    and "." not in venue_raw[:3]):  # kein Satzanfang
                # Venue für alle Daten mit "Hamburg" aktualisieren
                venues = info.get("venues", {})
                changed = False
                for d in dates:
                    if venues.get(d, "Hamburg") == "Hamburg":
                        venues[d] = venue_raw
                        changed = True
                if changed:
                    info["venues"] = venues
                    info["venue"] = venues.get(dates[0], venue_raw)
                    updated.append({"artist": name, "date": date_fmt, "venue": venue_raw})
        except Exception:
            continue

    if updated:
        concert_data["hamburg_artists"] = hamburg
        _save_concert_data(concert_data)

    return jsonify({"updated": updated, "checked": len(missing)})


@app.route("/remove_artist", methods=["POST"])
def remove_artist():
    """Entfernt einen Künstler aus concert_data.json (Hamburg + RiP)."""
    data = request.get_json(force=True) or {}
    artist_name = data.get("artist", "").strip()
    if not artist_name:
        return jsonify({"error": "Kein Name"})
    data_file = BASE_DIR / "concert_data.json"
    concert_data = json.loads(data_file.read_text(encoding="utf-8")) if data_file.exists() else {}
    concert_data.get("hamburg_artists", {}).pop(artist_name, None)
    concert_data.get("rip_artists", {}).pop(artist_name, None)
    _save_concert_data(concert_data)
    return jsonify({"ok": True})


@app.route("/clear_concerts", methods=["POST"])
def clear_concerts():
    """Löscht alle Konzertdaten (hamburg_artists + rip_artists + support_acts).
    Setlist-Daten (setlist_data) bleiben erhalten."""
    data_file = BASE_DIR / "concert_data.json"
    concert_data = json.loads(data_file.read_text(encoding="utf-8")) if data_file.exists() else {}
    concert_data["hamburg_artists"] = {}
    concert_data["rip_artists"] = {}
    concert_data["support_acts"] = {}
    _save_concert_data(concert_data)
    return jsonify({"ok": True})


@app.route("/add_artist_manual", methods=["POST"])
def add_artist_manual():
    """Fügt einen Künstler manuell mit Datum und Venue zu concert_data.json hinzu.
    festival != '' → rip_artists; sonst → hamburg_artists.
    Merged mit vorhandenen Daten statt zu überschreiben. Dates werden sortiert."""
    data = request.get_json(force=True) or {}
    artist_name = data.get("artist", "").strip()
    date_str    = data.get("date", "").strip()
    venue       = data.get("venue", "").strip()
    city_str    = data.get("city", "").strip()
    festival    = data.get("festival", "").strip()

    if not artist_name or not date_str:
        return jsonify({"error": "Künstlername und Datum erforderlich"})

    # Kapitalisierung: "die toten hosen" → "Die Toten Hosen"
    # Nur wenn vollständig lowercase — Bandnamen wie "AC/DC" bleiben unberührt
    if artist_name == artist_name.lower():
        artist_name = artist_name.title()

    data_file = BASE_DIR / "concert_data.json"
    concert_data = json.loads(data_file.read_text(encoding="utf-8")) if data_file.exists() else {}

    if festival:
        # ── Festival-Konzert → rip_artists ────────────────────────────
        # Festival-Slot: venue ist immer der Festivalort (z.B. "Rock im Park, Nuernberg"),
        # die Stage gehoert in das eigene stage-Feld (sonst rutscht sie ins venue wie bei Loathe-Bug).
        festival_venue = venue or f"{festival}, Nuernberg" if "rock im park" in festival.lower() else (venue or festival)
        target   = concert_data.setdefault("rip_artists", {})
        existing = target.get(artist_name, {})
        dates    = sorted(set(existing.get("dates", []) + [date_str]))
        venues_map = {**existing.get("venues", {}), date_str: festival_venue}
        new_entry = {
            **existing,
            "dates":    dates,
            "venue":    festival_venue,
            "venues":   venues_map,
            "festival": festival,
        }
        # Optionale Slot-Felder (Tag, Stage, Start, End) - nur setzen wenn ausgefuellt
        day_val   = (data.get("day") or "").strip()
        stage_val = (data.get("stage") or "").strip()
        start_val = (data.get("start") or "").strip()
        end_val   = (data.get("end") or "").strip()
        if day_val:   new_entry["day"]   = day_val
        if stage_val: new_entry["stage"] = stage_val
        if start_val: new_entry["start"] = start_val
        if end_val:   new_entry["end"]   = end_val
        target[artist_name] = new_entry
    else:
        # ── Stadt-Konzert → hamburg_artists ───────────────────────────
        fallback_venue = venue or city_str or "Hamburg"
        target   = concert_data.setdefault("hamburg_artists", {})
        existing = target.get(artist_name, {})
        dates    = sorted(set(existing.get("dates", []) + [date_str]))
        venues_map = {**existing.get("venues", {}), date_str: fallback_venue}
        entry = {
            **existing,             # Songs, URIs etc. bleiben erhalten
            "dates":  dates,
            "venue":  fallback_venue,
            "venues": venues_map,
        }
        if city_str:
            entry["city"] = city_str
        target[artist_name] = entry

    _save_concert_data(concert_data)
    return jsonify({"ok": True, "festival": festival})


@app.route("/check_spotify", methods=["POST"])
def check_spotify():
    """Check which songs exist on Spotify for an artist. Returns {song: uri_or_null}."""
    data = request.get_json(force=True) or {}
    artist_name = data.get("artist", "").strip()
    songs = data.get("songs", [])

    if not songs or not artist_name:
        return jsonify({"results": {}})

    # Sofort abbrechen wenn Spotify CC bekannt rate-limited ist
    _cc_health = _api_health.get("spotify_cc", {})
    if _cc_health.get("ok") is False:
        _retry = _cc_health.get("retry_after", 0)
        _checked = _cc_health.get("checked", 0)
        if _retry and (int(_time.time()) < _checked + _retry):
            return jsonify({"results": {s: None for s in songs}, "rate_limited": True, "retry_after": _retry})

    env = dotenv_values(BASE_DIR / ".env")
    try:
        import re as _re
        import requests as _req_cs
        from concurrent.futures import ThreadPoolExecutor, as_completed

        _auth_cs = _make_spotify_oauth(env)
        _tok_cs  = _auth_cs.get_cached_token()
        if not _tok_cs:
            return jsonify({"results": {s: None for s in songs}})
        _access_token = _tok_cs["access_token"]
        _headers_cs   = {"Authorization": f"Bearer {_access_token}"}

        def _norm(s):
            return _re.sub(r"[^\w\s]", "", s.lower()).strip()

        artist_lower = artist_name.lower()

        class _SpotifyRateLimit(Exception):
            def __init__(self, retry_after=0):
                self.retry_after = retry_after

        def _check_song(song):
            # Direkte HTTP-Requests statt Spotipy — kein internes Retry-Waiting bei 429
            song_norm = _norm(song)
            for q in [f'track:"{song}" artist:"{artist_name}"', f'{song} {artist_name}']:
                r = _req_cs.get(
                    "https://api.spotify.com/v1/search",
                    params={"q": q, "type": "track", "limit": 5},
                    headers=_headers_cs, timeout=5,
                )
                if r.status_code == 429:
                    raise _SpotifyRateLimit(int(r.headers.get("Retry-After", 0)))
                if r.status_code != 200:
                    return song, None
                items = r.json().get("tracks", {}).get("items", [])
                for t in items:
                    t_artists = [a["name"].lower() for a in t.get("artists", [])]
                    if _norm(t["name"]) == song_norm and any(artist_lower in a or a in artist_lower for a in t_artists):
                        return song, t["uri"]
            return song, None

        songs_to_check = songs[:40]
        results = {s: None for s in songs}
        rate_limited = False
        retry_after = 0
        executor = ThreadPoolExecutor(max_workers=5)
        try:
            futures = {executor.submit(_check_song, s): s for s in songs_to_check}
            for f in as_completed(futures, timeout=25):
                try:
                    song, uri = f.result()
                    results[song] = uri
                except _SpotifyRateLimit as _rl:
                    rate_limited = True
                    retry_after = _rl.retry_after
                    _update_api_health("spotify_cc", False, error="rate_limited", retry_after=retry_after)
                    break
        except Exception:
            pass
        finally:
            executor.shutdown(wait=False)

        if rate_limited:
            return jsonify({"results": {s: None for s in songs}, "rate_limited": True, "retry_after": retry_after})
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e), "results": {s: None for s in songs}})


@app.route("/health")
def health():
    return jsonify({"ok": True})


@app.route("/api_health")
def api_health():
    """Gibt den letzten bekannten Status aller APIs zurück (kein Probe)."""
    env = dotenv_values(BASE_DIR / ".env")
    keys = {
        "spotify_cc":  bool(env.get("SPOTIFY_CLIENT_ID") and env.get("SPOTIFY_CLIENT_SECRET")),
        "spotify_oauth": (BASE_DIR / ".cache").exists(),
        "setlist":     bool(env.get("SETLISTFM_API_KEY")),
        "gemini":      bool(env.get("GEMINI_API_KEY") and env.get("GEMINI_API_KEY") != "dein-key-hier"),
        "tavily":      bool(env.get("TAVILY_API_KEY")),
        "ticketmaster": bool(env.get("TICKETMASTER_API_KEY")),
        "serper":      bool(env.get("SERPER_API_KEY")),
    }
    result = {}
    for api_id, has_key in keys.items():
        cached = _api_health.get(api_id, {})
        result[api_id] = {
            "has_key":     has_key,
            "ok":          cached.get("ok"),
            "checked":     cached.get("checked"),
            "retry_after": cached.get("retry_after", 0),
            "error":       cached.get("error", ""),
        }
    return jsonify(result)


@app.route("/api_health_check", methods=["POST"])
def api_health_check():
    """Probe-Requests für alle (oder ausgewählte) APIs, aktualisiert Cache. Parallel via Threads."""
    import re as _re_h
    from concurrent.futures import ThreadPoolExecutor, as_completed
    data = request.get_json(force=True) or {}
    apis = data.get("apis") or ["spotify_cc", "spotify_oauth", "setlist", "gemini", "tavily", "ticketmaster", "serper"]
    env  = dotenv_values(BASE_DIR / ".env")

    def _probe_spotify_cc():
        cc_id  = env.get("SPOTIFY_CLIENT_ID", "")
        cc_sec = env.get("SPOTIFY_CLIENT_SECRET", "")
        if not (cc_id and cc_sec):
            return "spotify_cc", {"ok": None, "error": "Kein Key"}
        try:
            from spotipy import Spotify
            from spotipy.oauth2 import SpotifyClientCredentials
            sp = Spotify(auth_manager=SpotifyClientCredentials(client_id=cc_id, client_secret=cc_sec), requests_timeout=6)
            sp.search(q="test", type="track", limit=1)
            _update_api_health("spotify_cc", True)
            return "spotify_cc", {"ok": True}
        except Exception as e:
            err = str(e)
            m = _re_h.search(r'[Rr]etry.*?(\d+)\s*s', err)
            retry = int(m.group(1)) if m else 0
            _update_api_health("spotify_cc", False, error=err, retry_after=retry)
            return "spotify_cc", {"ok": False, "error": err[:120], "retry_after": retry}

    def _probe_spotify_oauth():
        cache_path = BASE_DIR / ".cache"
        if not cache_path.exists():
            return "spotify_oauth", {"ok": None, "error": "Kein .cache (noch nicht eingeloggt)"}
        try:
            from spotipy.oauth2 import SpotifyOAuth
            auth = SpotifyOAuth(
                client_id=env.get("SPOTIFY_CLIENT_ID", ""),
                client_secret=env.get("SPOTIFY_CLIENT_SECRET", ""),
                redirect_uri=env.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
                scope=_SPOTIFY_SCOPE, cache_path=str(cache_path),
            )
            token = auth.get_cached_token()
            if not token:
                return "spotify_oauth", {"ok": False, "error": "Kein gültiger Token"}
            elif auth.is_token_expired(token):
                auth.refresh_access_token(token["refresh_token"])
                _update_api_health("spotify_oauth", True)
                return "spotify_oauth", {"ok": True, "note": "Token erneuert"}
            else:
                _update_api_health("spotify_oauth", True)
                return "spotify_oauth", {"ok": True}
        except Exception as e:
            _update_api_health("spotify_oauth", False, error=str(e))
            return "spotify_oauth", {"ok": False, "error": str(e)[:120]}

    def _probe_setlist():
        sl_key = env.get("SETLISTFM_API_KEY", "")
        if not sl_key:
            return "setlist", {"ok": None, "error": "Kein Key"}
        try:
            import requests as _req_h
            r = _req_h.get(
                "https://api.setlist.fm/rest/1.0/search/artists",
                params={"artistName": "test", "p": 1},
                headers={"x-api-key": sl_key, "Accept": "application/json"},
                timeout=6,
            )
            if r.status_code == 429:
                retry = int(r.headers.get("Retry-After", 0)) or _seconds_until_midnight_utc()
                _update_api_health("setlist", False, error="429 Rate Limit", retry_after=retry)
                return "setlist", {"ok": False, "error": "Rate Limit", "retry_after": retry}
            else:
                _update_api_health("setlist", True)
                return "setlist", {"ok": True}
        except Exception as e:
            _update_api_health("setlist", False, error=str(e))
            return "setlist", {"ok": False, "error": str(e)[:120]}

    def _probe_gemini():
        gkey = env.get("GEMINI_API_KEY", "")
        if not gkey or gkey == "dein-key-hier":
            return "gemini", {"ok": None, "error": "Kein Key"}
        try:
            from google import genai as _gai
            _gai.Client(api_key=gkey).models.generate_content(model="gemini-2.0-flash-lite", contents="Hi")
            _gemini_tick()
            _update_api_health("gemini", True)
            return "gemini", {"ok": True, "requests_today": _gemini_counter["count"], "limit": GEMINI_RPD_LIMIT}
        except Exception as e:
            err = str(e)
            m = _re_h.search(r'[Rr]etry.*?(\d+)\s*s', err)
            retry = int(m.group(1)) if m else 0
            _update_api_health("gemini", False, error=err, retry_after=retry)
            return "gemini", {"ok": False, "retry_after": retry, "error": err[:120]}

    def _probe_tavily():
        tv_key = env.get("TAVILY_API_KEY", "")
        if not tv_key:
            return "tavily", {"ok": None, "error": "Kein Key"}
        try:
            import requests as _req_h
            r = _req_h.post(
                "https://api.tavily.com/search",
                json={"api_key": tv_key, "query": "test", "max_results": 1},
                timeout=6,
            )
            if r.status_code in (402, 429) or "quota" in r.text.lower() or "credit" in r.text.lower():
                _update_api_health("tavily", False, error="Credits erschöpft")
                return "tavily", {"ok": False, "error": "Credits erschöpft"}
            else:
                _update_api_health("tavily", True)
                return "tavily", {"ok": True}
        except Exception as e:
            _update_api_health("tavily", False, error=str(e))
            return "tavily", {"ok": False, "error": str(e)[:120]}

    def _probe_ticketmaster():
        tm_key = env.get("TICKETMASTER_API_KEY", "")
        if not tm_key:
            return "ticketmaster", {"ok": None, "error": "Kein Key"}
        try:
            import requests as _req_h
            r = _req_h.get(
                "https://app.ticketmaster.com/discovery/v2/events.json",
                params={"keyword": "test", "apikey": tm_key, "size": 1},
                timeout=6,
            )
            if r.status_code == 429:
                _update_api_health("ticketmaster", False, error="Rate Limit")
                return "ticketmaster", {"ok": False, "error": "Rate Limit"}
            else:
                _update_api_health("ticketmaster", True)
                return "ticketmaster", {"ok": True}
        except Exception as e:
            _update_api_health("ticketmaster", False, error=str(e))
            return "ticketmaster", {"ok": False, "error": str(e)[:120]}

    def _probe_serper():
        sr_key = env.get("SERPER_API_KEY", "")
        if not sr_key:
            return "serper", {"ok": None, "error": "Kein Key"}
        _update_api_health("serper", True)
        return "serper", {"ok": True, "note": "Key vorhanden (kein Probe-Request)"}

    probe_map = {
        "spotify_cc": _probe_spotify_cc,
        "spotify_oauth": _probe_spotify_oauth,
        "setlist": _probe_setlist,
        "gemini": _probe_gemini,
        "tavily": _probe_tavily,
        "ticketmaster": _probe_ticketmaster,
        "serper": _probe_serper,
    }

    out = {}
    with ThreadPoolExecutor(max_workers=7) as pool:
        futures = {pool.submit(probe_map[api_id]): api_id for api_id in apis if api_id in probe_map}
        for future in as_completed(futures, timeout=10):
            try:
                api_id, result = future.result()
                out[api_id] = result
            except Exception as e:
                api_id = futures[future]
                out[api_id] = {"ok": False, "error": str(e)[:120]}

    return jsonify(out)


@app.route("/get_playlists")
def get_playlists():
    """Alle Spotify-Playlists des Users, sortiert nach Datum im Namen."""
    env = dotenv_values(BASE_DIR / ".env")
    try:
        import re as _re
        sp = _make_spotify_client(env)
        my_id = sp.current_user().get("id", "")

        playlists = []
        offset = 0
        for _page in range(20):  # max 1000 Playlists (20×50), Sicherheits-Bremse
            result = sp.current_user_playlists(limit=50, offset=offset)
            items = result.get("items", [])
            if not items:
                break
            for p in items:
                if not p:
                    continue
                name = p.get("name", "")
                date_sort = ""
                m = _re.search(r'(\d{2})\.(\d{2})\.(\d{4})', name)
                if m:
                    date_sort = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
                else:
                    m2 = _re.search(r'(\d{2})/(\d{2})/(\d{4})', name)
                    if m2:
                        date_sort = f"{m2.group(3)}-{m2.group(2)}-{m2.group(1)}"
                    else:
                        m3 = _re.search(r'(\d{4})-(\d{2})-(\d{2})', name)
                        if m3:
                            date_sort = m3.group(0)
                images = p.get("images") or []
                owner_id = (p.get("owner") or {}).get("id", "")
                playlists.append({
                    "id": p.get("id", ""),
                    "name": name,
                    "tracks": (p.get("items") or p.get("tracks") or {}).get("total", 0),
                    "image": images[0]["url"] if images else None,
                    "url": p.get("external_urls", {}).get("spotify", ""),
                    "description": p.get("description", "") or "",
                    "date_sort": date_sort,
                    "is_mine": owner_id == my_id,
                })
            if result.get("next") is None:
                break
            offset += 50

        playlists.sort(key=lambda p: (p["date_sort"] == "", p["date_sort"]))
        for p in playlists:
            del p["date_sort"]

        followed_names = set()
        try:
            after = None
            for _artist_page in range(40):  # max 2000 Artists, Sicherheits-Bremse
                res = sp.current_user_followed_artists(limit=50, after=after)
                page = res["artists"]
                for a in page["items"]:
                    if a and a.get("name"):
                        followed_names.add(a["name"])
                after = page["cursors"]["after"]
                if not after:
                    break
        except Exception:
            pass
        artists = sorted(followed_names, key=len, reverse=True)

        return jsonify({"playlists": playlists, "artists": artists})
    except RuntimeError as e:
        if "auth" in str(e):
            return jsonify({"error": "auth", "playlists": [], "artists": []})
        return jsonify({"error": str(e), "playlists": [], "artists": []})
    except Exception as e:
        return jsonify({"error": str(e), "playlists": [], "artists": []})


@app.route("/rename_playlist", methods=["POST"])
def rename_playlist():
    env = dotenv_values(BASE_DIR / ".env")
    data = request.get_json() or {}
    playlist_id = data.get("id", "").strip()
    new_name = data.get("name", "").strip()
    if not playlist_id or not new_name:
        return jsonify({"error": "id und name erforderlich"}), 400
    try:
        from spotipy import Spotify
        from spotipy.oauth2 import SpotifyOAuth
        sp = Spotify(
            auth_manager=SpotifyOAuth(
                client_id=env.get("SPOTIFY_CLIENT_ID", ""),
                client_secret=env.get("SPOTIFY_CLIENT_SECRET", ""),
                redirect_uri=env.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
                scope="playlist-modify-public playlist-modify-private",
                cache_path=str(BASE_DIR / ".cache"),
            ),
            requests_timeout=8,
        )
        sp.playlist_change_details(playlist_id, name=new_name)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/track_preview")
def track_preview():
    """Gibt preview_url (30s MP3) für eine Spotify Track URI zurück."""
    uri = request.args.get("uri", "").strip()
    if not uri.startswith("spotify:track:"):
        return jsonify({"error": "Ungueltige URI", "preview_url": None})
    track_id = uri.split(":")[-1]
    env = dotenv_values(BASE_DIR / ".env")
    try:
        from spotipy import Spotify
        from spotipy.oauth2 import SpotifyClientCredentials
        sp = Spotify(auth_manager=SpotifyClientCredentials(
            client_id=env.get("SPOTIFY_CLIENT_ID", ""),
            client_secret=env.get("SPOTIFY_CLIENT_SECRET", ""),
        ), requests_timeout=8)
        track = sp.track(track_id)
        return jsonify({"preview_url": track.get("preview_url")})
    except Exception as e:
        return jsonify({"error": str(e), "preview_url": None})


@app.route("/player/play", methods=["POST"])
def player_play():
    """Startet Wiedergabe eines Tracks — optional auf device_id (Web Playback SDK)."""
    env = dotenv_values(BASE_DIR / ".env")
    data = request.get_json() or {}
    uri = data.get("uri", "").strip()
    device_id = data.get("device_id", None)
    if not uri:
        return jsonify({"error": "uri erforderlich"}), 400
    try:
        from spotipy import Spotify
        from spotipy.oauth2 import SpotifyOAuth
        sp = Spotify(auth_manager=SpotifyOAuth(
            client_id=env.get("SPOTIFY_CLIENT_ID", ""),
            client_secret=env.get("SPOTIFY_CLIENT_SECRET", ""),
            redirect_uri=env.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
            scope="user-modify-playback-state user-read-playback-state streaming user-read-email user-read-private",
            cache_path=str(BASE_DIR / ".cache"),
        ), requests_timeout=8)
        sp.start_playback(device_id=device_id, uris=[uri])
        return jsonify({"ok": True})
    except Exception as e:
        err = str(e)
        if "Premium" in err or "403" in err:
            return jsonify({"error": "premium", "message": "Spotify Premium benötigt"})
        if "404" in err or "active" in err.lower():
            return jsonify({"error": "no_device", "message": "Kein aktives Spotify-Gerät"})
        return jsonify({"error": err})


@app.route("/player/pause", methods=["POST"])
def player_pause():
    """Pausiert die aktuelle Spotify-Wiedergabe."""
    env = dotenv_values(BASE_DIR / ".env")
    try:
        from spotipy import Spotify
        from spotipy.oauth2 import SpotifyOAuth
        sp = Spotify(auth_manager=SpotifyOAuth(
            client_id=env.get("SPOTIFY_CLIENT_ID", ""),
            client_secret=env.get("SPOTIFY_CLIENT_SECRET", ""),
            redirect_uri=env.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
            scope="user-modify-playback-state user-read-playback-state streaming user-read-email user-read-private",
            cache_path=str(BASE_DIR / ".cache"),
        ), requests_timeout=8)
        sp.pause_playback()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/spotify_token")
def spotify_token():
    """Gibt den aktuellen Spotify Access Token zurück (für Web Playback SDK)."""
    env = dotenv_values(BASE_DIR / ".env")
    try:
        from spotipy.oauth2 import SpotifyOAuth
        auth = SpotifyOAuth(
            client_id=env.get("SPOTIFY_CLIENT_ID", ""),
            client_secret=env.get("SPOTIFY_CLIENT_SECRET", ""),
            redirect_uri=env.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
            scope="user-follow-read playlist-read-private playlist-modify-public playlist-modify-private ugc-image-upload user-modify-playback-state user-read-playback-state streaming user-read-email user-read-private",
            cache_path=str(BASE_DIR / ".cache"),
        )
        token_info = auth.get_cached_token()
        if not token_info:
            return jsonify({"error": "not_authenticated"}), 401
        if auth.is_token_expired(token_info):
            token_info = auth.refresh_access_token(token_info["refresh_token"])
        return jsonify({"access_token": token_info["access_token"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/search_tracks")
def search_tracks():
    """Spotify-Autocomplete: Songvorschläge für einen Künstler."""
    artist = request.args.get("artist", "").strip()
    q      = request.args.get("q", "").strip()
    if not artist or len(q) < 2:
        return jsonify({"tracks": []})

    env = dotenv_values(BASE_DIR / ".env")
    try:
        from spotipy import Spotify
        from spotipy.oauth2 import SpotifyClientCredentials
        sp = Spotify(auth_manager=SpotifyClientCredentials(
            client_id=env.get("SPOTIFY_CLIENT_ID", ""),
            client_secret=env.get("SPOTIFY_CLIENT_SECRET", ""),
        ), requests_timeout=8)
        r = sp.search(q=f'track:"{q}" artist:"{artist}"', type="track", limit=8)
        items = r.get("tracks", {}).get("items", [])
        # fallback: loose search if strict returns nothing
        if not items:
            r2 = sp.search(q=f'{q} {artist}', type="track", limit=8)
            items = r2.get("tracks", {}).get("items", [])
        tracks = []
        seen = set()
        for t in items:
            name = t.get("name", "")
            if name.lower() in seen:
                continue
            seen.add(name.lower())
            tracks.append({
                "title": name,
                "uri":   t["uri"],
                "album": t.get("album", {}).get("name", ""),
            })
        _update_api_health("spotify_cc", True)
        return jsonify({"tracks": tracks})
    except Exception as e:
        err = str(e)
        import re as _re2
        m = _re2.search(r'[Rr]etry.*?(\d+)\s*s', err)
        retry = int(m.group(1)) if m else 0
        _update_api_health("spotify_cc", False, error=err, retry_after=retry)
        return jsonify({"tracks": [], "error": err})


@app.route("/search_artists")
def search_artists():
    """Spotify-Autocomplete: Künstlervorschläge beim Tippen."""
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])
    env = dotenv_values(BASE_DIR / ".env")

    try:
        sp = _make_spotify_client(env)
    except RuntimeError:
        return jsonify({"error": "auth"})

    from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FutTimeout
    import re as _re_sa
    _ex = ThreadPoolExecutor(max_workers=1)
    _fut = _ex.submit(lambda: sp.search(q=q, type="artist", limit=8))
    try:
        r = _fut.result(timeout=6)
        _ex.shutdown(wait=False)
        _update_api_health("spotify_cc", True)
    except _FutTimeout:
        _ex.shutdown(wait=False)
        _update_api_health("spotify_cc", False, error="Timeout")
        return jsonify({"error": "timeout"})
    except Exception as _e_sa:
        _ex.shutdown(wait=False)
        _err_sa = str(_e_sa)
        _m_sa = _re_sa.search(r'[Rr]etry.*?(\d+)\s*s', _err_sa)
        _retry_sa = int(_m_sa.group(1)) if _m_sa else 0
        _update_api_health("spotify_cc", False, error=_err_sa, retry_after=_retry_sa)
        return jsonify([])

    items = r.get("artists", {}).get("items", [])
    return jsonify([
        {
            "name":   a["name"],
            "genres": a.get("genres", [])[:2],
            "image":  a["images"][-1]["url"] if a.get("images") else None,
        }
        for a in items
    ])


@app.route("/add_song_to_artist", methods=["POST"])
def add_song_to_artist():
    """Fügt einen manuell gesuchten Song zur setlist_data eines Künstlers hinzu."""
    data   = request.get_json(force=True) or {}
    artist = data.get("artist", "").strip()
    title  = data.get("title", "").strip()
    uri    = data.get("uri", "").strip()
    stype  = data.get("type", "setlist")   # "setlist" or "new"

    if not artist or not title:
        return jsonify({"ok": False, "error": "Fehlende Daten"})

    data_file = BASE_DIR / "concert_data.json"
    concert_data = json.loads(data_file.read_text(encoding="utf-8")) if data_file.exists() else {}
    setlist_data = concert_data.get("setlist_data", {})
    entry = setlist_data.setdefault(artist, {"setlist_titles": [], "new_titles": [], "spotify_uris": {}})

    target_list = entry["new_titles"] if stype == "new" else entry["setlist_titles"]
    if title not in target_list:
        target_list.append(title)
    if uri:
        entry["spotify_uris"][title] = uri

    concert_data["setlist_data"] = setlist_data
    _save_concert_data(concert_data)
    return jsonify({"ok": True})


@app.route("/new_releases", methods=["POST"])
def new_releases():
    """Holt neue/aktuelle Songs eines Künstlers von Spotify (neueste Releases)."""
    data       = request.get_json(force=True) or {}
    artist     = data.get("artist", "").strip()
    already    = set(data.get("already_have", []))
    needed     = int(data.get("needed", 5))

    if not artist:
        return jsonify({"songs": []})

    env = dotenv_values(BASE_DIR / ".env")
    import re as _re
    _live_pat = _re.compile(r'\blive\b', _re.IGNORECASE)

    try:
        from spotipy import Spotify
        from spotipy.oauth2 import SpotifyOAuth
        sp = Spotify(auth_manager=SpotifyOAuth(
            client_id=env.get("SPOTIFY_CLIENT_ID", ""),
            client_secret=env.get("SPOTIFY_CLIENT_SECRET", ""),
            redirect_uri=env.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
            scope="user-follow-read",
            cache_path=str(BASE_DIR / ".cache"),
        ))
        # Künstler-ID suchen
        r = sp.search(q=f"artist:{artist}", type="artist", limit=1)
        items = r.get("artists", {}).get("items", [])
        if not items:
            return jsonify({"songs": [], "error": "Künstler nicht gefunden"})
        artist_id = items[0]["id"]

        # Neueste Alben/Singles holen (nach Release-Datum sortiert)
        albums = sp.artist_albums(artist_id, album_type="album,single", limit=10)
        songs = []
        seen = {s.lower() for s in already}
        for album in sorted(albums["items"], key=lambda a: a["release_date"], reverse=True):
            tracks = sp.album_tracks(album["id"])
            for t in tracks["items"]:
                name = t.get("name", "")
                if name and name.lower() not in seen and not _live_pat.search(name):
                    songs.append(name)
                    seen.add(name.lower())
            if len(songs) >= needed:
                break

        return jsonify({"songs": songs[:needed]})
    except Exception as e:
        return jsonify({"songs": [], "error": str(e)})


@app.route("/create_playlist", methods=["POST"])
def create_playlist():
    """Create/update Spotify playlist from pre-resolved track URIs."""
    data = request.get_json(force=True) or {}
    playlist_name    = data.get("playlist_name", "Setlist-Mix 2026")
    track_uris       = data.get("track_uris", [])
    description      = data.get("description", "")
    artist_snapshot  = data.get("artist_snapshot", {})   # Concert-History Snapshot

    if not track_uris:
        return jsonify({"error": "Keine Tracks ausgewählt"})

    env = dotenv_values(BASE_DIR / ".env")
    try:
        from spotify_client import SpotifyClient
        spotify = SpotifyClient(
            client_id=env.get("SPOTIFY_CLIENT_ID", ""),
            client_secret=env.get("SPOTIFY_CLIENT_SECRET", ""),
            redirect_uri=env.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
        )
        playlist_id, created = spotify.get_or_create_playlist(playlist_name)
        added, removed = spotify.update_playlist(playlist_id, track_uris, description=description[:300])

        # ── Concert-History + Backup speichern ──────────────────────────
        if artist_snapshot:
            data_file = BASE_DIR / "concert_data.json"
            cd = json.loads(data_file.read_text(encoding="utf-8")) if data_file.exists() else {}
            history = cd.setdefault("concert_history", [])
            # Scores aus setlist_data ergänzen (falls Frontend sie nicht mitschickte)
            setlist_data = cd.get("setlist_data", {})
            for artist, snap in artist_snapshot.items():
                sd = setlist_data.get(artist, {})
                if sd.get("scores") and not snap.get("badges"):
                    snap["badges"] = {
                        s: {"badge": sd.get("badges", {}).get(s, "setlist"),
                            "score": sd["scores"].get(s, 0)}
                        for s in snap.get("songs", [])
                    }
            entry = {
                "playlist_id":   playlist_id,
                "playlist_name": playlist_name,
                "created_at":    _date.today().isoformat(),
                "description":   description,
                "artists":       artist_snapshot,
            }
            # Bestehenden Eintrag aktualisieren oder neu anhängen
            idx = next((i for i, h in enumerate(history)
                        if h.get("playlist_id") == playlist_id), -1)
            if idx >= 0:
                history[idx] = entry
            else:
                history.append(entry)
            _save_concert_data(cd)

        return jsonify({
            "ok": True,
            "playlist_id": playlist_id,
            "created": created,
            "added": added,
            "removed": removed,
            "total": len(track_uris),
            "name": playlist_name,
        })
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/concert_history")
def concert_history():
    """Gibt die gespeicherte Konzert-History zurück."""
    data_file = BASE_DIR / "concert_data.json"
    cd = json.loads(data_file.read_text(encoding="utf-8")) if data_file.exists() else {}
    history = cd.get("concert_history", [])
    # Neueste zuerst
    history = sorted(history, key=lambda h: h.get("created_at", ""), reverse=True)
    return jsonify({"history": history})


@app.route("/load_playlist_songs/<playlist_id>")
def load_playlist_songs(playlist_id):
    """Gibt gespeicherte Songs aus concert_history zurück — für Restore ohne API-Calls."""
    data_file = BASE_DIR / "concert_data.json"
    cd = json.loads(data_file.read_text(encoding="utf-8")) if data_file.exists() else {}
    history = cd.get("concert_history", [])
    entry = next((h for h in history if h.get("playlist_id") == playlist_id), None)
    if not entry:
        return jsonify({"error": "Kein Backup gefunden"}), 404
    return jsonify({
        "playlist_id":   entry["playlist_id"],
        "playlist_name": entry["playlist_name"],
        "created_at":    entry.get("created_at", ""),
        "artists":       entry.get("artists", {}),
    })


@app.route("/import_playlist_to_mix", methods=["POST"])
def import_playlist_to_mix():
    """
    Lädt eine Spotify-Playlist und rekonstruiert Konzert-Daten:
    1. Aus concert_history (exakt) falls vorhanden
    2. Aus Playlist-Beschreibung + setlist_data (Rekonstruktion)
    """
    data = request.get_json(force=True) or {}
    playlist_id   = data.get("playlist_id", "").strip()
    playlist_name = data.get("playlist_name", "").strip()
    if not playlist_id:
        return jsonify({"error": "playlist_id fehlt"}), 400

    data_file = BASE_DIR / "concert_data.json"
    cd = json.loads(data_file.read_text(encoding="utf-8")) if data_file.exists() else {}

    # Schritt 1: Exakt aus History laden
    history = cd.get("concert_history", [])
    exact = next((h for h in history if h.get("playlist_id") == playlist_id), None)
    if exact:
        return jsonify({
            "source":    "history",
            "entry":     exact,
            "quality":   "exact",
        })

    # Schritt 2: Tracks von Spotify holen + rekonstruieren
    env = dotenv_values(BASE_DIR / ".env")
    try:
        sp = _make_spotify_client(env)
        # Alle Tracks holen (paginiert)
        tracks_by_artist: dict[str, list] = {}
        uris_by_artist:   dict[str, dict] = {}
        offset = 0
        while True:
            result = sp.playlist_tracks(playlist_id, limit=100, offset=offset)
            items  = result.get("items", [])
            if not items:
                break
            for item in items:
                t = item.get("track")
                if not t or not t.get("name"):
                    continue
                title  = t["name"]
                uri    = t["uri"]
                artist = t["artists"][0]["name"] if t.get("artists") else "Unbekannt"
                tracks_by_artist.setdefault(artist, []).append(title)
                uris_by_artist.setdefault(artist, {})[title] = uri
            if result.get("next"):
                offset += 100
            else:
                break

        # Rekonstruktion: setlist_data abgleichen
        setlist_data = cd.get("setlist_data", {})
        artists_out  = {}
        for artist, songs in tracks_by_artist.items():
            sl = setlist_data.get(artist, {})
            artists_out[artist] = {
                "source":   "reconstructed",
                "date":     "",
                "meta":     "",
                "tt_start": "",
                "tt_end":   "",
                "songs":    songs,
                "uris":     uris_by_artist.get(artist, {}),
                "has_setlist_data": bool(sl.get("setlist_titles")),
            }

        # Beschreibung parsen für Datum/Festival-Hinweise
        pl_info = sp.playlist(playlist_id, fields="description,name")
        desc    = pl_info.get("description", "")
        name    = pl_info.get("name", playlist_name)

        return jsonify({
            "source":       "reconstructed",
            "quality":      "partial",
            "playlist_name": name,
            "description":  desc,
            "artists":      artists_out,
            "total_tracks": sum(len(v) for v in tracks_by_artist.values()),
        })
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/apply_import_to_mix", methods=["POST"])
def apply_import_to_mix():
    """
    Importiert Kuenstler aus einer alten Playlist in concert_data.json.
    Payload: {artists: {name: {source, date, tt_start, tt_end, songs, uris, meta, ...}}}
    source = 'rip' / 'festival' → rip_artists
    source = 'hh' / 'trip' / '' → hamburg_artists
    """
    data = request.get_json(force=True) or {}
    artists_in = data.get("artists", {})
    if not artists_in:
        return jsonify({"error": "Keine Kuenstler angegeben"})

    data_file = BASE_DIR / "concert_data.json"
    cd = json.loads(data_file.read_text(encoding="utf-8")) if data_file.exists() else {}
    hamburg    = cd.setdefault("hamburg_artists", {})
    rip        = cd.setdefault("rip_artists", {})
    setlist_dt = cd.setdefault("setlist_data", {})

    added_hamburg = 0
    added_rip     = 0

    for artist_name, info in artists_in.items():
        if not artist_name or not isinstance(info, dict):
            continue

        source   = info.get("source", "")        # 'hh', 'rip', 'trip', 'festival', 'reconstructed'
        date     = info.get("date", "").strip()
        if not date or date[:10] < today:
            date = today
        venue    = info.get("venue", "").strip()
        meta     = info.get("meta", "").strip()  # z.B. "Rock im Park, Nürnberg — 05.06.2026"
        songs    = info.get("songs", [])
        uris     = info.get("uris", {})
        tt_start = info.get("tt_start", "").strip()
        tt_end   = info.get("tt_end", "").strip()

        is_festival = source in ("rip", "festival")

        if is_festival:
            # ── Festival-Akt → rip_artists ────────────────────────────────
            # Festival-Name aus meta ableiten (z.B. "Rock im Park, Nürnberg"), fallback "Rock im Park"
            import re as _re_imp
            fest_name = "Rock im Park"
            m_fest = _re_imp.match(r'^([^—·,]+)', meta)
            if m_fest:
                cand = m_fest.group(1).strip()
                if 3 < len(cand) < 40:
                    fest_name = cand
            existing = rip.get(artist_name, {})
            dates    = sorted(set(existing.get("dates", []) + ([date] if date else [])))
            entry    = {
                **existing,
                "dates":    dates or ([date] if date else []),
                "venue":    venue or meta or f"{fest_name}, Nürnberg",
                "festival": existing.get("festival") or fest_name,
            }
            if tt_start: entry["start"] = tt_start
            if tt_end:   entry["end"]   = tt_end
            if info.get("day"):   entry["day"]   = info["day"]
            if info.get("stage"): entry["stage"] = info["stage"]
            rip[artist_name] = entry
            added_rip += 1
        else:
            # ── Stadt-Konzert → hamburg_artists ──────────────────────────
            # Für 'trip': venue aus meta extrahieren falls nötig
            city     = info.get("city", "").strip() or ("Hamburg" if source == "hh" else "")
            fallback = venue or city or "Hamburg"
            existing = hamburg.get(artist_name, {})
            dates    = sorted(set(existing.get("dates", []) + ([date] if date else [])))
            venues_mp = {**existing.get("venues", {}), **({date: fallback} if date else {})}
            entry = {
                **existing,
                "dates":  dates or ([date] if date else []),
                "venue":  fallback,
                "venues": venues_mp,
            }
            if city:
                entry["city"] = city
            hamburg[artist_name] = entry
            added_hamburg += 1

        # ── Songs in setlist_data speichern ──────────────────────────────
        if songs:
            sl = setlist_dt.setdefault(artist_name, {
                "setlist_titles": [], "new_titles": [], "spotify_uris": {}
            })
            existing_songs = set(sl.get("setlist_titles", []) + sl.get("new_titles", []))
            new_songs_list = [s for s in songs if s and s not in existing_songs]
            sl.setdefault("setlist_titles", []).extend(new_songs_list)
            if uris:
                sl.setdefault("spotify_uris", {}).update(uris)

    _save_concert_data(cd)
    return jsonify({
        "ok":            True,
        "added_hamburg": added_hamburg,
        "added_rip":     added_rip,
        "total":         added_hamburg + added_rip,
    })


@app.route("/generate_cover", methods=["POST"])
def generate_cover():
    """Generates a playlist cover image via Gemini and uploads it to Spotify."""
    import base64
    import io
    data = request.get_json(force=True) or {}
    playlist_id = data.get("playlist_id", "")
    playlist_name = data.get("playlist_name", "")
    band_name = data.get("band_name", "")
    artists = data.get("artists", [])   # list of {name, date, venue}
    songs = data.get("songs", [])       # list of song titles

    if not playlist_id:
        return jsonify({"error": "Keine Playlist-ID"})

    env = dotenv_values(BASE_DIR / ".env")

    artist_names = ", ".join(a["name"] if isinstance(a, dict) else a for a in artists[:12])
    song_sample = ", ".join(songs[:6])
    subject = band_name or artist_names or playlist_name
    gemini_key = env.get("GEMINI_API_KEY", "")
    prompt = None
    if gemini_key and gemini_key != "dein-key-hier":
        try:
            from google import genai as _genai_sdk3
            _gc3 = _genai_sdk3.Client(api_key=gemini_key)
            _gemini_tick()
            _resp = _gc3.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents=(
                    f"Create a short Stable Diffusion image prompt (max 60 words) for a dark Spotify playlist cover. "
                    f"The playlist is about: {subject}. "
                    + (f"Sample songs: {song_sample}. " if song_sample else "")
                    + f"Describe only visual elements: atmosphere, lighting, colors, abstract shapes, mood inspired by this band/artist's music style — "
                    f"NO artist names, NO song titles, NO text, NO letters in the image. "
                    f"Style: dark, cinematic, artistic. Reply with only the prompt."
                )
            )
            prompt = _resp.text.strip() + ", no text, no letters, no watermark"
        except Exception:
            prompt = None
    if not prompt:
        prompt = (
            f"Abstract dark concert atmosphere, dramatic colored light beams, "
            f"crowd silhouettes, pyrotechnics, smoke, cinematic mood, "
            f"no text, no letters, no words, no watermark"
        )

    try:
        import urllib.request
        import urllib.parse
        encoded_prompt = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=640&height=640&nologo=true&seed={hash(playlist_name) % 9999}"
        req = urllib.request.Request(url, headers={"User-Agent": "Concertify/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            image_bytes = resp.read()
        if not image_bytes:
            return jsonify({"error": "Pollinations hat kein Bild zurückgegeben"})
    except Exception as e:
        return jsonify({"error": f"Bild-Generierung Fehler: {e}"})

    # Compress to JPEG < 256 KB for Spotify
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img = img.resize((640, 640), Image.LANCZOS)
        quality = 90
        while True:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality)
            if buf.tell() <= 250_000 or quality <= 30:
                break
            quality -= 10
        jpeg_b64 = base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        return jsonify({"error": f"Bild-Verarbeitung Fehler: {e}"})

    # Upload to Spotify
    try:
        from spotipy import Spotify
        from spotipy.oauth2 import SpotifyOAuth
        sp = Spotify(auth_manager=SpotifyOAuth(
            client_id=env.get("SPOTIFY_CLIENT_ID", ""),
            client_secret=env.get("SPOTIFY_CLIENT_SECRET", ""),
            redirect_uri=env.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
            scope="playlist-modify-public playlist-modify-private ugc-image-upload",
            cache_path=str(BASE_DIR / ".cache"),
        ))
        sp.playlist_upload_cover_image(playlist_id, jpeg_b64)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": f"Spotify Upload Fehler: {e}"})


@app.route("/delete_playlist", methods=["POST"])
def delete_playlist():
    env = dotenv_values(BASE_DIR / ".env")
    data = request.get_json() or {}
    playlist_id = data.get("id", "").strip()
    if not playlist_id:
        return jsonify({"error": "id erforderlich"}), 400
    try:
        from spotipy import Spotify
        from spotipy.oauth2 import SpotifyOAuth
        sp = Spotify(auth_manager=SpotifyOAuth(
            client_id=env.get("SPOTIFY_CLIENT_ID", ""),
            client_secret=env.get("SPOTIFY_CLIENT_SECRET", ""),
            redirect_uri=env.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
            scope="user-follow-read playlist-read-private playlist-modify-public playlist-modify-private ugc-image-upload",
            cache_path=str(BASE_DIR / ".cache"),
        ))
        sp.current_user_unfollow_playlist(playlist_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)})


def _make_spotify_oauth(env: dict):
    """Baut SpotifyOAuth ohne Browser-Popup — hängt nie."""
    from spotipy.oauth2 import SpotifyOAuth
    return SpotifyOAuth(
        client_id=env.get("SPOTIFY_CLIENT_ID", ""),
        client_secret=env.get("SPOTIFY_CLIENT_SECRET", ""),
        redirect_uri=env.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
        scope=_SPOTIFY_SCOPE,
        cache_path=str(BASE_DIR / ".cache"),
        open_browser=False,
    )


def _make_spotify_client(env: dict | None = None):
    """
    Gibt Spotify-Instanz zurück, refresht abgelaufenen Token automatisch.
    Wirft RuntimeError('auth') wenn kein Token vorhanden — öffnet nie einen Browser.
    """
    from spotipy import Spotify
    if env is None:
        env = dotenv_values(BASE_DIR / ".env")
    auth = _make_spotify_oauth(env)
    token = auth.get_cached_token()   # refresh passiert hier automatisch wenn nötig
    if not token:
        raise RuntimeError("auth")
    return Spotify(auth=token["access_token"], requests_timeout=8)


_SPOTIFY_CONNECT_REDIRECT = "http://127.0.0.1:5000/callback"
_spotify_connect_status: dict = {"status": "idle"}


@app.route("/spotify_status")
def spotify_status():
    """Prüft ob Spotify-Token vorhanden und gültig ist."""
    try:
        sp = _make_spotify_client()
        user = sp.current_user()
        return jsonify({"connected": True, "name": user.get("display_name", "")})
    except RuntimeError:
        return jsonify({"connected": False})
    except Exception:
        return jsonify({"connected": False})


@app.route("/spotify_logout", methods=["POST"])
def spotify_logout():
    """Löscht das Spotify-Token (Cache-Datei) vom Server."""
    cache_file = BASE_DIR / ".cache"
    if cache_file.exists():
        try:
            cache_file.unlink()
            _spotify_connect_status["status"] = "idle"
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return jsonify({"success": True})


@app.route("/spotify_connect")
def spotify_connect():
    """Gibt die Spotify Auth-URL zurück. Callback kommt zu /callback."""
    env = dotenv_values(BASE_DIR / ".env")
    from spotipy.oauth2 import SpotifyOAuth
    auth = SpotifyOAuth(
        client_id=env.get("SPOTIFY_CLIENT_ID", ""),
        client_secret=env.get("SPOTIFY_CLIENT_SECRET", ""),
        redirect_uri=_SPOTIFY_CONNECT_REDIRECT,
        scope=_SPOTIFY_SCOPE,
        cache_path=str(BASE_DIR / ".cache"),
        open_browser=False,
    )
    auth_url = auth.get_authorize_url()
    _spotify_connect_status["status"] = "pending"
    return jsonify({"status": "pending", "url": auth_url})


@app.route("/callback")
def spotify_callback():
    """Empfängt Spotify OAuth Callback, tauscht Code gegen Token."""
    code  = request.args.get("code")
    error = request.args.get("error")
    if error or not code:
        _spotify_connect_status["status"] = "error"
        return "<h3>Spotify Auth fehlgeschlagen: " + str(error) + "</h3><p>Bitte schließe dieses Fenster.</p>", 400

    env = dotenv_values(BASE_DIR / ".env")
    from spotipy.oauth2 import SpotifyOAuth
    auth = SpotifyOAuth(
        client_id=env.get("SPOTIFY_CLIENT_ID", ""),
        client_secret=env.get("SPOTIFY_CLIENT_SECRET", ""),
        redirect_uri=_SPOTIFY_CONNECT_REDIRECT,
        scope=_SPOTIFY_SCOPE,
        cache_path=str(BASE_DIR / ".cache"),
        open_browser=False,
    )
    try:
        auth.get_access_token(code, as_dict=False, check_cache=False)
        _spotify_connect_status["status"] = "connected"
        return """<html><body style="background:#121212;color:#1db954;font-family:sans-serif;text-align:center;padding:60px;">
            <h2>✅ Spotify verbunden!</h2>
            <p style="color:#888;">Dieses Fenster kann geschlossen werden.</p>
            <script>setTimeout(()=>window.close(), 2000);</script>
        </body></html>"""
    except Exception as e:
        _spotify_connect_status["status"] = "error"
        return f"<h3>Fehler: {e}</h3>", 500


def _get_spotify_with_library_scope() -> tuple:
    """
    Gibt (Spotify-Instanz, None) zurück wenn Token mit Library-Scopes vorhanden,
    oder (None, error_response) wenn Neu-Auth nötig.
    Öffnet KEINEN Browser — hängt also nicht.
    """
    from spotipy import Spotify
    from spotipy.oauth2 import SpotifyOAuth
    env = dotenv_values(BASE_DIR / ".env")
    auth = SpotifyOAuth(
        client_id=env.get("SPOTIFY_CLIENT_ID", ""),
        client_secret=env.get("SPOTIFY_CLIENT_SECRET", ""),
        redirect_uri=env.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
        scope=_SPOTIFY_SCOPE,
        cache_path=str(BASE_DIR / ".cache"),
        open_browser=False,   # kein Browser-Pop-up
    )
    token_info = auth.get_cached_token()
    if not token_info:
        # Kein gueltiger Token mit Library-Scopes → Neu-Auth noetig
        return None, jsonify({
            "liked": False, "error": "scope",
            "hint": ".cache loeschen und App neu laden fuer Liked-Songs-Zugriff"
        })
    sp = Spotify(auth=token_info["access_token"], requests_timeout=8)
    return sp, None


@app.route("/liked_songs/check")
def liked_songs_check():
    """Prüft ob ein Track in den Liked Songs ist. ?uri=spotify:track:xxx"""
    uri = request.args.get("uri", "").strip()
    if not uri.startswith("spotify:track:"):
        return jsonify({"liked": False, "error": "Ungueltige URI"})
    track_id = uri.split(":")[-1]
    sp, err_resp = _get_spotify_with_library_scope()
    if err_resp:
        return err_resp
    try:
        result = sp.current_user_saved_tracks_contains([track_id])
        return jsonify({"liked": bool(result and result[0])})
    except Exception as e:
        err = str(e)
        if "403" in err or "Forbidden" in err:
            return jsonify({"liked": False, "error": "scope"})
        return jsonify({"liked": False, "error": err[:120]})


@app.route("/liked_songs/toggle", methods=["POST"])
def liked_songs_toggle():
    """Liked Song hinzufügen oder entfernen. {uri, liked: true/false}"""
    data  = request.get_json(force=True) or {}
    uri   = data.get("uri", "").strip()
    add   = bool(data.get("liked", True))
    if not uri.startswith("spotify:track:"):
        return jsonify({"error": "Ungueltige URI"})
    track_id = uri.split(":")[-1]
    sp, err_resp = _get_spotify_with_library_scope()
    if err_resp:
        return err_resp
    try:
        if add:
            sp.current_user_saved_tracks([track_id])
        else:
            sp.current_user_saved_tracks_delete([track_id])
        return jsonify({"ok": True, "liked": add})
    except Exception as e:
        err = str(e)
        if "403" in err:
            return jsonify({"error": "scope"})
        return jsonify({"error": err[:120]})


@app.route("/follow_playlist", methods=["POST"])
def follow_playlist():
    """Abonniert eine fremde Spotify-Playlist."""
    data        = request.get_json(force=True) or {}
    playlist_id = data.get("id", "").strip()
    if not playlist_id:
        return jsonify({"error": "id erforderlich"}), 400
    env = dotenv_values(BASE_DIR / ".env")
    try:
        from spotipy import Spotify
        from spotipy.oauth2 import SpotifyOAuth
        sp = Spotify(auth_manager=SpotifyOAuth(
            client_id=env.get("SPOTIFY_CLIENT_ID", ""),
            client_secret=env.get("SPOTIFY_CLIENT_SECRET", ""),
            redirect_uri=env.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
            scope="playlist-modify-public playlist-modify-private",
            cache_path=str(BASE_DIR / ".cache"),
        ), requests_timeout=8)
        sp.current_user_follow_playlist(playlist_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/search_cover_images", methods=["POST"])
def search_cover_images():
    env = dotenv_values(BASE_DIR / ".env")
    data = request.get_json() or {}
    query  = data.get("query", "").strip()
    artist = data.get("artist", "").strip()   # optional: direkte TM-Suche
    if not query and not artist:
        return jsonify({"error": "query erforderlich", "images": []})

    images = []

    # ── 1. Ticketmaster Event-Bilder (kein Credit-Limit) ─────────────
    tm_key = env.get("TICKETMASTER_API_KEY", "")
    search_term = artist or query.split()[0]
    if tm_key and search_term:
        try:
            import requests as _req
            r = _req.get("https://app.ticketmaster.com/discovery/v2/events.json", params={
                "apikey": tm_key, "keyword": search_term,
                "countryCode": "DE", "classificationName": "Music",
                "size": 5, "sort": "date,asc",
            }, timeout=8)
            for event in r.json().get("_embedded", {}).get("events", []):
                for img in event.get("images", []):
                    url = img.get("url", "")
                    # nur quadratische oder breite Bilder (Tour-Poster)
                    w, h = img.get("width", 0), img.get("height", 0)
                    if url and url not in images and w >= 640:
                        images.append(url)
        except Exception:
            pass

    # ── 2. Tavily (nur wenn Credits vorhanden) ────────────────────────
    # ── 2. Serper.dev Google Image Search ────────────────────────────
    serper_key = env.get("SERPER_API_KEY", "")
    if serper_key and len(images) < 4:
        try:
            import requests as _req
            r = _req.post("https://google.serper.dev/images",
                headers={"X-API-KEY": serper_key, "Content-Type": "application/json"},
                json={"q": query or f"{artist} 2026 tour poster concert", "num": 8},
                timeout=10)
            for item in r.json().get("images", []):
                url = item.get("imageUrl", "")
                if url and url not in images:
                    images.append(url)
        except Exception:
            pass

    tavily_warning = None
    tavily_key = env.get("TAVILY_API_KEY", "")
    if tavily_key and len(images) < 4:
        try:
            import requests as _req
            resp = _req.post("https://api.tavily.com/search", json={
                "api_key": tavily_key,
                "query": query or f"{artist} tour poster 2026",
                "search_depth": "basic",
                "include_images": True,
                "max_results": 5,
            }, timeout=15)
            rj = resp.json()
            if resp.status_code in (402, 429) or "quota" in str(rj).lower() or "credit" in str(rj).lower():
                tavily_warning = "Tavily-Credits erschöpft — nur Ticketmaster-Bilder verfügbar."
            else:
                for url in rj.get("images", []):
                    if url not in images:
                        images.append(url)
        except Exception:
            pass

    return jsonify({
        "images": images[:8],
        "warning": tavily_warning,
        "sources": {"ticketmaster": bool(tm_key)},
    })


@app.route("/apply_cover_url", methods=["POST"])
def apply_cover_url():
    import base64, io
    env = dotenv_values(BASE_DIR / ".env")
    data = request.get_json() or {}
    playlist_id = data.get("playlist_id", "").strip()
    image_url = data.get("image_url", "").strip()
    if not playlist_id or not image_url:
        return jsonify({"error": "playlist_id und image_url erforderlich"})
    if not image_url.startswith("http"):
        return jsonify({"error": "Ungueltige URL"})
    try:
        import urllib.request
        req = urllib.request.Request(image_url, headers={"User-Agent": "Concertify/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            image_bytes = resp.read()
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img = img.resize((640, 640), Image.LANCZOS)
        quality = 90
        while True:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality)
            if buf.tell() <= 250_000 or quality <= 30:
                break
            quality -= 10
        jpeg_b64 = base64.b64encode(buf.getvalue()).decode()
        from spotipy import Spotify
        from spotipy.oauth2 import SpotifyOAuth
        sp = Spotify(auth_manager=SpotifyOAuth(
            client_id=env.get("SPOTIFY_CLIENT_ID", ""),
            client_secret=env.get("SPOTIFY_CLIENT_SECRET", ""),
            redirect_uri=env.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
            scope="ugc-image-upload",
            cache_path=str(BASE_DIR / ".cache"),
        ))
        sp.playlist_upload_cover_image(playlist_id, jpeg_b64)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/reset_all_songs", methods=["POST"])
def reset_all_songs():
    """Löscht alle setlist_data (Songs + URIs) für alle Künstler auf einmal.
    Konzert- und Festival-Daten bleiben erhalten."""
    data_file = BASE_DIR / "concert_data.json"
    cd = json.loads(data_file.read_text(encoding="utf-8")) if data_file.exists() else {}
    artist_count = len(cd.get("setlist_data", {}))
    cd["setlist_data"] = {}
    _save_concert_data(cd)
    return jsonify({"ok": True, "cleared": artist_count})


@app.route("/save_setlist", methods=["POST"])
def save_setlist():
    """Persist loaded songs + Spotify URIs for an artist into concert_data.json."""
    data = request.get_json(force=True) or {}
    artist = data.get("artist", "").strip()
    songs  = data.get("songs", [])   # [{"title": "...", "uri": "...", "type": "setlist|new"}]

    if not artist:
        return jsonify({"ok": False})

    data_file = BASE_DIR / "concert_data.json"
    concert_data: dict = {}
    if data_file.exists():
        concert_data = json.loads(data_file.read_text(encoding="utf-8"))

    setlist_data = concert_data.get("setlist_data", {})
    existing = setlist_data.get(artist, {})
    incoming_titles = [s["title"] for s in songs if s.get("type") != "new"]
    incoming_new    = [s["title"] for s in songs if s.get("type") == "new"]
    # Schutzmechanismus: setlist_titles werden UNION-merged statt ersetzt.
    # Grund: Das Frontend schickt nur die aktuell sichtbaren/ausgewaehlten Songs
    # zurueck — die nicht-angezeigten Songs sollen erhalten bleiben (war ein Bug:
    # bei H-Blockx wurden 20 Songs auf 12 reduziert, weil 8 nicht im Frontend
    # waren). Wer wirklich loeschen will, nutzt /remove_song.
    existing_titles = existing.get("setlist_titles", [])
    existing_new    = existing.get("new_titles", [])
    _title_set = set(existing_titles)
    _new_set   = set(existing_new)
    final_titles = existing_titles + [t for t in incoming_titles if t not in _title_set]
    final_new    = existing_new    + [t for t in incoming_new    if t not in _new_set]

    deleted = data.get("deleted", [])
    if deleted:
        final_titles = [t for t in final_titles if t not in deleted]
        final_new    = [t for t in final_new if t not in deleted]

    new_entry: dict = {
        "setlist_titles": final_titles,
        "new_titles":     final_new,
        "spotify_uris":   {**existing.get("spotify_uris", {}),
                           **{s["title"]: s["uri"] for s in songs if s.get("uri")}},
    }
    # Preserve scores, badges, positions and setlist-stats from existing cache entry
    for key in ("scores", "badges", "positions", "is_encore",
                "set_type", "play_counts", "total_concerts_analyzed", "positions_hist",
                "excluded_songs", "manual_order"):
        if key in existing:
            new_entry[key] = existing[key]
    # Backup previous song lists before overwriting
    if existing.get("setlist_titles") or existing.get("new_titles"):
        new_entry["prev_setlist_titles"] = existing.get("setlist_titles", [])
        new_entry["prev_new_titles"]     = existing.get("new_titles", [])
    setlist_data[artist] = new_entry
    concert_data["setlist_data"] = setlist_data
    _save_concert_data(concert_data)
    return jsonify({"ok": True})


@app.route("/get_tour_info")
def get_tour_info():
    """Holt Tour-Name vom letzten Konzert auf setlist.fm."""
    artist = request.args.get("artist", "").strip()
    if not artist:
        return jsonify({"tour": None})
    env = dotenv_values(BASE_DIR / ".env")
    setlistfm = env.get("SETLISTFM_API_KEY", "")
    if not setlistfm:
        return jsonify({"tour": None})
    try:
        from setlist_client import SetlistClient
        import requests as _rsl
        client = SetlistClient(api_key=setlistfm)
        candidates = client._find_mbid_candidates(artist)
        if not candidates:
            return jsonify({"tour": None})
        resp = _rsl.get(
            f"https://api.setlist.fm/rest/1.0/artist/{candidates[0]}/setlists",
            params={"p": 1}, timeout=10,
            headers={"x-api-key": setlistfm, "Accept": "application/json"},
        )
        setlists = resp.json().get("setlist", [])
        for sl in setlists[:5]:
            tour_name = sl.get("tour", {}).get("name") if sl.get("tour") else None
            if tour_name:
                return jsonify({"tour": tour_name})
        return jsonify({"tour": None})
    except Exception:
        return jsonify({"tour": None})


@app.route("/get_tour_options")
def get_tour_options():
    """Gruppen-Ansicht aller Touren eines Künstlers für den Tour-Auswahl-Dialog."""
    artist = request.args.get("artist", "").strip()
    if not artist:
        return jsonify({"active_tour": None, "past_tours": [], "total_shows": 0})
    env = dotenv_values(BASE_DIR / ".env")
    setlistfm = env.get("SETLISTFM_API_KEY", "")
    if not setlistfm:
        return jsonify({"active_tour": None, "past_tours": [], "total_shows": 0})
    try:
        from setlist_client import SetlistClient
        client = SetlistClient(api_key=setlistfm)
        return jsonify(client.get_tour_options(artist))
    except RuntimeError as e:
        if "rate_limited" in str(e):
            # Retry-After-Wert (Sekunden) uebernehmen; fehlt/unknown -> bis Mitternacht.
            _retry = _seconds_until_midnight_utc()
            import re as _re2
            m = _re2.search(r"rate_limited:(\d+)", str(e))
            if m:
                _retry = int(m.group(1))
            _update_api_health("setlist", False, error="rate_limited", retry_after=_retry)
            return jsonify({"active_tour": None, "past_tours": [], "total_shows": 0, "error": "rate_limited", "retry_after": _retry})
        return jsonify({"active_tour": None, "past_tours": [], "total_shows": 0})
    except Exception as e:
        print(f"get_tour_options error: {e}")
        return jsonify({"active_tour": None, "past_tours": [], "total_shows": 0})


@app.route("/gemini_status")
def gemini_status():
    """Check Gemini quota by making a minimal test request."""
    import re as _re
    env = dotenv_values(BASE_DIR / ".env")
    gemini_key = env.get("GEMINI_API_KEY", "")
    if not gemini_key or gemini_key == "dein-key-hier":
        return jsonify({"available": False, "error": "Kein API Key"})
    try:
        from google import genai as _genai_sdk4
        _gc4 = _genai_sdk4.Client(api_key=gemini_key)
        _gc4.models.generate_content(model="gemini-2.0-flash-lite", contents="Hi")
        _gemini_tick()
        with _gemini_counter_lock:
            count = _gemini_counter["count"]
        reset_ts = _gemini_reset_ts()
        return jsonify({
            "available": True,
            "requests_today": count, "requests_limit": GEMINI_RPD_LIMIT, "reset_ts": reset_ts,
        })
    except Exception as e:
        err = str(e)
        retry_in = None
        # Parse "Retry will occur after: X s" or retryDelay from error
        m = _re.search(r'[Rr]etry.*?(\d+)\s*s', err)
        if m:
            retry_in = int(m.group(1))
        else:
            m = _re.search(r'"retryDelay":\s*"(\d+)', err)
            if m:
                retry_in = int(m.group(1))
        limited = any(x in err.lower() for x in ["quota", "rate", "limit", "429", "resource_exhausted"])
        with _gemini_counter_lock:
            count = _gemini_counter["count"]
        reset_ts = _gemini_reset_ts()
        return jsonify({
            "available": False, "limited": limited, "retry_in": retry_in, "error": err[:200],
            "requests_today": count, "requests_limit": GEMINI_RPD_LIMIT, "reset_ts": reset_ts,
        })


@app.route("/search_support_acts", methods=["POST"])
def search_support_acts():
    """Sucht Support Acts für ein Konzert via Ticketmaster + Tavily."""
    data   = request.get_json(force=True) or {}
    artist = data.get("artist", "").strip()
    date   = data.get("date", "").strip()
    venue  = data.get("venue", "").strip()

    if not artist:
        return jsonify({"acts": []})

    env     = dotenv_values(BASE_DIR / ".env")
    results: list[str] = []
    seen    = {artist.lower()}

    # Ticketmaster: Event-Attractions abrufen
    tm_key = env.get("TICKETMASTER_API_KEY")
    if tm_key:
        try:
            import requests as _rtm
            params = {
                "apikey": tm_key,
                "keyword": artist,
                "countryCode": "DE",
                "size": 5,
            }
            if date:
                params["startDateTime"] = date + "T00:00:00Z"
                params["endDateTime"]   = date + "T23:59:59Z"
            resp = _rtm.get(
                "https://app.ticketmaster.com/discovery/v2/events.json",
                params=params, timeout=10,
            )
            for event in resp.json().get("_embedded", {}).get("events", []):
                for att in event.get("_embedded", {}).get("attractions", []):
                    name = att.get("name", "").strip()
                    if name and name.lower() not in seen:
                        seen.add(name.lower())
                        results.append(name)
        except Exception:
            pass

    # Tavily-Fallback wenn TM nichts liefert
    tavily_key = env.get("TAVILY_API_KEY")
    if tavily_key and not results:
        try:
            from tavily import TavilyClient
            tc = TavilyClient(api_key=tavily_key)
            year = date[:4] if date else "2026"
            location = venue or "Hamburg"
            query = f'"{artist}" support act Vorband opener {location} {year}'
            search_resp = tc.search(query=query, max_results=5, search_depth="basic")
            import re as _re2
            for r in search_resp.get("results", []):
                content = r.get("content", "") + " " + r.get("title", "")
                # Einfache Heuristik: Zeilen die "support" oder "opener" nahe am Text enthalten
                for line in content.splitlines():
                    line = line.strip()
                    if any(k in line.lower() for k in ("support", "opener", "vorband", "special guest")):
                        # Versuche Künstlernamen aus der Zeile zu extrahieren
                        cleaned = _re2.sub(r'[:\-–|].*$', '', line).strip()
                        if 2 < len(cleaned) < 60 and cleaned.lower() not in seen:
                            seen.add(cleaned.lower())
                            results.append(cleaned)
        except Exception:
            pass

    # Serper-Fallback (Google) wenn TM + Tavily nichts liefern.
    # Google nennt Support-Acts oft explizit ("Support act Chevelle").
    serper_key = env.get("SERPER_API_KEY")
    if serper_key and not results:
        try:
            from support_act_search import serper_support_acts
            year = date[:4] if date else "2026"
            for name in serper_support_acts(serper_key, artist, venue=venue, year=year):
                if name.lower() not in seen:
                    seen.add(name.lower())
                    results.append(name)
        except Exception:
            pass

    return jsonify({"acts": results[:8]})


@app.route("/add_support_act", methods=["POST"])
def add_support_act():
    """Fügt einen Support Act zu einem Konzert hinzu."""
    data   = request.get_json(force=True) or {}
    artist = data.get("artist", "").strip()
    date   = data.get("date", "").strip()
    act    = data.get("act", "").strip()

    if not all([artist, date, act]):
        return jsonify({"ok": False, "error": "missing fields"})

    cd = json.loads((BASE_DIR / "concert_data.json").read_text(encoding="utf-8")) \
        if (BASE_DIR / "concert_data.json").exists() else {}
    support = cd.setdefault("support_acts", {})
    acts_for_artist = support.setdefault(artist, {})
    acts_for_date   = acts_for_artist.setdefault(date, [])
    if act not in acts_for_date:
        acts_for_date.append(act)
    _save_concert_data(cd)
    return jsonify({"ok": True})


@app.route("/get_support_acts")
def get_support_acts():
    """Gibt gespeicherte Support Acts für einen Künstler + Datum zurück."""
    artist = request.args.get("artist", "").strip()
    date   = request.args.get("date", "").strip()
    cd = json.loads((BASE_DIR / "concert_data.json").read_text(encoding="utf-8")) \
        if (BASE_DIR / "concert_data.json").exists() else {}
    acts = cd.get("support_acts", {}).get(artist, {}).get(date, [])
    return jsonify({"acts": acts})


@app.route("/remove_support_act", methods=["POST"])
def remove_support_act():
    """Entfernt einen Support Act von einem Konzert."""
    data   = request.get_json(force=True) or {}
    artist = data.get("artist", "").strip()
    date   = data.get("date", "").strip()
    act    = data.get("act", "").strip()

    cd = json.loads((BASE_DIR / "concert_data.json").read_text(encoding="utf-8")) \
        if (BASE_DIR / "concert_data.json").exists() else {}
    acts_list = cd.get("support_acts", {}).get(artist, {}).get(date, [])
    if act in acts_list:
        acts_list.remove(act)
    _save_concert_data(cd)
    return jsonify({"ok": True})


@app.route("/reorder_support_acts", methods=["POST"])
def reorder_support_acts_route():
    """Sortiert die Support-Acts eines Konzerts neu (Drag & Drop)."""
    data   = request.get_json(force=True) or {}
    artist = data.get("artist", "").strip()
    date   = data.get("date", "").strip()
    order  = data.get("order", [])

    if not artist or not date or not isinstance(order, list):
        return jsonify({"ok": False, "error": "missing fields"})

    cd = json.loads((BASE_DIR / "concert_data.json").read_text(encoding="utf-8")) \
        if (BASE_DIR / "concert_data.json").exists() else {}
    ok, err = _reorder_support_acts(cd, artist, date, order)
    if not ok:
        return jsonify({"ok": False, "error": err})
    _save_concert_data(cd)
    return jsonify({"ok": True})


@app.route("/toggle_song_excluded", methods=["POST"])
def toggle_song_excluded_route():
    """Toggelt den Ausschluss eines Songs von der Playlist-Generierung (persistent)."""
    data = request.get_json(force=True) or {}
    artist = data.get("artist", "").strip()
    song = data.get("song", "").strip()
    excluded = bool(data.get("excluded", False))

    if not artist or not song:
        return jsonify({"ok": False, "error": "missing fields"})

    cd = json.loads((BASE_DIR / "concert_data.json").read_text(encoding="utf-8")) \
        if (BASE_DIR / "concert_data.json").exists() else {}
    ok, err = _toggle_song_excluded(cd, artist, song, excluded)
    if not ok:
        return jsonify({"ok": False, "error": err})
    _save_concert_data(cd)
    return jsonify({"ok": True})


@app.route("/reorder_songs", methods=["POST"])
def reorder_songs_route():
    """Speichert die manuelle Song-Reihenfolge eines Kuenstlers (persistent)."""
    data = request.get_json(force=True) or {}
    artist = data.get("artist", "").strip()
    order = data.get("order", [])

    if not artist or not isinstance(order, list):
        return jsonify({"ok": False, "error": "missing fields"})

    cd = json.loads((BASE_DIR / "concert_data.json").read_text(encoding="utf-8")) \
        if (BASE_DIR / "concert_data.json").exists() else {}
    ok, err = _reorder_songs(cd, artist, order)
    if not ok:
        return jsonify({"ok": False, "error": err})
    _save_concert_data(cd)
    return jsonify({"ok": True})


# -- Setlist-Snapshots --

@app.route("/snapshots/create", methods=["POST"])
def snapshots_create():
    """Speichert den aktuellen Setlist-Zustand eines Kuenstlers als benannten Snapshot."""
    data   = request.get_json(force=True) or {}
    artist = data.get("artist", "").strip()
    name   = data.get("name", "").strip()
    if not artist or not name:
        return jsonify({"ok": False, "error": "missing fields"})

    cd    = _load_concert_data()
    entry = cd.get("setlist_data", {}).get(artist)
    if entry is None:
        return jsonify({"ok": False, "error": "unknown artist"})

    sid, err = _snapshot_service.create_snapshot(artist, name, entry)
    if err:
        return jsonify({"ok": False, "error": err})
    return jsonify({"ok": True, "id": sid})


@app.route("/snapshots/list", methods=["GET"])
def snapshots_list():
    """Listet alle Snapshots eines Kuenstlers (id, name, created_at)."""
    artist = request.args.get("artist", "").strip()
    if not artist:
        return jsonify({"ok": False, "error": "missing artist", "snapshots": []})
    return jsonify({"ok": True, "snapshots": _snapshot_service.list_snapshots(artist)})


@app.route("/snapshots/is_saved", methods=["GET"])
def snapshots_is_saved():
    """Prueft, ob die aktuelle Songliste eines Kuenstlers bereits gesichert ist."""
    artist = request.args.get("artist", "").strip()
    if not artist:
        return jsonify({"ok": False, "error": "missing artist", "saved": False})
    cd = _load_concert_data()
    titles = cd.get("setlist_data", {}).get(artist, {}).get("setlist_titles", [])
    saved  = _snapshot_service.is_current_saved(artist, titles)
    return jsonify({"ok": True, "saved": saved})


@app.route("/snapshots/restore", methods=["POST"])
def snapshots_restore():
    """Stellt einen Snapshot wieder her (ueberschreibt setlist_data[artist])."""
    data = request.get_json(force=True) or {}
    sid  = data.get("id")
    if sid is None:
        return jsonify({"ok": False, "error": "missing id"})

    artist, payload, err = _snapshot_service.get_restore_payload(int(sid))
    if err:
        return jsonify({"ok": False, "error": err})

    cd = _load_concert_data()
    cd.setdefault("setlist_data", {}).setdefault(artist, {})
    from services.snapshot_service import apply_snapshot_payload
    apply_snapshot_payload(cd["setlist_data"][artist], payload)
    _save_concert_data(cd)
    return jsonify({"ok": True, "artist": artist})


@app.route("/snapshots/rename", methods=["POST"])
def snapshots_rename():
    """Benennt einen Snapshot um."""
    data = request.get_json(force=True) or {}
    sid  = data.get("id")
    name = data.get("name", "").strip()
    if sid is None or not name:
        return jsonify({"ok": False, "error": "missing fields"})
    ok = _snapshot_service.rename_snapshot(int(sid), name)
    return jsonify({"ok": ok})


@app.route("/snapshots/delete", methods=["POST"])
def snapshots_delete():
    """Loescht einen Snapshot."""
    data = request.get_json(force=True) or {}
    sid  = data.get("id")
    if sid is None:
        return jsonify({"ok": False, "error": "missing id"})
    ok = _snapshot_service.delete_snapshot(int(sid))
    return jsonify({"ok": ok})


@app.route("/more_songs", methods=["POST"])
def more_songs():
    """Fetch additional songs for an artist via Gemini (or setlist.fm)."""
    data       = request.get_json(force=True) or {}
    artist     = data.get("artist", "").strip()
    already    = set(data.get("already_have", []))
    mode       = data.get("mode", "").strip()   # "concert"|"festival"|"support"|"support_full"|""
    fallback   = data.get("fallback", "").strip()

    if not artist:
        return jsonify({"songs": [], "error": "no artist"})

    env        = dotenv_values(BASE_DIR / ".env")
    gemini_key = env.get("GEMINI_API_KEY", "")
    setlistfm  = env.get("SETLISTFM_API_KEY", "")

    needed = int(data.get("needed", 12))

    # Typ-spezifische Song-Anzahl: Hauptact (Konzert) vs Festival-Act
    # Im Mode-Pfad (Abend-Tab) kein Limit anwenden — alle Tour-Songs nehmen
    konzert_songs = int(data.get("konzert_songs", 0))
    festival_songs_count = int(data.get("festival_songs", 0))
    if (konzert_songs or festival_songs_count) and not mode:
        _cd_type = json.loads((BASE_DIR / "concert_data.json").read_text(encoding="utf-8")) \
            if (BASE_DIR / "concert_data.json").exists() else {}
        _in_hamburg = artist in _cd_type.get("hamburg_artists", {})
        _in_rip     = artist in _cd_type.get("rip_artists", {})
        if _in_hamburg:
            # Hamburg-Konzert hat Vorrang — immer Vollkonzert-Anzahl
            needed = konzert_songs if konzert_songs else needed
        elif _in_rip:
            # Reiner Festival-Act — Frontend-Wert (aus Slot-Dauer) respektieren,
            # aber zwischen festival_songs und konzert_songs einschränken
            if festival_songs_count and needed < festival_songs_count:
                needed = festival_songs_count
            if konzert_songs and needed > konzert_songs:
                needed = konzert_songs
        else:
            needed = konzert_songs if konzert_songs else needed

    ask_for    = len(already) + needed + 5   # buffer so filtering leaves enough

    setlist_songs: list[str] = []
    new_songs: list[str] = []
    sources_used: list[str] = []
    song_source_count: dict[str, int] = {}   # song.lower() → Anzahl Quellen (für Bonus)
    setlistfm_freq: dict[str, float] = {}    # song.lower() → Häufigkeit aus setlist.fm (0–1)
    song_badges: dict[str, str] = {}
    scores: dict[str, float] = {}

    # ── Cache-Read: gespeicherte Setlist-Daten ohne API-Call liefern ────────
    _cache_file  = BASE_DIR / "concert_data.json"
    _cache_cd    = json.loads(_cache_file.read_text(encoding="utf-8")) if _cache_file.exists() else {}
    _cached_sd   = _cache_cd.get("setlist_data", {}).get(artist, {})
    _cached_list    = _cached_sd.get("setlist_titles", [])
    _cached_sc      = _cached_sd.get("scores", {})
    _cached_bg      = _cached_sd.get("badges", {})
    _cached_uri     = _cached_sd.get("spotify_uris", {})
    _cached_set_type = _cached_sd.get("set_type", "")
    _cached_pos      = _cached_sd.get("positions", {})
    _cached_hist     = _cached_sd.get("positions_hist", {})
    _cached_counts   = _cached_sd.get("play_counts", {})
    _cached_total    = _cached_sd.get("total_concerts_analyzed", 0)
    _cached_show     = _cached_sd.get("show_elements", [])   # Live-Show-Elemente ohne echten Spotify-Track

    # ── Cache-First: wenn lokale Daten vorhanden, sofort zurückgeben ────────
    # Kein API-Call wenn Cache gefüllt ist — außer force=true
    force_refresh = data.get("force", False)
    if not force_refresh and _cached_list:
        _remaining = [s for s in _cached_list if s not in already]
        if len(_remaining) >= min(needed, 3):
            _manual_order = _cached_sd.get("manual_order", [])
            if _manual_order:
                _in_m = [s for s in _manual_order if s in _remaining]
                _not_in_m = [s for s in _remaining if s not in _manual_order]
                _out = _in_m + _not_in_m
            else:
                _out = _remaining
            # Festival-Flag: Artist nur in rip_artists → Festival-Set
            _cd_type2 = _cache_cd
            _in_hamburg2 = artist in _cd_type2.get("hamburg_artists", {})
            _in_rip2     = artist in _cd_type2.get("rip_artists", {})
            _is_festival = _in_rip2 and not _in_hamburg2
            return jsonify({
                "songs":       _out,
                "scores":      {s: _cached_sc.get(s, 0.5) for s in _out},
                "badges":      {s: _cached_bg.get(s, "setlist") for s in _out},
                "uris":        {s: _cached_uri[s] for s in _out if s in _cached_uri},
                "sources":            ["setlist.fm"],
                "from_cache":         True,
                "is_festival":        _is_festival,
                "set_type":           _cached_set_type,
                "positions":          {s: _cached_pos[s] for s in _out if s in _cached_pos},
                "positions_hist":     {s: _cached_hist[s] for s in _out if s in _cached_hist},
                "play_counts":        {s: _cached_counts[s] for s in _out if s in _cached_counts},
                "concerts_analyzed":  _cached_total,
                "show_elements":      [s for s in _out if s in _cached_show],
            })

    # ── Mode-Pfad: geordnete Setlist (Abend-Tab + Mix-Tab mit Set-Typ) ───
    tour_name = data.get("tour_name", "").strip()
    effective_mode  = mode
    effective_tour  = tour_name
    freq_threshold  = 0.0
    if tour_name == "__best_of__":
        effective_tour = ""
        freq_threshold = 0.25
        if not effective_mode:
            effective_mode = "concert"
    elif tour_name == "__festival__":
        effective_tour = ""
        effective_mode = "festival"
    elif tour_name and not tour_name.startswith("__"):
        if not effective_mode:
            effective_mode = "concert"

    # Setlist.fm nur aufrufen wenn nicht rate-limited laut _api_health
    _sl_health = _api_health.get("setlist", {})
    _sl_blocked = not _sl_health.get("ok", True) and _sl_health.get("ok") is not None
    _sl_retry_secs = _sl_health.get("retry_after", 0)
    if _sl_blocked and _sl_retry_secs and (int(_time.time()) < _sl_health.get("checked", 0) + _sl_retry_secs):
        setlistfm = ""  # Als "nicht verfügbar" markieren → überspringen

    # Fallback-Option: Spotify Top-10 direkt abfragen (überspringt Setlist.fm)
    if fallback == "spotify_top10":
        from spotify_client import SpotifyClient
        spotify = SpotifyClient(
            client_id=env.get("SPOTIFY_CLIENT_ID", ""),
            client_secret=env.get("SPOTIFY_CLIENT_SECRET", ""),
            redirect_uri=env.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
        )
        
        # 1. Künstler suchen
        r = spotify.sp.search(q=f'artist:"{artist}"', type="artist", limit=1)
        items = r.get("artists", {}).get("items", [])
        if not items:
            # Fallback loose search
            r2 = spotify.sp.search(q=f'{artist}', type="artist", limit=1)
            items = r2.get("artists", {}).get("items", [])
        
        top_tracks = []
        if items:
            artist_id = items[0]["id"]
            top_tracks = spotify.get_artist_top_tracks(artist_id)
            print(f"DEBUG app.py: get_artist_top_tracks for {artist_id} returned {len(top_tracks)} tracks")
            
        if not top_tracks:
            # Fallback 1: Strikte Track-Suche nach dem Artist-Namen
            r3 = spotify.sp.search(q=f'artist:"{artist}"', type="track", limit=10)
            top_tracks = r3.get("tracks", {}).get("items", [])
            print(f"DEBUG app.py: Fallback 1 strictly track search returned {len(top_tracks)} tracks")
            
        if not top_tracks:
            # Fallback 2: Sehr lose Track-Suche (findet oft kleine/ungenaue Bands)
            r4 = spotify.sp.search(q=f'{artist}', type="track", limit=10)
            top_tracks = r4.get("tracks", {}).get("items", [])
            print(f"DEBUG app.py: Fallback 2 loose track search returned {len(top_tracks)} tracks")

        songs = [t.get("name") for t in top_tracks if t.get("name")]
        print(f"DEBUG app.py: Final songs length: {len(songs)}")
        
        if top_tracks:
            
            # Format output so it acts like a setlist result
            _cd_file = BASE_DIR / "concert_data.json"
            _cd = json.loads(_cd_file.read_text(encoding="utf-8")) if _cd_file.exists() else {}
            sl_entry = _cd.setdefault("setlist_data", {}).setdefault(artist, {})
            
            scores_map = {}
            badges_map = {}
            uris_map = {}
            
            # Create a fake setlist response based on spotify top 10
            # Ensure it works for frontend
            valid_songs = []
            for track in top_tracks:
                name = track.get("name", "")
                if name and name not in already:
                    valid_songs.append(name)
                    scores_map[name] = 1.0
                    badges_map[name] = "spotify"
                    if track.get("uri"):
                        uris_map[name] = track["uri"]
                        
            songs = valid_songs
            
            sl_entry["scores"] = {**sl_entry.get("scores", {}), **scores_map}
            sl_entry["badges"] = {**sl_entry.get("badges", {}), **badges_map}
            sl_entry["spotify_uris"] = {**sl_entry.get("spotify_uris", {}), **uris_map}
            sl_entry["set_type"] = "Spotify Top-10"
            _save_concert_data(_cd)
            
            return jsonify({
                "songs":      songs,
                "scores":     scores_map,
                "badges":     badges_map,
                "uris":       uris_map,
                "sources":    ["spotify_fallback"],
                "from_cache": False,
                "set_type":   "Spotify Top-10",
                "is_festival": False,
                "positions":  {},
                "positions_hist": {},
                "play_counts": {},
                "concerts_analyzed": 1,
            })

    if (effective_mode or effective_tour) and setlistfm and fallback != "spotify_top10":
        try:
            from setlist_client import SetlistClient
            ordered_data = SetlistClient(api_key=setlistfm).get_setlist_ordered(
                artist, mode=effective_mode or "concert", num_concerts=100,
                tour_name=effective_tour, freq_threshold=freq_threshold,
            )
            ordered_list  = ordered_data.get("ordered", [])   # [(song, avg_pos, is_encore, freq)]
            positions_map = ordered_data.get("positions", {})
            is_encore_map = ordered_data.get("is_encore", {})
            tour_active   = ordered_data.get("tour_active", False)
            play_counts   = ordered_data.get("play_counts", {})
            positions_hist= ordered_data.get("positions_hist", {})

            # Songs in Positions-Reihenfolge (Covers + already-have herausfiltern)
            ordered_songs = [s for s, *_ in ordered_list if s not in already]

            # Badge/Score nach Häufigkeit vergeben
            for s, avg_pos, enc, freq in ordered_list:
                if s in already:
                    continue
                setlistfm_freq[s.lower()] = freq
                song_badges[s] = "setlist"
                scores[s]      = round(freq, 2)

            songs = ordered_songs  # alle Tour-Songs, kein künstliches Limit im Abend-Tab

            # Speichern inkl. Positions + Encore
            _cd_file = BASE_DIR / "concert_data.json"
            _cd = json.loads(_cd_file.read_text(encoding="utf-8")) if _cd_file.exists() else {}
            sl_entry = _cd.setdefault("setlist_data", {}).setdefault(artist, {})
            sl_entry["scores"]    = {**sl_entry.get("scores", {}),    **{s: scores[s] for s in songs}}
            sl_entry["badges"]    = {**sl_entry.get("badges", {}),    **{s: song_badges[s] for s in songs}}
            sl_entry["positions"] = positions_map
            sl_entry["is_encore"] = is_encore_map
            sl_entry["play_counts"] = play_counts
            sl_entry["positions_hist"] = positions_hist
            sl_entry["total_concerts_analyzed"] = ordered_data.get("concerts_analyzed", 0)
            _save_concert_data(_cd)

            # Sort using manual_order:
            _manual_order = _cd.get("setlist_data", {}).get(artist, {}).get("manual_order", [])
            if _manual_order:
                _in_m = [s for s in songs if s in _manual_order]
                _not_in_m = [s for s in songs if s not in _manual_order]
                _sorted_songs = _in_m + _not_in_m
            else:
                _sorted_songs = songs

            return jsonify({
                "songs":      _sorted_songs,
                "scores":     {s: scores[s] for s in _sorted_songs},
                "badges":     {s: song_badges[s] for s in songs},
                "positions":  positions_map,
                "is_encore":  is_encore_map,
                "tour_active": tour_active,
                "mode_used":  effective_mode,
                "concerts_analyzed": ordered_data.get("concerts_analyzed", 0),
                "play_counts": play_counts,
                "positions_hist": positions_hist,
            })
        except RuntimeError as _re:
            if "rate_limited" in str(_re):
                # Rate-Limit IMMER registrieren (auch wenn gleich der Cache greift),
                # damit _sl_blocked folgende Calls — inkl. force:true — im
                # Retry-Fenster ueberspringt und setlist.fm nicht weiter anstoesst.
                err_str = str(_re)
                _retry = _seconds_until_midnight_utc()
                import re as _re2
                m = _re2.search(r"rate_limited:(\d+)", err_str)
                if m:
                    _retry = int(m.group(1))
                _update_api_health("setlist", False, error="rate_limited", retry_after=_retry)
                # Dann Cache nutzen, falls vorhanden
                if _cached_list and _cached_sc:
                    # _remaining lokal berechnen — im Force-Refresh-Pfad wurde es
                    # oben nie gesetzt (sonst UnboundLocalError beim Rate-Limit).
                    _remaining = [s for s in _cached_list if s not in already]
                    if _remaining:
                        _manual_order = _cached_sd.get("manual_order", [])
                        if _manual_order:
                            _in_m = [s for s in _manual_order if s in _remaining]
                            _not_in_m = [s for s in _remaining if s not in _manual_order]
                            _out = (_in_m + _not_in_m)
                        else:
                            _out = _remaining
                        return jsonify({
                            "songs":   _out,
                            "scores":  {s: _cached_sc.get(s, 0.5) for s in _out},
                            "badges":  {s: _cached_bg.get(s, "setlist") for s in _out},
                            "uris":    {s: _cached_uri[s] for s in _out if s in _cached_uri},
                            "sources": ["setlist.fm"],
                            "play_counts": {s: _cached_counts[s] for s in _out if s in _cached_counts},
                            "positions_hist": {s: _cached_hist[s] for s in _out if s in _cached_hist},
                            "concerts_analyzed": _cached_total,
                            "error": "rate_limited",
                            "retry_after": _retry,
                        })
                return jsonify({"error": "rate_limited", "songs": [], "scores": {}, "badges": {}, "retry_after": _retry})
            print(f"      more_songs mode error: {_re}")
        except Exception as _me:
            print(f"      more_songs mode error: {_me}")
            # Fallback: normaler Pfad

    # 1) setlist.fm — Cache prüfen, dann API
    # Cache gilt immer — auch wenn tour_name gesetzt war, aber API fehlschlug
    if _cached_list and _cached_sc:
        # Vorberechnete Setlist direkt liefern (kein API-Call nötig)
        _remaining = [s for s in _cached_list if s not in already]
        if len(_remaining) >= min(needed, 3):
            _out = _remaining
            resp_data = {
                "songs":   _out,
                "scores":  {s: _cached_sc.get(s, 0.5) for s in _out},
                "badges":  {s: _cached_bg.get(s, "setlist") for s in _out},
                "uris":    {s: _cached_uri[s] for s in _out if s in _cached_uri},
                "sources": ["setlist.fm"],
                "play_counts": {s: _cached_counts[s] for s in _out if s in _cached_counts},
                "positions_hist": {s: _cached_hist[s] for s in _out if s in _cached_hist},
                "concerts_analyzed": _cached_total,
            }
            if _sl_blocked:
                resp_data["error"] = "rate_limited"
                resp_data["retry_after"] = _sl_retry_secs
            return jsonify(resp_data)

    if setlistfm:
        try:
            from setlist_client import SetlistClient
            result = SetlistClient(api_key=setlistfm).get_setlist_tracks(
                artist, setlist_songs=ask_for, new_songs=2, num_concerts=20
            )
            # Frequenzen aus setlist.fm als Score-Basis speichern (vor dem Filter)
            for title, freq in result.get("frequencies", {}).items():
                setlistfm_freq[title.lower()] = freq
            # Nur Songs mit ≥75% Frequenz in die Kern-Setlist aufnehmen
            SETLIST_THRESHOLD = 0.75
            all_setlist = result.get("setlist_titles", [])
            setlist_songs = [s for s in all_setlist
                             if s not in already and setlistfm_freq.get(s.lower(), 0) >= SETLIST_THRESHOLD]
            new_songs = [s for s in result.get("new_titles", []) if s not in already]
            if setlist_songs or new_songs:
                sources_used.append("setlist.fm")
                for s in setlist_songs + new_songs:
                    song_source_count[s.lower()] = song_source_count.get(s.lower(), 0) + 1
        except RuntimeError as _re:
            # Rate-Limit auch hier registrieren, damit _sl_blocked greift.
            if "rate_limited" in str(_re):
                err_str = str(_re)
                _retry = _seconds_until_midnight_utc()
                import re as _re2
                m = _re2.search(r"rate_limited:(\d+)", err_str)
                if m:
                    _retry = int(m.group(1))
                _update_api_health("setlist", False, error="rate_limited", retry_after=_retry)
        except Exception:
            pass

    # 2) Tavily oder Gemini — aktuelle Tour-Songs + neue Songs vorhersagen
    gemini_limited = False
    tavily_key = env.get("TAVILY_API_KEY", "")

    def _merge_ai_result(result: dict, source_label: str):
        # Source-Tracking: jeden genannten Song zählen
        for s in result.get("setlist_titles", []) + result.get("new_titles", []):
            song_source_count[s.lower()] = song_source_count.get(s.lower(), 0) + 1
        seen = set(already) | {s.lower() for s in setlist_songs}
        added = 0
        for s in result.get("setlist_titles", []):
            if s.lower() not in seen:
                setlist_songs.append(s)
                seen.add(s.lower())
                added += 1
        seen_new = {s.lower() for s in new_songs}
        for s in result.get("new_titles", []):
            if s.lower() not in seen and s.lower() not in seen_new:
                new_songs.append(s)
                seen_new.add(s.lower())
                added += 1
        if added > 0:
            sources_used.append(source_label)

    if tavily_key:
        try:
            from tavily_setlist_client import TavilySetlistClient
            result = TavilySetlistClient(api_key=tavily_key).get_setlist_tracks(
                artist, setlist_songs=ask_for, new_songs=3
            )
            _merge_ai_result(result, "Tavily")
        except Exception as _te:
            print(f"      Tavily error: {_te}")

    if gemini_key and gemini_key != "dein-key-hier":
        try:
            from gemini_setlist_client import GeminiSetlistClient
            result = GeminiSetlistClient(api_key=gemini_key).get_setlist_tracks(
                artist, setlist_songs=ask_for, new_songs=3
            )
            _merge_ai_result(result, "Gemini")
        except Exception as _ge:
            if "rate" in str(_ge).lower() or "limit" in str(_ge).lower() or "quota" in str(_ge).lower() or "429" in str(_ge):
                gemini_limited = True

    # 3) Fallback: Spotify Top Tracks (meistgestreamt) — für kleine Acts ohne Setlist-Daten
    songs = setlist_songs + new_songs
    spotify_top_set: set[str] = set()
    if len(songs) < needed:
        try:
            from spotipy import Spotify
            from spotipy.oauth2 import SpotifyOAuth
            sp_env = dotenv_values(BASE_DIR / ".env")
            sp = Spotify(auth_manager=SpotifyOAuth(
                client_id=sp_env.get("SPOTIFY_CLIENT_ID", ""),
                client_secret=sp_env.get("SPOTIFY_CLIENT_SECRET", ""),
                redirect_uri=sp_env.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
                scope="user-follow-read",
                cache_path=str(BASE_DIR / ".cache"),
            ))
            results = sp.search(q=f"artist:{artist}", type="artist", limit=1)
            items = results.get("artists", {}).get("items", [])
            if items:
                artist_id = items[0]["id"]
                top = sp.artist_top_tracks(artist_id, country="from_token")
                seen = {s.lower() for s in songs} | {s.lower() for s in already}
                spotify_added = 0
                for t in top.get("tracks", []):
                    name = t.get("name", "")
                    if name and name.lower() not in seen:
                        songs.append(name)
                        seen.add(name.lower())
                        spotify_top_set.add(name.lower())
                        song_source_count[name.lower()] = song_source_count.get(name.lower(), 0) + 1
                        spotify_added += 1
                if spotify_added > 0:
                    sources_used.append("Spotify Top")
        except Exception:
            pass

    # Live-Songs herausfiltern (nur bei automatischer Suche, nicht manuell)
    import re as _re
    _live_pat = _re.compile(r'\blive\b', _re.IGNORECASE)
    songs = [s for s in songs if not _live_pat.search(s)]

    # Festival-Erkennung (Rock im Park)
    _cd_file = BASE_DIR / "concert_data.json"
    concert_data_scoring = json.loads(_cd_file.read_text(encoding="utf-8")) if _cd_file.exists() else {}
    # is_festival nur True wenn AUSSCHLIESSLICH Festival (nicht Hamburg-Konzert-Künstler)
    _rip_only = artist in concert_data_scoring.get("rip_artists", {}) and \
                artist not in concert_data_scoring.get("hamburg_artists", {})
    is_festival = _rip_only

    # Confidence-Scores berechnen
    # Basis: setlist.fm-Häufigkeit (gespielt in X% der letzten Konzerte)
    # Badge-Typ pro Song bestimmen
    # Kategorien: setlist (echte Live-Daten), prediction_hoch/mittel/niedrig, spotify
    pred_set = {s.lower() for s in new_songs}  # von KI/Tavily vorhergesagt

    song_badges: dict[str, str] = {}
    scores: dict[str, float] = {}
    for s in songs:
        s_lower = s.lower()
        freq = setlistfm_freq.get(s_lower, 0.0)
        src_count = song_source_count.get(s_lower, 0)

        if s_lower in spotify_top_set and freq == 0.0 and s_lower not in pred_set:
            song_badges[s] = "spotify"
            scores[s] = 0.1
        elif freq > 0.0:
            song_badges[s] = "setlist"
            scores[s] = round(freq, 2)
        else:
            # Vorhersage: Konfidenz nach Anzahl Quellen
            if src_count >= 2:
                level = "hoch"
            elif src_count == 1:
                level = "mittel"
            else:
                level = "niedrig"
            song_badges[s] = f"prediction_{level}"
            scores[s] = round(0.55 if level == "hoch" else 0.35 if level == "mittel" else 0.15, 2)

    # Prioritäts-Sortierung: setlist (hohe Freq) → setlist (niedrig) → pred_hoch → pred_mittel → pred_niedrig → spotify
    _badge_order = {"setlist": 0, "prediction_hoch": 1, "prediction_mittel": 2, "prediction_niedrig": 3, "spotify": 4}

    def _sort_key(s: str):
        badge = song_badges.get(s, "setlist")
        freq = setlistfm_freq.get(s.lower(), 0.0)
        return (_badge_order.get(badge, 5), -freq)

    songs = sorted(songs, key=_sort_key)

    # Scores + Badges in concert_data.json speichern
    # Fresh-Read direkt vor dem Schreiben — verhindert, dass parallel geschriebene
    # setlist_titles (z.B. von write_setlists.py) überschrieben werden.
    _fresh_cd = json.loads(_cd_file.read_text(encoding="utf-8")) if _cd_file.exists() else {}
    sl_entry = _fresh_cd.setdefault("setlist_data", {}).setdefault(artist, {})
    sl_entry["scores"]  = {**sl_entry.get("scores", {}),  **{s: scores[s] for s in songs[:needed]}}
    sl_entry["badges"]  = {**sl_entry.get("badges", {}),  **{s: song_badges[s] for s in songs[:needed]}}
    _save_concert_data(_fresh_cd)

    # Sort using manual_order:
    _manual_order = concert_data_scoring.get("setlist_data", {}).get(artist, {}).get("manual_order", [])
    if _manual_order:
        _in_m = [s for s in songs if s in _manual_order]
        _not_in_m = [s for s in songs if s not in _manual_order]
        _sorted_songs = _in_m + _not_in_m
    else:
        _sorted_songs = songs

    return jsonify({
        "songs":         _sorted_songs[:needed],
        "scores":        {s: scores[s] for s in _sorted_songs[:needed]},
        "badges":        {s: song_badges[s] for s in _sorted_songs[:needed]},
        "is_festival":   is_festival,
        "gemini_limited": gemini_limited,
        "sources":       sources_used,
        "set_type":      concert_data_scoring.get("setlist_data", {}).get(artist, {}).get("set_type", ""),
        "play_counts":   {s: _cached_counts[s] for s in _sorted_songs[:needed] if s in _cached_counts},
        "positions_hist": {s: _cached_hist[s] for s in _sorted_songs[:needed] if s in _cached_hist},
        "concerts_analyzed": _cached_total,
    })


@app.route("/timetable_data")
def timetable_data():
    """Gibt den Timetable fuer ein Festival zurueck (Tag, Buehne, Zeiten)."""
    festival = request.args.get("festival", "Rock im Park")
    data_file = BASE_DIR / "concert_data.json"
    concert_data = json.loads(data_file.read_text(encoding="utf-8")) if data_file.exists() else {}
    rip = concert_data.get("rip_artists", {})

    days = {"Freitag": [], "Samstag": [], "Sonntag": []}
    for name, info in rip.items():
        if info.get("festival") != festival:
            continue
        day = info.get("day", "")
        if not day or day not in days:
            continue
        days[day].append({
            "name":  name,
            "stage": info.get("stage", ""),
            "start": info.get("start", ""),
            "end":   info.get("end", ""),
        })

    # Sortieren nach Startzeit
    for day_acts in days.values():
        day_acts.sort(key=lambda x: x.get("start", ""))

    return jsonify({"days": days, "festival": festival})


if __name__ == "__main__":
    import socket
    import threading
    import webbrowser
    import signal
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # ── Nur eine Server-Instanz erlauben (PID-Datei) ─────────────────
    _pid_file = BASE_DIR / "server.pid"

    def _cleanup_pid():
        try:
            _pid_file.unlink(missing_ok=True)
        except Exception:
            pass

    if _pid_file.exists():
        try:
            old_pid = int(_pid_file.read_text().strip())
            try:
                os.kill(old_pid, signal.SIGTERM)
                _time.sleep(1)
            except (ProcessLookupError, PermissionError):
                pass  # Prozess existiert nicht mehr
            print(f"⚠️  Alte Instanz (PID {old_pid}) beendet.")
        except Exception:
            pass

    _pid_file.write_text(str(os.getpid()))
    import atexit
    atexit.register(_cleanup_pid)

    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "?.?.?.?"

    print("=" * 50)
    print("  🎶 Concertify")
    print(f"  PC:    http://localhost:5000")
    print(f"  Handy: http://{local_ip}:5000")
    print("=" * 50)

    # Browser nach kurzem Delay öffnen (Server braucht einen Moment)
    threading.Timer(1.2, lambda: webbrowser.open("http://localhost:5000")).start()

    app.run(host="0.0.0.0", port=5000, debug=False)
