# v6 — Administrator email integration test

This release adds one button to the already working administrator preview. It sends a real Resend verification email **only** to the exact email in `ADMIN_TEST_WHOP_EMAIL` after Whop OAuth authorization. The six-digit code is hashed and stored in PostgreSQL; entering it verifies the mail delivery and database write. It does **not** create customer records or NinjaTrader licenses.

## Update

Replace `app.py`, `store.py`, `templates/admin_test.html` and add `tests/test_admin_email_flow.py` in GitHub. Deploy on Render. No new services, credentials, or Whop apps required if the v5 environment is already configured.

Render environment must include `RESEND_API_KEY`, `RESEND_FROM` (not `EMAIL_FROM`), `ADMIN_TEST_WHOP_EMAIL`, `ADMIN_TEST_ENABLED=true`, `WHOP_CLIENT_SECRET`, `DATABASE_URL`, `REQUIRE_PERSISTENT_DB=true`. Keep `LICENSE_WRITES_ENABLED=false`.

`onboarding@resend.dev` is usable only with Resend's permitted test-recipient restrictions; the admin email must be an authorized test recipient. Otherwise use a verified sender domain.

Open `https://startuptrading-whop-bridge.onrender.com/admin-test` after authorized Whop login. Click **Send test verification email**, then paste the six-digit code into the **Verify test code** field. Success means the code was delivered and its verification was saved. Note: this does not yet prove persistence across a restart; use the same database after redeployment to test that separately.

Never publish customer licensing or enable production license writes on the basis of this test alone.
