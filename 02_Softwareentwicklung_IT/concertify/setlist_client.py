"""
Setlist.fm client — fetches most-played songs and new unreleased-live tracks.

Free API key: https://www.setlist.fm/api/apikey.xml  (login required, instant)
Add to .env:  SETLISTFM_API_KEY=your-key
"""

import time
from datetime import date, datetime, timedelta

import requests
from matcher import normalise

FESTIVAL_VENUE_KEYWORDS = [
    "festival", "open air", "open-air", "rock im park", "rock am ring",
    "wacken", "hurricane", "southside", "download", "hellfest",
    "lollapalooza", "coachella", "reading", "leeds festival",
    "elbriot", "impericon", "copenhell",
]


_BASE = "https://api.setlist.fm/rest/1.0"
_TODAY = date.today().isoformat()
_NEW_RELEASE_CUTOFF = (date.today() - timedelta(days=365)).isoformat()


class SetlistClient:
    def __init__(self, api_key: str):
        self.session = requests.Session()
        self.session.headers.update({
            "x-api-key": api_key,
            "Accept": "application/json",
        })

    def get_setlist_tracks(
        self,
        artist_name: str,
        setlist_songs: int = 8,
        new_songs: int = 2,
        num_concerts: int = 10,
    ) -> dict:
        """
        Returns {
            "setlist_titles":  [str, ...]  — most played, sorted by frequency
            "new_titles":      [str, ...]  — recent songs never played live yet
        }
        """
        candidates = self._find_mbid_candidates(artist_name)
        if not candidates:
            return {"setlist_titles": [], "new_titles": []}

        # Try each candidate until we get setlist data
        song_counts: dict[str, int] = {}
        concerts_with_songs = 0
        mbid = ""
        for candidate in candidates:
            song_counts, concerts_with_songs = self._count_songs(candidate, num_concerts)
            if song_counts:
                mbid = candidate
                break

        if not mbid:
            return {"setlist_titles": [], "new_titles": []}

        # Top setlist songs sorted by frequency
        top_titles = [
            title for title, _ in
            sorted(song_counts.items(), key=lambda x: x[1], reverse=True)
        ][:setlist_songs]

        # New songs: anything recent that never appeared in setlists
        new_titles = self._get_new_unreleased_live(mbid, song_counts)[:new_songs]

        # Frequencies: nur Konzerte mit Songs als Nenner (leere Setlists ignoriert)
        total = concerts_with_songs if concerts_with_songs > 0 else 1
        frequencies = {title: round(count / total, 2) for title, count in song_counts.items()}

        return {
            "setlist_titles": top_titles,
            "new_titles": new_titles,
            "frequencies": frequencies,
        }

    def get_tour_options(self, artist_name: str, num_setlists: int = 50) -> dict:
        """
        Fetches recent setlists and groups them by tour name.
        Returns {
            "active_tour": {"name": str, "shows": int, "from": str, "to": str} | None,
            "past_tours":  [{"name": str, "shows": int, "from": str, "to": str}, ...],
            "total_shows": int,
        }
        """
        candidates = self._find_mbid_candidates(artist_name)
        if not candidates:
            return {"active_tour": None, "past_tours": [], "total_shows": 0}

        all_setlists: list = []
        mbid = None
        for candidate in candidates:
            try:
                rate_limited_val = ""
                # Fetch up to 3 pages to get enough history
                for page in range(1, 4):
                    resp = self.session.get(
                        f"{_BASE}/artist/{candidate}/setlists",
                        params={"p": page},
                        timeout=10,
                    )
                    if resp.status_code == 429:
                        print("=== SETLIST.FM 429 IN get_tour_options ===")
                        retry_val = resp.headers.get("Retry-After", "")
                        rate_limited_val = retry_val if retry_val else "unknown"
                        break
                    resp.raise_for_status()
                    data = resp.json()
                    page_setlists = data.get("setlist", [])
                    if not page_setlists:
                        break
                    all_setlists.extend(page_setlists)
                    if len(all_setlists) >= num_setlists:
                        break
                    if page < 3:
                        import time
                        time.sleep(1.5)
                
                if rate_limited_val and not all_setlists:
                    return {"active_tour": None, "past_tours": [], "total_shows": 0, "error": "rate_limited"}

                if all_setlists:
                    mbid = candidate
                    break
            except Exception:
                continue

        if not mbid or not all_setlists:
            return {"active_tour": None, "past_tours": [], "total_shows": len(all_setlists)}

        # Group setlists by tour name
        tour_data: dict[str, dict] = {}
        for sl in all_setlists:
            tour_obj = sl.get("tour") or {}
            tour_name = (tour_obj.get("name") or "").strip()
            if not tour_name:
                continue
            date_str = sl.get("eventDate", "")
            try:
                ev_date = datetime.strptime(date_str, "%d-%m-%Y").date()
            except Exception:
                ev_date = None

            if tour_name not in tour_data:
                tour_data[tour_name] = {"shows": 0, "dates": []}
            tour_data[tour_name]["shows"] += 1
            if ev_date:
                tour_data[tour_name]["dates"].append(ev_date)

        # Sort tours by most recent date descending
        def _tour_last(td: dict) -> date:
            return max(td["dates"]) if td["dates"] else date.min

        sorted_tours = sorted(tour_data.items(), key=lambda x: _tour_last(x[1]), reverse=True)

        cutoff = date.today() - timedelta(days=210)
        active_tour = None
        past_tours: list[dict] = []

        for name, td in sorted_tours:
            dates = td["dates"]
            last = max(dates) if dates else None
            first = min(dates) if dates else None
            entry = {
                "name": name,
                "shows": td["shows"],
                "from": first.isoformat() if first else "",
                "to": last.isoformat() if last else "",
            }
            if active_tour is None and last and last >= cutoff:
                active_tour = entry
            elif len(past_tours) < 3:
                past_tours.append(entry)

        return {
            "active_tour": active_tour,
            "past_tours":  past_tours,
            "total_shows": len(all_setlists),
        }

    def get_setlist_ordered(
        self,
        artist_name: str,
        mode: str = "concert",
        num_concerts: int = 20,
        tour_name: str = "",
        freq_threshold: float = 0.0,
    ) -> dict:
        """
        Returns songs sorted by their average position in setlists.
        mode: "concert" | "festival" | "support" | "support_full"
        tour_name: filter to specific tour; "__best_of__" = all tours, freq_threshold applied
        freq_threshold: minimum frequency to include a song (0.0 = no filter)

        Returns {
            "ordered":           [(song, avg_pos, is_encore, freq), ...],
            "positions":         {song: avg_pos},
            "is_encore":         {song: bool},
            "tour_active":       bool,
            "mode_used":         str,
            "concerts_analyzed": int,
        }
        """
        candidates = self._find_mbid_candidates(artist_name)
        if not candidates:
            return self._empty_ordered(mode)

        # Best-of braucht viele Seiten für echte Karriere-Übersicht; Tour-Filter 4 Seiten, Standard 3
        max_pages = 5 if tour_name == "__best_of__" else (4 if tour_name else 3)

        mbid = None
        raw_setlists: list = []
        for candidate in candidates:
            try:
                candidate_setlists: list = []
                rate_limited_val = ""
                for page in range(1, max_pages + 1):
                    resp = self.session.get(
                        f"{_BASE}/artist/{candidate}/setlists",
                        params={"p": page},
                        timeout=10,
                    )
                    if resp.status_code == 429:
                        print("=== SETLIST.FM 429 DIAGNOSTICS ===")
                        print(f"Status: {resp.status_code}")
                        print(f"Headers: {resp.headers}")
                        print(f"Body: {resp.text}")
                        print("==================================")
                        retry_val = resp.headers.get("Retry-After", "")
                        rate_limited_val = retry_val if retry_val else "unknown"
                        break
                    resp.raise_for_status()
                    page_data = resp.json().get("setlist", [])
                    candidate_setlists.extend(page_data)
                    if not page_data:
                        break
                    if page < max_pages:
                        time.sleep(1.5)  # konservativ (war 0.4) — vermeidet Burst-Limit
                if rate_limited_val:
                    raise RuntimeError(f"rate_limited:{rate_limited_val}")
                if candidate_setlists:
                    mbid = candidate
                    raw_setlists = candidate_setlists
                    break
            except RuntimeError:
                raise  # weiterwerfen damit app.py es fangen kann
            except Exception:
                continue

        if not mbid or not raw_setlists:
            return self._empty_ordered(mode)

        # ── Tour-Erkennung ───────────────────────────────────────────────
        tour_active = False
        try:
            date_str = raw_setlists[0].get("eventDate", "")  # "DD-MM-YYYY"
            if date_str:
                last_gig = datetime.strptime(date_str, "%d-%m-%Y").date()
                tour_active = (date.today() - last_gig).days < 210
        except Exception:
            pass

        # ── Support-Standard: nur Top-8 nach Häufigkeit, keine Positions-Analyse ──
        if mode == "support":
            song_counts, concerts_with = self._count_songs(mbid, num_concerts)
            total = max(concerts_with, 1)
            freqs = {t: round(c / total, 2) for t, c in song_counts.items()}
            top8 = sorted(song_counts, key=lambda x: song_counts[x], reverse=True)[:8]
            return {
                "ordered":           [(s, float(i), False, freqs.get(s, 0)) for i, s in enumerate(top8)],
                "positions":         {s: float(i) for i, s in enumerate(top8)},
                "is_encore":         {s: False for s in top8},
                "tour_active":       tour_active,
                "mode_used":         mode,
                "concerts_analyzed": concerts_with,
            }

        # ── Setlist-Filterung je nach Mode ──────────────────────────────
        ENCORE_OFFSET = 1000.0
        cutoff = date.today() - timedelta(days=210)

        def _parse_event_date(sl: dict) -> date | None:
            try:
                return datetime.strptime(sl.get("eventDate", ""), "%d-%m-%Y").date()
            except Exception:
                return None

        def _is_festival_setlist(sl: dict) -> bool:
            venue_name = (sl.get("venue", {}).get("name", "") or "").lower()
            if any(kw in venue_name for kw in FESTIVAL_VENUE_KEYWORDS):
                return True
            all_songs = [
                song
                for s in sl.get("sets", {}).get("set", [])
                for song in s.get("song", [])
            ]
            return len(all_songs) <= 12

        filtered: list = []

        target_tours = []
        if tour_name and tour_name not in ("__best_of__", "__festival__", "__concert__"):
            target_tours = [t.strip() for t in tour_name.split("|") if t.strip()]

        if target_tours:
            for sl in raw_setlists:
                sl_tour = (sl.get("tour") or {}).get("name", "")
                if sl_tour in target_tours:
                    filtered.append(sl)
                if len(filtered) >= num_concerts:
                    break
        else:
            for sl in raw_setlists:
                ev_date = _parse_event_date(sl)
                if mode == "festival":
                    if _is_festival_setlist(sl):
                        filtered.append(sl)
                else:  # concert or support_full or best_of
                    if tour_active and ev_date and not tour_name:
                        if ev_date >= cutoff:
                            filtered.append(sl)
                    else:
                        filtered.append(sl)
                if len(filtered) >= num_concerts:
                    break

        if not filtered:
            filtered = raw_setlists[:num_concerts]

        # ── Positions über alle gefilterten Setlists aggregieren ─────────
        # Main-Set und Encore getrennt tracken, damit kein Misch-Durchschnitt entsteht
        song_main_pos: dict[str, list[float]] = {}
        song_enc_pos:  dict[str, list[float]] = {}
        song_appearances: dict[str, int] = {}
        positions_hist: dict[str, dict[str, int]] = {}
        concerts_analyzed = 0

        for sl in filtered:
            sets = sl.get("sets", {}).get("set", [])
            if not sets:
                continue
            had = False
            for song_set in sets:
                is_enc = bool(song_set.get("encore", 0))
                for idx, song in enumerate(song_set.get("song", [])):
                    name = song.get("name", "").strip()
                    if not name or song.get("cover"):
                        continue
                    if is_enc:
                        song_enc_pos.setdefault(name, []).append(float(idx))
                    else:
                        song_main_pos.setdefault(name, []).append(float(idx))
                    song_appearances[name] = song_appearances.get(name, 0) + 1
                    
                    pos_str = str(idx + 1)
                    if name not in positions_hist:
                        positions_hist[name] = {}
                    positions_hist[name][pos_str] = positions_hist[name].get(pos_str, 0) + 1
                    
                    had = True
            if had:
                concerts_analyzed += 1

        if not concerts_analyzed:
            return self._empty_ordered(mode, tour_active)

        all_songs = set(list(song_main_pos.keys()) + list(song_enc_pos.keys()))
        avg_pos: dict[str, float] = {}
        is_encore_map: dict[str, bool] = {}

        for song in all_songs:
            main_count = len(song_main_pos.get(song, []))
            enc_count  = len(song_enc_pos.get(song, []))
            is_enc = enc_count > main_count  # Mehrheit entscheidet
            is_encore_map[song] = is_enc
            if is_enc:
                # Nur Encore-Positionen (0-basiert innerhalb des Encores)
                positions = song_enc_pos.get(song, []) or song_main_pos.get(song, [])
                avg_pos[song] = ENCORE_OFFSET + (sum(positions) / len(positions))
            else:
                # Nur Main-Set-Positionen
                positions = song_main_pos.get(song, []) or song_enc_pos.get(song, [])
                avg_pos[song] = sum(positions) / len(positions)

        freqs = {
            s: round(song_appearances[s] / concerts_analyzed, 2)
            for s in all_songs
        }
        ordered = sorted(
            [(s, avg_pos[s], is_encore_map[s], freqs[s]) for s in all_songs],
            key=lambda x: x[1],
        )

        # Apply freq_threshold (used for Best-of: only songs played ≥25% of shows)
        if freq_threshold > 0.0:
            ordered = [(s, p, e, f) for s, p, e, f in ordered if f >= freq_threshold]

        return {
            "ordered":           ordered,
            "positions":         {s: round(avg_pos[s], 1) for s in avg_pos},
            "is_encore":         is_encore_map,
            "tour_active":       tour_active,
            "mode_used":         mode,
            "concerts_analyzed": concerts_analyzed,
            "play_counts":       song_appearances,
            "positions_hist":    positions_hist,
        }

    @staticmethod
    def _empty_ordered(mode: str = "concert", tour_active: bool = False) -> dict:
        return {
            "ordered": [], "positions": {}, "is_encore": {},
            "tour_active": tour_active, "mode_used": mode, "concerts_analyzed": 0,
            "play_counts": {}, "positions_hist": {},
        }

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _find_mbid_candidates(self, artist_name: str) -> list[str]:
        """Search setlist.fm, return list of candidate MBIDs (best matches first)."""
        try:
            resp = self.session.get(
                f"{_BASE}/search/artists",
                params={"artistName": artist_name, "p": 1},
                timeout=10,
            )
            if resp.status_code == 429:
                print("=== SETLIST.FM 429 DIAGNOSTICS ===")
                print(f"Status: {resp.status_code}")
                print(f"Headers: {resp.headers}")
                print(f"Body: {resp.text}")
                print("==================================")
                retry_val = resp.headers.get("Retry-After", "")
                raise RuntimeError(f"rate_limited:{retry_val if retry_val else 'unknown'}")
            resp.raise_for_status()
            artists = resp.json().get("artist", [])
        except RuntimeError:
            raise
        except Exception:
            return []

        norm_query = normalise(artist_name)
        preferred: list[str] = []
        fallback: list[str] = []

        for a in artists:
            mbid = a.get("mbid", "")
            if not mbid:
                continue
            name = a.get("name", "")
            dis = a.get("disambiguation", "").lower()
            if normalise(name) == norm_query:
                # Prefer real artist over tribute/cover/feat entries
                if not any(w in dis for w in ("tribute", "cover", "feat")):
                    preferred.append(mbid)
                else:
                    fallback.append(mbid)

        return preferred + fallback

    def _count_songs(self, mbid: str, num_concerts: int) -> tuple[dict[str, int], int]:
        """Fetch last num_concerts setlists, count song occurrences.
        Returns (song_counts, concerts_with_songs) — empty setlists are ignored."""
        song_counts: dict[str, int] = {}
        concerts_with_songs = 0
        try:
            resp = self.session.get(
                f"{_BASE}/artist/{mbid}/setlists",
                params={"p": 1},
                timeout=10,
            )
            resp.raise_for_status()
            setlists = resp.json().get("setlist", [])
        except Exception:
            return {}, 0

        for setlist in setlists[:num_concerts]:
            setlist_had_song = False
            for song_set in setlist.get("sets", {}).get("set", []):
                for song in song_set.get("song", []):
                    name = song.get("name", "").strip()
                    if name and not song.get("cover"):  # skip covers
                        song_counts[name] = song_counts.get(name, 0) + 1
                        setlist_had_song = True
            if setlist_had_song:
                concerts_with_songs += 1

        return song_counts, concerts_with_songs

    def _get_new_unreleased_live(
        self, mbid: str, existing_counts: dict[str, int]
    ) -> list[str]:
        """
        Get recent setlists and find song names from the last year
        that have never appeared in older setlists.
        Strategy: titles mentioned in the MOST RECENT 2 concerts
        but absent from the previous 8 → probably new/unreleased live.
        """
        try:
            resp = self.session.get(
                f"{_BASE}/artist/{mbid}/setlists",
                params={"p": 1},
                timeout=10,
            )
            resp.raise_for_status()
            setlists = resp.json().get("setlist", [])
        except Exception:
            return []

        if len(setlists) < 3:
            return []

        # Songs in the 2 most recent concerts
        recent_songs: set[str] = set()
        for setlist in setlists[:2]:
            for s in setlist.get("sets", {}).get("set", []):
                for song in s.get("song", []):
                    name = song.get("name", "").strip()
                    if name and not song.get("cover"):
                        recent_songs.add(name)

        # Songs in older concerts (3-10)
        older_songs: set[str] = set()
        for setlist in setlists[2:10]:
            for s in setlist.get("sets", {}).get("set", []):
                for song in s.get("song", []):
                    name = song.get("name", "").strip()
                    if name:
                        older_songs.add(name)

        # New = in recent but not in older catalog
        new_songs = [s for s in recent_songs if s not in older_songs]
        return sorted(new_songs)
