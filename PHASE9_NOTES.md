# Phase 9 — Variant Contract & Fail-Closed Game Modes

- Added an explicit game-variant catalog for Classic 4P, Duel 2P, Three-player, Shelem 4P and Nares 4P.
- Added `require_playable()` so unfinished variants cannot accidentally enter the classic 4-player engine.
- Added `/variants` backend endpoint for the Mini App to discover supported/coming-soon modes.
- Added engine tests covering the catalog and fail-closed behavior.
- This phase deliberately does **not** claim that 2P/3P/Shelem/Nares are playable yet; their rules need dedicated state machines rather than metadata-only switches.
