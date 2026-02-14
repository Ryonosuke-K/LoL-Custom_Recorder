import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

from config import (
    DB_PATH,
    DEMO_MODE,
    DISCORD_TOKEN,
    FERNET_KEY,
    PUBLIC_BASE_URL,
    RIOT_API_KEY,
    RIOT_REGION_BASE,
)
from crypto_util import Crypto
from db import DB
from riot_lol import get_match_timeline_v5, get_match_v5
from sheets import append_match_row, is_enabled

db = DB(DB_PATH)
crypto = Crypto(FERNET_KEY)

DEMO_MATCH_ID = "JP1_564691661"


def _make_link_code() -> str:
    return f"{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}"


def _normalize_game_id(raw: str) -> str:
    game_id = raw.strip()
    if not game_id.isdigit():
        raise ValueError("game_id must be numeric.")
    return game_id


def _build_demo_match() -> tuple[str, dict, dict, str]:
    if not RIOT_API_KEY:
        raise RuntimeError("RIOT_API_KEY is not set.")
    match = get_match_v5(DEMO_MATCH_ID, RIOT_API_KEY, RIOT_REGION_BASE)
    timeline = get_match_timeline_v5(DEMO_MATCH_ID, RIOT_API_KEY, RIOT_REGION_BASE)
    return DEMO_MATCH_ID, match, timeline, "match-v5"


class BotClient(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        await self.tree.sync()


client = BotClient()


@client.tree.command(name="link", description="Link organizer account for this bot")
async def link_command(interaction: discord.Interaction):
    code = _make_link_code()
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    db.insert_link_code(code, str(interaction.user.id), expires_at)

    await interaction.response.send_message("I sent a DM with your link URL.", ephemeral=True)
    try:
        await interaction.user.send(
            f"Open this link to complete account link (expires in 10 min):\n"
            f"{PUBLIC_BASE_URL}/connect?code={code}"
        )
    except discord.Forbidden:
        await interaction.followup.send(
            "DM failed. Please allow DM and run /link again.",
            ephemeral=True,
        )


@client.tree.command(name="record", description="Record a game using game_id")
@app_commands.describe(game_id="LoL game_id (string, e.g. 0123456789)", host="Organizer user (optional)")
async def record_command(
    interaction: discord.Interaction,
    game_id: str,
    host: discord.Member | None = None,
):
    await interaction.response.defer(ephemeral=True)
    try:
        _normalize_game_id(game_id)
    except ValueError:
        await interaction.followup.send(
            "game_id must be numeric. Example: 0123456789",
            ephemeral=True,
        )
        return

    host_user = host or interaction.user
    organizer_id_for_record = str(host_user.id)
    organizer_name_for_record = host_user.display_name

    if DEMO_MODE:
        try:
            match_id, match, timeline, source = _build_demo_match()
        except Exception as err:
            await interaction.followup.send(
                f"match-v5取得エラー: {err}\n"
                f"確認: RIOT_API_KEY / RIOT_REGION_BASE / matchId({DEMO_MATCH_ID})",
                ephemeral=True,
            )
            return
    else:
        await interaction.followup.send(
            "Production Riot flow is currently disabled. Enable DEMO_MODE=true for now.",
            ephemeral=True,
        )
        return

    try:
        append_match_row(
            match_id=match_id,
            game_id=game_id,
            host_discord_id=organizer_id_for_record,
            host_name=organizer_name_for_record,
            match=match,
            timeline=timeline,
        )
    except FileNotFoundError:
        await interaction.followup.send(
            "Google Sheets config error: service-account.json not found. "
            "Place it in project root or set GOOGLE_APPLICATION_CREDENTIALS.",
            ephemeral=True,
        )
        return
    except Exception as err:
        await interaction.followup.send(
            f"Google Sheets write error: {err}",
            ephemeral=True,
        )
        return

    sheets_state = "ON" if is_enabled() else "OFF"
    await interaction.followup.send(
        f"Recorded: `{match_id}`\nSource: {source}\nSheets append: {sheets_state}\nMode: {'DEMO' if DEMO_MODE else 'PROD'}",
        ephemeral=True,
    )


@client.event
async def on_ready():
    print(f"Logged in as {client.user} ({client.user.id})")


if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
