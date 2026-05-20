# Barfly Blackout Bingo

Render/GitHub-ready live bingo web app.

## Current build

- Separate player and host routes: `/player` and `/host`
- Logo splash, title screen, Tap to Begin flow
- Scheduled games by local date/time, stored as UTC milliseconds for Render-safe timing
- Lobby countdown before the scheduled game starts
- RSVP with name, phone number, and optional social handle
- My RSVP lookup by phone number
- Host player cap per scheduled game
- Rich share link and QR code buttons
- Optional Tip the Host link after the game
- Sponsor name/message/logo fields, displayed as sponsor cards under each player card
- Winner congratulations popup with Share Badge and Download Badge
- 5x5 BINGO cards, no free spaces
- Orange = called/highlighted; Green = selected by player
- No auto-selecting numbers
- Automatic blackout detection
- 1st, 2nd, and 3rd winners with server timestamps shown to the nearest tenth of a second
- Winner snapshots show who was in 2nd/3rd/etc. when a winner placed
- Host can rename or kick players

## Three-card mode

The recommended setting is 3 cards per player. When set to 3, each player receives all 75 BINGO numbers exactly once across their three cards. No number repeats in that player’s three-card set.

## Render setup

Use this as a Node Web Service, not a Static Site.

Build command:

```bash
npm install
```

Start command:

```bash
npm start
```

Leave Root Directory blank when these files are at the root of the repo.
