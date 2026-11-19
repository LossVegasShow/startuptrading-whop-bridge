# StartUpTrading consolidated audit — release candidate 1

## Scope and evidence
Source inspected: **local v7.12** build supplied in this conversation, not a verified checkout of the current private GitHub `main`. Previous production screenshots established the live Whop member lookup, a real eligible plan, vendor access, database connectivity, and signed webhook acceptance. **No live licensing transaction is verified.**

## Critical release blockers
1. **Inconsistent Whop membership retrieval:** OAuth relied on `user_id` filtered listing, admin intake used `member_id`, webhook and reconciliation used direct membership details. Live evidence showed different results. RC1 routes all normal membership retrieval through an unfiltered, paginated, locally verified business/product listing; uncertain or incomplete pagination fails closed.
2. **Background service reliability:** `RUN_RECONCILER` runs only while the Render app is awake. Free Render sleeping means missed or delayed license synchronization. This is **not solved by RC1**. Require always-on worker/scheduler and durable Postgres before launch.
3. **Real customer lifecycle remains untested:** No controlled end-to-end activation, expiry, renewal, verified email delivery or actual NinjaTrader Desktop enforcement. RC1 is not approved for production license writes.
4. **Email intake completeness:** Whop user profile API may omit email; the existing purchaser auto-intake then fails closed. Need supported contact data path verified against actual API before claim of automatic import.
5. **Account linkage email verification proves inbox control, not NinjaTrader account ownership.** Vendor API availability and customer install experience must be verified.

## High findings
- Administrator session lasted 1 hour regardless of deployment. RC1 expands to 8 hours (security expiry retained).
- Missing templates and accidentally deleted `app.py` caused actual Render failures. RC1 adds startup template checks, static release gate, and GitHub CI.
- The preview page/diagnostics return JSON for operator tests; not a customer-facing dashboard. Intentionally unchanged.
- Activation email status 'sent' means Resend accepted the email, not delivery to inbox; ensure webhook-based delivery tracking and support workflow.
- On untracked NinjaTrader API create timeout, reconciliation refuses further auto-create to avoid duplicates; manual recovery runbook needed.
- Admin basic-auth controls and write-mode operator actions need stronger deployment policy, origin protection and operational audits before launch.
- Repeated database DDL on each database connection adds overhead; migrate with a versioned DB migration tool before scale.

## Corrected in RC1
- Centralized Whop membership listing with exact business/product/ID verification and bounded complete pagination; shared by OAuth, intake and reconciliation.
- 8-hour administrator session instead of 1 hour.
- Startup fail-fast for missing critical HTML templates and incomplete license-write allowlist.
- Repository integrity script, CI workflow, and new regression tests.

## Required launch gates
- Check exact private GitHub repository at current `main` against this source; user must review changes before merge.
- A real verified paid/test member completes onboarding and receives all three licenses; check vendor license IDs and desktop access.
- Simulate renewal, cancellation and expired membership against real Whop event payloads and verify revoke behavior; no customer's live license changes without authorization.
- Durable always-on reconciliation and monitoring/alerts for retries and failures.
- Verified sender domain, actual install guide, customer support details, CRM settings when available.
- Deploy to staging, run smoke suite, then promote exact commit with rollback plan.

**Release status: NOT PRODUCTION READY.** Keep `LICENSE_WRITES_ENABLED=false`.
