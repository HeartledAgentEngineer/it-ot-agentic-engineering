"""Diagnose v3: Serper (Google) als quota-freier Fallback fuer Support-Suche.
Schreibt NICHTS.
"""
from pathlib import Path
from dotenv import dotenv_values
import requests, json

env = dotenv_values(Path(__file__).resolve().parent / ".env")
KEY = env.get("SERPER_API_KEY")
print("Serper key:", "SET len=%d" % len(KEY) if KEY else "MISSING")

QUERIES = [
    "Breaking Benjamin Hamburg 2026 support act opener",
    "Breaking Benjamin 2026 European tour support special guest",
]

for q in QUERIES:
    print("=" * 72)
    print("QUERY:", q)
    print("=" * 72)
    try:
        resp = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": KEY, "Content-Type": "application/json"},
            json={"q": q, "num": 8, "hl": "en", "gl": "de"},
            timeout=15,
        )
        print("HTTP:", resp.status_code)
        if resp.status_code != 200:
            print("BODY:", resp.text[:400])
            continue
        data = resp.json()
        # answerBox / knowledgeGraph oft am wertvollsten
        if data.get("answerBox"):
            print("  ANSWER BOX:", json.dumps(data["answerBox"], ensure_ascii=False)[:400])
        if data.get("knowledgeGraph"):
            kg = data["knowledgeGraph"]
            print("  KNOWLEDGE GRAPH title:", kg.get("title"), "| desc:", str(kg.get("description"))[:200])
        print("  ORGANIC:")
        for r in data.get("organic", [])[:6]:
            print(f"    - {r.get('title')!r}")
            print(f"      {r.get('snippet','')[:240]!r}")
    except Exception as e:
        print("EXCEPTION:", type(e).__name__, e)
    print()
