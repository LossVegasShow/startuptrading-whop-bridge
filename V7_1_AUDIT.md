# v7.1 audited API compatibility patch

### Verified corrections (November 19, 2026)
- Whop membership objects use `plan_id`, not the v7 `variant_id`. Scheduled cancellations retain `status=active` and set `cancel_at_period_end=true`; `canceling` is a list filter, not a membership billing state.
- NinjaTrader docs now describe `GET /v1/licenses/vendor` with product-keyed `result`, `POST /v1/licenses/vendor` with `productIds` and list of license IDs, and `PATCH /v1/licenses/vendor/{licenseId}`. v7 used older product-specific routes. These are replaced in `clients.py`.
- 3 regression tests assert these published formats.

### Tested
Automated tests pass locally with faked Whop and NinjaTrader responses. No production credentials were read or used; no external customer data was read; no real license was created, updated, or expired.

### Remaining launch blockers
- Confirm actual Whop OAuth/list and membership response via read-only requests; this patch relies on documented schemas.
- Confirm Whop event delivery and correct signature via its dashboard delivery test.
- Confirm NinjaTrader authorization and listing over real vendor credentials; no writes until single test membership is authorized and verified.
- Persistent Postgres, Resend sending, and live worker behavior require hosted checks.
- The free Render instance sleep and expiring free database are not production suitable.

**Keep LICENSE_WRITES_ENABLED=false.** No additional environment variables required to apply this patch.

References: https://docs.ninjatrader.com/marketplace/products-and-licenses ; https://www.withone.ai/knowledge/whop/conn_mod_def::GN5czuGw-HA::uGyueFoWQFuuItj4b-UfcA
