# Barfly Blackout Bingo

Live phone-based bingo game for bars and events.

## Current rules

- Players join with their name and the session code.
- Host receives a QR code and rich player link buttons.
- Everyone gets exactly 3 random 5x5 BINGO cards each round.
- The host chooses one of three modes:
  - Blackout: win with 1 completed blackout card.
  - Double Blackout: win with 2 completed blackout cards.
  - Triple Blackout: win with all 3 completed blackout cards.
- Numbers are called on a 7-second server-authoritative timer.
- Orange squares are called/highlighted but not selected.
- Green squares are officially selected.
- Players may select only one current called number during each 7-second call window.
- Leaderboard opens in a tab and updates every 8 seconds.
- Directions show in the lobby before the game begins.

## Powers

Powers appear underneath the card that earned them.

Power earning rules:

- Only horizontal and vertical BINGOs count for powers.
- Diagonals do not count for powers.
- The first valid BINGO on a card locks that card as Horizontal or Vertical.
- After that, only that direction earns powers for that card.
- Powers do not unlock until the 3rd valid BINGO on that card.
- The 3rd, 4th, and 5th valid BINGOs each award one random power.

Power list:

- Freeze: freezes the current called number for everyone else. The player who uses Freeze can still select that number.
- Shield: automatically blocks one Freeze so the player can still select a frozen call.
- Swap: moves one green mark to the same orange called number on another card.
- Steal: steals one random unused power from the highest-ranked player who currently has a power.

## Render setup

Deploy as a Web Service, not a Static Site.

Build command:

```bash
npm install
```

Start command:

```bash
npm start
```

Leave Root Directory blank if these files are at the root of the GitHub repo.
