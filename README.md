# StartUpTrading · Independent Whop ↔ NinjaTrader Licensing Bridge

**Deliverable: executable source project, not a published app.** Built using existing confirmed StartUpTrading IDs and the NinjaTrader API contract from vendor support. The interface, database, API clients, onboarding, signed webhook receiver, and guarded synchronization engine are included. Do not assume live API interoperability has been tested in this package: the automated tests are offline.

## One-time Windows start

1. Extract the ZIP to a new folder (not inside an older v1-v3 folder).
2. Double-click `START_WINDOWS.bat` (Python 3.11+ required). It installs dependencies and opens `http://127.0.0.1:8000`.
3. Edit the generated `.env` file in Notepad. Set `ADMIN_PASSWORD` to a **new, random, long** password. Restart `START_WINDOWS.bat` after editing.
4. Admin dashboard: `http://127.0.0.1:8000/admin`, username `admin`, password set in `.env`.
5. Double-click `TEST_WINDOWS.bat` to run the offline tests.

**Keep all credentials in `.env`, never in screenshots or chat. `.env` is excluded by `.gitignore`.** For production use managed secrets; do not store vendor trading-account credentials with trading permissions.

## Integrate directly with the existing Whop product

There is **no replacement checkout or new paid product**. The existing StartUpTrading Whop product and its two price plans remain unchanged.

**Preferred integration method: Whop member content → hosted activation app → Whop OAuth sign-in.** This is implemented in source code, but live OAuth authorization has not been exercised because the required app OAuth credentials are private. A secure one-time invitation remains available as an operator fallback.

1. Host this application on a stable HTTPS URL (`https://activate.your-domain.com`). Set `PUBLIC_BASE_URL` to that URL.
2. In Whop → Developer → Webhooks, edit the existing `StartupTrading-NinjaTrader-Licensing` webhook endpoint to `https://activate.your-domain.com/webhooks/whop`. Use the matching `ws_` secret in `WHOP_WEBHOOK_SECRET`. Do **not** use the old Cloudflare quick-tunnel URL in production.
3. In **Whop → Developer → Apps**, register an OAuth app for the existing business, enable `oauth:token_exchange`, and set the allowed callback to `https://activate.your-domain.com/oauth/callback`. Add its `WHOP_CLIENT_ID` and `WHOP_CLIENT_SECRET` to secure configuration. Our `/oauth/login` route implements Whop OAuth PKCE, CSRF state, nonce correlation and userinfo verification. It then uses the company read-only API key to find the user's eligible StartUpTrading membership by `user_id`.
4. Keep the existing $99/month and $495/year checkout plans and Discord app. Add a members-only **Activate Your Indicators** link to `https://activate.your-domain.com/` in the existing Whop member navigation/content. Buyers click **Sign in with Whop**, returning to the two-path NinjaTrader onboarding page. This is not a second purchase or StartUpTrading registration. Test OAuth with a real eligible test membership before public use.
5. **Fallback if OAuth setup is blocked:** in `/admin`, enter a real Whop `mem_` ID and purchaser email from Whop and issue a one-time invitation. Send that invitation privately to the matching purchaser only; do not post it publicly. Buyer email control is verified by OTP.

Whop company ID: `biz_a1txPozoELC3Yc`  
Whop product: `prod_Nr8ggb93WCyC1`  
Monthly plan: `plan_qSXeS0xoDapGU`  
Annual plan: `plan_B84PWLvXemyFX`

## Licensing safety and account paths

Three vendor products: `2067` (ATR Order Automation), `2071` (Trend Scanner & Market Selector), `2205` (TSMS & Fibs). No other products will be managed.

Customer chooses (a) existing NinjaTrader account, or (b) create an account using the **configurable** NinjaTrader registration/referral link and return. Jack's affiliate arrangement is unconfirmed. Do not claim commission or invent his link. A missing referral URL uses NinjaTrader's official account page.

Whop `GET /api/v1/memberships/{mem_id}` is used to fetch `account.id`, `product_id`, `variant_id`, `status`, `user_id`, and `current_period_end`. Any mismatched account/product/plan, inactive status, or absent/expired period fails closed. Never guess paid-through dates from plan durations. Memberships scheduled to cancel but currently entitled are still eligible. Missing or uncertain membership status triggers review rather than blind expiration.

Vendor tokens come from `POST https://demo.tradovateapi.com/v1/auth/accesstokenrequest`, then the app uses `GET/POST/PATCH` on the verified Ecosystem vendor endpoints with separate `license` (POST) vs `product` (PATCH) JSON wrappers. It handles real `result` values rather than invented objects.

**Default `LICENSE_WRITES_ENABLED=false`. There is NO production write option built into this version.** For a strictly authorized test, set all three `.env` values:

- `LICENSE_WRITES_ENABLED=true`
- `ALLOWED_TEST_EMAIL=the-owned-test-ninjatrader-email`
- `ALLOWED_TEST_MEMBERSHIP=mem_...` (a real eligible owned test membership)

Any other account or membership is **read-only**. Do not use test-only write settings for production rollout. Production rollout needs reviewed controls, actual data/schema verification, incident handling, and hosting hardening first.

