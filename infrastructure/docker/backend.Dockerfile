# Backend image: modular monolith (FastAPI + async SQLAlchemy).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /srv/app

# Copy engine (dependency-free) and backend.
COPY packages/game-engine /srv/app/packages/game-engine
COPY apps/backend /srv/app/apps/backend

WORKDIR /srv/app/apps/backend
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
