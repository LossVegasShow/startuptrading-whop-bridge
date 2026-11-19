# v7.12 — Member-based verified purchaser intake

Fixes the live intake failure `Subscription not found for expected Whop user`. The admin intake form now asks for the Whop Member ID (`mber_`) as well as the exact subscription (`mem_`) and Whop user (`user_`) IDs. The intake fetches from the same `member_id` filtered `/memberships` endpoint as the successful read-only lookup. It validates all identities, business/product, allowlisted plan, status, and expiration; it reuses the verified record for intake without a second API query.

No customer license or activation email is created. Keep `LICENSE_WRITES_ENABLED=false`.

Upload `app.py`, `member_lookup.py`, and the test file without deleting templates or unrelated files. The PATCH ZIP contains precisely those files.

After deployment use:

`/admin-test/intake?member_id=mber_1b6K65ghZrnuv&membership_id=mem_cBxTHc4Aun0q90&expected_user_id=user_ibzJP8GE1TE32`

The action creates or updates the internal record for this real customer; it does not touch their NinjaTrader credentials or subscriptions.
