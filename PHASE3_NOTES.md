# Phase 3 — Premium Economy

Implemented on top of Phase 2:

- Gem wallet + append-only gem ledger with idempotency.
- Monthly Battle Pass season with free/premium tracks, XP progression and claim protection.
- Premium Pass unlock using gems.
- VIP subscription entitlement model with 30-day Telegram Stars product.
- Telegram Stars purchase-intent records with unique payloads.
- Trusted server-side fulfillment endpoint protected by `HOKM_TELEGRAM_PAYMENT_WEBHOOK_SECRET`.
- Gem packs and VIP product catalog.
- Mini App premium screen for gems, Battle Pass and VIP state.

Important payment boundary:

The browser never marks a Telegram Stars purchase as paid. The backend creates a purchase intent and a trusted Telegram Bot/payment worker must call the internal fulfillment endpoint after Telegram confirms the payment. No fake payment success is exposed to the client.

Validation:

- Python compile: passed.
- Game engine tests: 61 passed.
- Backend integration tests still require the environment's `aiosqlite` dependency/database setup.
- Mini App build/typecheck requires installed Node dependencies; this workspace does not include `node_modules`.
