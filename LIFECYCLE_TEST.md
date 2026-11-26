# Release acceptance test: the complete customer experience

Goal: prove, with **one test purchase and one test NinjaTrader account**, that a
customer can buy, activate, **download and install both products**, use them in
NinjaTrader, and lose and regain them as the membership changes. Licensing runs
for **all members** (the release configuration); no membership-ID allowlist is
used.

A successful license API call is not a pass. A step passes only when the
customer-facing result (email, download, NinjaTrader behaviour) is confirmed.

Audited against the deployed code on 25 Nov 2026 and the live `/health`.
Products, files and NinjaTrader names: `products.json` (the single source).

---

## 0. Release configuration (live now)

`/health` returns `"mode":"all_members"`: `LICENSE_WRITES_ENABLED=true` and
`LICENSE_ALL_MEMBERS=true`. Every ~15 minutes the reconciler syncs up to 100
stored members, and every member who has completed activation is granted,
renewed or expired according to Whop. Members who never activated are not
touched. The circuit breaker (60 grants or 20 revocations an hour, 10 failures in
15 minutes) pauses everything if something runs away.

Clean up the test-only settings in Render → Environment (they no longer do
anything useful in this mode, and must not linger):

| Variable | Set to |
|---|---|
| `LICENSE_WRITES_ENABLED` | `true` |
| `LICENSE_ALL_MEMBERS` | `true` |
| `ALLOWED_TEST_MEMBERSHIP`, `ALLOWED_TEST_EMAIL`, `LICENSE_WRITE_ALLOWLIST` | **delete** |
| `ADMIN_TEST_ENABLED`, `ADMIN_TEST_WHOP_USER_ID`, `ADMIN_TEST_WHOP_EMAIL`, `LOCAL_DEMO_OTP` | **delete** (or `false`) |
| `ACTIVATION_REMINDERS_AUTO` | `false` (release reminders by hand at `/admin/reminders`) |
| `INDICATOR_SETUP_URL` | `https://startuptrading.com/setup` (one row only) |
| `RUN_RECONCILER` | `true` |
| `ALERT_WEBHOOK_URL` | a Discord webhook (recommended) |

The allowlist mechanism stays in the code as a fallback: if you ever need to
narrow licensing again, set `LICENSE_ALL_MEMBERS=false` and list
`mem_…:email` pairs in `LICENSE_WRITE_ALLOWLIST`.

## 1. Audit findings

### 1.1 Render variables that control licensing (exact names, from `config.py`)

| Variable | Values | Effect |
|---|---|---|
| `LICENSE_WRITES_ENABLED` | `true` / `false` (default `false`) | Master switch. `false` stops **every** NinjaTrader write: grants, renewals **and** revocations |
| `LICENSE_ALL_MEMBERS` | `true` / `false` (default `false`) | `true` = every verified, eligible member is licensed. `false` = only the allowlist |
| `LICENSE_WRITE_ALLOWLIST` | `mem_…:email,mem_…:email` | Allowlist pairs. **Both** the Whop membership ID **and** the verified NinjaTrader email must match (email case-insensitive) |
| `ALLOWED_TEST_MEMBERSHIP` + `ALLOWED_TEST_EMAIL` | one `mem_…` + one email | One more allowlist pair (the original single-test settings) |
| `ACTIVATION_REMINDERS_AUTO` | `true` / `false` (default `false`) | `false` = reminders wait for approval at `/admin/reminders` |
| `RUN_RECONCILER` / `RECONCILE_INTERVAL_SECONDS` | `true` / `900` | Background sync (webhook events, then up to 100 members) every 15 min |
| `BREAKER_MAX_GRANTS_PER_HOUR` / `..._REVOCATIONS_PER_HOUR` / `BREAKER_MAX_FAILURES_PER_15MIN` | 60 / 20 / 10 | Circuit breaker limits; tripping pauses all writes until `RESUME` at `/admin` |
| `INDICATOR_SETUP_URL` | must be `https://…` | The "Finish setup" link in the "tools ready" email. **If it isn't a valid https URL, no activation emails are sent at all** |
| `RESEND_API_KEY`, `RESEND_FROM` | set | Email delivery (codes, "tools ready", lifecycle) |
| `NT_AUTH_URL` | default `https://demo.tradovateapi.com/...` | Vendor token host (the demo host worked in the 24 Nov test) |

