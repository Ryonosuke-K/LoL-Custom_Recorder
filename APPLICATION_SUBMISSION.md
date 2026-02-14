# Riot Production Submission Pack

Use this project in `DEMO_MODE=true` to submit a review-ready demo before RSO credentials are issued.

## Public URLs to submit

- `https://<your-domain>/`
- `https://<your-domain>/review`
- `https://<your-domain>/terms`
- `https://<your-domain>/privacy`
- `https://<your-domain>/health`

## What reviewers can test

1. Run Discord command `/link`
2. Open DM URL and complete link on `/connect?code=...`
3. Run `/record game_id:1234567890`
4. Confirm success message and optional sheets append

## Suggested application description (English)

This is an invite-only Discord bot for internal custom game record tracking.
Organizers link their account and then submit game IDs via slash command.
The app writes game records directly to a private shared sheet for coaching and post-game review.
This is not a public consumer app. Access is restricted to approved Discord members.

## Data usage summary

- Stored on app DB: Discord user ID, linked account token (encrypted)
- Not stored on app DB: custom game result rows (written directly to private spreadsheet)
- Purpose: match record automation for internal scrims/custom games
- Sharing: no third-party public sharing
- Deletion: users can request account unlink/delete by contacting support email listed on `/privacy`

## Defensive notes for review

- Privacy-first architecture: custom match rows are written to a private spreadsheet and not persisted in application DB.
- Access is invite-only and limited to approved internal Discord members.
- No public endpoints expose match rows, profile history, or user-level data dumps.
- If unsupported matches or permission issues occur, the request is rejected rather than exposing partial/private data.

## Enforcement / sanctions policy

- Unauthorized sharing of private match data -> immediate access revocation.
- Repeated misuse, harassment, or policy violations -> permanent removal.
- API abuse (spam, token misuse, rate-limit abuse) -> suspension and credential rotation.

## Before submission checklist

- [ ] Bot is online and commands are visible in Discord
- [ ] `/link` and `/record` succeed in demo mode
- [ ] Public pages are reachable
- [ ] `CONTACT_EMAIL` is set in `.env`
- [ ] Optional demo video URL is set in `DEMO_VIDEO_URL`
