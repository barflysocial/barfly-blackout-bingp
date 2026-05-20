# Barfly Blackout Bingo

Live phone-based BARFLY blackout bingo with competitive powers.

## Folder setup for GitHub / Render

Upload the files exactly like this at the **root** of your GitHub repo:

```text
barfly-blackout-bingo/
├── package.json
├── server.js
├── render.yaml
├── .gitignore
├── README.md
└── public/
    ├── index.html
    ├── player.html
    ├── host.html
    ├── app.js
    ├── styles.css
    └── assets/
        └── title.png
```

Do **not** upload `node_modules`.

## Render settings

Create a **Web Service**, not a Static Site.

```text
Build Command: npm install
Start Command: npm start
Root Directory: leave blank
```

The app already uses Render's required port:

```js
const PORT = process.env.PORT || 3000;
```

## Main links after deploy

```text
Title:  https://your-app-name.onrender.com/
Player: https://your-app-name.onrender.com/player.html
Host:   https://your-app-name.onrender.com/host.html
Health: https://your-app-name.onrender.com/health
```

## Current game rules

- Players join with name + session code from the QR code.
- Players can purchase multiple scrollable cards.
- Cards wait for host approval/payment collection.
- The caller window is 7 seconds.
- Players may select only 1 number per 7-second call window.
- Called numbers glow on every card as visible reminders.
- Only the tapped card becomes officially marked/locked.
- Past called numbers cannot be claimed later.
- Double Tap allows one extra matching current number during the same call window.
- Freeze targets the strongest opponent card for 7 seconds.
- Shield blocks one Freeze.
- Auto-win detects full blackout.
- Same player cannot win more than once per round.

## Run locally

```bash
npm install
npm start
```

Open `http://localhost:3000`.
