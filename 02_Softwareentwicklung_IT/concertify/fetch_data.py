"""
Fetch & save concert data to concert_data.json
================================================
Holt gefolgte Künstler von Spotify, sucht Hamburg-Konzerte
(Ticketmaster + Songkick + Eventim + Tavily) und Rock im Park Lineup.
Speichert alles in concert_data.json für die Web-UI.

Run: python fetch_data.py
"""

import json
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")


def main() -> None:
    today = date.today().isoformat()
    concert_cities = [
        c.strip() for c in os.getenv("CONCERT_CITIES", "Hamburg").split(",") if c.strip()
    ] or ["Hamburg"]
    active_festivals = [
        f.strip() for f in os.getenv("ACTIVE_FESTIVALS", "Rock im Park").split(",")
        if f.strip()
    ]
    date_from = os.getenv("DATE_FILTER_FROM", "").strip() or today
    date_to   = os.getenv("DATE_FILTER_TO", "").strip() or "9999-12-31"
    print(f"\n  Staedte: {', '.join(concert_cities)}  |  Festivals: {', '.join(active_festivals) or '(keine)'}", flush=True)

    # ── Spotify: gefolgte Künstler ──────────────────────────────────
    print("\n[1/4] Gefolgte Künstler von Spotify holen …", flush=True)
    from spotify_client import SpotifyClient
    spotify = SpotifyClient(
        client_id=_require("SPOTIFY_CLIENT_ID"),
        client_secret=_require("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
    )
    followed = spotify.get_followed_artists()
    if not followed:
        print("Keine gefolgten Künstler gefunden.", flush=True)
        sys.exit(0)
    print(f"  >> {len(followed)} Künstler", flush=True)

    # ── Konzert-Suche für alle Städte ──────────────────────────────────
    print(f"\n[2/4] Konzerte in {', '.join(concert_cities)} suchen …", flush=True)
    hamburg_events: dict[str, list[dict]] = {}
    tavily_key = os.getenv("TAVILY_API_KEY")
    serper_key = os.getenv("SERPER_API_KEY")

    from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout

    def _merge_events(events: dict) -> int:
        new_count = 0
        for artist, evlist in events.items():
            if artist not in hamburg_events:
                hamburg_events[artist] = list(evlist)
                new_count += 1
            else:
                existing = {e.get("datetime", "") for e in hamburg_events[artist]}
                for ev in evlist:
                    if ev.get("datetime", "") not in existing:
                        hamburg_events[artist].append(ev)
        return new_count

    for concert_city in concert_cities:
        is_hamburg = "hamburg" in concert_city.lower()
        print(f"  -- {concert_city}:", flush=True)

        def _fetch_eventim(city=concert_city, hh=is_hamburg):
            if not hh:
                return {}
            from eventim_client import EventimClient
            import time as _t
            from matcher import normalise
            client = EventimClient()
            results = client.get_hamburg_artists(followed)
            missing = [a for a in followed if normalise(a["name"]) not in {normalise(k) for k in results}]
            for a in missing:
                found = client.search_artist_hamburg(a["name"])
                if found:
                    results[a["name"]] = [{"datetime": e["date"], "venue": e.get("venue", city)} for e in found]
                _t.sleep(0.3)
            return results

        def _fetch_ticketmaster(city=concert_city, hh=is_hamburg):
            tm_key = os.getenv("TICKETMASTER_API_KEY")
            if not tm_key:
                return {}
            from ticketmaster_client import TicketmasterClient
            if hh:
                return TicketmasterClient(api_key=tm_key).get_hamburg_artists(followed, max_pages=5)
            return {}

        _ex = ThreadPoolExecutor(max_workers=2)
        fs = {
            _ex.submit(_fetch_eventim):     "Eventim",
            _ex.submit(_fetch_ticketmaster): "Ticketmaster",
        }
        try:
            for fut in as_completed(fs, timeout=120):
                try:
                    result = fut.result() or {}
                    for evlist in result.values():
                        for ev in evlist:
                            ev.setdefault("city", concert_city)
                    n = _merge_events(result)
                    print(f"     {fs[fut]}: {n} Konzerte gefunden", flush=True)
                except Exception as e:
                    print(f"     !! {fs[fut]}: {e}", flush=True)
        except FuturesTimeout:
            pending = [name for fut, name in fs.items() if not fut.done()]
            print(f"     !! Timeout nach 120s: {', '.join(pending)} uebersprungen", flush=True)
        finally:
            _ex.shutdown(wait=False, cancel_futures=True)

        if tavily_key:
            already = set(hamburg_events.keys())
            remaining = len(followed) - len(already)
            print(f"  Tavily: {remaining} Artists noch nicht gefunden - suche ...", flush=True)
            try:
                from tavily_concert_client import TavilyConcertClient
                tv = TavilyConcertClient(api_key=tavily_key)
                if is_hamburg:
                    tv_raw = tv.get_hamburg_artists(followed, already_found=already)
                else:
                    tv_raw = {}
                    for a in followed:
                        if a["name"] not in already:
                            evs = tv._search_artist(a["name"], city=concert_city)
                            if evs:
                                tv_raw[a["name"]] = evs
                normalized = {
                    artist: [{"datetime": e.get("datetime", ""), "venue": e.get("venue", concert_city), "city": concert_city} for e in evs]
                    for artist, evs in tv_raw.items()
                }
                n = _merge_events(normalized)
                if n:
                    print(f"     {n} zusaetzliche Kuenstler via Tavily", flush=True)
            except Exception as e:
                print(f"     !! Tavily: {e}", flush=True)

        if serper_key:
            already_s = set(hamburg_events.keys())
            remaining_s = len(followed) - len(already_s)
            if remaining_s > 0:
                print(f"  Serper: {remaining_s} Artists noch nicht gefunden - suche ...", flush=True)
                try:
                    from serper_concert_client import SerperConcertClient
                    sc = SerperConcertClient(api_key=serper_key)
                    if is_hamburg:
                        sr_raw = sc.get_hamburg_artists(followed, already_found=already_s)
                    else:
                        sr_raw = {}
                        for a in followed:
                            if a["name"] not in already_s:
                                evs = sc._search_artist(a["name"], city=concert_city)
                                if evs:
                                    sr_raw[a["name"]] = evs
                    normalized_s = {
                        artist: [{"datetime": e.get("datetime", ""), "venue": e.get("venue", concert_city), "city": concert_city} for e in evs]
                        for artist, evs in sr_raw.items()
                    }
                    n_s = _merge_events(normalized_s)
                    if n_s:
                        print(f"     {n_s} zusaetzliche Kuenstler via Serper", flush=True)
                except Exception as e:
                    print(f"     !! Serper: {e}", flush=True)

    # Vergangene Konzerte herausfiltern + Live-Ausgabe pro Künstler
    filtered_hamburg: dict[str, dict] = {}
    removed = 0
    for name, events in hamburg_events.items():
        future_events = [
            e for e in events
            if date_from <= e.get("datetime", "9999")[:10] <= date_to
        ]
        if future_events:
            sorted_dates = sorted(set(
                e.get("datetime", "")[:10] for e in future_events if e.get("datetime")
            ))
            date_venue = {}
            date_city = {}
            for e in future_events:
                d = e.get("datetime", "")[:10]
                if not d:
                    continue
                v = e.get("venue", "") or ""
                if d not in date_venue or not date_venue[d] or len(date_venue[d]) < len(v):
                    date_venue[d] = v or concert_cities[0]
                if d not in date_city:
                    date_city[d] = e.get("city", concert_cities[0]) or concert_cities[0]
            filtered_hamburg[name] = {
                "dates": sorted_dates,
                "venue": date_venue.get(sorted_dates[0], concert_cities[0]),
                "venues": date_venue,
                "cities": date_city,
            }
            venue = date_venue.get(sorted_dates[0], concert_cities[0])
            date_fmt = f"{sorted_dates[0][8:10]}.{sorted_dates[0][5:7]}.{sorted_dates[0][0:4]}"
            extra = f" +{len(sorted_dates)-1} weitere" if len(sorted_dates) > 1 else ""
            print(f"  🎸 {name} — {date_fmt}{extra} · {venue}", flush=True)
        else:
            removed += 1
    if removed:
        print(f"  >> {removed} Künstler mit vergangenen Konzerten entfernt", flush=True)
    print(f"  >> {len(filtered_hamburg)} Künstler mit zukünftigen Hamburg-Konzerten", flush=True)

    # ── Festivals ───────────────────────────────────────────────────
    print(f"\n[3/4] Festival-Lineups holen ({', '.join(active_festivals)}) …", flush=True)
    rip_artists: dict[str, dict] = {}
    try:
        from festival_client import KNOWN_FESTIVALS, get_lineup
        from matcher import match_artists
        for fest_name in active_festivals:
            fest_info = KNOWN_FESTIVALS.get(fest_name, {})
            fest_date = fest_info.get("date", "2026-06-05")
            fest_city = fest_info.get("city", fest_name)
            fest_venue = f"{fest_name}, {fest_city}"
            # Festival liegt ausserhalb des gewaehlten Zeitraums
            if not (date_from <= fest_date[:10] <= date_to):
                print(f"  -- {fest_name} uebersprungen (ausserhalb {date_from} - {date_to})", flush=True)
                continue
            print(f"  Lineup holen: {fest_name} …", flush=True)
            try:
                lineup = get_lineup(fest_name, tavily_key or "")
                if not lineup:
                    print(f"  !! Kein Lineup gefunden fuer {fest_name}", flush=True)
                    continue
                print(f"  >> {len(lineup)} Kuenstler im {fest_name} Lineup", flush=True)
                matches = match_artists(followed, lineup)

                # Timetable (Bühne + Zeiten) für Rock im Park holen
                timetable: dict = {}
                if fest_name == "Rock im Park" and matches:
                    try:
                        from rock_im_park import scrape_timetable
                        print("  Timetable-Daten holen ...", flush=True)
                        timetable = scrape_timetable(list(matches.keys()), tavily_key or "")
                    except Exception as te:
                        print(f"  !! Timetable: {te}", flush=True)

                for name in matches:
                    slot = timetable.get(name, {})
                    entry = {
                        "dates":    [fest_date],
                        "venue":    fest_venue,
                        "festival": fest_name,
                        "day":      slot.get("day",   ""),
                        "stage":    slot.get("stage", ""),
                        "start":    slot.get("start", ""),
                        "end":      slot.get("end",   ""),
                    }
                    if name not in rip_artists:
                        rip_artists[name] = entry
                    else:
                        rip_artists[name]["dates"].append(fest_date)
                        # Timetable-Daten überschreiben falls neu gefunden
                        for k in ("day", "stage", "start", "end"):
                            if slot.get(k):
                                rip_artists[name][k] = slot[k]
                    slot_str = ""
                    if slot.get("day"):   slot_str += f" {slot['day']}"
                    if slot.get("stage"): slot_str += f" · {slot['stage']}"
                    if slot.get("start"): slot_str += f" {slot['start']}"
                    if slot.get("end"):   slot_str += f"-{slot['end']}"
                    print(f"  + {name} -- {fest_date[:10]}{slot_str} · {fest_venue}", flush=True)
            except Exception as e:
                print(f"  !! {fest_name} Fehler: {e}", flush=True)
        print(f"  >> {len(rip_artists)} Matches gesamt: {', '.join(rip_artists) or '(keine)'}", flush=True)
    except Exception as e:
        print(f"  !! Festival-Fehler: {e}", flush=True)

    # ── Speichern ───────────────────────────────────────────────────
    print("\n[4/4] Speichere concert_data.json …", flush=True)

    # Bestehende setlist_data behalten
    existing_setlist: dict = {}
    data_file = BASE_DIR / "concert_data.json"
    if data_file.exists():
        try:
            existing = json.loads(data_file.read_text(encoding="utf-8"))
            existing_setlist = existing.get("setlist_data", {})
        except Exception:
            pass

    concert_data = {
        "hamburg_artists": filtered_hamburg,
        "rip_artists": rip_artists,
        "setlist_data": existing_setlist,
        "last_updated": today,
    }
    data_file.write_text(json.dumps(concert_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  >> Gespeichert: {len(filtered_hamburg)} Hamburg + {len(rip_artists)} RiP Kuenstler", flush=True)
    print(f"\n✅ Fertig! concert_data.json aktualisiert.", flush=True)


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        print(f"ERROR: {key} nicht gesetzt.", flush=True)
        sys.exit(1)
    return val


if __name__ == "__main__":
    main()
