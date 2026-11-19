# StartUpTrading — Launch Plan

Last updated: 2026-11-19

Goal: a visitor can buy the $99/month membership, activate all three NinjaTrader
indicators on their own in a few minutes, and lose access automatically when the
membership ends. The sales site should look modern and credible, not templated.

> Scope note: this plan is based on a review of the GitHub `main` source code.
> The live Render site, the Whop dashboard and startuptrading.com could not be
> loaded from the review environment, so the visual and copy recommendations
> below still need checking against the live pages and brand assets.

---

## 1. Findings from the code review

### Why `startuptrading-whop-bridge` fails to deploy
- **`clients.py` was missing from the project root.** Commit `edf8aab` deleted
  it and the replacement was uploaded to `tests/clients.py` instead. `app.py`,
  `engine.py`, `diagnostics.py` and `member_lookup.py` all import it, so the app
  crashed on startup with `ModuleNotFoundError: No module named 'clients'`.
- Most of the history is "Add files via upload" / "Delete app.py" commits from
  the GitHub web UI. That workflow is what caused the breakage.

### The test suite had decayed
- There were duplicate and nested copies (`tests/tests/`, `tests/app.py`, and
  `test_v7_9_intake.py` in two places), so pytest could not collect them.
- Seven test files were deleted and never restored: the integration,
  lifecycle, CRM/email, account-linking, diagnostics, member-lookup and
  auto-intake suites.
- The "85 passing tests" figure in the V2 guide came from a different codebase.

### Bugs found in the bridge logic
- **Members who had cancelled but were still paid up would lose their
  indicators at once.** Whop reports these members with the status
  `canceling`. The entitlement check only accepted `active` and `trialing`,
  which contradicts the documented policy. *(Fixed in Phase 1.)*
- **The background reconciler was on by default** in code (`RUN_RECONCILER`
  defaulted to `true`, every 300 s), while the docs and `.env.example` say it
  is off by default with a 900 s interval. *(Fixed in Phase 1.)*
- **The monthly plan ID has two spellings.** `config.py` uses
  `plan_qSXeS0xoDapGU` (capital X, changed by hand on Nov 19); older code and
  the README used `plan_qSxeS0xoDapGU`. Whop IDs are case-sensitive.
  **Action: confirm the exact ID in the Whop dashboard.**
- **The NinjaTrader vendor token comes from `demo.tradovateapi.com`.** The
  NinjaTrader vendor contact must confirm this is correct for production
  licenses.

### The sales funnel is not in this repository
- `main` contains only the activation bridge. There is no sales page and no
  `/checkout` route. `/` is an "Activate your indicators" page, and its "Back to
  Whop" button points to whop.com's homepage.
- The V2 frontend appears to exist only on the `startuptrading-v2-preview`
  Render service. Its source has to be located and reconciled.
- The bridge's Content-Security-Policy allows only scripts and styles from the
  app itself. That is right for the licensing app, but it blocks the
  analytics, video embeds and web fonts a sales page needs.

### Customer-experience gaps
- Errors show raw JSON (`{"detail":"..."}`) with no next step, for example on
  "no eligible membership", an expired code or an email conflict.
- There is no friendly recovery path for a member who leaves halfway through
  activation.

### What is solid
The licensing engine is careful. It reads before every write, refuses to touch
licenses it did not create, holds a lock per customer, never revokes access when
Whop's data is incomplete, and queues the activation email only after all three
licenses succeed. **It doesn't need a rebuild.**

---

## 2. Platform recommendations

