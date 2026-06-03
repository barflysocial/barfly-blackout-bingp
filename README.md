# Battle Bingo v2 Freeze / Fire / Peek Build

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

- `/rsvp` - Player RSVP / join screen
- `/host` - Host dashboard
- `/tv/<code>` - TV board for a session

## Power rules in this build

Only three powers are awarded and usable:

- **Freeze**: targets the player ranked directly above you. If you are in 1st place, it targets 2nd place. Freeze applies to the next called number and blocks that player from clicking it for half of the call duration. The number still stays highlighted for the full call.
- **Fire**: activates Freeze immunity. The next Freeze attempt against that player is negated.
- **Peek**: reveals the next called number.

Removed older powers from active gameplay: Lucky Spot, Second Chance, Row Block, Card Shuffle, Shield Breaker, Mirror Attack, and Power Swap.

## Notes

- Session codes and QR codes are generated only after a session is created.
- Host creates sessions; players join via RSVP.
- The game uses server-timed countdowns and session-specific game state.
