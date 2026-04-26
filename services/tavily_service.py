import requests
import os

def search_tavily(query):
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY is not set")

    url = "https://api.tavily.com/search"

    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": 3
    }

    res = requests.post(url, json=payload, timeout=20)
    res.raise_for_status()
    return [r.get("content", "") for r in res.json().get("results", []) if r.get("content")]
