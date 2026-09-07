# Telegram Hokm Platform

A production-oriented Persian/RTL Telegram platform for **Hokm** (Iranian
trick-taking card game): a server-authoritative real-time multiplayer backend, a
deterministic standalone game engine, and a Telegram Mini App.

**Engineering decisions, exact `hokm-v1` rules, and visual direction are documented
in the repo and in the accompanying notebook.** See `DESIGN.md` and the notebook's
"Engineering Decisions" cell.

---

## What's here

```
hokm-telegram/
  packages/game-engine/   # dependency-free deterministic Hokm engine (+ unit/property tests)
  packages/shared/        # shared client-safe contract notes
  apps/backend/           # FastAPI modular monolith (auth, rooms, matchmaking, real-time, bots, rating, reports, admin)
  apps/mini-app/          # React + TypeScript Telegram Mini App (Vite)
  apps/admin/             # (future) admin console
  infrastructure/docker/  # backend + miniapp images, docker-compose (Postgres/Redis)
  scripts/                # dev helpers
  .github/workflows/      # CI
  DESIGN.md               # visual direction + design system
```

### Key guarantees
- **Server authority** — the client only sends validated commands; the server
  computes trump, trick/round winners, scores, rating, XP. The engine is the
  single rules authority and has **zero infrastructure dependencies**.
- **No private leakage** — `PlayerGameView` never serializes another seat's cards.
  Enforced by automated anti-leak tests (engine + integration).
- **Idempotent + serialized** — per-game `asyncio.Lock`; duplicate request IDs are
  no-ops; game finalization is idempotent.
- **Reconnect + timeout + bot takeover** — server-authoritative deadlines; bots
  play the same engine with legal actions only; human reconnect restores control.

---

## Ruleset: `hokm-v1` (exact, deterministic)

4 players in 2 teams (seats `0,1,2,3`; partners opposite). 52-card deck, no jokers.
Hakem chosen randomly (first deal), deals 13 each, picks trump. Play proceeds in a
fixed cyclic seat order (`next = seat+1 mod 4`); first leader = `next(hakem)`.
Follow-suit is mandatory when able; otherwise any card (including trump). Trick
winner = highest trump, else highest of the led suit; trick winner leads next.
One deal = one match (online-Hokm MVP format); team winning ≥ 7 of 13 tricks wins.
Full breakdown, scoring, and edge cases are unit-tested in
`packages/game-engine/tests/`. The engine models rounds separately so multi-deal
formats can be added without changing it.

---

## Technology
- **Backend:** Python 3.11, FastAPI, Uvicorn, SQLAlchemy 2.0 async, Alembic,
  aiosqlite (dev) / asyncpg (prod), Redis (optional, in-memory fallback), PyJWT.
- **Real-time:** raw WebSockets (no Socket.IO — smaller, explicit auth/reconnect).
- **Auth:** Telegram WebApp init-data HMAC verification + server-issued access
  token and rotating refresh sessions. Client identity is never trusted.
- **Frontend:** React + TypeScript + Vite (authored; see Status below).

---

## Running locally (backend)

```bash
cd apps/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../../.env.example .env   # set HOKM_TELEGRAM_BOT_TOKEN
alembic upgrade head
uvicorn backend.main:app --reload --port 8000
# run migrations / tests
# python -m pytest tests/
```

Backend tests use an isolated SQLite DB configured automatically by
`tests/conftest.py`.

### Engine tests
```bash
cd packages/game-engine
python -m pytest tests/
```

### Backend tests
```bash
cd apps/backend
PYTHONPATH="." python -m pytest tests/
```

### Mini App (build + run in a real environment)
```bash
cd apps/mini-app
npm install
VITE_API_URL=https://your-backend npm run build   # or npm run dev
```
From @BotFather set the Mini App URL to the deployed bundle; the app reads
`window.Telegram.WebApp.initData` and sends it to `/api/v1/auth/telegram`.

---

## Status / honest scope

**Implemented and tested in this session** (all green):
- Deterministic `hokm-v1` engine + comprehensive unit, property, and anti-leak
  tests.
- Backend: Telegram auth, sessions, users/profiles, XP/level, Elo rating, private
  rooms, Quick-Match (rating-range + bot fill), WebSocket real-time, reconnect,
  authoritative timers, timeout → bot takeover, Easy/Medium/Hard bots, idempotent
  post-game result processing (rating/XP/stats), reports, admin, rankings.
- Backend integration suite (13 tests across auth, security/no-leak, full game via
  API, idempotency, WebSocket auth/state/action/reconnect).
- Alembic initial migration; Docker images + compose; CI workflow.

**Authored but NOT built/compiled here (explicitly):** the React Mini App. This
sandbox has **no Node.js**, so `npm install`/`tsc`/`vite build` cannot run here;
the TypeScript is complete and internally consistent but must be compiled and
verified in a Node environment before release.

**Not measured here:** live k-user load testing — this sandbox is 8 vCPU/8 GiB and
can't simulate real network/WebSocket scale. A CI load harness is the intended
next step; do not claim a specific concurrency/scale figure until it is measured.

**Known small issue:** SQLAlchemy logs warnings about aiosqlite pooled connections
not being explicitly closed at teardown (cosmetic; not a failure). Production uses
PostgreSQL/asyncpg.

---

## Convention / style
- Persian-first UI/UX, RTL, Vazirmatn. Natural Persian microcopy.
- Code, identifiers, docs comments: English. Persian only where user-facing.
- Modular monolith; the engine is isolated; infra (Telegram/DB/Redis) is isolated
  from game rules; DB/repository logic is separate from business rules.
