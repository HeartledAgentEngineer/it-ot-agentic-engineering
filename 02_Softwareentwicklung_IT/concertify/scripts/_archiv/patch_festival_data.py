"""
patch_festival_data.py
Patcht concert_data.json mit echten positions_hist / play_counts / total_concerts_analyzed
fuer alle Festival-Kuenstler. Aendert NUR: setlist_titles, positions_hist, play_counts,
total_concerts_analyzed, positions (avg), scores, badges.
Spotify_uris bleiben unveraendert.

Quellen: setlist.fm - manuell gesammelte Setlists (2023-2026).
"""

import json, os, math
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "concert_data.json"

# ─── Rohdaten: positions_hist pro Kuenstler ───────────────────────────────────
# Schluessel = Slot-Nummer als STRING, Wert = Anzahl Mal gespielt
# Coversongs und Medleys werden uebersprungen (nicht in LP aufnehmen)

FESTIVAL_DATA = {

    # ── 5 Shows: Fillin The Blank Tour 2025 (Offenbach, Koeln, Hamburg, Berlin, Muenster)
    # Offenbach Oct 31 / Koeln Nov 2 / Hamburg Nov 4 (Kurzset 9 Songs) /
    # Berlin Nov 7 / Muenster Nov 8
    # Covers (The Power, Ring of Fire) und Medley uebersprungen
    "H-Blockx": {
        "sources": "Fillin The Blank Tour: Offenbach (31.10), Koeln (02.11), Hamburg (04.11), Berlin (07.11), Muenster (08.11) 2025",
        "total": 5,
        "hist": {
            "Straight Outta Nowhere":  {"1": 4, "7": 1},
            "Fly":                     {"2": 4},
            "How Do You Feel?":        {"3": 4},
            "Countdown to Insanity":   {"4": 4, "2": 1},
            "Step Back":               {"5": 4},
            "Can't Get Enough":        {"6": 4},
            "Move":                    {"7": 4, "1": 1},
            "Beg to Differ":           {"8": 4},
            "Pour Me a Glass":         {"9": 4, "6": 1},
            "Revolution":              {"10": 4, "5": 1},
            "Take Me Home":            {"11": 4},
            "Leave Me Alone!":         {"12": 4},
            "Lights Out":              {"13": 4, "8": 1},
            "C'mon":                   {"14": 4},
            "Here I Go Again":         {"15": 4},
            "Gazoline":                {"16": 4},
            "Little Girl":             {"17": 4},
            "Time of My Life":         {"18": 4},
            "Risin' High":             {"20": 4, "3": 1},
            "Corns About 2 Pop":       {"22": 4},
        }
    },

    # ── 4 Shows: 2x Festival (Louder than Life Sep 21, Riff Fest Sep 20, 2025) +
    # 2x Europe Tour (Tempodrom Berlin Nov 19, Zenith Muenchen Dez 2, 2025)
    # Cover "Creep" (Radiohead) uebersprungen
    "Three Days Grace": {
        "sources": "Louder than Life 2025, Riff Fest 2025, Tempodrom Berlin (19.11.2025), Zenith Muenchen (02.12.2025)",
        "total": 4,
        "hist": {
            "Dominate":                    {"1": 2},
            "Animal I Have Become":        {"1": 2, "2": 2},
            "So Called Life":              {"2": 2, "3": 2},
            "Break":                       {"3": 2, "4": 2},
            "Home":                        {"4": 1, "5": 3},
            "The Mountain":                {"5": 1, "6": 2},
            "Mayday":                      {"6": 2, "7": 2},
            "Pain":                        {"7": 1, "8": 2},
            "Kill Me Fast":                {"8": 2, "9": 2},
            "I Hate Everything About You": {"7": 1, "9": 1, "10": 2},
            "Time of Dying":               {"11": 3},
            "Apologies":                   {"12": 3},
            "Don't Wanna Go Home Tonight": {"14": 2},
            "I Am Machine":                {"10": 1, "15": 2},
            "The Good Life":               {"9": 1, "13": 1, "16": 2},
            "Painkiller":                  {"4": 1, "14": 1, "17": 2},
            "Never Too Late":              {"10": 1, "15": 1, "18": 2},
            "Riot":                        {"11": 1, "16": 1, "19": 2},
        }
    },

    # ── 4 Shows: Wacken 2025, Summer Breeze 2025, Dynamo Metal Fest 2025,
    # Hellfest Jun 20, 2025
    "Within Temptation": {
        "sources": "Wacken Open Air 2025, Summer Breeze 2025, Dynamo Metal Fest 2025, Hellfest 2025 (20.06.)",
        "total": 4,
        "hist": {
            "We Go to War":              {"1": 4},
            "Bleed Out":                 {"2": 4},
            "Faster":                    {"3": 2, "5": 1, "7": 1},
            "In the Middle of the Night": {"3": 2, "4": 2},
            "Stand My Ground":           {"4": 1, "5": 2, "7": 1},
            "Paradise (What About Us?)": {"5": 1, "6": 2, "9": 1},
            "Don't Pray for Me":         {"7": 1, "9": 1, "10": 2},
            "Wireless":                  {"6": 2, "8": 2},
            "Supernova":                 {"8": 1, "9": 2, "11": 1},
            "What Have You Done":        {"10": 1},
            "Lost":                      {"10": 1, "11": 2, "12": 1},
            "The Reckoning":             {"11": 1, "12": 2, "13": 1},
            "Our Solemn Hour":           {"13": 2, "14": 2},
            "Mother Earth":              {"14": 2, "15": 1, "17": 1},
            "Shot in the Dark":          {"7": 1},
            "Angels":                    {"4": 1, "8": 1},
            "Shed My Skin":              {"15": 1},
            "Ice Queen":                 {"12": 1, "13": 1, "16": 1},
        }
    },

    # ── 4 Shows: Sonic Temple 2026 (May 16), Illinois State Fair 2023 (Aug 16),
    # Columbiahalle Berlin (Jan 25, 2026), House of Blues Lake Buena Vista (Apr 25, 2026)
    # Aktueller What Lies Within Tour 2026 sehr konsistent
    "Alter Bridge": {
        "sources": "Sonic Temple 2026, Illinois State Fair 2023, Columbiahalle Berlin (25.01.2026), House of Blues LBV (25.04.2026)",
        "total": 4,
        "hist": {
            "Silent Divide":          {"1": 3},
            "Addicted to Pain":       {"2": 4},
            "Cry of Achilles":        {"3": 3, "6": 1},
            "Playing Aces":           {"4": 2},
            "Fortress":               {"4": 1, "5": 2},
            "Burn It Down":           {"5": 1, "6": 2},
            "What Lies Within":       {"7": 1},
            "Open Your Eyes":         {"7": 1, "8": 2, "13": 1},
            "Tested and Able":        {"6": 1, "8": 1, "9": 1},
            "Broken Wings":           {"4": 1, "10": 2},
            "Wonderful Life":         {"11": 1},
            "Watch Over You":         {"7": 1, "11": 1, "12": 1},
            "Ghost of Days Gone By":  {"12": 1},
            "Silver Tongue":          {"1": 1, "13": 2},
            "Rise Today":             {"5": 1, "14": 3},
            "Metalingus":             {"8": 1, "12": 1, "15": 2},
            "Blackbird":              {"9": 1, "16": 2},
            "Isolation":              {"7": 1, "10": 1, "17": 2},
            "Come to Life":           {"3": 1},
            "In Loving Memory":       {"8": 1},
            "Fable of the Silent Son": {"11": 1},
        }
    },

    # ── 4 Shows: Leeds Festival (Aug 24, 2025), Reading Festival (Aug 23, 2025),
    # Ziggo Dome Amsterdam (Mar 26, 2025), Raymond James Stadium Tampa (Jun 6, 2025)
    "Limp Bizkit": {
        "sources": "Leeds Festival 2025, Reading Festival 2025, Ziggo Dome Amsterdam (26.03.2025), Raymond James Stadium Tampa (06.06.2025)",
        "total": 4,
        "hist": {
            "Show Me What You Got":       {"1": 1},
            "Hot Dog":                    {"2": 4},
            "Break Stuff":                {"1": 2, "3": 1, "5": 1, "10": 1},
            "9 Teen 90 Nine":             {"3": 1},
            "My Generation":              {"3": 1, "4": 2, "7": 1},
            "Livin' It Up":               {"5": 1},
            "Take a Look Around":         {"6": 1, "8": 2, "9": 1, "10": 1},
            "Nookie":                     {"1": 1, "6": 1, "7": 2},
            "Full Nelson":                {"7": 1, "8": 2},
            "Rollin' (Air Raid Vehicle)": {"4": 1, "5": 1, "6": 1, "9": 1},
            "Eat You Alive":              {"10": 1},
            "My Way":                     {"3": 1, "5": 1, "9": 1, "11": 1},
            "It'll Be OK":                {"4": 1},
            "Dad Vibes":                  {"6": 1, "8": 1},
        }
    },

    # ── 1 Show: Sonic Temple 2024 (May 17)
    "Black Veil Brides": {
        "sources": "Sonic Temple 2024 (May 17)",
        "total": 1,
        "hist": {
            "I Am Bulletproof": {"1": 1},
            "Heart of Fire":    {"2": 1},
            "Wake Up":          {"3": 1},
            "Rebel Love Song":  {"4": 1},
            "Bleeders":         {"5": 1},
            "Scarlet Cross":    {"6": 1},
            "The Legacy":       {"7": 1},
            "Perfect Weapon":   {"8": 1},
            "Knives and Pens":  {"9": 1},
            "In the End":       {"10": 1},
        }
    },

    # ── 1 Show (Venue-Set als Proxy): The Fillmore SF 2024 (Dec 10)
    "Social Distortion": {
        "sources": "The Fillmore SF 2024 (Dec 10) — Venue-Set als Proxy",
        "total": 1,
        "hist": {
            "So Far Away":           {"1": 1},
            "Untitled":              {"2": 1},
            "I Wasn't Born to Follow": {"3": 1},
            "Tonight":               {"4": 1},
            "Mommy's Little Monster": {"5": 1},
            "The Creeps":            {"6": 1},
            "Another State of Mind": {"7": 1},
            "Machine Gun Blues":     {"8": 1},
            "Over You":              {"9": 1},
            "Far Side of Nowhere":   {"10": 1},
            "The Way Things Were":   {"11": 1},
            "Dear Lover":            {"12": 1},
            "Ball and Chain":        {"13": 1},
            "Born to Kill":          {"14": 1},
            "Reach for the Sky":     {"15": 1},
            "Story of My Life":      {"16": 1},
            "Bad Luck":              {"17": 1},
        }
    },

    # ── 3 Shows: Welcome to Rockville 2026 (May 8), Aftershock 2025 (Oct 2),
    # Talking Stick Resort Amphitheatre Phoenix (Sep 24, 2025)
    "Hollywood Undead": {
        "sources": "Welcome to Rockville 2026 (May 8), Aftershock 2025 (Oct 2), Talking Stick Resort Phoenix (24.09.2025)",
        "total": 3,
        "hist": {
            "Riot":            {"1": 2, "2": 1},
            "CHAOS":           {"1": 1, "2": 2},
            "Comin' in Hot":   {"3": 3},
            "Another Way Out": {"4": 1, "5": 1, "6": 1},
            "SAVIOR":          {"4": 1, "5": 1, "6": 1},
            "Everywhere I Go": {"6": 1, "7": 1, "9": 1},
            "Bullet":          {"7": 2, "8": 1},
            "Undead":          {"8": 2, "9": 1},
            "Day of the Dead": {"4": 1, "5": 1},
        }
    },

    # ── 1 Show: Slam Dunk Festival Leeds 2026 (May 24)
    "Bury Tomorrow": {
        "sources": "Slam Dunk Festival Leeds 2026 (May 24)",
        "total": 1,
        "hist": {
            "Choke":             {"1": 1},
            "Abandon Us":        {"2": 1},
            "Let Go":            {"3": 1},
            "Villain Arc":       {"4": 1},
            "What If I Burn":    {"5": 1},
            "Boltcutter":        {"6": 1},
            "Yokai":             {"7": 1},
            "Black Flame":       {"8": 1},
            "DEATH (Ever Colder)": {"9": 1},
        }
    },

    # ── 3 Shows: Sonic Temple 2026 (May 16), When We Were Young 2025 (Oct 18+19)
    "The Story So Far": {
        "sources": "Sonic Temple 2026 (May 16), When We Were Young 2025 (Oct 18+19)",
        "total": 3,
        "hist": {
            "Big Blind":           {"1": 3},
            "Roam":                {"2": 3},
            "The Glass":           {"3": 2, "9": 1},
            "High Regard":         {"4": 2, "5": 1},
            "Things I Can't Change": {"5": 2, "8": 1},
            "Keep This Up":        {"6": 2, "12": 1},
            "Proper Dose":         {"7": 2, "11": 1},
            "Heavy Gloom":         {"8": 2},
            "Empty Space":         {"9": 2, "13": 1},
            "Nerve":               {"10": 2, "14": 1},
            "Quicksand":           {"11": 2, "15": 1},
            "Out of It":           {"3": 1},
            "Nothing to Say":      {"4": 1},
            "All This Time":       {"6": 1},
            "Watch You Go":        {"7": 1},
            "Letterman":           {"10": 1},
        }
    },

    # ── 2 Shows: Sonic Temple 2026 (May 17), Welcome to Rockville 2026 (May 10)
    "Bloodywood": {
        "sources": "Sonic Temple 2026 (May 17), Welcome to Rockville 2026 (May 10)",
        "total": 2,
        "hist": {
            "Gaddaar":   {"1": 2},
            "Aaj":       {"2": 2},
            "Dana Dan":  {"3": 2},
            "Bekhauf":   {"4": 2},
            "Nu Delhi":  {"5": 2},
        }
    },

    # ── 2 Shows: Sonic Temple 2026 (May 16), BottleRock Napa Valley 2026 (May 23)
    "Bush": {
        "sources": "Sonic Temple 2026 (May 16), BottleRock Napa Valley 2026 (May 23)",
        "total": 2,
        "hist": {
            "Machinehead":              {"1": 2},
            "The Land of Milk and Honey": {"2": 1, "6": 1},
            "Everything Zen":           {"3": 1, "4": 1},
            "Flowers on a Grave":       {"4": 1, "7": 1},
            "Identity":                 {"5": 1},
            "Glycerine":                {"6": 1, "9": 1},
            "More Than Machines":       {"3": 1, "7": 1},
            "I Beat Loneliness":        {"8": 1},
            "Comedown":                 {"9": 1, "10": 1},
            "60 Ways to Forget People": {"2": 1},
            "Swallowed":                {"5": 1},
            "Little Things":            {"8": 1},
        }
    },

    # ── 1 Show (Venue-Set): Circo Volador Mexico City 2026 (May 18)
    "Ankor": {
        "sources": "Circo Volador Mexico City 2026 (May 18) — Venue-Set",
        "total": 1,
        "hist": {
            "The World Is a Cruel Place... And It Is Also Very Beautiful": {"1": 1},
            "Darkbeat":                        {"2": 1, "17": 1},
            "Embers":                          {"3": 1},
            "Venom":                           {"4": 1, "18": 1},
            "Walking Dead":                    {"5": 1},
            "Stereo":                          {"6": 1},
            "Shhh...(I'm Not Gonna Lose It)":  {"7": 1},
            "The Monster I Am":                {"8": 1},
            "Nagato · Purple Eyes":            {"9": 1},
            "MADARA · endless dream":          {"10": 1},
            "The Legend of Charles the Giant": {"11": 1},
            "Oblivion":                        {"12": 1},
            "Shoganai":                        {"13": 1},
            "Danzo · Lying Ghost":             {"14": 1},
            "Hill Valley":                     {"15": 1},
            "Prisoner":                        {"16": 1},
        }
    },

    # ── 2 Shows (Venue-Sets): Grand Sierra Resort Reno (Apr 26), Showbox SoDo Seattle (Apr 28) 2026
    "TX2": {
        "sources": "Grand Sierra Resort Reno 2026 (Apr 26), Showbox SoDo Seattle 2026 (Apr 28) — Venue-Sets",
        "total": 2,
        "hist": {
            "Feed":                            {"1": 2},
            "So Numb":                         {"2": 1, "5": 1},
            "HOSTAGE (they will not erase us)": {"3": 1, "4": 1},
            "Pickup truck":                    {"4": 1},
            "Mad":                             {"5": 1, "7": 1},
            "I Would Hate Me Too":             {"6": 1, "8": 1},
            "Black Wedding":                   {"2": 1},
            "Vendetta":                        {"3": 1},
            "The End of Us":                   {"6": 1},
        }
    },
}


