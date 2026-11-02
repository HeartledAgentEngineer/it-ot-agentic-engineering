"""
Debug-Script: Testet verschiedene Eventim URLs.
Ausfuehren mit: python debug_eventim.py
"""
import json
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9",
}

URLS_TO_TRY = [
    "https://www.eventim.de/city/hamburg-11/music-1/",
    "https://www.eventim.de/city/hamburg-11/",
    "https://www.eventim.de/konzerte/hamburg/",
    "https://www.eventim.de/search/?location=Hamburg&category=Konzerte",
]

session = requests.Session()
session.headers.update(HEADERS)

for URL in URLS_TO_TRY:
    print(f"\nTrying: {URL}")
    try:
        resp = session.get(URL, timeout=15, allow_redirects=True)
        print(f"  Status: {resp.status_code}  |  Final URL: {resp.url}")
        print(f"  Size: {len(resp.text)} chars")

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            tag = soup.find("script", {"id": "__NEXT_DATA__"})
            if tag and tag.string:
                data = json.loads(tag.string)
                page_props = data.get("props", {}).get("pageProps", {})
                print(f"  [OK] __NEXT_DATA__ found! pageProps keys: {list(page_props.keys())[:8]}")

                # Find any list with >5 items (likely events)
                def scan(d, path="", depth=0):
                    if depth > 6:
                        return
                    if isinstance(d, dict):
                        for k, v in d.items():
                            scan(v, f"{path}.{k}", depth+1)
                    elif isinstance(d, list) and len(d) > 5:
                        print(f"  List at '{path}': {len(d)} items, first keys: "
                              f"{list(d[0].keys())[:6] if isinstance(d[0], dict) else type(d[0]).__name__}")

                scan(page_props)
            else:
                print("  No __NEXT_DATA__ tag")
                if "cloudflare" in resp.text.lower():
                    print("  -> Cloudflare block!")
                elif resp.text.strip().startswith("{"):
                    print("  -> JSON response!")
                    print(f"  {resp.text[:300]}")
    except requests.exceptions.Timeout:
        print("  TIMEOUT")
    except Exception as e:
        print(f"  Error: {e}")
