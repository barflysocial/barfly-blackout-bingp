# Barfly Blackout Bingo

Render/GitHub-ready live bingo web app.

## Run locally

```bash
npm install
npm start
```

Open:

- Player: http://localhost:3000/player
- Host: http://localhost:3000/host

## Current features

- Separate `/player` and `/host` screens.
- Player logo splash, clean title graphic, Tap to Begin.
- RSVP by scheduled game date/time.
- RSVP form collects name, phone number, and optional social handle.
- My RSVP lookup by phone number.
- Host-set player cap per scheduled game.
- Check-in from My RSVP.
- Session QR code and rich share/copy link buttons.
- Host-created scheduled games automatically open at the scheduled time.
- Host controls first call, next calls, auto-call, end game, new round, and clear players/scores.
- Optional Tip the Host link shown after game ends.
- 5x5 BINGO cards, no free spaces.
- Orange = called/highlighted. Green = selected.
- Numbers are never auto-selected.
- Automatic blackout detection.
- 1st, 2nd, and 3rd place winners with server timestamps rounded to nearest tenth of a second.
- Winner snapshot captures who was 2nd/3rd/etc. at the exact winning moment.
- Host can rename or kick players.

## Render settings

Deploy as a **Web Service**, not a Static Site.

- Build Command: `npm install`
- Start Command: `npm start`
- Root Directory: leave blank when files are at repo root.
