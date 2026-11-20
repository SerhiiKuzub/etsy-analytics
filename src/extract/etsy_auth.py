"""Авторизація в Etsy API (OAuth 2.0 + PKCE) та оновлення токенів.

Перший запуск (одноразово): python -m src.extract.etsy_auth
"""
import base64
import hashlib
import json
import os
import secrets
import time
from pathlib import Path
from urllib.parse import parse_qs, quote, urlencode, urlparse

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

AUTH_URL = "https://www.etsy.com/oauth/connect"
TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"
TOKEN_FILE = ROOT / "secrets" / "etsy_tokens.json"  # папка secrets/ у .gitignore


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def save_tokens(payload: dict) -> None:
    """Зберігає токени локально з правами лише для власника."""
    old = {}
    if TOKEN_FILE.exists():
        old = json.loads(TOKEN_FILE.read_text())
    data = {
        "access_token": payload["access_token"],
        "refresh_token": payload.get("refresh_token", old.get("refresh_token")),
        "expires_at": time.time() + int(payload.get("expires_in", 3600)),
    }
    TOKEN_FILE.parent.mkdir(exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(data))
    TOKEN_FILE.chmod(0o600)


def authorize() -> None:
    client_id = os.environ["ETSY_API_KEY"]
    redirect_uri = os.environ["ETSY_REDIRECT_URI"]
    scopes = os.getenv("ETSY_SCOPES", "listings_r shops_r transactions_r billing_r")

    # PKCE: випадковий verifier і його SHA-256 хеш (challenge)
    verifier = _b64url(secrets.token_bytes(48))
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    state = secrets.token_urlsafe(16)

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scopes,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    url = AUTH_URL + "?" + urlencode(params, quote_via=quote)

    print("\n1) Відкрий це посилання в браузері, увійди в Etsy-акаунт власниці магазину")
    print("   й натисни «Allow access»:\n")
    print(url)
    print("\n2) Після дозволу браузер перейде на redirect-адресу. Сторінка може")
    print("   показати помилку, це нормально. Скопіюй ПОВНУ адресу з рядка браузера.\n")
    redirected = input("Встав адресу сюди: ").strip()

    query = parse_qs(urlparse(redirected).query)
    if query.get("state", [""])[0] != state:
        raise SystemExit("Помилка: state не збігається, авторизацію скасовано.")
    code = query["code"][0]

    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code": code,
            "code_verifier": verifier,
        },
        timeout=30,
    )
    resp.raise_for_status()
    save_tokens(resp.json())
    print("\nГотово: токени збережено в secrets/etsy_tokens.json")


def get_access_token() -> str:
    """Повертає чинний access-токен, за потреби оновлюючи його."""
    if not TOKEN_FILE.exists():
        raise SystemExit("Токенів немає. Спершу: python -m src.extract.etsy_auth")
    data = json.loads(TOKEN_FILE.read_text())
    if data["expires_at"] - 60 > time.time():
        return data["access_token"]

    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": os.environ["ETSY_API_KEY"],
            "refresh_token": data["refresh_token"],
        },
        timeout=30,
    )
    resp.raise_for_status()
    save_tokens(resp.json())
    return json.loads(TOKEN_FILE.read_text())["access_token"]


if __name__ == "__main__":
    authorize()