# Barfly Blackout Bingo

Render/GitHub-ready Node + Socket.IO bingo app.

## Render
- Web Service, not Static Site
- Build: `npm install`
- Start: `npm start`
- Root Directory: blank if files are at repo root

## Main URLs
- Player: `/player`
- Host: `/host`

## Current rules
- Scheduled games use host-selected local time stored as UTC.
- Games auto-start at the scheduled time.
- Lobby shows countdown.
- 5x5 cards, no free space.
- Called numbers highlight orange.
- Players manually tap orange numbers to turn them green.
- No auto-selecting.
- Automatic blackout detection.
- 1st, 2nd, and 3rd winners are timestamped to nearest tenth of a second.
- Winner snapshots show who was 2nd/3rd/etc. at that exact moment.
- After 3 winners, a 1-minute countdown clears the board and starts a new round while keeping players and cumulative wins.
- Clear Players & Scores resets players, RSVPs, and cumulative wins.
