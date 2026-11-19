# Phase 3: live lifecycle test runbook

Goal: prove, with **one real test membership and one real NinjaTrader
account**, that indicator licenses follow Whop membership status through every
lifecycle event, inside NinjaTrader itself.

Works on the current address (`https://startuptrading-whop-bridge.onrender.com`).
It doesn't need DNS or GoHighLevel access.

The same steps run offline in `tests/test_phase3_rehearsal.py`, so every
expected result below has already been checked against the code.

---

## 0. What you need before starting

| Item | Who | Notes |
|---|---|---|
| **Test Whop membership** (`mem_…`) | Jack / Whop admin | A real membership on product `prod_Nr8ggb93WCyC1`, monthly plan. Cheapest route: a 100%-off promo code on the monthly plan, or a real purchase refunded at the end. Note its `mem_` ID. |
| **Test NinjaTrader account** | Jack | A NinjaTrader login you control, on a Windows PC with NinjaTrader 8, whose email inbox you can open. **Not** a customer's account. |
| **NinjaTrader vendor answers** | Vendor contact | See section 5. At minimum, confirm the token endpoint (demo vs live) before step 3. |
| **Render access** | You | To set environment variables and read logs. |
| **Whop dashboard access** | You / Jack | To cancel, expire and restore the test membership. |
| **Transactional email** | You | `RESEND_API_KEY`, `RESEND_FROM` (verified domain), `INDICATOR_SETUP_URL`. Without these the code and activation emails can't send. |

## 1. Configure Render for the test

In Render → `startuptrading-whop-bridge` → **Environment**:

| Variable | Value |
|---|---|
| `LICENSE_WRITES_ENABLED` | `true` |
| `ALLOWED_TEST_MEMBERSHIP` | the test `mem_…` ID |
| `ALLOWED_TEST_EMAIL` | the test NinjaTrader account's email |
| `NT_AUTH_URL` | the endpoint the vendor confirms (default is the demo host) |
| `RUN_RECONCILER` | `true` (lets missed webhooks recover) |
| `ADMIN_PASSWORD` | set, long and random |

**Only that one membership + email pair can receive license writes.** Every
other customer stays observe-only, whatever happens.

**Emergency stop at any point:** set `LICENSE_WRITES_ENABLED=false`.

## 2. How to check each step

Open **`/admin`** (username `admin`, your `ADMIN_PASSWORD`), find the test
customer, and click **Snapshot** (`/admin/lifecycle/<id>`). It's read-only. It
shows:

- **`whop`**: status, paid-through date, `entitled`.
- **`write_gate`**: whether writes are allowed for this customer, and why.
- **`ninjatrader.licenses`**: what NinjaTrader actually has for the email.
- **`products`**: per indicator, `ok` or `mismatch`, with the reason.
- **`overall`**: `consistent` means NinjaTrader matches what Whop entitles.
- **`database`**: our license rows, email status, the last 20 audit events.

To apply a change immediately instead of waiting for the reconciler, click
**Reconcile** on the same row.

Record each step in the results table (section 4): snapshot `overall`, what
NinjaTrader Desktop shows, and anything odd.

## 3. The test steps