| Layer | Recommendation | Why |
|---|---|---|
| Billing + Discord | **Stay on Whop** | It already handles billing, Discord access and OAuth. Moving to Stripe or Memberful means rebuilding Discord access and webhooks for little gain at a few hundred members. |
| Sales site | **Framer** (editable by Jack/Robert without a developer) or **Astro on Cloudflare Pages / Vercel** (if it should live in code) | Separating it lets copy and design change without risking the licensing deploy, and keeps the bridge's strict security policy. |
| Domains | `startuptrading.com` → sales site · `activate.startuptrading.com` → bridge | Clear separation, and the activation link looks trustworthy inside Whop. |
| Bridge hosting | **Render**: one production web service and one paid Postgres with backups. Staging uses its own database. | Sized well for this business; no need for more infrastructure. |
| Transactional email | **Resend** (already supported), domain verified with SPF, DKIM and DMARC | License and verification emails must land in the inbox, and they stay separate from marketing email. |
| CRM | **GoHighLevel** (already holds the free-indicator leads; sync code exists) | Avoid running two CRMs. Choose Klaviyo only as part of a full migration. |
| Deploys | **GitHub Actions runs the tests on every pull request; Render auto-deploys `main` only after they pass** | Stops the web-upload breakage for good. |

---

## 3. Phased plan

### Phase 1: Get the deploy working ✅ code done, ⏳ Render/DB steps need dashboard access

- [x] Restore `clients.py` to the project root (v7.11 version, which the
      v7.12 `app.py` needs).
- [x] Remove the stale duplicates (`tests/app.py`, `tests/tests/`, the
      root-level `test_v7_9_intake.py`) and keep the newest version of each
      test.
- [x] Restore the seven deleted test suites from Git history.
- [x] Fix the `canceling` entitlement bug, which still caps access at
      `current_period_end`.
- [x] Make the reconciler opt-in (`RUN_RECONCILER` defaults to `false`,
      interval 900 s), matching the docs.
- [x] Point the auto-intake test at the configured plan ID instead of a
      hard-coded one.
- [x] Add a startup smoke test: the app must import and `/health` must return
      `observe_only` from a clean checkout.
- [x] Add `pytest.ini` and the GitHub Actions workflow
      (`.github/workflows/tests.yml`: pytest plus a Docker build).
- [x] Result: **67 tests pass**, and a clean checkout boots with the
      Dockerfile's start command.
- [ ] **(You)** Merge the PR, then confirm the `startuptrading-whop-bridge`
      deploy turns green on Render.
- [ ] **(You)** In Render, set the service to deploy from `main` and enable
      "Auto-Deploy: After CI checks pass".
- [ ] **(You)** Upgrade `startuptrading-db` from Free to a paid plan (free
      databases expire after 30 days) and turn on backups.
- [ ] **(You)** Confirm production env vars: `REQUIRE_PERSISTENT_DB=true`,
      `DATABASE_URL` → the production DB, `LICENSE_WRITES_ENABLED=false`,
      `LOCAL_DEMO_OTP=false`, and `RUN_RECONCILER` set on purpose.
- [ ] **(You)** Give `startuptrading-v2-preview` its own database so it never
      writes to production customer records.
- [ ] **(You)** Confirm the exact monthly plan ID in Whop (`qSX…` vs `qSx…`).
- [ ] From now on, make all changes through branches and pull requests, never
      web uploads.

### Phase 2: Make the bridge customer-ready ✅ code done, ⏳ needs your links and content
- [x] Friendly errors: browsers get a branded page or an inline banner with one
      next step (`customer_errors.py`). API clients, webhooks and `/admin` keep
      JSON and the same status codes.
- [x] New `/` activation landing page: what you'll need, how it works, the three
      indicators, and FAQ (different emails, no NinjaTrader account, passwords,
      cancellation).
- [x] Onboarding rebuilt as a three-step flow with a progress bar: confirm
      membership → NinjaTrader email + code (resend, use a different email) →
      indicators, with per-indicator status (Active / Activating / Needs
      attention / Expired).
- [x] Success state: install steps, install-guide and Discord buttons.
      Inactive-membership state links to renewal.
- [x] Redesigned stylesheet in the dark trading-terminal look. No inline
      styles or scripts, so the strict CSP stays intact. Admin pages still work
      and got the spacing they had lost to the CSP.
- [x] HTML emails for the verification code and activation, with plain-text
      fallback. The code is in the subject line.
