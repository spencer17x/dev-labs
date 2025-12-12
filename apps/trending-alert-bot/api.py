from curl_cffi import requests


def fetch_trending(period: str = "1M", category: str = "", chain: str = "sol") -> dict:
    resp = requests.post(
        "https://www.xxyy.io/api/data/list/trending",
        headers={
            "referer": "https://www.xxyy.io",
            "x-chain": chain,
        },
        json={"period": period, "category": category},
        timeout=30,
        impersonate="chrome120",
    )
    resp.raise_for_status()
    return resp.json()
