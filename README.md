# Battle Bingo v2 Final Consolidated Build

## Render deploy settings

Use these exact Render settings:

**Environment:** Python

**Build Command:**
```bash
pip install -r requirements.txt
```

**Start Command:**
```bash
gunicorn app:app --workers 1 --threads 8 --timeout 120
```

Do not put the Gunicorn command in `requirements.txt`. Requirements must contain package names only.

## Routes

- `/player` - Player RSVP / play screen
- `/host` - Host dashboard
- `/tv` - TV board

## Notes

- Session codes and QR codes are generated only after a session is created.
- Host creates sessions; players join via RSVP.
- The game uses server-timed countdowns and session-specific game state.
