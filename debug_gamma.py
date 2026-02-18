import requests
import json

url = "https://gamma-api.polymarket.com/markets"
params = {
    "active": "true",
    "closed": "false",
    "limit": 10,
    "sort": "volume24hr:desc"
}

resp = requests.get(url, params=params)
data = resp.json()

for m in data:
    print(f"Question: {m.get('question')}")
    print(f"Volume 24h: {m.get('volume24hr')}")
    print(f"Active: {m.get('active')}, Closed: {m.get('closed')}")
    print(f"Tokens: {m.get('tokens')}")
    print(f"Clob Token IDs: {m.get('clobTokenIds')}")
    print("-" * 20)
