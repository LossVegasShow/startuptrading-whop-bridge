# v7.8 — Whop variant entitlement compatibility

The current Whop membership API uses `variant_id` for the purchased `plan_` identifier. v7.8 now accepts `variant_id`, legacy `plan_id`, and nested `plan.id` only when consistent. The optional secondary source is the payment API, restricted to the exact membership, business, user, paid status, and product line item. Conflicts, missing evidence, API failures and unsupported variants fail closed.

Upload the patch files to GitHub at matching paths. Do not delete `app.py`, `templates/index.html`, or other existing files. `LICENSE_WRITES_ENABLED=false` must stay set. Re-run the read-only member lookup and inspect `plan_id`, `plan_source`, `eligibility_reason`. A payment fallback may require `payment:basic:read` in the Whop API key. Missing permission does not authorize access.

**Never run real licensing against the paying customer's membership or account without authorization.**
