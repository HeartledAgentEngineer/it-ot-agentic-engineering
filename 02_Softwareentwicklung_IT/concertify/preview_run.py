"""
SetlistMixPrepper — Vorschau / Trockenlauf
=====================================
Zeigt welche Künstler und Songs ausgewählt würden,
ohne Spotify oder andere APIs aufzurufen.
Liest alles aus concert_data.json.
"""

import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

# Ensure UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).parent


def _norm(title: str) -> str:
    t = title.lower()
    t = re.sub(r"\(.*?\)", "", t)
    t = re.sub(r"[^\w\s]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def main() -> None:
    load_dotenv()

    data_file = BASE_DIR / "concert_data.json"
    if not data_file.exists():
        print("❌ concert_data.json nicht gefunden — bitte zuerst Daten laden.")
        sys.exit(1)

    concert_data = json.loads(data_file.read_text(encoding="utf-8"))
    hamburg    = concert_data.get("hamburg_artists", {})
    rip        = concert_data.get("rip_artists", {})
    setlist_db = concert_data.get("setlist_data", {})

    # ── Config from env (set by app.py /run) ──────────────────────────────
    playlist_name = os.getenv("PLAYLIST_NAME", "Concert Ready 2026")
    track_limit   = int(os.getenv("TRACK_LIMIT_PER_ARTIST", "10"))
    date_from     = os.getenv("DATE_FILTER_FROM", "").strip()
    date_to       = os.getenv("DATE_FILTER_TO",   "").strip()
    exclude_list  = [a.strip() for a in os.getenv("EXCLUDE_ARTISTS", "").split(",") if a.strip()]

    exclude_songs_raw = os.getenv("EXCLUDE_SONGS", "")
    excl_songs: dict[str, set[str]] = {}
    for item in (exclude_songs_raw.split(",") if exclude_songs_raw else []):
        item = item.strip()
        if "::" in item:
            art, sng = item.split("::", 1)
            excl_songs.setdefault(art.strip(), set()).add(_norm(sng.strip()))

    # ── Header ────────────────────────────────────────────────────────────
    print(f"\n{'='*55}")
    print(f"  🔍 Vorschau — {playlist_name}")
    print(f"{'='*55}")
    print(f"  Songs pro Künstler : {track_limit}")
    if date_from or date_to:
        print(f"  Datum-Filter       : {date_from or '...'} → {date_to or '...'}")
    if exclude_list:
        print(f"  Ausgeschlossen     : {', '.join(exclude_list)}")
    print()

    # ── Build full artist map ─────────────────────────────────────────────
    artists: dict[str, dict] = {}
    for name, info in hamburg.items():
        dates = sorted(info.get("dates", []))
        artists[name] = {"source": "HH", "dates": dates}
    for name in rip:
        if name not in artists:
            artists[name] = {"source": "RiP", "dates": ["2026-06-05"]}

    # ── Apply filters ─────────────────────────────────────────────────────
    included: list[str] = []
    skipped:  list[tuple[str, str]] = []

    for name, info in artists.items():
        if name in exclude_list:
            skipped.append((name, "Ausschlussliste"))
            continue
        if (date_from or date_to) and info["source"] == "HH":
            dates = info["dates"]
            if dates:
                earliest = min(d[:10] for d in dates if d)
                latest   = max(d[:10] for d in dates if d)
                if date_from and latest < date_from:
                    skipped.append((name, f"vor {date_from}"))
                    continue
                if date_to and earliest > date_to:
                    skipped.append((name, f"nach {date_to}"))
                    continue
        included.append(name)

    print(f"[1/3] Künstler: {len(included)} dabei, {len(skipped)} rausgefiltert")
    for name, reason in skipped:
        print(f"  -- {name} ({reason})")

    # ── Song selection ────────────────────────────────────────────────────
    print(f"\n[2/3] Song-Auswahl:")

    total_songs  = 0
    no_setlist   = []

    for name in included:
        safe = name.encode("ascii", "replace").decode("ascii")
        src  = artists[name]["source"]
        dates = artists[name]["dates"]
        date_str = dates[0][:10] if dates else "?"

        sl     = setlist_db.get(name, {})
        songs  = sl.get("setlist_titles", [])
        new_s  = sl.get("new_titles", [])
        ex_set = excl_songs.get(name, set())

        pool: list[tuple[str, str]] = []
        for s in songs:
            if _norm(s) not in ex_set:
                pool.append(("🎵", s))
        for s in new_s:
            if _norm(s) not in ex_set:
                pool.append(("✨", s))

        selected = pool[:track_limit]
        cnt      = len(selected)
        total_songs += cnt

        if not pool and not songs:
            no_setlist.append(name)
            print(f"  [{src}] {safe} ({date_str}) → {cnt} Songs  ⚠ keine Setlist (Album-Tracks beim echten Run)")
        else:
            excl_cnt = len(songs) + len(new_s) - len(pool)
            excl_note = f", {excl_cnt} entfernt" if excl_cnt else ""
            print(f"  [{src}] {safe} ({date_str}) → {cnt} Songs{excl_note}")
            for icon, s in selected[:6]:
                safe_s = s.encode("ascii", "replace").decode("ascii")
                print(f"        {icon} {safe_s}")
            if len(selected) > 6:
                print(f"        … +{len(selected)-6} weitere")

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"\n[3/3] Zusammenfassung:")
    print(f"  Künstler gesamt : {len(included)}")
    print(f"  Songs gesamt    : {total_songs}  (ohne Spotify-Matching, echte Zahl kann abweichen)")
    if no_setlist:
        print(f"  Ohne Setlist    : {len(no_setlist)} → {', '.join(no_setlist[:8])}")

    print(f"\n{'='*55}")
    print(f"✅ Vorschau fertig — {total_songs} Songs für {len(included)} Künstler")
    print(f"{'='*55}")


if __name__ == "__main__":
    main()
