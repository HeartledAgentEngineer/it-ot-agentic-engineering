import os
import json
from setlist_client import SetlistClient
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("SETLISTFM_API_KEY")
client = SetlistClient(api_key)

mbid = client._find_mbid_candidates("Breaking Benjamin")[0]

resp = client.session.get(f"https://api.setlist.fm/rest/1.0/artist/{mbid}/setlists", params={"p": 1})
data = resp.json().get("setlist", [])

for sl in data:
    tour = sl.get("tour", {}).get("name", "")
    if tour == "UK/ EU Tour 2026":
        all_songs = [song.get("name") for s in sl.get("sets", {}).get("set", []) for song in s.get("song", [])]
        print(f"Date: {sl.get('eventDate')}, Songs: {len(all_songs)}")
