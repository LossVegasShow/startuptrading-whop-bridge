# StartUpTrading: safe deployment process

## Do not overwrite production blindly

This is an **audited release candidate**, NOT a verified checkout of the latest private GitHub `main` or a certified live launch release. Do not enable license writes. Diff it with current `main` before merging.

1. Download the full-source ZIP and preserve it as a backup; never delete application files while patching.
2. Create a new Git branch, e.g. `audit/rc1`, based on the latest `main`.
3. Compare the candidate against the current repository. Copy only reviewed changes (or use the patch ZIP).
4. Check that `.github/workflows/ci.yml` is present and that GitHub Actions runs `release_check.py` plus all pytest tests.
5. Confirm `app.py`, `clients.py`, templates, static assets, and other application modules are present.
6. Merge after CI passes, then inspect Render's deployment commit SHA.
7. Test `/` and `/health`, admin preview, read-only member lookup, and webhook delivery with license writes **disabled**.
8. Keep the previous working commit available for rollback. Never deploy partially uploaded files.

## Unresolved before production

- Actual signed Whop membership event ingestion and email availability on real events.
- Verified entitlement/identity to DB record and then to real NinjaTrader license lifecycle (owned test account only).
- Always-on reconciliation worker and production-grade, backed-up Postgres; free instances are unsuitable for subscription enforcement.
- Email sender domain, guide URL, support contact, delivery status monitoring.
- NinjaTrader license-recovery runbook (network timeouts after create/update) and alerting.
- Database migrations, rate limiting, operational security review, privacy policy and access controls.
- GoHighLevel connection when available.

## Never do these during testing

- Enable production-wide license writes.
- Reconcile or expire licenses belonging to an unconsenting paying customer.
- Paste secrets into chat, source files, or screenshots.
- Treat an HTTP 200 webhook receipt as proof of complete license provisioning.
