# Phase 4 — Spectator + Fairness + Anti-Cheat Observability

Implemented:
- Live spectator registration with unique DB membership.
- REST spectate/leave/list endpoints.
- WebSocket spectator subscription.
- Public spectator projection never exposes player hands or legal-card lists.
- Server-authoritative fairness commitment generated before play.
- Seed + nonce reveal only after a finished game.
- Public fairness verification endpoint.
- Game-created event now records the commitment rather than the secret seed.
- Malformed and illegal actions are recorded as audit GameEvents for moderation/anti-cheat analysis.
- Spectators are included in normal game broadcasts through the existing connection manager.

Validation:
- Python compile and engine tests are required after packaging.
- Integration tests still depend on the environment's aiosqlite setup.
