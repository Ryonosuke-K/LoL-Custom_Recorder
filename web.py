from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

from config import (
    CONTACT_EMAIL,
    DB_PATH,
    DEMO_MODE,
    DEMO_VIDEO_URL,
    FERNET_KEY,
    LOL_PLATFORM,
    RIOT_OAUTH_READY,
    RIOT_REGION_BASE,
    STATE_SIGNING_SECRET,
)
from crypto_util import Crypto
from db import DB
from riot_oauth import build_authorize_url, exchange_code_for_tokens, get_accounts_me
from state_signer import decode_state, encode_state

app = FastAPI()
db = DB(DB_PATH)
crypto = Crypto(FERNET_KEY)

RIOT_VERIFY_TOKEN = "c768f352-d42e-401a-8dd5-4d88c3c9f925"


@app.get("/riot.txt")
def riot_verify() -> PlainTextResponse:
    return PlainTextResponse(RIOT_VERIFY_TOKEN)


@app.get("/")
def index() -> HTMLResponse:
    video = (
        f'<p>Demo video: <a href="{DEMO_VIDEO_URL}" target="_blank" rel="noopener">open</a></p>'
        if DEMO_VIDEO_URL
        else "<p>Demo video: not set</p>"
    )
    return HTMLResponse(
        """
        <h1>LoL Custom Record Bot</h1>
        <p>This is an invite-only demo service for Discord game record automation.</p>
        <ul>
          <li>Use <code>/link</code> in Discord to connect organizer account</li>
          <li>Use <code>/record game_id:...</code> in Discord to save game result</li>
        </ul>
        <p>Mode: <b>DEMO</b> (Riot OAuth pending)</p>
        """
        + video
        + """
        <p>
          <a href="/review">Review</a> |
          <a href="/terms">Terms</a> |
          <a href="/privacy">Privacy</a> |
          <a href="/health">Health</a>
        </p>
        """
    )


@app.get("/terms")
def terms() -> HTMLResponse:
    return HTMLResponse(
        """
        <h1>Terms of Service</h1>
        <p>This service is private and invite-only.</p>
        <p>By using this bot, users agree to:</p>
        <ul>
          <li>use data only for internal review/coaching,</li>
          <li>not redistribute private match data,</li>
          <li>follow administrator instructions and platform rules.</li>
        </ul>
        <p>Policy enforcement:</p>
        <ul>
          <li>unauthorized sharing of private data: immediate access revocation,</li>
          <li>repeated misuse/harassment: permanent removal,</li>
          <li>API abuse (spam, token misuse): immediate suspension and credential rotation.</li>
        </ul>
        """
    )


@app.get("/privacy")
def privacy() -> HTMLResponse:
    return HTMLResponse(
        """
        <h1>Privacy Policy</h1>
        <p>Data processed:</p>
        <ul>
          <li>Discord user ID for account mapping,</li>
          <li>match statistics for internal record automation,</li>
          <li>encrypted integration credentials.</li>
        </ul>
        <p>Storage policy:</p>
        <ul>
          <li>custom match rows are written directly to a private spreadsheet,</li>
          <li>custom match rows are not stored in app DB,</li>
          <li>no public publishing of user match data.</li>
        </ul>
        <p>Users can request unlink/deletion at any time.</p>
        <p>Contact: """
        + CONTACT_EMAIL
        + """</p>
        """
    )


@app.get("/review")
def review() -> HTMLResponse:
    organizers = db.count_organizers()
    video = DEMO_VIDEO_URL if DEMO_VIDEO_URL else "(not set)"
    return HTMLResponse(
        f"""
        <h1>Reviewer Guide</h1>
        <p>This app is invite-only and used for internal custom game recording.</p>
        <ol>
          <li>In Discord, run <code>/link</code></li>
          <li>Open DM URL to complete linking</li>
          <li>Run <code>/record game_id:1234567890</code></li>
          <li>Check response and optional Google Sheets append</li>
        </ol>
        <p>Current mode: {'DEMO' if DEMO_MODE else 'PROD'}</p>
        <p>Linked organizers: {organizers}</p>
        <p>Recorded matches: not stored locally (spreadsheet-only write)</p>
        <p>Demo video URL: {video}</p>
        <h2>Known Limitations & Mitigations</h2>
        <ul>
          <li>Current review mode is restricted to approved members and private Discord servers only.</li>
          <li>Match access depends on Riot API permissions and key scope; unsupported matches are rejected and not exposed publicly.</li>
          <li>Operational controls include invite-only onboarding, restricted spreadsheet sharing, and immediate access revocation for policy violations.</li>
        </ul>
        <p>Contact: {CONTACT_EMAIL}</p>
        """
    )


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "demo_mode": DEMO_MODE,
        "riot_oauth_ready": RIOT_OAUTH_READY,
        "linked_organizers": db.count_organizers(),
        "local_match_storage": False,
    }


@app.get("/connect")
def connect(code: str):
    row = db.get_link_code(code)
    if not row:
        raise HTTPException(status_code=404, detail="Invalid code")
    if row["used_at"] is not None:
        raise HTTPException(status_code=400, detail="Code already used")

    if DEMO_MODE or not RIOT_OAUTH_READY:
        consumed = db.consume_link_code(code)
        if not consumed:
            raise HTTPException(status_code=400, detail="Code expired or already used")
        db.upsert_organizer(
            discord_user_id=consumed["discord_user_id"],
            encrypted_refresh_token=crypto.encrypt("demo_refresh_token"),
            riot_puuid="demo-puuid",
            region_base=RIOT_REGION_BASE,
            platform=LOL_PLATFORM,
        )
        return HTMLResponse(
            "<h2>Demo link complete.</h2><p>Organizer linked in demo mode. Return to Discord.</p>"
        )

    state = encode_state(code, STATE_SIGNING_SECRET)
    return RedirectResponse(build_authorize_url(state))


@app.get("/oauth/callback")
def oauth_callback(code: str, state: str):
    if DEMO_MODE or not RIOT_OAUTH_READY:
        raise HTTPException(status_code=400, detail="OAuth callback is disabled in demo mode.")

    try:
        link_code = decode_state(state, STATE_SIGNING_SECRET)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err

    consumed = db.consume_link_code(link_code)
    if not consumed:
        raise HTTPException(status_code=400, detail="Code expired or already used")

    tokens = exchange_code_for_tokens(code)
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    if not access_token or not refresh_token:
        raise HTTPException(status_code=400, detail="Missing OAuth tokens")

    account = get_accounts_me(access_token)
    db.upsert_organizer(
        discord_user_id=consumed["discord_user_id"],
        encrypted_refresh_token=crypto.encrypt(refresh_token),
        riot_puuid=account.get("puuid"),
        region_base=RIOT_REGION_BASE,
        platform=LOL_PLATFORM,
    )
    return HTMLResponse("<h2>RSO linked successfully.</h2><p>Return to Discord and use /record.</p>")
