import os


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def _optional(name: str, default: str) -> str:
    return os.getenv(name, default)


DISCORD_TOKEN = _required("DISCORD_TOKEN")
PUBLIC_BASE_URL = _optional("PUBLIC_BASE_URL", "http://localhost:8000")

RIOT_CLIENT_ID = os.getenv("RIOT_CLIENT_ID", "").strip()
RIOT_CLIENT_SECRET = os.getenv("RIOT_CLIENT_SECRET", "").strip()
RIOT_REDIRECT_URI = os.getenv("RIOT_REDIRECT_URI", "").strip()
RIOT_REGION_BASE = _optional("RIOT_REGION_BASE", "https://asia.api.riotgames.com")
LOL_PLATFORM = _optional("LOL_PLATFORM", "JP1")
RIOT_API_KEY = os.getenv("RIOT_API_KEY", "").strip()

FERNET_KEY = _required("FERNET_KEY")
STATE_SIGNING_SECRET = _required("STATE_SIGNING_SECRET")
DB_PATH = _optional("DB_PATH", "app.db")
DEMO_MODE = _optional("DEMO_MODE", "true").lower() in {"1", "true", "yes", "on"}
RIOT_OAUTH_READY = bool(RIOT_CLIENT_ID and RIOT_CLIENT_SECRET and RIOT_REDIRECT_URI)
CONTACT_EMAIL = _optional("CONTACT_EMAIL", "owner@example.com")
DEMO_VIDEO_URL = os.getenv("DEMO_VIDEO_URL", "").strip()

SHEETS_SPREADSHEET_ID = os.getenv("SHEETS_SPREADSHEET_ID", "").strip()
SHEETS_WORKSHEET_NAME = _optional("SHEETS_WORKSHEET_NAME", "records")
GOOGLE_APPLICATION_CREDENTIALS = _optional("GOOGLE_APPLICATION_CREDENTIALS", "service-account.json")
