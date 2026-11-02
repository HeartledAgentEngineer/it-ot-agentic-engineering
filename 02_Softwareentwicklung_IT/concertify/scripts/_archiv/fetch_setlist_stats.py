"""
fetch_setlist_stats.py — Holt echte Positions-Histogramm-Daten von setlist.fm

Für jeden Künstler in setlist_data:
  - Tour-Künstler  (set_type = echter Tour-Name): filtert nach Tour-Name
  - Festival-Künstler (set_type = "__festival__"): filtert nach Festival-Sets
  - Konzert-Künstler (set_type = "__concert__"): letzte 50 Sets, kein Filter

Speichert positions_hist, play_counts, total_concerts_analyzed.

Verwendung:
    python fetch_setlist_stats.py                    # alle Künstler
    python fetch_setlist_stats.py "Linkin Park"      # einzelner Künstler
    python fetch_setlist_stats.py --dry-run          # keine Änderungen, nur Ausgabe
"""

import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import dotenv_values

from external.setlistfm_quota import SetlistFmQuota

BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "concert_data.json"
BASE_URL = "https://api.setlist.fm/rest/1.0"

# Quota-Tracker: zaehlt taegliche API-Calls, blockt bei 1000 (Soft-Limit)
QUOTA = SetlistFmQuota(BASE_DIR / "setlistfm_quota.json")

FESTIVAL_KEYWORDS = [
    "festival", "open air", "open-air", "rock im park", "rock am ring",
    "wacken", "hurricane", "southside", "download", "hellfest",
    "lollapalooza", "coachella", "reading", "leeds", "elbriot",
    "impericon", "copenhell", "sonic temple", "knotfest",
]

MAX_PAGES = 10         # max 20 Setlists pro Seite × 10 = 200 Setlists
SLEEP_BETWEEN = 2.0    # Sekunden zwischen API-Calls — bewusst konservativ.
                       # Setlist.fm-Limit: 2/s. Burst-Schutz schlaegt frueher zu.
                       # 2.0s = 0.5 req/sec ist sicher unter dem Limit.


def _is_festival_set(setlist: dict) -> bool:
    """True wenn das Set ein Festival-Auftritt ist."""
    tour = (setlist.get("tour") or {}).get("name", "")
    if tour:
        for kw in FESTIVAL_KEYWORDS:
            if kw in tour.lower():
                return True
    venue_name = (setlist.get("venue") or {}).get("name", "").lower()
    if any(kw in venue_name for kw in FESTIVAL_KEYWORDS):
        return True
    # Kein Tour-Name → wahrscheinlich Festival oder One-off
    songs = _extract_songs_ordered(setlist)
    if not tour and len(songs) <= 20:
        return True
    return False


def _extract_songs_ordered(setlist: dict) -> list[tuple[str, int]]:
    """Gibt [(song_name, position_1based), ...] zurück. Coversongs werden übersprungen."""
    songs = []
    pos = 1
    for song_set in setlist.get("sets", {}).get("set", []):
        for song in song_set.get("song", []):
            name = song.get("name", "").strip()
            if name and not song.get("cover"):
                songs.append((name, pos))
                pos += 1
    return songs


def _find_mbid(artist_name: str, session: requests.Session) -> str | None:
    """Sucht MBID für einen Künstler."""
    # Quota-Check VOR Request
    if not QUOTA.can_make_request():
        print(f"  Quota erreicht — MBID-Suche fuer {artist_name} uebersprungen")
        return None
    try:
        resp = session.get(
            f"{BASE_URL}/search/artists",
            params={"artistName": artist_name, "sort": "relevance", "p": 1},
            timeout=10,
        )
        QUOTA.record_request()
        if resp.status_code == 429:
            print(f"  Rate-Limit bei MBID-Suche fuer {artist_name}")
            return None
        resp.raise_for_status()
        artists = resp.json().get("artist", [])
        for a in artists:
            if a.get("name", "").lower() == artist_name.lower():
                return a.get("mbid")
        if artists:
            return artists[0].get("mbid")
    except Exception as e:
        print(f"  Fehler bei MBID-Suche: {e}")
    return None


