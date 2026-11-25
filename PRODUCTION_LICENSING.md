# Production licensing: controls, procedures and launch checklist

How the licensing app is switched on for every member, how to stop it, and what
happens to members' indicators when it is stopped. Read this before changing any
of the settings below in Render.

The membership now licenses **two** NinjaTrader indicators: **ATR Order
Automation (2067)** and **Trend Scanner & Market Selector (2071)**. It also
includes the **Discord** and the **masterclass**, which Whop grants directly at
checkout (the licensing app doesn't manage them). **TSMS & Fibs (2205) is no
longer part of the membership** (section 6).

---

## 1. The controls at a glance

| Control | Where | Default | Effect |
|---|---|---|---|
| `LICENSE_WRITES_ENABLED` | Render env | `false` | **Emergency stop.** `false` stops *every* NinjaTrader write: no grants, no renewals, **no revocations**. |
| `LICENSE_ALL_MEMBERS` | Render env | `false` | `true` licenses every member with a verified NinjaTrader email and an eligible Whop membership. `false` licenses only the allowlist below. |
| `ALLOWED_TEST_MEMBERSHIP` + `ALLOWED_TEST_EMAIL`, `LICENSE_WRITE_ALLOWLIST` | Render env | empty | The allowlist: exact `mem_…` + NinjaTrader email pairs. Used when `LICENSE_ALL_MEMBERS` is off. |
| Circuit breaker | Automatic; resume in `/admin` | armed | Pauses **all** writes, revocations included, when a limit is exceeded (section 3). Survives restarts and deploys. |
| `BREAKER_MAX_GRANTS_PER_HOUR` | Render env | `60` | Licenses granted (created, or an expired license taken over) per rolling hour before the breaker trips. |
| `BREAKER_MAX_REVOCATIONS_PER_HOUR` | Render env | `20` | Licenses switched off per rolling hour before the breaker trips. |
| `BREAKER_MAX_FAILURES_PER_15MIN` | Render env | `10` | Failed NinjaTrader writes per 15 minutes before the breaker trips. |
| Reminder release | `/admin/reminders` | nothing released | Activation reminders send only after you approve the recipients (section 5). |
| `ACTIVATION_REMINDERS_AUTO` | Render env | `false` | `true` sends future reminders without per-batch approval. Leave off until after launch. |
| `ALERT_WEBHOOK_URL` | Render env | empty | Discord or Slack webhook. Breaker trips and other HIGH issues are posted there. **Set it before launch.** |

`/admin` shows the current mode (Writes off / Allowlist only / All members),
the breaker status, and how close each limit is. `/health` reports `mode` and
`circuit_breaker` for monitoring.

Every write passes all three checks, in this order, immediately before it is
sent to NinjaTrader: the emergency stop, the scope (all members or allowlist),
then the breaker.

## 2. Emergency stop (`LICENSE_WRITES_ENABLED=false`)

**Use it when** something looks wrong and you want NinjaTrader left exactly as it
is while you investigate: unexpected licenses, a Whop outage, a bad deploy.

**How:** Render → startuptrading-whop-bridge → Environment → set
`LICENSE_WRITES_ENABLED` to `false` → Save, rebuild, and deploy. It takes effect
when the deploy is live, usually 1–2 minutes.

**Effect on revocation (important):**
- Nothing is revoked while the stop is on. A member whose membership ends keeps
  their indicators until writes are back on.
- **That access is still bounded.** Every license the app issues expires on the
  member's paid-through date, so NinjaTrader switches it off at the end of the
  paid period on its own. A member cancelled *immediately* (refund or chargeback)
  keeps access until writes resume, or until their paid-through date if that
  comes first.
- Nothing is granted either. New members can verify but get no licenses until
  writes resume.
- Whop, the activation page and the snapshot keep working. Customer records
  still update.

**Recovery:** set `LICENSE_WRITES_ENABLED=true` and deploy. Every sync is
state-based, so on the next pass (every `RECONCILE_INTERVAL_SECONDS`, 15 minutes
by default) the app applies whatever Whop says *then*: it revokes members who
ended and grants members who joined. To catch one member up immediately, click
**Reconcile** on their row. Then check `/admin` → Needs attention for anything
left over.

## 3. Circuit breaker

**What trips it:**
- more than `BREAKER_MAX_GRANTS_PER_HOUR` licenses granted in an hour (for
  example a bug or bad data granting access to the wrong people)
- more than `BREAKER_MAX_REVOCATIONS_PER_HOUR` licenses revoked in an hour (for
  example a bad Whop response marking many active members as ended)
- `BREAKER_MAX_FAILURES_PER_15MIN` failed NinjaTrader writes in 15 minutes (for
  example a NinjaTrader outage or expired vendor credentials)

The write that would go over the limit is **not** sent. The breaker trips first.

**What happens when it trips:**
- **All license writes stop, grants and revocations alike,** for every member,
  until you resume. The effect on revocation is the same as the emergency stop
  (section 2): access lasts at most until each member's paid-through date.
- The state is stored in the database, so restarts and deploys don't clear it.
- A **HIGH** "License writes paused (circuit breaker)" item appears in
  `/admin` → Needs attention, with the reason. If `ALERT_WEBHOOK_URL` is set, it
  is posted to Discord or Slack within one sync, and again daily while it lasts.
- The `/admin` header shows **WRITES PAUSED**. `/health` reports
  `"circuit_breaker": "tripped"`. Each member's snapshot shows
  `write_gate.allowed: false` with the reason.
- The audit history records `circuit_breaker_tripped` with the reason.

**Recovery:**
1. **Read the reason** in `/admin` → Licensing controls.
2. **Investigate before resuming:**
   - *Grants:* open the newest member records and their snapshots. Are these
     real, paying members? Was there a reminder release or a launch that explains
     the volume? If yes, it's expected: raise `BREAKER_MAX_GRANTS_PER_HOUR` for
     the launch window if needed.
   - *Revocations:* compare a few affected members' snapshots with Whop. If Whop
     really ended those memberships, it's legitimate churn. If Whop shows them
     active, **keep writes paused** and check Whop's status page and the app
     logs. Turning on the emergency stop as well is a sensible precaution.
   - *Failures:* check the `sync_error` audit lines and `/admin-test/diagnostics`
     (NinjaTrader auth and products). Fix credentials or wait for NinjaTrader to
     recover.
3. **Resume:** `/admin` → Licensing controls → type `RESUME` → **Resume license
   writes**. The counts restart from that moment, so the same backlog doesn't
   immediately trip it again. The audit records `circuit_breaker_reset`.
4. **Catch up:** within one sync interval the app applies the current Whop state
   to everyone, revocations included. Click **Reconcile** on a member to do it
   immediately. Watch the limits panel for the next hour.

If it trips again straight away for the same reason, leave it paused and
escalate. Don't raise the limits just to get past it.

## 4. Turning on licensing for every member

**Before (all must be true):**
- [ ] The NinjaTrader revocation check from `LIFECYCLE_TEST.md` step 6 is
      confirmed: the indicators stopped working in NinjaTrader after the
      membership ended.
- [ ] `INDICATOR_SETUP_URL` points to a **live** install page (the "indicators
      ready" email links to it).
- [ ] `ALERT_WEBHOOK_URL` is set and a test alert arrived.
- [ ] Jack has confirmed how current members' existing 2067/2071 licenses were
      issued (see "Existing licenses" below).
- [ ] The breaker shows **OK** and Needs attention has no HIGH items.

**Switch on:**
1. Render → Environment → `LICENSE_WRITES_ENABLED=true`, `LICENSE_ALL_MEMBERS=true`
   → Save, rebuild, and deploy.
2. Within one sync interval, every member who has *already* verified their
   NinjaTrader email is licensed. Watch `/admin` → Licensing controls: the grant
   count should match about 2 × the number of verified members. If more than
   ~30 members are already verified, raise `BREAKER_MAX_GRANTS_PER_HOUR` for the
   first hour, or the breaker will (correctly) pause the backlog.
3. Spot-check two or three member snapshots: `overall: consistent`.

**Existing licenses (check with Jack before launch):** if a member's NinjaTrader
email already has a 2067 or 2071 license the app didn't issue:
- lifetime, or lasting at least as long as the membership: recorded as owned
  separately and never touched
- already expired: taken over and extended
- **still active but ending before the membership** (for example a manually
  issued monthly license): stopped for **manual review**, a HIGH item. If many
  current members have manually issued licenses like that, decide with Jack
  whether to let them expire first or extend them by hand.

**A 5–10 member pilot isn't required.** The single-account lifecycle test passed
and the circuit breaker limits the blast radius. Do the switch-on during a watched
window instead: business hours, alerts set, `/admin` open for the first hour. A
pilot is worth it only if Jack's current members hold many manually issued
licenses (above).

**Switch off (back to allowlist only):** set `LICENSE_ALL_MEMBERS=false` and deploy.
Members outside the allowlist stop receiving writes, both grants and revocations.
Their existing licenses stay as they are and still expire at their paid-through
date. To freeze everything instead, use the emergency stop.

## 5. Releasing activation reminders (separate from licensing)

Reminders ("your indicators are waiting", sent 24 h and 72 h after joining) go to
paying members who haven't activated. Purchase intake now records real members,
so a backlog has built up. **Turning on `LICENSE_ALL_MEMBERS` does not send it.**

A reminder sends only when **all** of these are true:
1. you approved it at `/admin/reminders` (or `ACTIVATION_REMINDERS_AUTO=true`)
2. its scheduled time has come
3. licensing is open for that member (writes on, and all members on or the
   member allowlisted)
4. the member still hasn't activated and is still eligible

**To release a batch:**
1. Open `/admin/reminders`. It lists every waiting reminder: membership,
   recipient email, first or second reminder, when it's scheduled, whether
   licensing is open for them, and whether it's approved.
2. Tick exactly the recipients you approve.
3. Type `SEND` and the number you ticked (for example `SEND 12`), then click
   **Release ticked reminders**.
4. Approved reminders that are already due go out within one sync interval.
   Others go at their scheduled time. The audit records `reminders_released`
   with the batch ID and count.

Approving the first reminder doesn't approve the second. Approval can't be
undone from the page, so release in small batches if unsure. Each released
member who activates creates 2 license grants, so large batches count towards
`BREAKER_MAX_GRANTS_PER_HOUR`. Release more than ~30 members at once only
after raising it.

After launch, once you're happy, you can set `ACTIVATION_REMINDERS_AUTO=true`
so new buyers get reminders without a manual release.

## 6. TSMS & Fibs removal

- New members are never licensed 2205.
- **Licenses the app itself issued for 2205** are switched off on the member's
  next sync (when writes are allowed for them). They're recorded as `retired`
  and audited as `ninjatrader_retired`. The snapshot lists them under
  `retired_products`. While one is still active, the snapshot shows `mismatch`.
- **2205 licenses the app didn't issue** (for example a separate purchase) are
  never touched.
- At the time of the change, only the test account had an app-issued 2205
  license (82913). It is switched off the next time that account syncs with
  writes allowed.

## 7. Manual checklist

### Render (Environment)
- [ ] **Delete the duplicate `INDICATOR_SETUP_URL` row** (it's listed twice). Keep one.
- [ ] `INDICATOR_SETUP_URL` must point to a page that exists.
      `https://startuptrading.com/setup` returns 404 today. While writes are on,
      licensed members would get an email linking to it.
- [ ] Add `ALERT_WEBHOOK_URL` (Discord: Server settings → Integrations → Webhooks → New webhook → Copy URL).
- [ ] Leave `LICENSE_ALL_MEMBERS` unset or `false` until section 4 is complete.
- [ ] Leave `ACTIVATION_REMINDERS_AUTO` unset or `false`.
- [ ] Optional: `BREAKER_MAX_GRANTS_PER_HOUR`, `BREAKER_MAX_REVOCATIONS_PER_HOUR`,
      `BREAKER_MAX_FAILURES_PER_15MIN` (defaults 60 / 20 / 10).
- [ ] `CHECKOUT_URL=https://startuptrading.com/join#pricing` (already set).
- [ ] After the test: `LICENSE_WRITES_ENABLED=false` until launch (done), and clear
      `ALLOWED_TEST_MEMBERSHIP` / `ALLOWED_TEST_EMAIL` when no longer testing.
- [ ] Rotate `WHOP_API_KEY` (part of it appeared in a screenshot) and set the new
      key's expiry beyond 16 Feb 2027.

### Whop (Jack's StartUpTrading business)
- [ ] Remove TSMS & Fibs from the StartUpTrading product's description, images and
      any delivery (apps, files, links) attached to the membership.
- [ ] Make sure the **Discord** and the **masterclass** are attached to the
      $99/month and $495/year plans, so Whop grants both at checkout. Test with a
      100%-off code.
- [ ] Post-purchase redirect: `https://startuptrading.com/welcome`.
- [ ] Promo codes: first period only.
- [ ] API key (Developer → API keys): rotate; keep "Read members" and "Read member
      emails"; set the expiry beyond 16 Feb 2027; paste the new key into Render.
- [ ] Webhooks: keep the existing endpoint (`/webhooks/whop`) and events.

### GoHighLevel (startuptrading.com)
- [ ] Replace the `/join` page block with the rebuilt
      `sales-site/dist/ghl-embed.html`: two indicators plus Discord and masterclass,
      no TSMS & Fibs. Publish `/join`.
- [ ] Replace the `/welcome` page block with `sales-site/dist/welcome-embed.html`.
- [ ] Point the Home page's Join button to `/join`.
- [ ] Remove TSMS & Fibs from any other page that lists what the membership
      includes (Home, Tools section). Separate one-time products can stay.
- [ ] Publish the `/setup` install guide (`sales-site/dist/setup-embed.html`,
      `sales-site/SETUP.md` step 2e). The download buttons come from
      `products.json` (each product's `download_url`; files hosted on GoHighLevel Media, never in GitHub).
      Add the screenshots, rebuild and paste again. `INDICATOR_SETUP_URL` already
      points to it.

### Affiliate attribution (before announcing the affiliate program)
Setup:
- [ ] **Whop:** turn on the affiliate program for the StartUpTrading product. The
      commission rate is Jack's decision; nothing in this repo sets or changes it.
- [ ] **GoHighLevel:** paste `sales-site/dist/affiliate-tracking.html` into
      **Settings → Tracking code → Header** (site-wide), so `?a=` is captured on
      any startuptrading.com page, not only `/join`.
- [ ] Publish the rebuilt `/join` (`ghl-embed.html`) and `/welcome` pages.
- [ ] Tell affiliates to share **`https://startuptrading.com/join?a=THEIR_WHOP_USERNAME`**.
      (A link to `whop.com/startuptrading?a=…` also attributes, but skips the /join page.)

Tests. Use a fresh incognito window per test and a 100%-off, single-use promo code
on a test Whop account. **Commission rates and prices are not changed by any of these.**
- [ ] **A1 Monthly, direct:** open `startuptrading.com/join?a=AFFILIATE` and buy
      **monthly**. In Whop → Affiliates (or the membership's details), the sale is
      credited to AFFILIATE.
- [ ] **A2 Annual, direct:** same link, buy **annual**. Credited to AFFILIATE.
      (Use a cheap test or refund the purchase, and don't change the annual price.)
- [ ] **A3 Landing elsewhere:** open `startuptrading.com/?a=AFFILIATE` (Home), click
      **Join**, buy. Credited (needs the GHL tracking code above).
- [ ] **A4 Return visit:** open `startuptrading.com/join?a=AFFILIATE`, close the tab,
      come back to `startuptrading.com/join` with no `?a=` in the same browser
      within 30 days, buy. Credited.
- [ ] **A5 Latest affiliate wins:** visit with `?a=AFF_ONE`, then `?a=AFF_TWO`, buy.
      Credited to AFF_TWO.
- [ ] **A6 No affiliate:** fresh browser, `startuptrading.com/join`, buy. No affiliate credited.
- [ ] **A7 Nothing else changed**, for at least one of A1–A5:
  - the browser lands on `startuptrading.com/welcome` after paying
  - `/admin-test/member-lookup` shows the new membership as `eligible`
  - activation at `activate.startuptrading.com` works as before (with
    licensing writes still limited to the test pair)
- [ ] Record the results (membership IDs and who was credited) under section 8.

### NinjaTrader (Jack)
- [ ] Confirm the revocation check (`LIFECYCLE_TEST.md` step 6).
- [ ] Tell us how current members' 2067/2071 licenses were issued (section 4).
- [ ] Provide the indicator installation instructions for `/setup`.

## 8. Affiliate attribution

**How it works:** `sales-site/src/affiliate.js` runs on every built page, and site-wide
through the GoHighLevel tracking code.
- **Capture:** it reads Whop's `?a=` affiliate code from the page URL and keeps only
  valid codes (letters, digits, `.`, `_`, `-`, up to 64 characters).
- **Remember:** it stores the code in this browser for **30 days**
  (`SUT_AFF_DAYS`). The most recent affiliate wins.
- **Pass to Whop:** on `/join` it sets `data-whop-checkout-affiliate-code` on
  **both** embedded checkouts (monthly and annual) before Whop's loader mounts them.
- **Links:** it adds `?a=` to Whop checkout links and to links to `/join`. A link
  that already names an affiliate is never changed.

**What it doesn't touch:**
- the plan IDs, prices and checkout theme
- the return URL (`data-whop-checkout-return-url` stays `https://startuptrading.com/welcome`)
- the licensing app. Attribution lives entirely in Whop: membership verification,
  purchase intake and NinjaTrader licensing don't read it and don't change.

**To verify before launch:** the attribute name `data-whop-checkout-affiliate-code`
and the `?a=` link format follow Whop's embedded-checkout affiliate documentation
(https://docs.whop.com/third-party-integrations/embedded-checkouts/attribute-affiliates-embedded-checkout).
That page couldn't be fetched from the build environment, so confirm them against
it. Tests A1–A6 in section 7 confirm the end-to-end behaviour either way.

| Test | Date | Plan | Membership | Credited to | Pass? |
|---|---|---|---|---|---|
| A1 | | Monthly | | | |
| A2 | | Annual | | | |
| A3 | | | | | |
| A4 | | | | | |
| A5 | | | | | |
| A6 | | | | (none) | |
| A7 | | | | | |
