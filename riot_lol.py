import requests


def get_rso_match(match_id: str, access_token: str, region_base: str) -> dict:
    response = requests.get(
        f"{region_base}/lol/rso-match/v1/matches/{match_id}",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    if response.status_code == 404:
        raise FileNotFoundError("Match not found (404).")
    response.raise_for_status()
    return response.json()


def get_match_v5(match_id: str, riot_api_key: str, region_base: str) -> dict:
    response = requests.get(
        f"{region_base}/lol/match/v5/matches/{match_id}",
        headers={"X-Riot-Token": riot_api_key},
        timeout=30,
    )
    if response.status_code == 404:
        raise FileNotFoundError("Match not found (404).")
    if response.status_code >= 400:
        detail = response.text[:300]
        raise RuntimeError(f"match-v5 error {response.status_code}: {detail}")
    return response.json()


def get_match_timeline_v5(match_id: str, riot_api_key: str, region_base: str) -> dict:
    response = requests.get(
        f"{region_base}/lol/match/v5/matches/{match_id}/timeline",
        headers={"X-Riot-Token": riot_api_key},
        timeout=30,
    )
    if response.status_code == 404:
        raise FileNotFoundError("Timeline not found (404).")
    if response.status_code >= 400:
        detail = response.text[:300]
        raise RuntimeError(f"timeline-v5 error {response.status_code}: {detail}")
    return response.json()