**Licensing for all members** = `LICENSE_WRITES_ENABLED=true` **and**
`LICENSE_ALL_MEMBERS=true`. `/health` then shows `"mode":"all_members"`.

**`ALLOWED_TEST_MEMBERSHIP_IDS` does not exist.** The implemented allowlist is
`LICENSE_WRITE_ALLOWLIST` (pairs) plus `ALLOWED_TEST_MEMBERSHIP` /
`ALLOWED_TEST_EMAIL`. A membership ID alone never qualifies: the pair must match.

### 1.2 Who can gain or lose a license (verified in `engine.py`, `controls.py`)

With `LICENSE_ALL_MEMBERS=false` (mode `allowlist`):
- Every sync path (webhook, reconciler, the member's own refresh, admin
  Reconcile) goes through `Engine.reconcile`, which returns **before any
  NinjaTrader call** unless the member is verified **and** their exact
  (membership, NinjaTrader email) pair is allowlisted. Grants, renewals, expiries
  and the retired-product (TSMS & Fibs) switch-off are all behind that check.
- So non-allowlisted members receive nothing **and lose nothing**. One consequence:
  a non-allowlisted member who cancels during the test keeps any bridge license
  until its own expiry date (licenses always carry the paid-through date, so
  NinjaTrader still switches them off then).
- Licenses the bridge didn't create (for example one-time purchases) are never
  modified for anyone, in any mode. The only exception is a license on the same
  email that had **already expired**, which the bridge takes over and extends.
- Tests: `test_without_all_members_only_the_allowlist_is_written`,
  `test_restricted_test_touches_only_the_allowlisted_member`.

**New in this release:** `/admin` → **License changes (last 7 days)** lists
every license the app granted, renewed, expired, retired or took over, with the
Whop membership and NinjaTrader email. Use it before the test (to see what
`all_members` mode already did) and after it (only the test membership should
appear).

### 1.3 Product mapping (`config.py`)

| NinjaTrader product ID | Name in the code | In the membership |
|---|---|---|
| 2067 | ATR Order Automation | Yes |
| 2071 | Trend Scanner & Market Selector | Yes |
| 2205 | TSMS & Fibs | **No** (retired: licenses the bridge issued are expired on the next sync) |

The IDs were confirmed live on 24 Nov (licenses 82908 = 2067, 82912 = 2071,
82913 = 2205 on the test account). The **names** are only labels in our code:
check them against the product list in the NinjaTrader vendor portal (P5).

### 1.4 Product delivery (what the customer actually receives)

1. Whop checkout → redirect to `startuptrading.com/welcome` → **Activate my trading tools**
   → `activate.startuptrading.com`.
2. **Sign in with Whop** → a code to the Whop purchase email → NinjaTrader email →
   a code to that inbox → licenses are written to that NinjaTrader account.
3. When **both** indicators are licensed to the paid-through date, one
   **"Your tools are ready"** email is queued (`store.queue_activation_email`).
   It goes to the NinjaTrader email and links to `INDICATOR_SETUP_URL`.
4. `/setup` has a download button for each product, then: import each .zip
   (*Tools → Import → NinjaScript Add-On*), restart, and add them to a chart.

**Downloads:** the product files are proprietary and never committed (the GitHub
repository is public). An admin uploads them once at
`https://activate.startuptrading.com/admin/products`; they're stored in the licensing
app's database (accepted only if the SHA-256 matches `products.json`) and served at
`/downloads/<file>` **only to signed-in members with an active paid membership**.
Anyone else is sent through Whop sign-in first and returned to the download. `/setup`
links to those URLs:

