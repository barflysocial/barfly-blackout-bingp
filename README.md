# Barfly Social Bingo — Battle Bingo v1

A Flask starter build for **Battle Bingo**, designed for Render deployment and GitHub version control.

## Included

- Player screen: `/player`
- Host dashboard: `/host`
- TV leaderboard board: `/tv`
- RSVP, My RSVP, and Share buttons
- Phone-number reserved seat recovery
- 3 bingo cards per player with numbers 1–75 divided across the cards
- No late joins after game start
- Manual or auto-mark mode
- Current-number-only marking in manual mode
- Horizontal-row Bingo detection
- Blackout detection
- Scoring:
  - Correct mark: +5
  - Horizontal Bingo row: +25
  - Blackout: +50
  - Successful power use: +10
- Random power awards after 4 completed rows on a card
- Maximum 1 power per card, maximum 3 powers per player, no duplicate powers
- Battle Feed
- Leaderboard
- Host settings lock after start
- Host alias moderation
- Host reset controls
- TV display mode
- Dark, polished Barfly Social visual style

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python app.py
```

Open:

- Player: http://localhost:5000/player
- Host: http://localhost:5000/host
- TV Board: http://localhost:5000/tv

## Deploy to Render

### Option 1: Use `render.yaml`

1. Push this folder to a GitHub repository.
2. In Render, choose **New +** → **Blueprint**.
3. Connect the GitHub repo.
4. Render will read `render.yaml` and create the web service.

### Option 2: Manual Render Web Service

Use these settings:

- Environment: `Python`
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app`
- Python Version: `3.11.9`

Add environment variable:

- `SECRET_KEY` = any long random string

Optional if using a persistent Render disk:

- `DATA_DIR=/var/data`

Without a persistent disk, the SQLite database may reset when the service restarts. For production, use a persistent disk or migrate to PostgreSQL.

## GitHub Ready Files

This package includes:

- `app.py`
- `requirements.txt`
- `Procfile`
- `runtime.txt`
- `render.yaml`
- `.gitignore`
- `templates/`
- `static/`

## Notes

This is a strong V1 starter app. The power inventory and feed framework are included. Some advanced power effects can be expanded further as playtesting reveals what needs more depth.
