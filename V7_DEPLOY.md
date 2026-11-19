# v7 — End-to-end licensing engine (TEST ACCOUNT ONLY)

This release implements the Whop-authoritative reconciliation lifecycle for NinjaTrader products 2067, 2071 and 2205. Whop membership dates are fetched live; no inferred 30/365 day entitlements. It handles creation, renewal, cancellation-at-period-end (access remains through paid-through), expiry, duplicate detection, persisted ownership IDs, and automatic retry after API failures. A database lease prevents parallel reconciliation for the same customer.

## Deploy: one patch, one Render deployment

1. Replace the patch files in the existing GitHub repo with matching paths and push `main`.
2. Keep `LICENSE_WRITES_ENABLED=false`. Set `RUN_RECONCILER=true` (default). Keep `DATABASE_URL` and `REQUIRE_PERSISTENT_DB=true`.
3. Add `WHOP_WEBHOOK_SECRET` **only after** configuring the Whop webhook to `https://startuptrading-whop-bridge.onrender.com/webhooks/whop`, using webhook signing secrets from Whop. Never paste credentials into chat.
4. Add NinjaTrader vendor credentials `NT_USERNAME`, `NT_PASSWORD`, `NT_CID`, `NT_SEC` once ready (secrets go in Render, never GitHub). Vendor trading permissions must be disabled.
5. To perform the **single test membership** end-to-end, set `ALLOWED_TEST_EMAIL` and `ALLOWED_TEST_MEMBERSHIP` to the exact verified test NinjaTrader email and eligible Whop membership ID. Only then set `LICENSE_WRITES_ENABLED=true`. This mode is restricted to that single membership+email, and must return to false after the test.
6. An actual member signs in through Whop and enters their NinjaTrader email. Email verification is required before any writes. When verified, reconciliation runs; scheduled retries happen every five minutes by default and read the latest Whop data.

## Limitations / launch blockers

- This build **does not** allow production-wide license writes, intentionally. It must first pass a real live test and API schema/whop webhook payload verification. Do not remove allowlist gates to launch.
- Existing licenses not created by this bridge are **never mutated or claimed**. If an API write succeeds but the response or local DB save fails, reconciliation requires operator review rather than blindly issuing a duplicate.
- Webhook event schemas for payments may not provide membership IDs; periodic database reconciliation is the backstop. Signed webhook verification is in place but must be configured on Whop.
- The reconciler runs in the Render web-service process; run **one Uvicorn worker and one Render instance** for this iteration. A dedicated queue worker and proper locking are recommended before scale-out.
- Free Render web services may sleep; scheduled reconciliation pauses during sleep. Use an always-on service or external scheduler before production. Free Render Postgres expires after 30 days.
- Resend test sender is not for real customers; configure a verified domain for production.
- Test the exact live Whop response fields; membership and period naming may change with API version. This engine fails closed when required values are missing.
