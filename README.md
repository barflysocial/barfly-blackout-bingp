# Barfly Blackout Bingo

Live phone-based competitive bingo for bars.

## Render setup

Deploy as a **Web Service**, not a Static Site.

- Build Command: `npm install`
- Start Command: `npm start`
- Root Directory: leave blank if these files are at the repo root

## Pages

- Player: `/player.html` or `/player`
- Host: `/host.html` or `/host`

## Current game rules

- Players join with name + session code.
- Player app starts with logo splash, title screen, then join screen.
- Join page includes a Share Game button.
- Host dashboard is separate from player app.
- Everyone gets exactly 3 random 5x5 BINGO cards each round.
- There are no free spaces.
- Host chooses mode:
  - Blackout: 1 card
  - Double Blackout: 2 cards
  - Triple Blackout: all 3 cards
- Calls happen every 7 seconds.
- Orange means the number was called and available.
- Green means selected/official.
- No numbers auto-select.
- Players may select only one number per 7-second call.
- Leaderboard opens as a toggle tab and refreshes every 8 seconds.

## Powers

Powers appear underneath each card. Powers unlock only after a card earns its 3rd valid BINGO. Only horizontal and vertical BINGOs count. Diagonals do not count. The first BINGO on a card locks the card to either horizontal or vertical for future power earning.

Random power pool:

- Freeze: freezes the current called number for everyone else. The person who used Freeze can still select it.
- Shield: blocks one Freeze.
- Swap: moves one green selected number from one of your cards to the same orange number on another card.
- Steal: steals one random unused power from the leaderboard leader, or the next ranked player with an available power.

## Host controls

- Show Directions
- Start 2-minute lobby countdown
- Start Game Now
- Pause
- Next Now
- End Game
- New Round / Keep Players
- Clear Players & Scores
- Rename player
- Kick player

## Notes

The server is authoritative for countdowns, call windows, powers, and wins. Player phones only display the countdown and request selections.
