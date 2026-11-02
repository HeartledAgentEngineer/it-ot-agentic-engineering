import os
from setlist_client import SetlistClient
from dotenv import dotenv_values

env = dotenv_values('.env')
client = SetlistClient(api_key=env.get("SETLISTFM_API_KEY", ""))

candidates = client._find_mbid_candidates("Breaking Benjamin")
if not candidates:
    print("No MBID found")
    exit()

mbid = candidates[0]
found = False
for p in range(1, 4):
    try:
        data = client._fetch_setlists(mbid, p)
        setlists = data.get("setlist", [])
        for sl in setlists:
            city = sl.get("venue", {}).get("city", {}).get("name", "")
            if "Leipzig" in city:
                found = True
                print(f"--- Leipzig Setlist (Date: {sl.get('eventDate')}, Tour: {sl.get('tour',{}).get('name')}) ---")
                for st in sl.get("sets", {}).get("set", []):
                    for song in st.get("song", []):
                        name = song.get("name")
                        if name:
                            print(name)
        if found:
            break
    except Exception as e:
        print("Error fetching page", p, e)
