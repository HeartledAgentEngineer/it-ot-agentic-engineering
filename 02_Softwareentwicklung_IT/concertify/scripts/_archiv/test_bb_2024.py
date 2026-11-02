import os
from setlist_client import SetlistClient
from dotenv import load_dotenv

load_dotenv()
client = SetlistClient(os.getenv("SETLISTFM_API_KEY"))
mbid = client._find_mbid_candidates("Breaking Benjamin")[0]

total = 0
for page in range(1, 15):
    resp = client.session.get(f"https://api.setlist.fm/rest/1.0/artist/{mbid}/setlists", params={"p": page})
    if resp.status_code == 429: break
    data = resp.json().get("setlist", [])
    if not data: break
    for sl in data:
        t = sl.get("tour", {}).get("name", "")
        if "Spring Tour 2024" in t or "Staind" in t or "2024" in t:
            total += 1
print(f"Total 2024 sets: {total}")
