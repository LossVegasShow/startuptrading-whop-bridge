# v7.11 — Whop intake subscription search fix

## Root cause
Read-only member lookup used `/api/v1/memberships?member_id=mber_...` and successfully confirmed the active subscription. Administrator intake, however, used `/api/v1/memberships?user_id=user_...`, and that query returned no matching record in production. This was shown by `Subscription not found for expected Whop user`.

## Fix
The administrator intake now enumerates memberships scoped to the approved StartUpTrading business and product through the authenticated Whop API, with strict cursor pagination. It matches the **exact** subscription `mem_...` and Whop user `user_...` locally, then reuses existing eligibility and purchaser-intake validations. If pagination is incomplete, a user differs, or entitlement is unverified, intake stops without a database write.

## Deployment
Upload only `app.py`, `clients.py`, and the included two updated/new test files into matching paths in the existing GitHub repository. Preserve all other files and the templates folder. Commit to `main`; allow Render to deploy.

Keep `LICENSE_WRITES_ENABLED=false` and don't change secrets. Once Live, revisit `/admin-test/intake?membership_id=mem_cBxTHc4Aun0q90&expected_user_id=user_ibzJP8GE1TE32` in your authenticated admin session and submit once. Successful response shows `customer_record_exists:true`, `user_matches_expected:true`, and `license_rows:0`.

This intake verification creates an internal record of the real paying customer in PostgreSQL; it does not send them an email or grant/alter indicator licenses. The actual webhook-intake path still uses a separate API detail request and requires later end-to-end validation.

73 local tests passed; the changed code has not been verified against the deployed live Whop API yet.
