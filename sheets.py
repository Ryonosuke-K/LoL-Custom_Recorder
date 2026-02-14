from datetime import datetime, timezone

import requests
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import (
    GOOGLE_APPLICATION_CREDENTIALS,
    SHEETS_SPREADSHEET_ID,
    SHEETS_WORKSHEET_NAME,
)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_CHAMPION_KEY_CACHE: dict[int, str] | None = None


def is_enabled() -> bool:
    return bool(SHEETS_SPREADSHEET_ID)


def _fmt_duration(seconds: int) -> str:
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins:02d}:{secs:02d}"


def _kda(kills: int, deaths: int, assists: int) -> str:
    value = (kills + assists) / max(1, deaths)
    return f"{value:.2f}"


def _role_label(role: str) -> str:
    mapping = {
        "TOP": "TOP",
        "JUNGLE": "JG",
        "MIDDLE": "MID",
        "BOTTOM": "ADC",
        "UTILITY": "SUP",
    }
    return mapping.get(role, role or "")


def _champion_name_from_id(champion_id: int) -> str:
    global _CHAMPION_KEY_CACHE
    if _CHAMPION_KEY_CACHE is None:
        _CHAMPION_KEY_CACHE = _load_champion_map()
    return _CHAMPION_KEY_CACHE.get(champion_id, f"ID:{champion_id}")


def _load_champion_map() -> dict[int, str]:
    try:
        version_resp = requests.get(
            "https://ddragon.leagueoflegends.com/api/versions.json",
            timeout=10,
        )
        version_resp.raise_for_status()
        version = version_resp.json()[0]

        champion_resp = requests.get(
            f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json",
            timeout=10,
        )
        champion_resp.raise_for_status()
        data = champion_resp.json().get("data", {})
        mapping: dict[int, str] = {}
        for champ in data.values():
            key_int = int(champ.get("key", 0))
            name = str(champ.get("name", ""))
            if key_int > 0 and name:
                mapping[key_int] = name
        return mapping
    except Exception:
        # Fallback map for common champions if Data Dragon is temporarily unavailable.
        return {
            21: "Miss Fortune",
            35: "Shaco",
            39: "Irelia",
            40: "Janna",
            51: "Caitlyn",
            56: "Nocturne",
            64: "Lee Sin",
            82: "Mordekaiser",
            86: "Garen",
            90: "Malzahar",
            103: "Ahri",
            222: "Jinx",
            238: "Zed",
            350: "Yuumi",
            360: "Samira",
            412: "Thresh",
            517: "Sylas",
            555: "Pyke",
        }


def _participant_name(p: dict) -> str:
    # Prefer classic summoner name, then Riot ID, then fallback.
    name = str(p.get("summonerName", "")).strip()
    if name:
        return name
    riot_name = str(p.get("riotIdGameName", "")).strip()
    riot_tag = str(p.get("riotIdTagline", "")).strip()
    if riot_name and riot_tag:
        return f"{riot_name}#{riot_tag}"
    if riot_name:
        return riot_name
    return str(p.get("puuid", ""))[:12]


def _get_frame_at_14m(timeline: dict | None) -> dict | None:
    if not timeline:
        return None
    frames = timeline.get("info", {}).get("frames", [])
    if not frames:
        return None
    target_ms = 14 * 60 * 1000
    best = None
    for frame in frames:
        ts = int(frame.get("timestamp", 0))
        if ts <= target_ms:
            best = frame
        else:
            break
    return best or frames[0]


def _build_gold_diff_14_map(match: dict, timeline: dict | None) -> dict[int, int | str]:
    frame = _get_frame_at_14m(timeline)
    if not frame:
        return {}
    pf = frame.get("participantFrames", {})
    participants = match.get("info", {}).get("participants", [])

    by_pos: dict[tuple[int, str], dict] = {}
    for p in participants:
        team_id = int(p.get("teamId", 0))
        pos = str(p.get("teamPosition", "") or p.get("individualPosition", ""))
        if team_id in (100, 200) and pos:
            by_pos[(team_id, pos)] = p

    out: dict[int, int | str] = {}
    for p in participants:
        pid = int(p.get("participantId", 0))
        team_id = int(p.get("teamId", 0))
        opp_team = 200 if team_id == 100 else 100
        pos = str(p.get("teamPosition", "") or p.get("individualPosition", ""))
        opponent = by_pos.get((opp_team, pos))
        if not pid or not opponent:
            out[pid] = ""
            continue
        opp_pid = int(opponent.get("participantId", 0))
        mine = int((pf.get(str(pid), {}) or pf.get(pid, {})).get("totalGold", 0))
        theirs = int((pf.get(str(opp_pid), {}) or pf.get(opp_pid, {})).get("totalGold", 0))
        out[pid] = mine - theirs
    return out


