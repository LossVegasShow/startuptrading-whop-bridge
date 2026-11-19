# v7.4 — Optional GoHighLevel CRM + activation emails

Upload the patch, preserving root paths. No new credentials are required to deploy.

## GoHighLevel (optional, later)
Set both `GHL_API_KEY` (Private Integration Token) and `GHL_LOCATION_ID` in Render. Until both are present no GHL requests are made; CRM changes are coalesced in the persistent database for later synchronization. `GHL_CUSTOM_FIELDS_JSON` is an optional mapping between named fields and your GHL custom-field IDs, for example `{"whop_membership_id":"YOUR_GHL_FIELD_ID","activation_status":"YOUR_FIELD_ID"}`. Only configured custom fields are written, avoiding corruption of existing CRM tags/data. Never put secrets in GitHub.

## Activation confirmation email
Set `INDICATOR_SETUP_URL` to the official HTTPS StartUpTrading download and installation guide, `SUPPORT_EMAIL` if desired, and ensure existing `RESEND_API_KEY` and `RESEND_FROM` work for real customer recipients (verified domain). The email is *queued only after all 3 bridge-owned licenses have been recorded* with the current Whop entitlement period; no activation email when writes are disabled. It sends to the **verified NinjaTrader email**, not necessarily the Whop purchase email. Provider message IDs and retry state are saved. Resend API success means accepted for delivery, not proof of inbox delivery.

**Important:** The worker currently runs on a single instance (`RUN_RECONCILER=true`). Do not scale multiple workers until distributed locking is added. Account discovery of entirely new webhook customers still depends on Whop OAuth sign-in / invitation; this release does not import every signup directly from event payloads. No real API integration tests performed.

Keep `LICENSE_WRITES_ENABLED=false` until the membership allowlist and controlled live test are ready. Existing tests can be run with `python -m pytest -q`.
