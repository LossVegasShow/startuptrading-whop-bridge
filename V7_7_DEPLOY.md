# v7.7 Entitlement Resolution Patch

Upload all patched files at the same relative paths to the existing GitHub repository. **Do not delete `app.py`, `templates/index.html`, or any other existing files.**

Whop membership list responses that omit `plan_id` now trigger an authoritative direct membership detail request. Explicit direct and embedded `plan.id` values are validated; conflicting or unknown plans fail closed. CRM purchaser intake, OAuth and licensing reconciliation use the same normalized plan identity. The admin lookup now reports `plan_source` and `eligibility_reason`.

Keep `LICENSE_WRITES_ENABLED=false`. After deploy, repeat the read-only member lookup. This patch does not write customer records or licenses on that endpoint. If the detail response still omits a plan ID, the result remains ineligible until a verified payment/plan relationship is identified.
