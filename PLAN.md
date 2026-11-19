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

## ⏸ Deferred: waiting on GoHighLevel access (do at the end of the build)

> **Reminder:** the GoHighLevel (GHL) admins haven't granted access yet. These
> tasks are parked until access is given, and are lowest priority, for the end
> of the product build. When access arrives, work through this list in order.
> Everything here is already built and committed; it only needs setting up in GHL.

1. **Publish the sales page:** create the GHL site, page path `/`, and paste
   `sales-site/dist/ghl-embed.html` into a Code element (`sales-site/SETUP.md`
   step 2). Rebuild first (`python sales-site/build.py`) if anything changed.
2. **Publish the thank-you page:** page path `/welcome`, paste
   `sales-site/dist/welcome-embed.html`, add the Purchase pixel / conversion
   code to its header tracking (`SETUP.md` step 2b).
3. **Connect `startuptrading.com` in GHL** and add the `@` / `www` records GHL
   shows into Namecheap (`SETUP.md` steps 3–4, root and www only).
4. **Only after `/welcome` is live:** set Whop's post-purchase redirect to
   `https://startuptrading.com/welcome` (`SETUP.md` step 2b.5). Until then
   leave Whop's redirect as it is, so hosted-checkout buyers don't hit a
   missing page. (The embedded checkout only exists on the GHL page, so it
   can't send anyone to `/welcome` before then.)
5. **Run the sales-site launch checks** in `SETUP.md` step 6 (embed loads,
   Annual toggle, test purchase lands on `/welcome`, tracking fires).
6. **CRM sync (Phase 5):** create a GHL API key and location ID, set
   `GHL_API_KEY`, `GHL_LOCATION_ID` and `GHL_CUSTOM_FIELDS_JSON` in Render, and
   build the "paid but never activated" reminder sequence.

**Not blocked by GHL, so it can be done now:** moving the activation app to
`activate.startuptrading.com`. Follow `ACTIVATE_DOMAIN.md` (Namecheap CNAME →
Render custom domain → Whop redirect URI → `PUBLIC_BASE_URL` → Whop webhook),
checking each step with `python scripts/check_activate_domain.py`.

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
  **Resolved: `plan_qSXeS0xoDapGU` confirmed correct by the owner (Nov 19).**
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
| Sales site | **GoHighLevel** (decided), with the page built in `sales-site/` and pasted into a GHL Code element | Already the team's CRM and funnel tool. Copy and design changes never touch the licensing deploy. |
| Domains | Namecheap DNS: `startuptrading.com` + `www` → GHL · `activate.startuptrading.com` → Render | Clear separation, and the activation link looks trustworthy inside Whop. See `sales-site/SETUP.md`. |
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
- [x] Monthly plan ID confirmed: `plan_qSXeS0xoDapGU`.
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

### Phase 4: Sales site and copy ✅ page built, ⏳ needs assets, sign-off and DNS
- [x] Sales page in `sales-site/`: one source, built into a paste-ready
      GoHighLevel block (`dist/ghl-embed.html`) plus a standalone preview
      (`dist/index.html`). All CSS is scoped under `.sut` so GHL's styles can't
      clash.
- [x] Sections: hero with demo frame, what's included, the three indicators,
      trade room, Jack, how it works, pricing (Monthly $99 / Annual $495
      toggle), member quotes, FAQ, final CTA, risk disclosure.
- [x] Copy is concrete and makes no profit claims. No invented testimonials
      or numbers; missing facts and assets are dashed placeholder boxes.
- [x] Every Join button goes to the Whop checkout from `site.config.json`, and
      UTM tags plus Whop's `?a=` affiliate code are forwarded automatically.
- [x] `SETUP.md`: GHL page build, GHL domain connection, Namecheap records,
      and moving the bridge to `activate.startuptrading.com`.
- [x] `COPY_REVIEW.md`: 10 claims for Jack to confirm, plus the asset list.
- [x] Tests: the committed build matches the source, links are correct, CSS is
      scoped, and there are no profit or guarantee phrases.
- [ ] **(You/Jack)** Work through `sales-site/COPY_REVIEW.md` (claims,
      assets, decisions).
- [x] Code prep for `activate.startuptrading.com`: optional
      `CANONICAL_REDIRECT` moves visitors off the old onrender.com address
      (never webhooks, health or the OAuth callback); `/health` reports the
      configured host; `scripts/check_activate_domain.py` verifies each step.
- [ ] **(You, now)** Follow `ACTIVATE_DOMAIN.md`: Namecheap CNAME, Render
      custom domain, Whop redirect URI, `PUBLIC_BASE_URL`, Whop webhook.
      Doesn't need GHL.
- [ ] ⏸ **Deferred until GHL access:** publish the sales and thank-you pages,
      connect the domain in GHL, Whop redirect to `/welcome`, launch checks.
      See "Deferred: waiting on GoHighLevel access" at the top.
- [x] Monthly/Annual toggle and an embedded Whop checkout in Pricing: buyers
      pay on the page, then Whop redirects them straight to activation. The
      `embed_checkout` switch falls back to hosted-checkout buttons.
- [x] Thank-you page (`/welcome`) on GHL: Whop redirects buyers there after
      payment; one main "Activate my indicators" action, then the Discord and
      install steps, plus support. Hook for purchase-conversion tracking.

### Phase 5: Launch operations
- [ ] ⏸ **Deferred until GHL access:** connect GoHighLevel CRM sync, with a
      "paid but never activated" reminder sequence (see the deferred list at
      the top).
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
4. **Confirmations:** ~~the exact monthly plan ID in Whop~~ (confirmed), ~~the domain~~ (`startuptrading.com`, confirmed), and the NinjaTrader
   production token endpoint.
