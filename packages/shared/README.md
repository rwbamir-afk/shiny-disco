# packages/shared — shared client-safe contracts

The platform deliberately keeps two contract surfaces:

1. **Backend / Python** (`apps/backend/backend/schemas.py`): Pydantic models used to
   validate and serialize every API/WebSocket payload. These are the authority on
   what leaves the server.

2. **Frontend / TypeScript** (`apps/mini-app/src/lib/contracts.ts`): hand-mirrored
   types for the safe client surfaces (`PlayerGameView`, `Room`, `Profile`,
   `Result`, `RankingEntry`, `Session`, `WsMessage`).

## Rules
- `PlayerGameView` is the **only** game state ever sent to a client. It must never
  include another seat's cards or server-only fields (`hands`, `snapshot`, `_rng`).
  This is enforced by `tests/test_engine_privacy.py` and the backend security
  tests.
- When either side changes a shared contract, update **both** mirrors and re-run
  the engine + backend test suites + the Mini App `npm run typecheck`.
- The frontend never reconstructs authoritative state from cached data and never
  sends state to the backend — only validated commands.
