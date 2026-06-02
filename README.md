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
- Random power wheel at 5, 10, and 15 cleared lines after at least 10 calls; maximum 3 powers per game
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


## v2.4 Gameplay/Host Updates

- Battle Feed now returns gameplay activity only: line clears, powers, Full Clears, badges, and game-over events.
- Host/admin/setup actions are hidden from Battle Feed, including RSVP confirmations, game creation, alias updates, scheduling changes, pauses, resumes, resets, and prize edits.
- Row clears now use a short localized confetti animation before the row disappears and the board collapses.
- Removed player-facing “wheel cannot be skipped” language.
- Power earning changed to every 5 cleared rows with a maximum of 3 powers per game: rows 5, 10, and 15.
- Host dashboard settings summary removed.
- First-place prize tracking now uses a horizontal form layout.
- Called spaces remain highlighted until marked; players can mark any called/unmarked space, but cannot mark uncalled spaces.

## Multi-session support

Battle Bingo supports multiple independent sessions. Each session has its own game code and separate:

- RSVP list and mobile recovery
- Player boards and powers
- Call pool and server timer
- Rankings and feed
- First-place prize tracking
- TV board URL
- Reset controls

Host routes:

- `/host` — create and manage sessions
- `/host/<code>` — control one session
- `/game/<code>` — player RSVP/share link for one session
- `/tv/<code>` — TV display for one session

Use **Duplicate Session** to copy venue/settings/prize templates into a new independent session without copying players, calls, rankings, or feed history.

## Session Codes and QR Codes

Session codes are generated only after a host creates and saves a session. There are no generic or pre-assigned session codes.

Each saved session automatically receives:
- Unique session code
- Join URL
- QR code at `/qr/<session_code>.png`
- Host QR page at `/host/<session_code>/qr`

The QR code links to that specific session's player join page and is tied to that session's RSVP list, lobby countdown, calls, rankings, prizes, TV board, and game state.


## v2.8 RSVP updates
- Player main screen shows only RSVP, MY RSVP, SHARE.
- RSVP opens current joinable games; if none exist, it displays COMING SOON.
- Join form uses Alias, Mobile Number, and optional Instagram Handle.
- Host Dashboard and Hall of Fame buttons removed from player main screen.
- Inactive/AFK warning language removed from player-facing feed.


## v2.9 Update
- Removed Recent Activity from the main Board screen.
- WIN mode now uses static/sticky W I N header boxes under the horizontal power slots.
- Board cells show numbers only in WIN mode and Numbers Only mode.
- Number tiles are larger and bolder for readability.
