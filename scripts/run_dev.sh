#!/usr/bin/env bash
# Start the backend in development with auto-reload.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/apps/backend"
export PYTHONPATH="$ROOT/apps/backend:$ROOT/packages/game-engine"
python -m uvicorn backend.main:app --reload --port 8000
