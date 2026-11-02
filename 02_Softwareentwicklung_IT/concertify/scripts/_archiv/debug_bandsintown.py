"""Quick debug: check what Bandsintown returns for a known artist."""
import requests, json

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def check(artist):
    url = f"https://rest.bandsintown.com/artists/{requests.utils.quote(artist)}/events"
    resp = SESSION.get(url, params={"app_id": "concert_playlist_generator", "date": "upcoming"}, timeout=10)
    print(f"\n--- {artist} ---")
    print(f"Status: {resp.status_code}")
    try:
        data = resp.json()
        if isinstance(data, list):
            print(f"Events: {len(data)}")
            for e in data[:3]:
                v = e.get("venue", {})
                print(f"  {e.get('datetime','')[:10]}  {v.get('city','')} {v.get('country','')}  lat={v.get('latitude')} lon={v.get('longitude')}")
        else:
            print(f"Response: {data}")
    except Exception as ex:
        print(f"Parse error: {ex}")
        print(resp.text[:200])

check("Rammstein")
check("Die Toten Hosen")
check("Broilers")
