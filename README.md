# Barfly Blackout Bingo

Render/GitHub-ready Node + Express + Socket.IO build.

## New in this build

- Three separate sponsor sections for Card 1, Card 2, and Card 3.
- Each card can show a different sponsor name, message, and logo.
- Host controls the caller timer: 5, 7, 8, 10, 12, 15, 20, or 30 seconds.
- Scheduled games auto-start at the host-selected time and begin auto-calling using the selected timer.
- Host dashboard is slimmer and horizontal, with an all-sessions strip for running multiple sessions at one time.
- Quick session controls from the session strip: Open, Call, Auto, QR.
- Player/host remain separate routes: `/player` and `/host`.
- No powers.
- 5x5 BINGO cards, no free spaces.
- Orange = called/highlighted. Green = selected by the player.
- Automatic blackout detection and 1st/2nd/3rd timestamped winners.

## Deploy to Render

1. Upload this folder to GitHub with `package.json` in the repo root.
2. Create a Render **Web Service**.
3. Build command: `npm install`
4. Start command: `npm start`
5. Leave Root Directory blank unless you place this project in a subfolder.

Do not upload `node_modules`. Render installs dependencies automatically.
