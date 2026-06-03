# Battle Bingo v2 Freeze / Fire / Recover Build

This build keeps the power system simple and game-focused:

- **Freeze**: targets the player ranked directly above you. If you are in 1st place, it targets 2nd place. Freeze applies to the next called number and blocks that player for the full call duration, causing them to miss that call unless they use Recover later.
- **Fire**: activates Freeze immunity and negates the next Freeze attempt against that player.
- **Recover**: marks one missed previously called number from the player's card. It cannot mark the current live call or any number that was never called.

Other gameplay fixes included:

- Removed Peek from active gameplay.
- Added a medic-style Recover icon: a red medical plus inside a white circle.
- Smoothed the countdown display with a browser-side countdown synced to server time.
- Stopped the player page from running duplicate player/game timer updates.
- Added Game Over / Winner Results presentation on player, host, and TV screens.
- Host manual End now posts a visible game-over feed item.
- Added host post-game actions in the winner modal: Back to Sessions, Export Results, Reset Session, and Duplicate Session.


## Power earning update

- Players earn **1 power every 3 cleared rows**.
- Players can hold only **3 powers** at a time.
- If all 3 slots are full when a power is earned, that power is skipped and is not banked.
- Powers cycle for each player in this order before repeating: **Freeze → Fire → Recover**.
