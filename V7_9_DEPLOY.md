# v7.9 — Verified purchaser intake

Deploy the 2 changed files `app.py`, `tests/test_v7_9_intake.py` at their existing repo-relative paths. Do not remove templates or other files.

**Safety:** `LICENSE_WRITES_ENABLED=false` required. No NinjaTrader license is created, updated, or expired by this tool. No activation email is sent.

1. Sign in at `/admin-test/login` using the allowlisted operator Whop identity.
2. Open `/admin-test/intake` in the same browser.
3. Enter the actual **subscription** ID (`mem_`, not `mber_`) and its Whop `user_` ID.
4. Submit once. Expect `customer_record_exists: true`, `user_matches_expected: true`, `license_rows: 0`. A CRM outbox status of `pending` is expected until GHL is connected.
5. Submit again to confirm `result: updated` with no duplicate record.

This tests actual buyer intake, **not** the customer's login or code verification. Only the customer (or an authorized controlled test account) can complete email verification. Never use an unrelated paid subscriber for destructive license tests.
