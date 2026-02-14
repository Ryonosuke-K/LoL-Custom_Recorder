# lol-custom-record (Demo-first)

This project is a Discord bot demo for Riot production application review.
It works now without Riot OAuth credentials.

## What works now

- `/link`: creates one-time link and stores organizer mapping
- `/record game_id:...`: records a demo match (`JP1_<game_id>`)
- Optional Google Sheets append
- Custom match rows are not stored in local DB (spreadsheet-only write)
- Public web pages for review:
  - `/`
  - `/review`
  - `/terms`
  - `/privacy`
  - `/health`

## Demo mode vs production mode

- `DEMO_MODE=true`:
  - No Riot credentials required
  - `/connect` links organizer in demo mode
  - `/record` uses dummy match data
- `DEMO_MODE=false`:
  - Riot flow is intentionally left disabled in `bot.py` as future code comments
  - Enable later after Riot production + RSO approval

## Setup

1. Copy env template
```powershell
Copy-Item .env.example .env
```

2. Fill required values in `.env`
- `DISCORD_TOKEN`
- `FERNET_KEY`
- `STATE_SIGNING_SECRET`

Generate keys:
```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

3. Install deps
```powershell
pip install -r requirements.txt
```

4. (Optional) set reviewer metadata
- `CONTACT_EMAIL=...`
- `DEMO_VIDEO_URL=...`

## Run

Terminal 1:
```powershell
uvicorn web:app --reload --port 8000
```

Terminal 2:
```powershell
python bot.py
```

## Discord usage

1. Organizer runs `/link`
2. Open DM link in browser
3. Run `/record game_id:1234567890`

## Files

- `bot.py`: Discord bot commands
- `web.py`: review pages + link endpoint
- `db.py`: SQLite storage
- `sheets.py`: optional Sheets append
- `config.py`: env settings
- `APPLICATION_SUBMISSION.md`: copy-ready submission checklist/text
