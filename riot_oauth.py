import base64
from urllib.parse import urlencode

import requests

from config import RIOT_CLIENT_ID, RIOT_CLIENT_SECRET, RIOT_REDIRECT_URI, RIOT_REGION_BASE

AUTH_BASE = "https://auth.riotgames.com"


def build_authorize_url(state: str) -> str:
    if not (RIOT_CLIENT_ID and RIOT_REDIRECT_URI):
        raise RuntimeError("Riot OAuth is not configured yet.")
    params = {
        "client_id": RIOT_CLIENT_ID,
        "redirect_uri": RIOT_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid offline_access",
        "state": state,
    }
    return f"{AUTH_BASE}/authorize?{urlencode(params)}"


def _basic_auth_header() -> str:
    if not (RIOT_CLIENT_ID and RIOT_CLIENT_SECRET):
        raise RuntimeError("Riot OAuth is not configured yet.")
    encoded = base64.b64encode(f"{RIOT_CLIENT_ID}:{RIOT_CLIENT_SECRET}".encode()).decode()
    return f"Basic {encoded}"


def exchange_code_for_tokens(code: str) -> dict:
    if not RIOT_REDIRECT_URI:
        raise RuntimeError("Riot OAuth is not configured yet.")
    response = requests.post(
        f"{AUTH_BASE}/token",
        headers={
            "Authorization": _basic_auth_header(),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": RIOT_REDIRECT_URI,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def refresh_access_token(refresh_token: str) -> dict:
    response = requests.post(
        f"{AUTH_BASE}/token",
        headers={
            "Authorization": _basic_auth_header(),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_accounts_me(access_token: str) -> dict:
    response = requests.get(
        f"{RIOT_REGION_BASE}/riot/account/v1/accounts/me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()