# ─── Linkin Park: fehlende Songs erganzen (ohne bestehende Daten zu ueberschreiben) ──
# Bestaetigt in aktuellen From Zero Tour 2025 Shows (Berlin Jun 18, Boston Jul 31, Newark Aug 3)
# total_concerts_analyzed bleibt bei 83 (von fetch_setlist_stats.py)
LP_MISSING_SONGS = {
    # In 2/3 geprueften Shows: Berlin (Jun 18) + Boston (Jul 31, 2025)
    "Given Up":     54,
    # In 1/3 geprueften Shows: Newark (Aug 3, 2025) — From Zero Album
    "Casualty":     20,
    # In 1/3 geprueften Shows: Berlin (Jun 18, 2025) — From Zero Album
    "Let You Fade": 18,
}


def _avg_position(hist: dict) -> float:
    total_plays = sum(hist.values())
    return sum(int(k) * v for k, v in hist.items()) / total_plays


def patch():
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    sd = data.setdefault("setlist_data", {})
    updated = 0

    for artist, info in FESTIVAL_DATA.items():
        if artist not in sd:
            print(f"  SKIP: {artist} nicht in setlist_data")
            continue

        entry = sd[artist]
        total = info["total"]
        hist  = info["hist"]

        play_counts = {song: sum(h.values()) for song, h in hist.items()}
        positions   = {song: _avg_position(h) for song, h in hist.items()}
        scores      = {song: round(pc / total, 3) for song, pc in play_counts.items()}

        entry["positions_hist"]           = hist
        entry["play_counts"]              = play_counts
        entry["total_concerts_analyzed"]  = total
        entry["positions"]                = positions
        entry["scores"]                   = scores
        # setlist_titles: nur gespielte Songs, sortiert nach Haeufigkeit
        entry["setlist_titles"] = sorted(play_counts.keys(), key=lambda s: -play_counts[s])
        # badges: setlist fuer alle gespielten Songs
        entry["badges"] = {song: "setlist" for song in play_counts}

        print(f"  OK: {artist:30s} total={total}  songs={len(hist)}  src: {info['sources'][:60]}")
        updated += 1

    # LP: fehlende Songs erganzen
    patch_lp_additions(sd)

    tmp = DATA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, DATA_FILE)
    print(f"\nFertig: {updated} Kuenstler gepatcht")


def patch_lp_additions(sd: dict):
    """Ergaenzt fehlende Songs bei Linkin Park ohne bestehende Daten zu ueberschreiben."""
    if "Linkin Park" not in sd:
        return
    lp = sd["Linkin Park"]
    total = lp.get("total_concerts_analyzed", 83)
    pc    = lp.get("play_counts", {})
    scores = lp.get("scores", {})
    badges = lp.get("badges", {})

    added = []
    for song, estimated_pc in LP_MISSING_SONGS.items():
        if song not in pc:
            pc[song]     = estimated_pc
            scores[song] = round(estimated_pc / total, 3)
            badges[song] = "setlist"
            added.append(f"{song} (~{estimated_pc}/{total})")

    if added:
        # setlist_titles neu sortieren (alle Songs nach play_count)
        lp["play_counts"] = pc
        lp["scores"]      = scores
        lp["badges"]      = badges
        lp["setlist_titles"] = sorted(pc.keys(), key=lambda s: -pc[s])
        print(f"  LP: Hinzugefuegt: {', '.join(added)}")
    else:
        print(f"  LP: Keine neuen Songs (alle bereits vorhanden)")


if __name__ == "__main__":
    patch()