| ID | Product | File | Appears in NinjaTrader as |
|---|---|---|---|
| 2067 | ATR Order Automation | `SUT_ATR_Orders_2026.zip` | **SUT ATR Orders** (Strategies → StartupTrading) |
| 2071 | Trend Scanner & Market Selector | `StartupTrading_Tools_Scanner_2026.zip` | **StartupTrading Scanner** (Indicators → StartupTrading) |

Checked from the files themselves: both are protected NinjaTrader exports
(Agile.NET-protected `.dll` plus a generated stub; no source), exported with
NinjaTrader 8.1.8.1 and 8.1.8.4, and both call NinjaTrader `VendorLicense`
("No active license was found for SUT ATR-Orders" / "…for StartupTrading
Tools"). Test L7 confirms the protection in NinjaTrader.

**Permissions:** the download links are public. Anyone can download the files,
but they only run for a NinjaTrader account with an active vendor license.

Discord and the masterclasses are delivered by Whop (attached to the plans), not
by this app.

### 1.5 When emails are sent

| Email | Sent when | Can it go before licensing succeeds? |
|---|---|---|
| Whop receipt | By Whop at purchase | n/a (Whop) |
| Verification codes (Whop email, NinjaTrader email) | On each code request | n/a |
| **"Your tools are ready"** | After a sync in which **every** indicator has a bridge license matching the paid-through date (or is owned separately), with no failures | **No.** Observe-only, paused and partial-failure syncs return before queuing it. At most once per customer |
| Activation reminders (24 h / 72 h) | Only for paying members who haven't activated, and only after release at `/admin/reminders` (`ACTIVATION_REMINDERS_AUTO=false`) | They're held while the member isn't in licensing scope |
| "Access ending" | Verified member sets cancel-at-period-end | Independent of licensing mode |
| "Access ended" | A verified, previously eligible member becomes ineligible | Independent of licensing mode |

---

## 2. Before the test

| # | Item | Owner | How to clear it |
|---|---|---|---|
| **R1** | **Upload the two product files** | You | `https://activate.startuptrading.com/admin/products` → choose both zips → Upload and verify. Both rows must say "verified" |
| **R2** | **Confirm the NinjaTrader locations** (`ninjatrader_location` in `products.json`): ATR Order Automation under **Strategies**, the scanner under **Indicators**, both in a **StartupTrading** folder | Jack | Import both files and look. If either is wrong, tell me and I'll update `products.json` (the setup page follows) |
| **R3** | **Scanner build contents.** The scanner file also contains a "StartupTrading Tools (Tester)" item | Jack | Confirm it's meant to ship to customers, or re-export without it |
| **R4** | **Support email.** The license messages inside both products say `contact@startuptrading.com`; the site and emails use `support@startuptrading.com` | You | Make sure both inboxes reach you (or forward one to the other) |
| **R5** | **Test membership and NinjaTrader account.** A new 100%-off redemption creates a **new** `mem_…` (not `mem_T1AdJRcFkJNNSk`, which is the first, ended test). `bitbanditbrand@gmail.com` is still linked to the earlier test record | You | Use the new `mem_…`, and a **new NinjaTrader account with a fresh email** for C1–C9. Keep `bitbanditbrand@gmail.com` for L6 (rejoin, same Whop user) |
| **R6** | Earlier test cleanup: `mem_XN7y9ppQsdx2np` ended on 25 Nov; its licenses should be expired by now | You | Pre-flight P3 |
| **R7** | NinjaTrader Desktop revocation never confirmed | You / Jack | Test L4 |

## 3. Pre-flight (before the purchase)

| # | Check | Expect | Pass |
|---|---|---|---|
| P1 | Render environment as in section 0; `/health` | `"mode":"all_members"`, `"circuit_breaker":"ok"`; no test-only variables left | |
| P2 | `/admin` → **License changes (last 7 days)** | Every membership listed is a real, paying member or a test. Note them; anything unexpected, tell me | |
| P3 | `/admin` → `mem_XN7y9ppQsdx2np` → **Snapshot** | `whop.entitled: false`; 2067/2071 `no active license (expired …)`; `overall: consistent` | |
| P4 | `/admin/attention` | No HIGH items | |
| P5 | NinjaTrader vendor portal → Products | 2067 = ATR Order Automation, 2071 = Trend Scanner & Market Selector | |
| P6 | `startuptrading.com/setup` in a private window (after re-pasting `setup-embed.html`) | Two download buttons; each file downloads as the .zip named on the page | |
| P7 | Whop → product → both plans | Discord and masterclasses attached; post-purchase redirect `https://startuptrading.com/welcome` | |
| P8 | Test NinjaTrader account (R5) | You can sign into NinjaTrader 8 with it on a Windows PC, and open its email inbox | |

---

## 4. How to check each step

- **Snapshot:** `/admin` → the member → **Snapshot** (`/admin/lifecycle/<id>`).
  Read-only. Shows `whop` (status, `entitled`, paid-through), `write_gate`
  (allowed and why), `ninjatrader.licenses` (what NinjaTrader actually has for the
  email), per-product `ok` / `mismatch`, `overall`, and the database rows, emails
  and last 20 audit events.
- **Reconcile:** applies Whop's current state now instead of waiting up to 15 minutes.
- **License changes (last 7 days):** the cross-member check. After every step,
  only the test membership may appear.
- **NinjaTrader Desktop:** section 5.

---

## 5. Verifying inside NinjaTrader

Do this on a Windows PC with NinjaTrader 8, signed in with the **test**
NinjaTrader account.

1. **Fully close NinjaTrader** (File → Exit; check it's gone from the tray).
   Licenses are checked when NinjaTrader starts and when an indicator loads.
2. Start NinjaTrader and sign in with the test account.
3. **First time only:** import the downloaded file (*Control Center → Tools →
   Import → NinjaScript Add-On…*, choose the .zip, OK), then restart NinjaTrader.
4. *Control Center → New → Chart* → ES (any timeframe) → right-click →
   **Indicators…** → add **ATR Order Automation**, then **Trend Scanner & Market
   Selector**.
5. **Licensed:** each indicator loads and draws, with no error.
   **Not licensed:** the indicator doesn't load. Check the Control Center
   **Log** tab for a license message and **copy its exact wording** into the results.
6. Record the time you checked. For expiry tests, also record how long after the
   snapshot showed `expired` NinjaTrader stopped the indicator (vendor question 2).

---

## 6. The customer journey (new customer)

Use the fresh NinjaTrader account from R5 and the test Whop account. Private
browser window throughout.

| # | Action | Expected | Pass |
|---|---|---|---|
| C1 | Buy through `startuptrading.com/join` with the 100%-off code (monthly) | Whop checkout completes; browser lands on `/welcome` | |
| C2 | Check the Whop email inbox | Whop receipt. Whop shows Discord and masterclass access | |
| C3 | `/welcome` → **Activate my trading tools** → **Sign in with Whop** | Sign-in succeeds and the activation page shows the membership. `/admin` lists the new `mem_…` | |
| C4 | Enter the code sent to the Whop email | Verified | |
| C5 | Choose "I have a NinjaTrader account", enter the test NinjaTrader email, enter that inbox's code | "Linked". Snapshot: `write_gate.allowed: true` (reason: LICENSE_ALL_MEMBERS is on); after seconds or **Reconcile**: 2067 and 2071 `active until <paid-through>`, `overall: consistent` | |
| C6 | **License changes** | Exactly 2 `created` rows, both for the test membership; nothing else new | |
| C7 | NinjaTrader inbox | **One** "Your tools are ready" email, **after** C5 (compare times with the audit). Its button opens `/setup` | |
| C8 | `/setup` → download **both** files → import each → restart (section 5) | **SUT ATR Orders** (Strategies) and **StartupTrading Scanner** (Indicators) both load on a chart | |
| C9 | Whop email inbox and NinjaTrader inbox over the next hour | No reminder emails (the member is activated) | |

**Pass** only if C7 and C8 are confirmed by a person, not just C5.

---

## 7. Lifecycle tests

Run in order. After each one: Snapshot, License changes, and (where marked) NinjaTrader.

| # | Test | Action | Expected | NinjaTrader | Pass |
|---|---|---|---|---|---|
| L1 | **Duplicate activation** | Press **Reconcile** twice, refresh the activation page, press the page's refresh button | Still `consistent`; audit `ninjatrader_unchanged`; no new `created`; no second email | Still works | |
| L2 | **No silent relink** | Sign in again on the activation page | It shows the linked NinjaTrader account with no way to change it (the server also refuses a change: "NinjaTrader account already linked; contact support"). Licenses unchanged | — | |
| L3 | **Cancel at period end** | Whop → member → cancel *at the end of the billing period* | `whop.status: canceling`, still `entitled: true`, `consistent`, **no writes**. One "access ending" email to the Whop email. (A $0 promo may have no billing period: if Whop offers no "at period end", record that and skip) | Still works | |
| L4 | **Expiration / revocation** | Whop → end the membership **now** (cancel immediately / terminate), then **Reconcile** | Before: `mismatch: NOT entitled, but the NinjaTrader license is still active`. After: `writes: 2`, both `expired`, `consistent`. License changes: 2 `expired` rows for the test membership only. One "access ended" email | **Key check:** restart NinjaTrader → neither indicator loads (section 5). Record the time taken | |
| L5 | **Webhook path** | Repeat L4's effect via webhook only: don't press Reconcile; wait up to 15 minutes after a Whop membership change | `/admin` → Webhook deliveries shows the event `processed`; the snapshot updates without a manual Reconcile | — | |
| L6 | **Reactivation (rejoin)** | Same Whop user buys again (new `mem_…`) and activates with the **same** NinjaTrader email | Old record `transferred`; new record `consistent`; the **same** license IDs `renewed` (no new `created`). Audit `ninjatrader_link_transferred_in` | Works again after restart | |
| L7 | **Unlicensed account (protection)** | Sign NinjaTrader into an account with **no** license (or the test account after L4), import the same .zip, add the indicators | — | **Must not load.** If they load, the file isn't protected: stop and tell Jack before launch | |
| L8 | **No surprises for other members** | After all tests: **License changes (last 7 days)** | Besides the test memberships, only real members who activated, each with `created`/`renewed` for 2067 and 2071 (and `expired` only for members whose Whop membership ended) | — | |

Same-membership restore (Whop "uncancel" before the period ends) isn't
possible for an ended membership in Whop. L3's cancel can be undone in Whop
before the period end: if you do, expect no writes and the "access ending" email
cancelled.

---

## 8. Rollback

| Situation | Do this | Effect |
|---|---|---|
| **Anything unexpected** (unexpected member changes, duplicate licenses, errors) | Render: `LICENSE_WRITES_ENABLED=false` → deploy | Stops every write, including revocations, within one deploy. Licenses already issued keep their expiry dates, so NinjaTrader still switches them off when the paid period ends |
| Circuit breaker trips | Investigate `/admin/attention`; resume only by typing `RESUME` at `/admin` | Writes stay paused until then, even across restarts |
| Narrow licensing again | `LICENSE_ALL_MEMBERS=false` and `LICENSE_WRITE_ALLOWLIST=mem_…:email,…` | Only those pairs are written; nobody else gains or loses anything |
| A bad product file | Update its `sha256` in `products.json` (and the file name if it changes), deploy, then upload the new file at `/admin/products` | Customers download the new file; licenses are unaffected |
| The test is done | End and refund the test membership in Whop, then Reconcile its record | Its licenses expire; nothing else changes |
| Revert the free pages' membership links | Tell me to set `membership_open` back to off; re-paste the three free pages | The "Become a Member" nav and links disappear |

---

## 9. Results (this run)

| # | Date / time (UTC) | Snapshot / admin | NinjaTrader / inbox | Notes |
|---|---|---|---|---|
| R1–R7 | | | | |
| P1–P8 | | | | |
| C1–C9 | | | | |
| L1 | | | | |
| L2 | | | | |
| L3 | | | | |
| L4 | | | | Time to stop in NinjaTrader: |
| L5 | | | | |
| L6 | | | | |
| L7 | | | | |
| L8 | | | | |

**Pass** = C1–C9, L1, L2, L4, L7 and L8 as expected, confirmed in NinjaTrader and
the inboxes. Then promote (Gate 2–4 in `growth/LAUNCH_AND_GROWTH.md`). L3, L5 and L6 are strongly recommended.

---

## 10. Previous run (24–25 Nov 2026, allowlist test)

Run on 24–25 Nov 2026 against the live app, test NinjaTrader account
`bitbanditbrand@gmail.com`, Whop account `phonysolvent77`. At the time the
membership had three indicators (2067, 2071, 2205). TSMS & Fibs (2205) was
removed from the membership afterwards (see PRODUCTION_LICENSING.md, section 6).

| # | Date / time (UTC) | Snapshot `overall` | NinjaTrader Desktop | Notes |
|---|---|---|---|---|
| 1 | 24 Nov | `entitled: true` | — | `mem_T1AdJRcFkJNNSk`, $0 promo, no period dates from Whop. Needed fixes #24 (sign-in lookup) and #25 (active promo memberships without dates). |
| 2 | 24 Nov ~22:1x | `consistent` | Licensed | Needed #26 (adopt the account's already-expired licenses 82908/82912/82913 instead of manual review) and #27 (admin buttons). Licenses extended to 2026-12-24. |
| 3 | 24 Nov | `consistent` | — | Repeat reconciles: `ninjatrader_unchanged`, no new licenses, no second email. |
| 4 | — | — | — | Not run (needs a real renewal). Renewal path covered by the offline rehearsal. |
| 5 | — | — | — | Skipped: the $0 promo membership has no period end. Cancel-at-period-end is covered offline. |
| 6 | 24 Nov 23:03 | `consistent` (not entitled) | **Pending confirmation** | Membership ended in Whop → `writes: 3`, all three `expired` at 23:03:49–50Z. NinjaTrader Desktop check to be confirmed. |
| 7 | — | — | — | Skipped: Whop can't reactivate an ended membership. Same-membership restore is covered offline. |
| 8 | 25 Nov ~00:2x | `consistent` | — | New purchase `mem_XN7y9ppQsdx2np`: `ninjatrader_link_transferred_in` from customer 1; the same licenses 82908/82912/82913 were `renewed` to 2026-12-24T23:21:22Z. No duplicates. |
| 9 | 25 Nov | — | — | Whop test webhook sent and recorded. |
| 10 | 25 Nov | `write_gate.allowed: false` | — | `LICENSE_WRITES_ENABLED=false`; test membership ended. |

Also found during the run and fixed: the buyer email now comes from Whop's
Members API (#28), and activation reminders are held while licensing is
test-only (#29).

**Pass** = steps 1–7 and 9 behave as expected, *and* step 6 shows the
indicators actually stop working in NinjaTrader.

## 11. Questions for the NinjaTrader vendor contact

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

## 12. Rejoining with a new membership (how L6 works)

When a membership fully ends and the person buys again, Whop issues a **new
`mem_…` ID**, so the bridge creates a new customer record. The bridge now lets
that person reclaim their NinjaTrader link (`returning_member.py`), but only
when **all** of these hold:

1. both records belong to the **same Whop user**, and the new one was signed
   in through Whop;
2. Whop confirms, live, that the **old membership has ended** (a paying
   membership never loses its licenses);
3. they've just verified the NinjaTrader inbox with a code;
4. no license sync for the old record is running.

The email link and license rows then move to the new record in one database
transaction, audited on both. The engine extends the **same** NinjaTrader
licenses (no new ones) to the new paid-through date.

What the customer sees in the other cases:

| Situation | Result |
|---|---|
| Email held by a **different** Whop user | "That NinjaTrader email is already linked": contact support (unchanged) |
| Old membership **still active** | "That NinjaTrader account is active on another membership": contact support. The code isn't used up. |
| Whop unreachable | "We couldn't reach Whop": try again. Nothing moves. |
| A sync on the old record is running | "One moment": try again in a minute |
