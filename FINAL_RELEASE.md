# Hokm Telegram Mini App — Final Release Candidate

## Scope
This package consolidates the implemented foundation through Phase 9. It is an honest release candidate, not a claim that every item in the original 200-point vision is complete.

## Implemented
- Server-authoritative deterministic classic 4-player Hokm engine
- Action idempotency and privacy-safe player views
- Telegram init-data authentication and JWT sessions
- Rooms, matchmaking, WebSocket gameplay and reconnect handling
- Ratings, XP, streaks, rewards, missions and achievements
- Coins, inventory, cosmetics and daily rewards
- Gems, premium economy, Battle Pass and VIP scaffolding
- Telegram Stars purchase-intent/fulfillment boundary
- Friends, blocks, notifications, presence and profile settings
- Clubs and tournament lifecycle
- Tournament/game integration, entry fees and idempotent prizes
- Spectator lifecycle with hidden hands
- Fairness commitment/verification and anti-cheat observability
- Expert bot with deterministic simulation-based decisions
- Variant catalog with fail-closed handling for unfinished variants
- Mini App pages for core gameplay, economy, premium, clubs and tournaments
- Iranian visual theme, responsive RTL UI, lightweight 3D-like card/table effects and reduced-motion support

## Explicitly not claimed as complete
- Independent production-ready engines for 2-player, 3-player, Shelem and Nares
- Full React Three Fiber 3D renderer and physics-grade card interaction
- Final custom Iranian card-art asset pack and professional audio/music pack
- Production Redis-backed distributed rate limiting/session coordination
- Full tournament operations dashboard and payment-provider webhook integration

## Verification performed in this environment
- Game-engine tests: 71 passed
- Python compileall: passed
- Archive integrity: passed
- Backend integration tests are environment-dependent and require the project's database test dependency (`aiosqlite`) to be installed.
- Mini App production build requires Node dependencies (`npm ci`) in the target build environment.

## Security packaging
- `.env` files and secrets are excluded from this release archive.
- `.env.example` is included as configuration documentation.

## Completion update — Variant gameplay
- Playable 2-player Duel engine with deterministic 52-card deal, 26-card kitty, winner-first draw order, trump selection, follow-suit enforcement, full-match resolution, privacy-safe views and snapshots.
- Playable 3-player Hokm-family engine with deterministic 51-card deal (2C removed), independent player scoring, trump selection, follow-suit enforcement and full-match resolution.
- Backend GameService accepts `variant` in game configuration and uses the appropriate engine for classic/duel/three-player games. Duel and three-player games use independent rating opponents; tournament progression remains classic 4-player only.
- Shelem and Nares remain explicitly disabled because their regional/product rules need a signed-off ruleset before implementation; they are not silently mapped to classic Hokm.
