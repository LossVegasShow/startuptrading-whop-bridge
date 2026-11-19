# v7.5 — Automatic Whop purchaser intake

Deploy this patch to the existing GitHub repository (preserve paths), then let Render rebuild.
No new credentials or environment variables. Keep `LICENSE_WRITES_ENABLED=false`.

## What changes
- A valid signed Whop membership event now triggers an authenticated Whop membership lookup.
- Eligible StartUpTrading buyers are recorded before their first activation visit.
- Their CRM change is queued in PostgreSQL even when GoHighLevel is unconfigured.
- Customer email comes from Whop's authenticated API only; a missing email triggers retry rather than inventing a customer.
- Existing buyer records are reused; ownership conflicts stop the sync.
- Invoice/payment events without a membership ID stay `needs_mapping` and do not create records. These require additional mapping support, if payment-only events are expected.
- The user must still authenticate with Whop, verify the NinjaTrader address, and meet restricted licensing rules before any licenses can be issued.
- Fixes an existing seven-arguments-for-eight-columns bug in `/admin/invite`.

## Preconditions
`WHOP_WEBHOOK_SECRET`, `WHOP_API_KEY`, `DATABASE_URL`, and `RUN_RECONCILER=true`.
A valid webhook must be delivered from Whop to the Render URL. Check `/admin` for event and customer rows. The v7.3 diagnostic checks secret configuration, **not** actual webhook delivery.

## Limitations
- This is not a historical bulk-import of all Whop members: it covers eligible membership webhooks received after deployment and customers who sign in.
- A user email missing from both the Whop membership and user API needs investigation in Render logs.
- Full activation, real sends, CRM writes, and customer-facing installation directions still require live validation.
- Live licensing remains off by default, with allowlisted test membership restrictions.
