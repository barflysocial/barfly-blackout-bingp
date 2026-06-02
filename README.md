# Battle Bingo Full v1

A Render/GitHub-ready Flask app for Barfly Social Bingo / Battle Bingo.

## Included
- Host-created joinable games
- RSVP with name, mobile number, and alias
- My RSVP lookup by mobile number
- Dynamic share metadata with title graphic URL
- 3 cards per player with numbers 1–75 divided across the cards, no duplicates per player
- Auto-highlight current called number
- Manual or auto mark mode
- 5 points per correct mark, 25 per horizontal Bingo row, 50 per blackout, 10 per power use
- Automatic row, power, blackout, and leaderboard tracking
- Battle Feed
- Host dashboard
- TV board
- Prize tracking
- Alias moderation
- Hall of Fame stats
- Host reset controls

## Render Deploy
Create a Web Service.

Build command:
```bash
pip install -r requirements.txt
```

Start command:
```bash
gunicorn app:app
```

Do not use npm for this version.

## Local Run
```bash
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

## Notes
SQLite is used by default for simple deployment/testing. For production persistence on Render, add a Postgres database and set `DATABASE_URL`.
