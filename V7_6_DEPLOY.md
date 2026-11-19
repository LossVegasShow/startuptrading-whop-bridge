# v7.6 — Read-only member-to-membership lookup

Upload `app.py`, `member_lookup.py`, and `tests/test_member_lookup_v7_6.py` from the patch to GitHub at their correct relative paths, then allow Render to deploy.

While signed in to the restricted Whop administrator preview, open:

`https://startuptrading-whop-bridge.onrender.com/admin-test/member-lookup?member_id=mber_1b6K65ghZrnuv&expected_user_id=user_ibzJP8GE1TE32`

It returns the corresponding `mem_` membership(s), eligibility result, and whether a customer row already exists. It never creates or changes records or licenses. If the member has no matching product subscriptions, `results` is empty. The query is restricted to the configured Whop business and product; no credentials are returned.

**Important:** `mber_` is a Member ID, not a subscription Membership ID (`mem_`). Keep `LICENSE_WRITES_ENABLED=false`.