def _build_vision_diff_map(match: dict) -> dict[int, int | str]:
    participants = match.get("info", {}).get("participants", [])
    by_pos: dict[tuple[int, str], dict] = {}
    for p in participants:
        team_id = int(p.get("teamId", 0))
        pos = str(p.get("teamPosition", "") or p.get("individualPosition", ""))
        if team_id in (100, 200) and pos:
            by_pos[(team_id, pos)] = p

    full_diff: dict[int, int | str] = {}
    for p in participants:
        pid = int(p.get("participantId", 0))
        team_id = int(p.get("teamId", 0))
        opp_team = 200 if team_id == 100 else 100
        pos = str(p.get("teamPosition", "") or p.get("individualPosition", ""))
        opponent = by_pos.get((opp_team, pos))
        if not pid or not opponent:
            full_diff[pid] = ""
            continue

        self_vs = int(p.get("visionScore", 0))
        opp_vs = int(opponent.get("visionScore", 0))
        full_diff[pid] = self_vs - opp_vs
    return full_diff


def _build_rows(match_id: str, match: dict, timeline: dict | None = None) -> list[list]:
    info = match.get("info", {})
    participants = info.get("participants", [])
    teams = {t.get("teamId"): t for t in info.get("teams", [])}
    team_indices: dict[int, int] = {100: 0, 200: 0}
    team_kills: dict[int, int] = {100: 0, 200: 0}
    team_damage_to_champs: dict[int, int] = {100: 0, 200: 0}
    team_gold: dict[int, int] = {100: 0, 200: 0}
    gold_diff_14 = _build_gold_diff_14_map(match, timeline)
    vision_diff_full = _build_vision_diff_map(match)

    for p in participants:
        team_id = int(p.get("teamId", 0))
        team_kills[team_id] = team_kills.get(team_id, 0) + int(p.get("kills", 0))
        team_damage_to_champs[team_id] = team_damage_to_champs.get(team_id, 0) + int(
            p.get("totalDamageDealtToChampions", 0)
        )
        team_gold[team_id] = team_gold.get(team_id, 0) + int(p.get("goldEarned", 0))

    # Match-v5 duration semantics:
    # - If gameEndTimestamp exists (patch >= 11.20), gameDuration is seconds.
    # - Otherwise older matches may report milliseconds.
    game_duration_raw = int(info.get("gameDuration", 0) or 0)
    game_end_ts = info.get("gameEndTimestamp")
    if game_end_ts is not None:
        game_duration_sec = game_duration_raw
    else:
        game_duration_sec = int(game_duration_raw / 1000) if game_duration_raw > 10000 else game_duration_raw

    # Prefer start timestamp when available, fallback to gameCreation.
    game_start_ms = int(info.get("gameStartTimestamp", 0) or info.get("gameCreation", 0) or 0)
    game_dt = datetime.fromtimestamp(game_start_ms / 1000, tz=timezone.utc) if game_start_ms > 0 else datetime.now(timezone.utc)
    date_text = game_dt.strftime("%Y-%m-%d")
    duration_text = _fmt_duration(game_duration_sec)
    game_minutes = max(game_duration_sec / 60.0, 1e-9)

    rows: list[list] = []
    for p in participants:
        team_id = int(p.get("teamId", 0))
        challenges = p.get("challenges", {}) if isinstance(p.get("challenges", {}), dict) else {}
        side = "Blue" if team_id == 100 else "Red"
        win_lose = "Win" if p.get("win") else "Lose"
        kills = int(p.get("kills", 0))
        deaths = int(p.get("deaths", 0))
        assists = int(p.get("assists", 0))
        cs = int(p.get("totalMinionsKilled", 0)) + int(p.get("neutralMinionsKilled", 0))
        # Use participant timePlayed if present; otherwise fallback to match duration.
        time_played_sec = int(p.get("timePlayed", 0) or game_duration_sec)
        minutes = max(time_played_sec / 60.0, game_minutes, 1e-9)
        cspm = f"{(cs / minutes):.2f}"
        player_damage = int(p.get("totalDamageDealtToChampions", 0))
        player_gold = int(p.get("goldEarned", 0))
        team_total_kills = max(1, team_kills.get(team_id, 0))
        team_total_damage = max(1, team_damage_to_champs.get(team_id, 0))
        team_total_gold = max(1, team_gold.get(team_id, 0))

        kp_pct = round(((kills + assists) / team_total_kills) * 100, 2)
        dpm = round(player_damage / minutes, 2)
        dmg_share_pct = round((player_damage / team_total_damage) * 100, 2)
        gold_share_pct = round((player_gold / team_total_gold) * 100, 2)
        vision_per_min = round(float(p.get("visionScore", 0)) / minutes, 2)
        total_time_spent_dead = int(p.get("totalTimeSpentDead", 0))
        gpm = round(float(challenges.get("goldPerMinute", player_gold / minutes)), 2)
        solo_kills = int(challenges.get("soloKills", 0))

        team_bans = teams.get(team_id, {}).get("bans", [])
        ban_names: list[str] = []
        for ban in team_bans:
            champion_id = int(ban.get("championId", 0))
            if champion_id > 0:
                ban_names.append(_champion_name_from_id(champion_id))
        if ban_names:
            idx = team_indices.get(team_id, 0)
            bans_text = ban_names[idx % len(ban_names)]
            team_indices[team_id] = idx + 1
        else:
            bans_text = ""

        rows.append([
            date_text,                              # A 日付
            match_id,                               # B ゲーム数
            side,                                   # C サイド
            win_lose,                               # D 勝敗
            duration_text,                          # E 時間
            bans_text,                              # F Ban
            _participant_name(p),                   # G 参加者 (summoner name)
            _role_label(str(p.get("teamPosition", "") or p.get("individualPosition", ""))),  # H ロール
            p.get("championName", ""),              # I チャンピオン
            kills,                                  # J キル
            deaths,                                 # K デス
            assists,                                # L アシスト
            _kda(kills, deaths, assists),           # M KDA
            cs,                                     # N CS
            cspm,                                   # O 分間CS
            kp_pct,                                 # P KP%
            dpm,                                    # Q DPM
            dmg_share_pct,                          # R DMGShare%
            gold_share_pct,                         # S GoldShare%
            vision_per_min,                         # T Vision/Min
            total_time_spent_dead,                  # U TotalTimeSpentDead
            gpm,                                    # V GoldPerMinute
            solo_kills,                             # W SoloKills
            gold_diff_14.get(int(p.get("participantId", 0)), ""),  # X 14m GoldDiff vs lane opponent
            vision_diff_full.get(int(p.get("participantId", 0)), ""),     # Y VisionScoreDiff vs lane opponent
        ])
    return rows


