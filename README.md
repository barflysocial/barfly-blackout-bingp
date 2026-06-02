# Battle Bingo v2 — Render/GitHub Ready

Battle Bingo v2 is a Flask + SQLAlchemy web app designed for Render deployment.

## What this version includes

- Host-created joinable games
- RSVP with name, mobile number, and alias
- My RSVP lookup by mobile number
- Phone-number recovery without showing phone numbers publicly
- Single Battle Board per player
- 25 lines x 3 numbers = all numbers 1–75 exactly once
- Exact called letter/number validation through standard bingo ranges
- Auto-highlight of current called number
- Manual mark or auto-mark host setting
- Server-side number calling
- Server-side auto-call loop for Auto Call mode
- Countdown to next call
- Player activity-only Battle Feed
- Leaderboard showing rank, alias, lines left, and points
- Scoring: +5 correct mark, +25 line clear, +50 Full Clear, +10 successful power use
- Cleared lines disappear from the player board
- Random power wheel every 4 cleared lines after at least 10 calls
- Power inventory, cooldown, no duplicate powers, max 3 held powers
- Direct rival power targeting: powers affect the player directly above you; if you are ranked #1, they affect the player directly behind you
- Host alias moderation, player removal, prize tracking, reset controls
- TV board with current call, countdown, leaderboard, feed, venue/sponsor branding
- Hall of Fame / stats foundation

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python app.py
```

Open:

- Player/title page: `/`
- Host dashboard: `/host`
- Hall of Fame: `/hall`

## Render setup

Create a new Render Web Service from the GitHub repo.

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
gunicorn app:app --workers 1 --threads 8 --timeout 120
```

Use one worker for the built-in server-side auto-call loop. For multi-worker deployments, replace the loop with an external scheduler/queue.

Add a PostgreSQL database and set `DATABASE_URL`.

Recommended environment variables:

- `SECRET_KEY` — random secure string
- `HOST_PIN` — optional host password/PIN. If blank, host pages are open.

## Notes

This is a deployable Flask implementation. It should still be tested on real phones and venue Wi-Fi before a paid live event.


## v2.2 Changes
- Added host Board Display setting: Numbers Only or WIN.
- Numbers Only mode displays spaces as plain numbers.
- WIN mode displays W/I/N columns with W 1-25, I 26-50, N 51-75.
- Updated power targeting: attack powers affect only the player directly above you in Rankings; if you are ranked #1, the target is the player directly behind you.
- Maintains 25 rows x 3 numbers, Full Clear, player/host/TV separation, and Rankings tab.


## v2.3 Fixes
- Removed unused Called Numbers sections from Host and TV screens.
- Battle Feed remains player activity only.
- Rankings exclude removed players.
- Added a server-side background auto-call loop for Auto Call mode.
- README targeting language corrected to Direct Rival Only.
- Packaged at repository root for Render/GitHub; no nested app folder required.


## Latest v2.2 Changes
- Game automatically shows GAME OVER when all 75 numbers have been called.
- Player current-call panel is sticky/non-scrollable so calls remain visible while scrolling.
- Active gameplay header no longer shows Barfly Social Bingo, venue, or alias.
- Power slot labels have higher contrast for dim venues.

## v2.3 Automated Scheduling

This build adds scheduled game automation:

- Host can set RSVP open time, game start time, optional RSVP close time, and time zone.
- Game statuses flow automatically: Draft -> Lobby/RSVP Open -> Started -> Ended.
- Lobby countdown is server-time based and visible to player, host, and TV screens.
- At scheduled start, RSVP closes automatically, no late joins are allowed, and the first call begins.
- Host override controls include Start Now, Delay 5 Minutes, Pause Lobby, Resume Lobby, Cancel, Pause Game, Resume Game, End, Reset Session, and Reset Everything.
- Background server loop advances scheduled games and auto-call sessions. On Render, use one worker for this prototype unless you move scheduling to a dedicated worker/queue.

Host dashboard cleanup included:

- Horizontal gameplay controls.
- Host battle feed removed from dashboard.
- Host rankings removed from dashboard.
- Alias moderation available any time.
- First-place prize tracking.
- Horizontal alias moderation rows.
