"""
Spotify Concert Playlist Generator
===================================
Builds / updates a Spotify playlist from:
  - Artists with upcoming concerts in Hamburg (Ticketmaster + Claude AI web search)
  - Artists in the Rock im Park 2026 lineup

Run:  python main.py
"""

import os
import sys

from dotenv import load_dotenv

from ticketmaster_client import TicketmasterClient
from songkick_client import SongkickClient
from description_builder import build_description
from matcher import match_artists
from rock_im_park import scrape_lineup
from spotify_client import SpotifyClient


def main() -> None:
    load_dotenv()

    # ------------------------------------------------------------------ #
    # Config                                                               #
    # ------------------------------------------------------------------ #
    spotify_client_id = _require("SPOTIFY_CLIENT_ID")
    spotify_client_secret = _require("SPOTIFY_CLIENT_SECRET")
    spotify_redirect_uri = os.getenv(
        "SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"
    )

    playlist_name = os.getenv("PLAYLIST_NAME", "Concert Ready 2026")
    hamburg_radius = int(os.getenv("HAMBURG_RADIUS_KM", "50"))
    track_limit = int(os.getenv("TRACK_LIMIT_PER_ARTIST", "8"))

    # ------------------------------------------------------------------ #
    # Step 1 — Spotify: get followed artists                              #
    # ------------------------------------------------------------------ #
    print("\n[1/6] Fetching followed artists from Spotify …")
    spotify = SpotifyClient(spotify_client_id, spotify_client_secret, spotify_redirect_uri)
    followed = spotify.get_followed_artists()

    if not followed:
        print("No followed artists found. Exiting.")
        sys.exit(0)

    followed_names = [a["name"] for a in followed]
    followed_by_name = {a["name"]: a for a in followed}

    # ------------------------------------------------------------------ #
    # Step 2 — Hamburg concerts (Ticketmaster + Claude AI web search)    #
    # ------------------------------------------------------------------ #
    hamburg_events: dict[str, list[dict]] = {}

    # 2a — Ticketmaster
    tm_api_key = os.getenv("TICKETMASTER_API_KEY")
    if tm_api_key:
        print(f"\n[2/6] Searching Hamburg concerts via Ticketmaster …")
        tm = TicketmasterClient(api_key=tm_api_key)
        tm_events = tm.get_hamburg_artists(followed, max_pages=5)
        for artist, events in tm_events.items():
            hamburg_events.setdefault(artist, []).extend(events)
        print(f"  >> {len(tm_events)} artists via Ticketmaster")
    else:
        print("\n[2/6] TICKETMASTER_API_KEY not set — skipping Ticketmaster.")

    # 2b — Songkick (checks each artist individually, free, no key needed)
    print("  Searching Hamburg concerts via Songkick (per artist) …")
    try:
        sk = SongkickClient()
        sk_events = sk.get_hamburg_artists(followed)
        new_from_sk = 0
        for artist, events in sk_events.items():
            if artist not in hamburg_events:
                hamburg_events[artist] = events
                new_from_sk += 1
            else:
                existing_dates = {e.get("datetime", "") for e in hamburg_events[artist]}
                for ev in events:
                    if ev.get("datetime", "") not in existing_dates:
                        hamburg_events[artist].append(ev)
        print(f"  >> {new_from_sk} additional artists via Songkick")
    except Exception as e:
        print(f"  !! Songkick search failed: {e}")

    # 2c — Eventim (disabled: blocks Python requests, always times out)

    # 2d — Tavily web search (finds Eventim/local concerts Ticketmaster misses)
    tavily_key = os.getenv("TAVILY_API_KEY")
    if tavily_key:
        print("  Searching Hamburg concerts via Tavily web search …")
        try:
            from tavily_concert_client import TavilyConcertClient
            tv = TavilyConcertClient(api_key=tavily_key)
            tv_events = tv.get_hamburg_artists(followed, already_found=set(hamburg_events.keys()))
            new_from_tv = 0
            for artist, events in tv_events.items():
                if artist not in hamburg_events:
                    hamburg_events[artist] = events
                    new_from_tv += 1
                else:
                    existing_dates = {e.get("datetime", "") for e in hamburg_events[artist]}
                    for ev in events:
                        if ev.get("datetime", "") not in existing_dates:
                            hamburg_events[artist].append(ev)
            print(f"  >> {new_from_tv} additional artists via Tavily")
        except Exception as e:
            print(f"  !! Tavily search failed: {e}")

    # 2e — Claude AI web search (optional, needs ANTHROPIC_API_KEY)
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        print("  Searching Hamburg concerts via Claude AI …")
        try:
            from claude_concert_client import ClaudeConcertClient
            claude_client = ClaudeConcertClient(api_key=anthropic_key)
            claude_events = claude_client.get_hamburg_artists(followed)
            new_from_claude = 0
            for artist, events in claude_events.items():
                if artist not in hamburg_events:
                    hamburg_events[artist] = events
                    new_from_claude += 1
                else:
                    existing_dates = {e.get("datetime", "") for e in hamburg_events[artist]}
                    for ev in events:
                        if ev.get("datetime", "") not in existing_dates:
                            hamburg_events[artist].append(ev)
            print(f"  >> {new_from_claude} additional artists via Claude AI")
        except Exception as e:
            print(f"  !! Claude AI search failed: {e}")

    if not tm_api_key:
        print("  (Tipp: TICKETMASTER_API_KEY in .env setzen fuer noch mehr Konzerte)")

    hamburg_artist_names = list(hamburg_events.keys())
    print(f"  >> {len(hamburg_artist_names)} total artists with Hamburg shows")

    if hamburg_artist_names:
        for name in sorted(hamburg_artist_names):
            dates = [e.get("datetime", "")[:10] for e in hamburg_events[name]]
            print(f"     - {name}: {', '.join(d for d in dates if d) or '(date unknown)'}")

    # ------------------------------------------------------------------ #
    # Step 3 — Rock im Park lineup                                        #
    # ------------------------------------------------------------------ #
    print("\n[3/6] Fetching Rock im Park 2026 lineup …")
    rip_lineup = scrape_lineup()

    if rip_lineup:
        print(f"  >> {len(rip_lineup)} artists in Rock im Park lineup")
    else:
        print("  !!  Could not retrieve Rock im Park lineup")

    # ------------------------------------------------------------------ #
    # Step 4 — Match Rock im Park against followed artists               #
    # ------------------------------------------------------------------ #
    print("\n[4/6] Matching Rock im Park lineup with followed artists …")
    rip_matches = match_artists(followed, rip_lineup)
    rip_artist_names = list(rip_matches.keys())
    print(f"  >> {len(rip_artist_names)} matches: {', '.join(rip_artist_names) or '(none)'}")

    # ------------------------------------------------------------------ #
    # Step 5 — Collect tracks                                             #
    # ------------------------------------------------------------------ #
    artists_to_include = list(
        dict.fromkeys(hamburg_artist_names + rip_artist_names)
    )

    if not artists_to_include:
        print("\nNo artists to include. Exiting without creating a playlist.")
        sys.exit(0)

    # ------------------------------------------------------------------ #
    # Filter: date range + exclusions (from env / web UI)                 #
    # ------------------------------------------------------------------ #
    exclude_list = [
        a.strip() for a in os.getenv("EXCLUDE_ARTISTS", "").split(",") if a.strip()
    ]
    date_from = os.getenv("DATE_FILTER_FROM", "").strip()
    date_to   = os.getenv("DATE_FILTER_TO",   "").strip()

    if exclude_list or date_from or date_to:
        filtered: list[str] = []
        for name in artists_to_include:
            if name in exclude_list:
                print(f"  -- Excluding {name} (exclusion list)")
                continue
            if (date_from or date_to) and name in hamburg_events:
                dates = sorted([
                    e.get("datetime", "")[:10]
                    for e in hamburg_events[name]
                    if e.get("datetime", "")[:10]
                ])
                if dates:
                    earliest = min(dates)
                    latest   = max(dates)
                    if date_from and latest < date_from:
                        continue
                    if date_to and earliest > date_to:
                        continue
            filtered.append(name)
        print(f"  >> {len(filtered)} artists after filters (was {len(artists_to_include)})")
        artists_to_include = filtered

    if not artists_to_include:
        print("\nNo artists after filtering. Exiting.")
        sys.exit(0)

    # Optional: setlist.fm for smarter track selection
    setlistfm_key = os.getenv("SETLISTFM_API_KEY")
    setlist_client = None
    if setlistfm_key:
        from setlist_client import SetlistClient
        setlist_client = SetlistClient(api_key=setlistfm_key)
        print(f"\n[5/6] Fetching tracks for {len(artists_to_include)} artists (with setlist.fm) …")
    else:
        print(f"\n[5/6] Fetching tracks for {len(artists_to_include)} artists …")
        print("  (Tipp: SETLISTFM_API_KEY in .env setzen fuer bessere Track-Auswahl)")

    # Per-song exclusions: "Artist::Song1,Artist::Song2"
    exclude_songs_raw = os.getenv("EXCLUDE_SONGS", "")
    exclude_songs_by_artist: dict[str, list[str]] = {}
    for _item in (exclude_songs_raw.split(",") if exclude_songs_raw else []):
        _item = _item.strip()
        if "::" in _item:
            _art, _sng = _item.split("::", 1)
            exclude_songs_by_artist.setdefault(_art.strip(), []).append(_sng.strip())

    # Optional: KI-Fallback für fehlende Setlists (Gemini bevorzugt, sonst Claude)
    claude_setlist_client = None
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")

    if gemini_key and gemini_key != "dein-key-hier":
        from gemini_setlist_client import GeminiSetlistClient
        claude_setlist_client = GeminiSetlistClient(api_key=gemini_key)
        print("  KI-Setlists: Gemini aktiviert")
    elif os.getenv("USE_CLAUDE_SETLIST") == "1" and anthropic_key:
        from claude_setlist_client import ClaudeSetlistClient
        claude_setlist_client = ClaudeSetlistClient(api_key=anthropic_key)
        print("  KI-Setlists: Claude aktiviert")

    all_track_uris: list[str] = []

    for idx, name in enumerate(artists_to_include, 1):
        safe_name = name.encode("ascii", "replace").decode("ascii")
        print(f"  [{idx}/{len(artists_to_include)}] {safe_name} …")
        artist = followed_by_name[name]

        setlist_titles: list[str] = []
        new_titles: list[str] = []

        # setlist.fm — historische Kern-Setlist
        if setlist_client:
            try:
                sl = setlist_client.get_setlist_tracks(name, setlist_songs=max(track_limit - 2, 0), new_songs=min(2, track_limit))
                setlist_titles = sl["setlist_titles"]
                new_titles = sl["new_titles"]
                if setlist_titles:
                    print(f"      setlist.fm: {len(setlist_titles)} songs, {len(new_titles)} new")
            except Exception as e:
                print(f"      setlist.fm error: {e}")

        # Gemini — immer zusätzlich: aktuelle Tour-Songs + Chart-Bänger
        if claude_setlist_client:
            try:
                sl = claude_setlist_client.get_setlist_tracks(name, setlist_songs=max(track_limit - 2, 0), new_songs=2)
                seen = {t.lower() for t in setlist_titles}
                for s in sl["setlist_titles"]:
                    if s.lower() not in seen:
                        setlist_titles.append(s)
                        seen.add(s.lower())
                seen_new = {t.lower() for t in new_titles}
                for s in sl.get("new_titles", []):
                    if s.lower() not in seen and s.lower() not in seen_new:
                        new_titles.append(s)
                        seen_new.add(s.lower())
                if sl["setlist_titles"]:
                    print(f"      Gemini: +{len(sl['setlist_titles'])} songs, +{len(sl.get('new_titles', []))} new")
            except Exception as e:
                print(f"      Gemini error: {e}")

        if setlist_titles:
            print(f"      → {len(setlist_titles)} setlist + {len(new_titles)} neue Bänger")

        tracks = spotify.get_best_tracks(
            artist["id"],
            artist["name"],
            max_tracks=track_limit,
            setlist_titles=setlist_titles,
            new_titles=new_titles,
            setlist_count=max(track_limit - 2, 0),
            new_count=min(2, track_limit),
            exclude_titles=exclude_songs_by_artist.get(name),
        )
        uris = [t["uri"] for t in tracks if t.get("uri")]
        if len(uris) < track_limit and (setlist_titles or new_titles):
            not_found = track_limit - len(uris)
            print(f"      {len(uris)} tracks selected  ⚠ {not_found} nicht auf Spotify gefunden")
        else:
            print(f"      {len(uris)} tracks selected")
        all_track_uris.extend(uris)

    print(f"  >> {len(all_track_uris)} total tracks")

    # ------------------------------------------------------------------ #
    # Step 6 — Create / update playlist                                   #
    # ------------------------------------------------------------------ #
    print(f"\n[6/6] Creating / updating Spotify playlist '{playlist_name}' …")

    description = build_description(
        hamburg_events=hamburg_events,
        rip_artists=rip_artist_names,
    )
    print(f"  Description: {description}")

    playlist_id, created = spotify.get_or_create_playlist(playlist_name)
    action = "Created" if created else "Found existing"
    print(f"  {action} playlist: {playlist_id}")

    added, removed = spotify.update_playlist(playlist_id, all_track_uris, description)
    print(f"  Diff: +{added} tracks added, -{removed} tracks removed")

    # ------------------------------------------------------------------ #
    # Summary                                                              #
    # ------------------------------------------------------------------ #
    print("\n" + "=" * 60)
    print(f"Playlist '{playlist_name}' updated successfully!")
    print(f"  Total tracks   : {len(all_track_uris)}")
    print(f"  Hamburg artists: {len(hamburg_artist_names)}")
    print(f"  Rock im Park   : {len(rip_artist_names)}")
    if hamburg_artist_names:
        print(f"\n  Hamburg shows  : {', '.join(sorted(hamburg_artist_names))}")
    if rip_artist_names:
        print(f"\n  Rock im Park   : {', '.join(sorted(rip_artist_names))}")
    print("=" * 60)


def _require(env_var: str) -> str:
    val = os.getenv(env_var)
    if not val:
        print(f"ERROR: {env_var} is not set. Copy .env.example to .env and fill it in.")
        sys.exit(1)
    return val


if __name__ == "__main__":
    main()