def append_match_row(
    match_id: str,
    game_id: str,
    host_discord_id: str,
    host_name: str,
    match: dict,
    timeline: dict | None = None,
) -> None:
    del game_id, host_discord_id, host_name
    if not is_enabled():
        return

    values = _build_rows(match_id, match, timeline)
    if not values:
        return

    creds = Credentials.from_service_account_file(
        GOOGLE_APPLICATION_CREDENTIALS, scopes=SCOPES
    )
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    target_range = f"{SHEETS_WORKSHEET_NAME}!A:Y"
    try:
        result = service.spreadsheets().values().append(
            spreadsheetId=SHEETS_SPREADSHEET_ID,
            range=target_range,
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": values},
        ).execute()
        _apply_row_style(service, SHEETS_SPREADSHEET_ID, result.get("updates", {}).get("updatedRange", ""))
    except HttpError as err:
        if err.resp.status != 400:
            raise
        meta = service.spreadsheets().get(spreadsheetId=SHEETS_SPREADSHEET_ID).execute()
        sheets = meta.get("sheets", [])
        if not sheets:
            raise
        first_title = sheets[0]["properties"]["title"]
        result = service.spreadsheets().values().append(
            spreadsheetId=SHEETS_SPREADSHEET_ID,
            range=f"{first_title}!A:Y",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": values},
        ).execute()
        _apply_row_style(service, SHEETS_SPREADSHEET_ID, result.get("updates", {}).get("updatedRange", ""))


def _col_to_index(col: str) -> int:
    idx = 0
    for ch in col:
        idx = idx * 26 + (ord(ch.upper()) - ord("A") + 1)
    return idx - 1


def _parse_updated_range(a1_range: str) -> tuple[str, int, int, int, int] | None:
    # Example: test_sheet!A11:W20
    if "!" not in a1_range or ":" not in a1_range:
        return None
    sheet_name, cells = a1_range.split("!", 1)
    start, end = cells.split(":", 1)
    start_col = "".join([c for c in start if c.isalpha()])
    start_row = "".join([c for c in start if c.isdigit()])
    end_col = "".join([c for c in end if c.isalpha()])
    end_row = "".join([c for c in end if c.isdigit()])
    if not (start_col and start_row and end_col and end_row):
        return None
    return (
        sheet_name,
        int(start_row) - 1,
        int(end_row),
        _col_to_index(start_col),
        _col_to_index(end_col) + 1,
    )


def _apply_row_style(service, spreadsheet_id: str, updated_range: str) -> None:
    parsed = _parse_updated_range(updated_range)
    if not parsed:
        return
    sheet_name, start_row, end_row, start_col, end_col = parsed
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheet_id = None
    for s in meta.get("sheets", []):
        if s.get("properties", {}).get("title") == sheet_name:
            sheet_id = s.get("properties", {}).get("sheetId")
            break
    if sheet_id is None:
        return

    # Keep background untouched (no extra fill), set text to black.
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": start_row,
                            "endRowIndex": end_row,
                            "startColumnIndex": start_col,
                            "endColumnIndex": end_col,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {
                                    "foregroundColor": {"red": 0, "green": 0, "blue": 0}
                                }
                            }
                        },
                        "fields": "userEnteredFormat.textFormat.foregroundColor",
                    }
                }
            ]
        },
    ).execute()
