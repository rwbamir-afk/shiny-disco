# Phase 8 — Information-safe Expert Bot

Implemented an `expert` bot difficulty using public-information reconstruction and short deterministic Monte Carlo-style rollouts.

## Safety contract
- The expert strategy reads only its own hand plus public trick/played-card state.
- Opponent hands are never consulted to build simulations.
- Simulations sample plausible unknown cards from the remaining deck.
- The chosen action is always validated by the same Hokm engine as human actions.
- Expert decision-making does not mutate the authoritative runtime.

## Additional hardening
- Easy bot selection no longer uses Python's process-randomized `hash()`; it uses SHA-256 for stable choices.
- Added engine-level bot determinism/privacy tests.

## Verification
- `pytest -q packages/game-engine`: 64 passed.
- `python -m compileall -q apps/backend/backend packages/game-engine/hokm`: passed.
