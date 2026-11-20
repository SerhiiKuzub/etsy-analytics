"""Мінімальний клієнт Etsy Open API v3.

Перевірка підключення: python -m src.extract.etsy_client
"""
import os
import time

import requests

from src.extract.etsy_auth import get_access_token

BASE_URL = "https://openapi.etsy.com/v3/application"


def _headers() -> dict:
    # Формат keystring:shared_secret обов'язковий з 9 лютого 2026
    api_key = f'{os.environ["ETSY_API_KEY"]}:{os.environ["ETSY_SHARED_SECRET"]}'
    return {"x-api-key": api_key, "Authorization": f"Bearer {get_access_token()}"}


def get(path: str, params: dict | None = None) -> dict:
    """GET-запит із повтором при ліміті запитів (HTTP 429)."""
    for attempt in range(5):
        resp = requests.get(BASE_URL + path, headers=_headers(),
                            params=params, timeout=30)
        if resp.status_code == 429:
            time.sleep(2 ** attempt)
            continue
        if resp.status_code >= 400:
            raise RuntimeError(f"Etsy API {resp.status_code}: {resp.text[:300]}")
        return resp.json()
    raise RuntimeError("Etsy API: забагато запитів (429), спробуй пізніше")


def main() -> None:
    me = get("/users/me")
    shop_id = me["shop_id"]
    listings = get(f"/shops/{shop_id}/listings", {"state": "active", "limit": 1})
    print("OK: підключення працює")
    print(f"Shop ID (для .env, нікуди не публікуй): {shop_id}")
    print(f"Активних товарів у магазині: {listings['count']}")


if __name__ == "__main__":
    main()