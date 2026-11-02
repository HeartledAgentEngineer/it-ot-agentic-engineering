import os
import time
from setlist_client import SetlistClient
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("SETLISTFM_API_KEY")
client = SetlistClient(api_key)

mbid = client._find_mbid_candidates("Breaking Benjamin")[0]

total_awaken = 0
total_uk = 0
awaken_unstripped = 0

for page in range(1, 15):
    print(f"Fetching page {page}...")
    resp = client.session.get(f"https://api.setlist.fm/rest/1.0/artist/{mbid}/setlists", params={"p": page})
    if resp.status_code == 429:
        print("Rate limit!")
        time.sleep(2)
        resp = client.session.get(f"https://api.setlist.fm/rest/1.0/artist/{mbid}/setlists", params={"p": page})
    data = resp.json().get("setlist", [])
    if not data:
        break
    for sl in data:
        tour = sl.get("tour", {}).get("name", "")
        if tour == "Awaken The Fallen Tour":
            awaken_unstripped += 1
        tour = tour.strip()
        if tour == "Awaken The Fallen Tour":
            total_awaken += 1
        elif tour == "UK/ EU Tour 2026":
            total_uk += 1
    time.sleep(1.0)

print(f"Awaken (stripped): {total_awaken}")
print(f"Awaken (unstripped): {awaken_unstripped}")
print(f"UK/EU: {total_uk}")