| # | Action | Expected snapshot | Check in NinjaTrader / inbox |
|---|---|---|---|
| 1 | **Join:** activate the test membership in Whop (promo or purchase). | Customer appears; `whop.entitled: true`. Products show `mismatch: entitled, but no NinjaTrader license exists` until step 2. | Whop receipt email. Discord access granted by Whop. |
| 2 | **Activate:** open the activation page, **Sign in with Whop**, pick "I have a NinjaTrader account", enter the test email, enter the 6-digit code. | `write_gate.allowed: true`. After a few seconds (or **Reconcile**): `overall: consistent`, all three `active until <paid-through>`. `database.emails`: activation `pending` → `sent`. | Verification code email arrives. Activation email arrives **once**. In NinjaTrader 8 (restart it), all three indicators are available and load on a chart. |
| 3 | **Repeat activation:** click **Reconcile** twice and refresh the activation page. | Still `consistent`. Audit shows `ninjatrader_unchanged`, no new `created`. | No second activation email. No duplicate licenses. |
| 4 | **Renewal:** wait for the monthly renewal, or have Jack extend the period in Whop if possible. | Before reconcile: `mismatch` (expiry behind paid-through). After: `consistent` at the new date. | Indicators keep working. |
| 5 | **Cancel at period end:** cancel the membership in Whop, choosing *at the end of the billing period*. | `whop.status: canceling`, `cancel_at_period_end: true`, still `entitled: true`, `overall: consistent`. **No writes.** | Indicators still work. |
| 6 | **Expire:** end the membership now in Whop (terminate / cancel immediately). | Before reconcile: `mismatch: NOT entitled, but the NinjaTrader license is still active`. After: `consistent`, `no active license (expired …)`. | **Key check:** after restarting NinjaTrader, all three indicators are no longer usable. Note how long this took. |
| 7 | **Restore the same membership:** reactivate it in Whop if Whop allows (for example payment recovery or "uncancel"). | `consistent`, `active until <new paid-through>`. Still exactly 3 license rows (reused, not duplicated). | Indicators work again after a restart. |
| 8 | **Rejoin with a new purchase:** after expiry, buy again (new `mem_…`). | **Known gap, see section 6.** Expect the activation page to say the NinjaTrader email is linked to another account. | Record exactly what happens. |
| 9 | **Webhook check:** in Whop → Developer → Webhooks, send a test event. In `/admin`, check webhook deliveries. | Event recorded; no license change for a test event. | — |
| 10 | **Clean up:** set `LICENSE_WRITES_ENABLED=false`. Refund the test purchase if it was paid. | `write_gate.allowed: false`. | — |

**Failure-mode checks** (optional, already covered offline):
- If Whop is unreachable, the snapshot shows `whop.error` and nothing is
  revoked.
- If one NinjaTrader write fails, no activation email is sent until all three
  succeed.

## 4. Results

| # | Date / time | Snapshot `overall` | NinjaTrader Desktop | Notes |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |
| 5 | | | | |
| 6 | | | | |
| 7 | | | | |
| 8 | | | | |
| 9 | | | | |
| 10 | | | | |

**Pass** = steps 1–7 and 9 behave as expected, *and* step 6 shows the
indicators actually stop working in NinjaTrader.

## 5. Questions for the NinjaTrader vendor contact (ask before step 2)

1. Vendor API tokens: should production licensing authenticate against
   `demo.tradovateapi.com` or `live.tradovateapi.com`? (Set `NT_AUTH_URL`.)
2. When a license's `expirationDateUTC` is moved into the past via
   `PATCH /v1/licenses/vendor/{id}`, how quickly does NinjaTrader Desktop stop
   the indicator? Immediately, on restart, or after a cache period?
3. Is updating the expiry the supported way to revoke, or is there a delete or
   disable call we should use instead?
4. Can a license be re-extended after it expires (step 7), or must a new one be
   created?
5. Rate limits on `/v1/licenses/vendor` (we read the full vendor list per
   product on every sync).
6. If a customer changes the email on their NinjaTrader account, what happens to
   licenses issued to the old email?

## 6. Known gap: rejoining with a new membership (step 8)

When a membership fully ends and the person buys again, Whop issues a **new
`mem_…` ID**. The bridge creates a new customer record for it, and then:

- the activation page refuses the same NinjaTrader email ("linked to another
  account"), because the old, expired customer record still holds it; and
- even past that, the engine won't touch the existing NinjaTrader license
  ("not bridge-owned"), because it belongs to the old record.

So **a returning customer can't reactivate without manual support.**

**Proposed fix (needs approval before building):** when a newly verified,
*eligible* membership and an older, *ineligible* customer record belong to the
**same Whop user** (proven by OAuth) and use the same NinjaTrader email,
transfer the email link and license ownership from the old record to the new
one, with an audit entry. Different Whop users would still be refused, so one
person can never take over another's licenses.