- [x] Tests: 11 new (78 total). Screenshots checked at desktop and phone width
      with no horizontal scrolling.
- [ ] **(You)** Set in Render: `SUPPORT_EMAIL`, `DISCORD_URL`,
      `INDICATOR_SETUP_URL` (activation emails stay off until this is set),
      `CHECKOUT_URL`, `WHOP_HUB_URL`.
- [ ] **(You)** Provide the official logo. A placeholder candlestick mark is in
      `templates/_base.html`.
- [ ] **(You)** Confirm the copy "access continues until the end of the paid
      period, then indicators deactivate automatically" matches policy.
- [ ] Get NinjaTrader vendor confirmation of the production token endpoint.

### Phase 3: Test the full lifecycle (needs Jack's test account)
- [ ] One real test membership: buy → activate → all three indicators work
      **inside NinjaTrader** → cancel with time left (access kept) → expire
      (access removed) → resubscribe (access restored).
- [ ] Duplicate and out-of-order webhook replays create no duplicate licenses.
- [ ] Rollout gate: one test account → an allowlist of 5–10 friendly members →
      everyone. This needs a reviewed production-write setting to replace the
      single-account test switch.

### Phase 4: Sales site and copy (runs alongside Phases 2–3)

**Design direction (avoiding the "AI slop" look)**
- Use real proof instead of decoration: indicator screenshots, short chart
  recordings, and Jack and his actual trading setup.
- Keep the existing dark trading-terminal look and the orange accent
  (`#fa7b39`), with tabular numbers and a dense, platform-like layout.
- Avoid purple gradients, emoji or glyph icons, three identical feature boxes,
  stock photos and vague superlatives.

**Page structure**
1. **Hero:** a specific headline, one CTA, and the price visible up front.
2. **Demo:** 30–60 seconds of the indicators on a live chart.
3. **The three indicators**, one section each: ATR Order Automation, Trend
   Scanner and Momentum Selector, and TSMS & Fibs. Say what each does and
   when to use it.
4. **Who Jack is,** with proof: YouTube streams and member quotes (real ones
   only).
5. **Inside the Discord:** what happens there daily and what access to Jack
   means.
6. **"What happens after you subscribe,"** in three steps. This also reduces
   failed activations.
7. **FAQ:** cancellation, NinjaTrader requirements, existing accounts,
   refunds.
8. **Final CTA** plus a trading-risk disclaimer.

**Copy direction (example):**
> *The three indicators Jack trades with, licensed to your NinjaTrader in
> under 5 minutes. $99/month. Cancel anytime.*

Be concrete and make no profit claims. Regulators look closely at trading
products, and specific copy converts better anyway.

**Tracking:** the checkout CTA passes UTM tags to Whop, so paying members can
be traced back to YouTube, social or email.

### Phase 5: Launch operations
- [ ] Connect GoHighLevel, with a "paid but never activated" reminder sequence.
- [ ] Error alerts (Sentry or Render notifications) and a tested Postgres
      backup restore.
- [ ] Launch to a small group first. Track paid → activated rate, activation
      time and early cancellations.

### Phase 6: Growth (after launch)
- [ ] Audit Jack's online presence (YouTube → subscription conversion).
- [ ] Nurture sequence for free-ATR-indicator leads.
- [ ] Add the NinjaTrader referral link once Jack provides the approved URL and
      terms.

---

## 4. Open inputs needed

1. **V2 frontend source,** or access to the repo behind
   `startuptrading-v2-preview`.
2. **Brand assets:** logo, photos of Jack, indicator screenshots and videos,
   the live startuptrading.com URL.
3. **Decisions:**
   - Is the $495 annual plan offered publicly?
   - Jack's NinjaTrader referral URL.
   - Support email and the scope of support.
   - GoHighLevel vs Klaviyo.
   - Policy for `past_due` (grace period or immediate removal) and for
     refunds and chargebacks.
4. **Confirmations:** the exact monthly plan ID in Whop, and the NinjaTrader
   production token endpoint.
