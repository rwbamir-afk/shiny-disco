# Phase 5 — Tournament/Game Integration

This phase turns tournament brackets into real four-seat Hokm games instead of a separate two-player result flow.

## Implemented
- Tournament matches now carry four player seats (`player_a_id`..`player_d_id`).
- Round 1 groups entrants into real four-seat Hokm matches.
- Added `POST /tournaments/{tid}/matches/{match_id}/start` to create an authoritative GameService runtime.
- Games created for tournaments persist `tournament_match_id`.
- Game finalization automatically advances the tournament from the authoritative Game result.
- Winning teams advance as two players; the next round groups two winning teams into another four-seat Hokm game.
- Final winning pair receives the configured prize, split with deterministic remainder handling and idempotent ledger keys.
- Tournament entry fees are debited idempotently at join time.
- Mini App tournament page can open brackets and start ready matches.

## Verification
- Python compile: passed.
- Game Engine tests: 61 passed.
- Backend integration tests are still environment-limited when `aiosqlite` is unavailable.
- Frontend build is not run in this environment when `node_modules` is absent.

## Honest limitation
This phase does not claim full tournament production hardening yet. Cross-process locks, scheduled match timeouts, automated no-show forfeits, and a richer admin tournament dashboard remain future work.
