import os
import json
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()
client = TavilyClient(api_key=os.getenv('TAVILY_API_KEY'))
res = client.search(query='"Breaking Benjamin" support act Vorband opener Hamburg 2026', max_results=5, search_depth='basic')
print(json.dumps(res, indent=2))
