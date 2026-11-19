# v7.10 — Intake path consistency fix

The read-only member lookup succeeded because Whop's list endpoint returned `variant_id`. The administrator intake route then independently called the subscription-detail endpoint and returned `Whop lookup could not be verified`. This release makes admin intake reuse a separately authenticated list result selected by exact `mem_` subscription ID and expected Whop `user_` ID, and validates active entitlement, business, product and approved plan before creating the record.

Upload `app.py`, `purchaser_intake.py`, and the two `tests/` files into the existing GitHub repository, preserving paths. Do not delete existing templates, modules or tests.

Keep `LICENSE_WRITES_ENABLED=false`. After Render deploy, use the existing `/admin-test/intake?membership_id=...&expected_user_id=...` page and submit. Expect a created/updated PostgreSQL record and 0 license rows. This administrative intake test does not send activation emails or link NinjaTrader accounts. Automated webhook intake still uses its independent detail-fetch path and must be validated separately.
