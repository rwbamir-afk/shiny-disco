# Render Free deployment

This release is prepared for a Render Free deployment.

## Services
- `hokm-backend`: Python/FastAPI Web Service
- `hokm-mini-app`: React/Vite Static Site
- `hokm-db`: PostgreSQL Free

## Important
1. After the first Render deployment, replace `VITE_API_URL` in `render.yaml`
   with the actual backend `https://...onrender.com` URL if Render assigns a
   different URL.
2. Set the Telegram secrets in the backend service environment.
3. The project is configured to run without Redis (`HOKM_USE_REDIS=false`).
4. Free PostgreSQL is intended for development/testing and is not a permanent
   production datastore.
5. Alembic migrations should be run from the backend service before the app
   starts if your Render setup requires explicit migration execution.

## Local verification
Backend:
    cd apps/backend
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    PYTHONPATH=.:../../packages/game-engine python -m pytest tests/ -q

Mini app:
    cd apps/mini-app
    npm ci
    npm run typecheck
    npm run build

## Changes made for Render
- Added `render.yaml` for Backend + Static Mini App + PostgreSQL.
- Backend startup runs `alembic upgrade head` before Uvicorn.
- PostgreSQL `postgresql://` URLs are normalized to `postgresql+asyncpg://`.
- Mini App receives the backend host through Render's service reference.
- Redis is disabled for the Free single-instance deployment.
