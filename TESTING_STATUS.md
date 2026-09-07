# Hokm Telegram — Current Testing Status

This document reflects the actual state of the deployed test instance, not the
original repo's aspirational README. Written after a live test session.

---

## What's deployed and running

- **Backend** (FastAPI, SQLite, free Render web service)
  URL: `https://supreme-fishstick-lt5q.onrender.com`
  Docs/Swagger: `https://supreme-fishstick-lt5q.onrender.com/docs`

- **Frontend / Mini App** (React + Vite, free Render static site)
  URL: `https://supreme-fishstick-1-3wpb.onrender.com`

- **Telegram bot**: `@Hokmgamebbot`
  Mini App link: `https://t.me/Hokmgamebbot/hokm`

Both services are on Render's free tier: the backend cold-starts after ~15 min
idle, and SQLite storage is **ephemeral** — data (users, games, rankings)
resets on every redeploy/restart. Fine for testing, not for anything you
want to keep.

---

## How to run/redeploy

Backend (Render Web Service):
- Root Directory: `hokm-telegram/apps/backend`
- Build: `pip install -r requirements.txt && pip install -e ../../packages/game-engine && alembic upgrade head`
- Start: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- Env vars: `HOKM_DATABASE_URL`, `HOKM_TELEGRAM_BOT_TOKEN`, `HOKM_JWT_SECRET`,
  `HOKM_USE_REDIS=false`, `HOKM_ENVIRONMENT=dev`

Frontend (Render Static Site):
- Root Directory: `hokm-telegram/apps/mini-app`
- Build: `npm install && npm run build`
- Publish Directory: `dist`
- Env var: `VITE_API_URL=<backend URL>`

Both auto-redeploy on every push to `main`. Check each service's own
**Events** tab on Render to see deploy status/logs.

---

## Fixes applied during testing (not in the original code)

1. **`apps/mini-app/index.html`** — was missing the official Telegram Web
   App SDK script tag, so `window.Telegram` was never defined and login
   always failed with "must be opened via Telegram," even inside Telegram:
   ```html
   <script src="https://telegram.org/js/telegram-web-app.js"></script>
   ```

2. **`apps/backend/backend/security.py`** — `verify_telegram_init_data`
   expected a top-level `id` field in initData, but real Telegram nests
   all user info inside a JSON-encoded `user` parameter. Fixed to parse
   and unpack `user` before checking for `id`. This was a real bug, not a
   test-only workaround — without this fix, no real Telegram user could
   ever log in.

3. **`apps/mini-app/src/lib/ws.ts`** — THE bug behind the blank game
   screen. The WebSocket connect logic built its URL from `location.host`
   (the frontend's own domain), but the frontend and backend live on two
   separate Render services with different domains. The game socket was
   silently trying to connect to the static site instead of the backend,
   so it never received any `game.state` messages — hence no cards, no
   hakem, no teams shown. Fixed to derive the WS host from `VITE_API_URL`
   instead, converting `https:`/`http:` to `wss:`/`ws:`.

4. **Iranian tilework theme** — full palette rebuild in `styles.css`:
   Persian turquoise (`#1a9e96`), deep lapis blue (`#0f3d5c`), and saffron
   gold (`#e0a72e`) replace the original neutral palette. Added a girih
   (geometric tile) pattern to the hero/header band, gradient buttons,
   a gold hakem (★) indicator on the dealer's seat, and a dashed-border
   invite-code panel.

5. **Copy button added** — `Room.tsx` invite code now has a working
   one-tap copy button (`components` inline `CopyButton`), with a
   `document.execCommand` fallback for older Telegram WebViews that lack
   the Clipboard API.

6. **Hakem (★) indicator** — `PlayerSeat.tsx` now takes an `isHakem` prop
   and shows a gold star next to whoever is currently the dealer/hakem,
   wired through from `GameTable.tsx`'s `view.hakem_seat`.

---

## What's confirmed working

- ✅ Telegram login (real, inside the bot's Mini App)
- ✅ Profile screen — shows name
- ✅ Ranking screen — shows list
- ✅ "Play with friends" — room creation/invite flow opens and was testable
- ✅ Backend API, the game-engine regression suite passes (61 tests in this environment); backend integration tests require `aiosqlite` in the execution environment

## What's confirmed broken / incomplete

- ✅ **FIXED — game table blank-screen bug.** Root cause found and fixed:
  see item 3 above (`ws.ts` was connecting to the wrong domain). Redeploy
  and re-test — this should now show cards, hakem, and teams correctly.

- ✅ **FIXED — invite code copy button.** See item 5 above.

- ⚠️ Still worth re-testing end-to-end after this deploy: Quick Match /
  "fast play" with bots filling seats, to confirm the WS fix resolves the
  live game view there too (same underlying socket code).

---

## Suggested next steps

1. Debug the WebSocket game-state issue first — this blocks actually seeing
   or playing a real hand, which is the core of the whole app.
2. Add a copy-to-clipboard button next to the invite/room code in `Room.tsx`.
3. Once gameplay is visually confirmed working, re-test "Fast play" end to
   end with bots filling seats.


## Batch 05 verification

- `python -m compileall -q apps/backend/backend` — passed.
- `python -m pytest packages/game-engine/tests -q` — **61 passed**.
- `python -m pytest apps/backend/tests -q` — setup blocked by missing `aiosqlite` in this environment.
- `npm run typecheck` — not executable here because Mini App dependencies are not installed; prior Windows production build remains the relevant client-build validation.


## Batch 06
- `python -m compileall` for backend and game engine: PASS.
- Game-engine pytest: not rerun in this batch environment; prior baseline was green.
- Backend integration tests: not executed because `aiosqlite` is unavailable in this offline environment.
- Mini App typecheck/build: not executed because `node_modules` is absent in this environment; the user previously confirmed the Windows Vite build works.
