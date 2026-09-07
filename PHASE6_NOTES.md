# Phase 6 — Competitive Integrity & Match Lifecycle

Implemented on top of Phase 5.

## Included
- Tournament matches now preserve the four-seat Hokm team structure across rounds.
- Tournament results can only be finalized from a finished tournament-linked Game, or by an explicit tournament/admin result path.
- Tournament match deadlines, started/finished timestamps, reporter, and forfeit lifecycle.
- Idempotent tournament prize credit.
- Authoritative turn deadlines are stored in the runtime instead of being recomputed on every view refresh.
- Admin anti-cheat audit endpoint with deterministic review signals: illegal actions, rapid action pairs, disconnects and bot takeovers.
- No automatic cheating ban: signals are evidence for human/admin review.

## Validation
- Python compile check.
- Existing Game Engine suite is expected to remain 61/61; run it in an environment with the project dependencies installed.
- Backend integration tests require the configured async DB driver (SQLite dev uses `aiosqlite`).
