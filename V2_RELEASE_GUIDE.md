# StartUpTrading V2 — Customer Experience Candidate

## Purpose and source
Built on **StartUpTrading Audit RC1** source already provided in this conversation, not a fresh clone of the current private GitHub `main`. **Review as a branch; do not deploy this bundle directly to production without comparing it with current `main`.**

## New pages and behavior
- `/`: redesigned responsive public sales page with confirmed indicator names and disclosed monthly/annual prices; approved assets and statements remain absent until supplied. No admin links or implementation controls.
- `/checkout`: redirects to **your actual Whop checkout** only when a valid `WHOP_CHECKOUT_URL` has been configured. Does not create a new checkout or charge; fails closed if missing or not under `whop.com`. This is a handoff, not an embedded checkout.
- `/activate`: existing customer onboarding view, with membership status, NinjaTrader email code flow, license status and resources. The existing `/onboarding` endpoint still functions; old form POSTs remain available. Unauthenticated customers go through existing Whop OAuth and must be eligible.
- `/admin`: existing protected operator interface preserved. `ADMIN_PASSWORD` and server-side credential authorization remain in effect. Legacy `/admin-test` remains private for existing operations but has no links on the public sales page.
- `/health`, OAuth, Whop webhooks, NinjaTrader vendor integration, renewals, outbox, GoHighLevel placeholder, and reconciliation have not been replaced.

## Required commercial assets / approvals — not provided
- `WHOP_CHECKOUT_URL`: **actual existing checkout URL from Whop** (must be HTTPS and hosted under whop.com). Without it, public CTA points to pricing section and does not falsely claim to check out.
- `JACK_PHOTO_URL` and `JACK_BIO_URL`: approved portrait and verifiable bio. No unsubstantiated performance claims or endorsements.
- `INDICATOR_IMAGE_2067`, `_2071`, `_2205`: actual approved indicator screenshots.
- `INDICATOR_DEMO_2067`, `_2071`, `_2205`: approved demonstration URLs.
- `DISCORD_JOIN_URL`, `DIRECT_SUPPORT_URL`: exact member resources / direct access per Jack's offering.
- Existing `INDICATOR_SETUP_URL`, `SUPPORT_EMAIL`: customer installation instructions and support address, needed before activation email can be sent.
- Optional `NINJATRADER_REFERRAL_URL` remains optional and will not be claimed as an affiliate arrangement. Only a URL at `ninjatrader.com` is used for the registration path, otherwise the default official account page.

**Never commit account keys or secrets into these files.** Set URLs via Render environment only once approved.

## Analytics
- Anonymous aggregate `visitor` event on sales-page view.
- `checkout_initiated` logged on `/checkout` redirect (only when checkout is configured).
- `activation_opened` on member activation view.
- `conversion_confirmed` queued once by `import_membership` after a fresh verified eligible Whop membership is imported. This is a *membership entitlement* conversion event, not proof the customer came from a particular page view or clicked CTA. No claim of full-funnel attribution without an approved consent and attribution implementation.
- New persistent table `funnel_events` is additive. No personal IP address/user agent stored in this table.

## Deployment safely
1. Keep `LICENSE_WRITES_ENABLED=false`. Make a new feature branch from latest GitHub main.
2. Copy these files to the matching repository paths **without removing existing files**; compare changes and confirm backend files have not regressed since Audit RC1.
3. `python release_check.py` then `python -m pytest -q`. This candidate passed **85 tests** locally on its source basis.
4. Check root/activate/checkout behavior in staging with `WHOP_CHECKOUT_URL` set to the approved live URL; do not test purchasing without authorization.
5. Verify Whop login for a real eligible test user, NinjaTrader email OTP, remote licensing with a test allowlist, webhook retries, cancellation/renewal and email once after confirmed provisioning.
6. Verify Chrome/Safari/mobile browser rendering, accessibility navigation, keyboard forms, link destinations and approved content. These have **not** been certified by the local test suite.
7. Configure reliable paid hosting / durable database and scheduled reconciler before customer launch.
8. Only after completing launch gates, merge reviewed branch to main with rollback plan.

## Known launch blockers
- Real checkout URL and approved screenshots/demos/bio/support promises not provided.
- Admin currently uses restricted Basic operator access, not a newly designed role-based multi-admin system.
- Full checkout-to-license-to-email live E2E not yet certified.
- Some email ownership validation relies on inbox OTP, not NinjaTrader-side confirmation.
- Full attribution of visitors to purchases is not implemented (aggregate funnel events only).
- No current authenticated Whop app deep link/SSO embed validation.
- Free-tier hosting and DB are unsuitable for a production licensing service.

## Summary
This is a **frontend + routing candidate**, preserving billing and license safety behavior. It is not launch-certified. Do not set LICENSE_WRITES_ENABLED=true as part of V2 deployment.