## Email verification

Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` for real OTP delivery. Codes expire in ten minutes, can be attempted five times, and are stored hashed in the database. During **local-only** testing, set `LOCAL_DEMO_OTP=true`: the OTP appears in the Python terminal rather than being emailed. Never enable demo OTP on a public deployment. Email OTP confirms access to an inbox, not NinjaTrader account ownership.

## Background jobs and webhooks

Whop webhook signatures use the established `webhook-id.webhook-timestamp.raw_body` HMAC-SHA256 format. Events are persisted with unique IDs. Run queued events via admin; set `RUN_RECONCILER=true` in a **single-worker deployment** for scheduled entitlement polling. Events whose object ID is a payment rather than `mem_` are flagged `needs_mapping` rather than blindly acted on. For production, use a dedicated job queue with explicit mapping, retries and alerts, and move to managed PostgreSQL rather than multiworker SQLite.

## Production limitations and checklist

- **No production deployment was performed.** The package runs locally and is designed to deploy behind HTTPS and a reverse proxy, but cloud infrastructure is not supplied.
- Whop **OAuth sign-in and member lookup are implemented**; they still require creating an OAuth app in Whop and real sign-in testing. An iframe-embedded Whop app is not supplied; the member uses a branded hosted activation link from inside the existing Whop membership.
- Real Whop API read and NinjaTrader test-account licensing must be checked using **your own private credentials**, which are not in this project.
- Email SMTP delivery, real paid membership onboarding, Whop cancellation webhook mapping and NinjaTrader Desktop enforcement need real-world verification.
- The v4 admin uses HTTP Basic: it **must be behind HTTPS and additional network/access controls** in production. Do not expose it from a temporary tunnel.
- For real customer scale, move persistent state from SQLite to managed PostgreSQL, add a durable worker queue, backups, security review and monitoring.
- For deeper native integration inside Whop's app sidebar rather than a member link, add the required Whop app-installation wrapper and verified embedded-app identity. The current OAuth link integration is the portable fallback and can be placed in existing Whop Content/Courses without altering checkout. Never trust user-supplied member IDs.
- Do not enable live production license writes until durable auditing, crash-safe retries, end-to-end real tests and approval from Jack are in place.

## Code map

- `app.py`: customer/admin HTTP routes, Whop OAuth PKCE, email verification, webhook receiver
- `config.py`: verified product and plan identifiers, environment configuration
- `clients.py`: Whop and NinjaTrader REST clients
- `engine.py`: guarded entitlement reconciliation and license updates
- `store.py`: SQLite customer records, licenses, OTP state, events, audit log
- `security.py`: signed webhook verification, random token hashing, admin login
- `templates/` and `static/`: branded customer and operator interfaces
- `tests/`: offline contract and security tests

## Development workflow

Make changes on a branch and open a pull request; do not upload files through the GitHub web UI. `.github/workflows/tests.yml` runs `python -m pytest` and a Docker build on every pull request. Configure Render to auto-deploy `main` only after CI passes. See `PLAN.md` for the launch plan.

No Whop product, customer, price, or license was modified while building and testing this ZIP.

## Hosting

A `Dockerfile` is included for a single-worker container hosting service. Point a permanent HTTPS domain at the app, configure environment secrets, and mount a persistent volume at `/app/data`. This is **not a fully hardened production deployment**: use protected admin access, a reviewed backing database/queue, TLS reverse proxy, logging and backups.

## v5: Hosted persistence and email verification

This version adds optional PostgreSQL (`DATABASE_URL`) and Resend HTTPS email delivery (`RESEND_API_KEY`, `RESEND_FROM`). Local development continues to use SQLite when `DATABASE_URL` is absent and `REQUIRE_PERSISTENT_DB=false`.

For a hosted service with real customer records, set `REQUIRE_PERSISTENT_DB=true`. The application refuses to start without a configured PostgreSQL URL; Render's free web-service filesystem is ephemeral and should never be used for actual customer verification records.

**Deploy sequence:** Provision a PostgreSQL database first and save its connection string directly in Render's private Environment variables, then apply the v5 patch to GitHub. Do not include credentials in GitHub or screenshots. Render Postgres free databases expire after 30 days and are appropriate only for temporary, disposable tests. A paid or otherwise durable Postgres service with backups is required before handling production customer records.

For email verification, set up a verified sending domain in Resend, obtain a restricted API key, and add `RESEND_API_KEY` and `RESEND_FROM` as secret environment variables. The app sends a six-digit code over the Resend HTTPS API instead of SMTP when configured. When neither Resend nor SMTP is configured, verification is unavailable; the admin-preview UI still works. On Render's free tier, SMTP ports may be unavailable.

Retain `LICENSE_WRITES_ENABLED=false`, `LOCAL_DEMO_OTP=false`, and `RUN_RECONCILER=false` during initial setup. Do not enable automatic reconciliation or customer provisioning until authoritative Whop membership handling and live test-member controls have been reviewed.

**Validation performed:** Local pytest suite passed (18 tests); no live PostgreSQL connection, Resend send, or Whop/NinjaTrader provisioning was performed. Before production, perform a real database persistence/restart test and a verified-domain Resend delivery test using a designated test mailbox.
