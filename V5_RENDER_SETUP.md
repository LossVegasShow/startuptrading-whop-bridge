# v5: One update, two integrations

This update preserves your working Whop OAuth and restricted admin preview. No new Whop developer app or new membership product is required.

## 1. Database first (before deploying the patch)

In Render, create a PostgreSQL database within the same workspace/project if available. You can use a free database temporarily for disposable test data only: free instances expire after 30 days and aren't appropriate for live subscribers. Copy its **internal database URL** to your web service's private Environment variables:

- `DATABASE_URL` = internal PostgreSQL connection URL
- `REQUIRE_PERSISTENT_DB` = `true`

Do not paste the URL into ChatGPT or GitHub. Preserve the existing Whop OAuth/administrator variables and keep `LICENSE_WRITES_ENABLED=false`.

Important: v5 will initialize its tables automatically at startup. Do not switch an existing production SQLite customer database to Postgres without a migration plan. This project has only been used for testing so far.

## 2. Email (optional until test database is connected)

Create a Resend account and verify a sender domain. In the same Render service Environment variables, add:

- `RESEND_API_KEY` = secret API key
- `RESEND_FROM` = verified sender, for example `StartUpTrading <verification@your-verified-domain.com>`

Don't use an invented domain: it must be one you've verified in Resend. Resend email is sent by HTTPS; SMTP configuration can remain blank.

## 3. Apply the update

Update these existing files at the repository root: `app.py`, `config.py`, `store.py`, `requirements.txt`, `.env.example`, `README.md`; add `tests/test_persistence_email.py` and `V5_RENDER_SETUP.md`. Keep the existing `static/` and `templates/` folders unchanged.

Push to `main`. Render will redeploy. Confirm **Live**, then test the current admin preview; it should still work. The `/health` route is intentionally minimal and does not expose secrets.

## 4. Next real test

With persistent DB + real verified-domain email configured, use an approved test membership (not just business-admin access), send/verify one test account email, and inspect whether the verified mapping survives a Render redeploy. Keep licensing writes disabled until that test is complete.

## Do not do yet

Do not turn on customer provisioning, invite existing subscribers, or publish this as a finished production service. The event-processing model and DB concurrency/reliability still need hardening, including job locking and duplicate-account protection across workers.