def _fetch_all_setlists(mbid: str, session: requests.Session) -> list[dict]:
    """Holt alle verfügbaren Setlists (paginiert, max MAX_PAGES Seiten)."""
    all_setlists = []
    for page in range(1, MAX_PAGES + 1):
        # Quota-Check VOR jedem Request
        if not QUOTA.can_make_request():
            remaining_secs = QUOTA.reset_in_seconds()
            hrs = remaining_secs // 3600
            mins = (remaining_secs % 3600) // 60
            print(f"  Quota erreicht ({QUOTA.requests_today()} Requests heute) — Reset in {hrs}h{mins}min")
            raise RuntimeError("quota_exhausted")
        try:
            resp = session.get(
                f"{BASE_URL}/artist/{mbid}/setlists",
                params={"p": page},
                timeout=12,
            )
            QUOTA.record_request()  # zaehlen auch wenn 429 zurueckkam
            if resp.status_code == 429:
                retry = int(resp.headers.get("Retry-After", 3600))
                print(f"  Rate-Limit! Retry-After: {retry}s — breche ab")
                raise RuntimeError(f"rate_limited:{retry}")
            resp.raise_for_status()
            data = resp.json()
            batch = data.get("setlist", [])
            if not batch:
                break
            all_setlists.extend(batch)
            total = int(data.get("total", 0))
            if len(all_setlists) >= total:
                break
            time.sleep(SLEEP_BETWEEN)
        except RuntimeError:
            raise
        except Exception as e:
            print(f"  Fehler auf Seite {page}: {e}")
            break
    return all_setlists


def _build_hist(setlists: list[dict], filter_fn) -> tuple[dict, dict, int]:
    """
    Baut positions_hist und play_counts aus gefilterten Setlists.
    Returns (positions_hist, play_counts, total_concerts)
    """
    positions_hist: dict[str, dict[str, int]] = {}
    play_counts: dict[str, int] = {}
    total = 0

    for sl in setlists:
        if not filter_fn(sl):
            continue
        songs = _extract_songs_ordered(sl)
        if not songs:
            continue
        total += 1
        for name, pos in songs:
            pos_str = str(pos)
            if name not in positions_hist:
                positions_hist[name] = {}
            positions_hist[name][pos_str] = positions_hist[name].get(pos_str, 0) + 1
            play_counts[name] = play_counts.get(name, 0) + 1

    return positions_hist, play_counts, total


