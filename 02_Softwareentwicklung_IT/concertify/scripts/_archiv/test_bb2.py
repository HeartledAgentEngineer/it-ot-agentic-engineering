import os
import time
from setlist_client import SetlistClient
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("SETLISTFM_API_KEY")
client = SetlistClient(api_key)

mbids = client._find_mbid_candidates("Breaking Benjamin")
mbid = mbids[0]

tours = {}
for page in range(1, 6):
    print(f"Fetching page {page}...")
    resp = client.session.get(f"https://api.setlist.fm/rest/1.0/artist/{mbid}/setlists", params={"p": page})
    if resp.status_code == 429:
        print("Rate limit!")
        break
    data = resp.json().get("setlist", [])
    for sl in data:
        tour = sl.get("tour", {}).get("name")
        if tour:
            tours[tour] = tours.get(tour, 0) + 1
    time.sleep(1.5)

print("Tours found:")
for t, c in tours.items():
    print(f"{t}: {c} shows")
