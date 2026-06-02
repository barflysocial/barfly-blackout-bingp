# Battle Bingo Final Production v1

A Render/GitHub-ready Barfly Social Bingo web app with player, host, and TV-board views.

## Included

- Host-created joinable games
- Dynamic RSVP links and share metadata
- Player RSVP with name, mobile number, and public alias
- My RSVP recovery by mobile number
- Private phone-based seat recovery; phone numbers are never shown publicly
- Three bingo cards per player with numbers 1-75 distributed across the three cards
- No duplicate numbers across a player’s three cards
- Server-side call sequence
- Host Call and Auto Call modes
- Countdown to next call
- Auto-highlight current called number
- Manual Mark and Auto Mark modes
- Automatic row Bingo detection
- Automatic blackout detection
- Blackout timestamps
- Leaderboard ranked by blackouts, timestamps, points, rows, and remaining spaces
- Scoring: 5 per correct mark, 25 per horizontal row, 50 per blackout, 10 per successful power use
- Random power wheel with 5-second unskippable room-wide reveal
- Power inventory, cooldown, random targeting, and power effects
- Battle Feed, near-miss-style activity feed, AFK indicator
- Host alias moderation and player removal
- Prize tracking, venue branding, sponsor text
- TV Board with current call, countdown, leaderboard, Battle Feed, and recent calls
- Hall of Fame / player stats
- Reset Session and Reset Everything
- Optional host PIN protection

## Render Deployment

1. Push this folder to GitHub.
2. In Render, create a new **Blueprint** from the repository, or create a Python Web Service manually.
3. Build command:

```bash
pip install -r requirements.txt
```

4. Start command:

```bash
gunicorn app:app --workers 1 --threads 8 --timeout 120
```

5. Add environment variables:

```bash
SECRET_KEY=<random long string>
DATABASE_URL=<Render PostgreSQL connection string>
HOST_PIN=<optional host dashboard PIN>
```

If using `render.yaml`, Render can create the PostgreSQL database automatically.

## Important Routes

- `/` — public home
- `/host` — host dashboard / create games
- `/game/<code>` — public title screen and share page
- `/game/<code>/rsvp` — player RSVP
- `/my-rsvp` — recover RSVP by mobile number
- `/play/<code>/<player_id>` — player game screen
- `/tv/<code>` — TV board
- `/hall` — Hall of Fame
- `/healthz` — health check

## Host PIN

If `HOST_PIN` is set in Render, host routes require the PIN. If `HOST_PIN` is blank, host routes are open. For public deployment, set `HOST_PIN`.

## Notes

This package is built for one Render web service using database polling instead of WebSockets. For extremely large events, the next scaling step would be Redis/WebSockets, but this version is suitable for venue testing and normal bar/restaurant game nights.