def process_artist(artist: str, entry: dict, session: requests.Session, dry_run: bool) -> dict | None:
    """Verarbeitet einen Künstler. Gibt aktualisiertes entry-dict zurück oder None bei Fehler."""
    set_type = entry.get("set_type", "")
    print(f"\n  {artist} [{set_type}]")

    mbid = _find_mbid(artist, session)
    if not mbid:
        print(f"  -> MBID nicht gefunden, uebersprungen")
        return None
    print(f"  MBID: {mbid}")
    time.sleep(SLEEP_BETWEEN)

    try:
        all_setlists = _fetch_all_setlists(mbid, session)
    except RuntimeError as e:
        if "rate_limited" in str(e):
            seconds = int(str(e).split(":")[1])
            print(f"  Rate-Limit fuer {artist}, {seconds//3600}h{(seconds%3600)//60}min verbleibend")
            raise
        return None

    print(f"  {len(all_setlists)} Setlists gefunden")

    # Filterfunktion bestimmen
    if set_type == "__festival__":
        filter_fn = _is_festival_set
        label = "Festival-Sets"
    elif set_type in ("__concert__", ""):
        filter_fn = lambda sl: True  # alle nehmen
        label = "alle Sets"
    else:
        # Echter Tour-Name: nach Tour filtern
        tour_name_lower = set_type.lower()
        filter_fn = lambda sl: tour_name_lower in (sl.get("tour") or {}).get("name", "").lower()
        label = f"Tour '{set_type}'"

    positions_hist, play_counts, total = _build_hist(all_setlists, filter_fn)

    # Fallback: zu wenig Festival-Sets -> alle Sets nehmen (Sebastians Minimum: 5)
    MIN_SETS = 5
    if total < MIN_SETS and set_type == "__festival__":
        print(f"  -> Nur {total} {label} gefunden, Fallback auf alle Sets")
        positions_hist, play_counts, total = _build_hist(all_setlists, lambda sl: True)
        label = "alle Sets (Festival-Fallback)"

    if total == 0:
        print(f"  -> Keine passenden Sets ({label}), uebersprungen")
        return None

    print(f"  -> {total} passende Sets ({label}), {len(positions_hist)} Songs")

    if dry_run:
        for song, hist in list(positions_hist.items())[:5]:
            top = sorted(hist.items(), key=lambda x: x[1], reverse=True)[:3]
            print(f"     {song}: " + ", ".join(f"Pos{k}={v}" for k, v in top))
        return None

    # Positions-Durchschnitt berechnen
    positions_avg = {}
    for song, hist in positions_hist.items():
        total_plays = sum(hist.values())
        positions_avg[song] = sum(int(k) * v for k, v in hist.items()) / total_plays

    # Entry aktualisieren — nur Statistik-Felder, spotify_uris bleiben
    updated = dict(entry)
    updated["positions_hist"] = positions_hist
    updated["positions"] = positions_avg
    updated["play_counts"] = play_counts
    updated["total_concerts_analyzed"] = total

    # setlist_titles in CHRONOLOGISCHER Reihenfolge (nach haeufigster Position aufsteigend);
    # bei gleicher Top-Position: haeufigerer Song zuerst.
    def _sort_key(s: str) -> tuple[int, int]:
        h = positions_hist.get(s, {})
        if not h:
            return (9999, 0)
        top_pos, top_cnt = max(h.items(), key=lambda x: x[1])
        return (int(top_pos), -top_cnt)
    all_songs_sorted = sorted(play_counts.keys(), key=_sort_key)
    updated["setlist_titles"] = all_songs_sorted

    # Scores neu berechnen (play_count / total)
    updated["scores"] = {s: round(play_counts[s] / total, 3) for s in all_songs_sorted}
    updated["badges"] = {s: "setlist" for s in all_songs_sorted}

    return updated


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    target_artist = next((a for a in args if not a.startswith("--")), None)

    if dry_run:
        print("DRY-RUN — keine Änderungen werden gespeichert\n")

    # Quota-Status anzeigen
    status = QUOTA.status()
    print(f"Quota heute: {status['used']}/{status['limit']} Requests ({status['remaining']} verbleibend)")
    if not status["can_request"]:
        reset_secs = status["reset_in_seconds"]
        print(f"Quota erreicht. Reset in {reset_secs//3600}h{(reset_secs%3600)//60}min — Abbruch")
        sys.exit(1)
    print()

    env = dotenv_values(BASE_DIR / ".env")
    api_key = env.get("SETLISTFM_API_KEY", "")
    if not api_key:
        print("FEHLER: SETLISTFM_API_KEY fehlt in .env")
        sys.exit(1)

    session = requests.Session()
    session.headers.update({"x-api-key": api_key, "Accept": "application/json"})

    cd = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    sd = cd.setdefault("setlist_data", {})

    artists = [target_artist] if target_artist else list(sd.keys())
    print(f"Verarbeite {len(artists)} Kuenstler...")

    updated_count = 0
    for artist in artists:
        if artist not in sd:
            print(f"\n  {artist} nicht in setlist_data gefunden")
            continue
        try:
            result = process_artist(artist, sd[artist], session, dry_run)
        except RuntimeError:
            print("  -> Rate-Limit erreicht, Abbruch")
            break
        if result is not None:
            sd[artist] = result
            updated_count += 1
            if not dry_run:
                tmp = DATA_FILE.with_suffix(".tmp")
                tmp.write_text(json.dumps(cd, ensure_ascii=False, indent=2), encoding="utf-8")
                os.replace(tmp, DATA_FILE)
                print(f"  -> Gespeichert")

    print(f"\nFertig: {updated_count} Kuenstler aktualisiert")


if __name__ == "__main__":
    main()
