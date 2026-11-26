# Marketing attribution, analytics and CRM

How StartUpTrading learns where customers come from and which channels produce
revenue. It reuses the existing site scripts, the licensing app (Render +
PostgreSQL), Whop's signed webhooks and GoHighLevel. Nothing here changes
licensing, prices, checkout or the launch gates.

Audited 25 Nov 2026 against the repository, the live site and the live app.

---

## 1. Audit: what exists

| Piece | State found | Notes |
|---|---|---|
| Site attribution script (`sales-site/src/tracking.js`, in `site-tracking.html` and every page embed) | **Live** on every page | First/last touch in browser storage, `dataLayer` events, Form 7 hidden fields |
| Google Tag Manager | Was not installed → **GTM-ML2LKZ7C** now in the site-wide header code and the activation app | Container: `growth/gtm/` |
| Google Analytics 4 | Was not installed → **G-S0PT1NK0FK** via GTM (browser) and Measurement Protocol (verified server events) | Data API connector for the dashboard |
| Meta pixel | Not installed | — |
| Google Search Console | Verified, sitemap submitted | Organic search queries only |
| Form 7 (GoHighLevel) | Live on 3 free pages, 12 hidden fields filled | Confirmed by your test contact |
| Affiliate capture (`affiliate.js`) | **Live** | `?a=` kept 30 days, passed to both Whop checkouts and `/join` links. Unchanged |
| Licensing app → GoHighLevel CRM sync | In code (`customer_communications.py`) | Upserts the buyer's contact with membership and activation fields when `GHL_API_KEY` + `GHL_CUSTOM_FIELDS_JSON` are set |
| Whop webhooks | Live; membership and payment events stored by type and id only | Payment amounts were **not** kept, so revenue couldn't be reported |
| Visitor → subscriber link | **Missing** | Browser attribution never reached the licensing app or Whop |
| Revenue reporting | **Missing** | — |

## 2. Broken or unreliable attribution (found and fixed)

| # | Problem | Cause | Fix |
|---|---|---|---|
| A1 | **`last_utm_source: app.gohighlevel.com`** on your test contact | The test visit was opened from inside the GoHighLevel dashboard. The browser reported `app.gohighlevel.com` as the referrer, and the old logic treated any outside referrer as a new source. The embedded form was not the cause: the script runs on the page, not in the form | Our own journey is now never a source: our domains and subdomains, GoHighLevel (`gohighlevel.com`, `leadconnectorhq.com`, `msgsndr.com`), Whop, Stripe, PayPal and sign-in pages. Already-stored contaminated values are dropped on the next visit |
| A2 | Returning from Whop checkout would have overwritten the source with `whop.com` | Same as A1 | Same fix |
| A3 | Direct visits were indistinguishable from "no data" | A first visit with no referrer stored nothing | First touch is now `(direct)` for a genuinely direct first visit, and `(unknown)` when the first visit came through our own journey or storage was unavailable. Nothing is invented |
| A4 | Referrer hosts stored raw (`chatgpt.com`, `l.instagram.com`, `t.co`) | No normalisation | Canonical sources and a channel for every touch (section 3) |
| A5 | Ad click IDs ignored | — | `gclid`/`gbraid`/`wbraid` → Google paid, `msclkid` → Bing paid, `ttclid` → TikTok paid, `fbclid` → Facebook (when there's no UTM) |
| A6 | Affiliate visits had no source | `?a=` was only used for checkout | An affiliate link without UTMs is now source `affiliate`, channel `affiliate`, campaign = the code. The code itself is still passed to Whop unchanged |
| A7 | **`sut_purchase` fired on every `/welcome` page load** | A reload or shared link counted as a purchase | Renamed `checkout_return` and documented as unverified. Purchases come from Whop's signed payment webhooks only |
| A8 | `tracking.js` ran twice on pages with both the header code and an embed | — | Fixed earlier (every event guarded once per page) |
| A9 | No way to tie a subscriber to a source | Browser storage is per site; the licensing app and Whop never saw it | Section 4 |

## 3. Taxonomy and UTM conventions

**Source** = the platform (`youtube`). **Medium** = the kind of traffic (`social`).
**Campaign** = the series or initiative (`risk_lab`). **Content** = the asset or
placement (`short25`). **Channel** = the reporting bucket, worked out from source +
medium. You never type the channel.

| Channel key | Label | How it's recognised |
|---|---|---|
| `google_organic` | Google organic search | Referrer `google.*`, or `utm_source=google` with medium organic or none |
| `google_paid` | Google paid advertising | `gclid`/`gbraid`/`wbraid`, or `utm_source=google` + a paid medium (`cpc`, `ppc`, `paid`, `display`…) |
| `tradingview` | TradingView | Any `*.tradingview.com` referrer or `utm_source=tradingview` |
| `youtube` / `instagram` / `facebook` / `tiktok` / `discord` / `reddit` / `x_twitter` | The platform | Referrer host or `utm_source` (`yt`, `ig`, `fb`, `twitter`, `t.co` normalised). Paid versions keep the platform channel, and are marked paid by their medium |
| `ai_referral` | ChatGPT & AI assistants | chatgpt.com, chat.openai.com, perplexity.ai, claude.ai, gemini.google.com, copilot.microsoft.com, you.com, phind.com |
| `affiliate` | Affiliate referrals | `?a=CODE` link, or `utm_medium=affiliate` |
| `email` | Email campaigns | `utm_medium=email`, or webmail referrers (Gmail, Outlook, Yahoo Mail) |
| `direct` | Direct | No referrer and nothing in the URL |
| `other_referral` | Other referrals | Any other outside site (NexusFi, podcasts' sites, Bing…) |
| `unknown` | Unknown | Not determinable (first seen via our own journey, storage blocked, or never reached the activation app) |

**Rules:** lowercase, words joined with underscores, no spaces, no personal data.

| Placement | utm_source | utm_medium | Example campaign / content |
|---|---|---|---|
| YouTube description, pinned comment | `youtube` | `social` | `risk_lab` / `short25`, `pinned_comment` |
| Instagram, TikTok, Facebook, X, Discord, Reddit | the platform | `social` | `jack_reacts` / `bio`, `story` |
| TradingView profile signature | `tradingview` | `social` | `futures_risk_planner` / `signature` |
| Email (GoHighLevel campaigns) | `newsletter` | `email` | `opening_bell_2026_12_01` |
| Podcast / collaboration (vanity redirect) | `podcast` | `referral` | the show, e.g. `tradingnut` |
| Google Ads | `google` | `cpc` | campaign name |
| Meta / TikTok ads | `facebook` / `tiktok` | `paid_social` | campaign / ad name |
| Affiliates | `affiliate` + `?a=<Whop username>` | `affiliate` | the code |

**Link generator:** `https://activate.startuptrading.com/admin/campaign-links`
(admin sign-in). It builds the URL from these rules, shows the channel, and keeps
affiliate codes intact.

## 4. Architecture

```
Visitor's browser (startuptrading.com)                 Licensing app (activate.startuptrading.com)        Whop
 tracking.js: first + latest touch, channel,            /  (activation page) reads sut_* from the link     signed webhooks
 anonymous visitor id (random, no PII)                    -> short-lived httpOnly cookie                    payment.* ---------+
   |                                                    /oauth/callback (Whop sign-in = verified membership)                     |
   +-- Form 7 hidden fields -----> GoHighLevel contact     -> customer_attribution (ONCE per membership) <--- membership id ----+
   +-- dataLayer events ---------> GTM -> GA4            payments table (non-personal fields; refunds re-read from the API)
   +-- links to activate.* carry sut_* (from /welcome, /setup)   /admin/marketing: subscribers, activation, revenue by channel
                                                          CRM sync adds acquisition_*_channel to the buyer's GoHighLevel contact
```

**Why this join:** Whop sign-in at activation is the one moment a browser, a
verified Whop membership and (next) a NinjaTrader account meet. Checkout
redirects to `/welcome`, whose "Activate" link carries the attribution, so the
same browser that bought hands its history to the membership. It's stored once
and never overwritten. Nothing personal is passed: source, medium, campaign,
content, channel, landing page, affiliate code and a random visitor id.

**What it can't see (reported as Unknown, never guessed):** buyers who check out on
Whop's own store page, activate on another device, or block storage.

**Phase 2 (more coverage, needs a Whop API key with `checkout_configuration:create`):**
Whop checkout configurations accept `metadata`, which Whop copies onto the
membership **and** every payment (confirmed in Whop's API docs). The licensing app
would create one per checkout with the visitor's attribution, and the embed would
use it. That covers buyers who never activate. It changes the checkout, so it
needs your approval and a test purchase first.

**Revenue rules** (`acquisition.report`):
- **Revenue** = Whop payments with status `paid` and an amount above zero (USD
  total). $0 promo or test memberships are never revenue; they're counted
  separately as "free or promo-only".
- **Initial vs renewal:** a membership's first paid payment is initial; every later one
  is a renewal.
- **Refunds:** Whop has no refund webhook, so paid payments from the last 120 days are
  re-read from the Whop API every few hours (`refunded_amount`, `substatus`).
- **Failed payments:** `payment.failed` events.
- **Churn:** members whose membership ended.
- **Realised LTV** = net revenue per paying subscriber.
- **MRR** is labelled an estimate: each active member's latest payment, with annual
  divided by 12.
- **Excluded:** memberships or emails in `MARKETING_EXCLUDE_MEMBERSHIPS` /
  `MARKETING_EXCLUDE_EMAILS` (internal QA).
- **Webhook retries** are idempotent (`webhook-id` and payment id), and an older copy of
  a payment never replaces a newer one.

## 5. Event specification

Browser events are pushed to `dataLayer` by `tracking.js` and sent to GA4 by the
GTM container (`growth/gtm/startuptrading-gtm-container.json`). Verified outcomes
are sent to GA4 **by the licensing app** (Measurement Protocol), never by the
browser. No emails, names, affiliate codes, license data or credentials are sent to
GA4. Page URLs keep only `utm_*`/click IDs, and `/activate/<token>` is masked.

| Activity | dataLayer event | GA4 event | Parameters | Fires | Dedupe |
|---|---|---|---|---|---|
| Page view | `sut_attribution` (trigger) | `page_view` (Google tag) | page_location (cleaned), user properties `first_channel`, `last_channel` | Once per page load; on activate.startuptrading.com on page load | Google tag set to once per load |
| Free tool page opened | `free_tool_view` | `free_tool_view` | `tool_id` | Page load | Once per page |
| Calculator used | `tool_use` | `tool_use` | `tool_id` | First input | Once per tool per page |
| Calculation completed | `calculation_complete` | `calculation_complete` | `tool_id`, `calculator` | First result after the visitor changes an input | Once per calculator per page |
| Free tool selected | `free_tool_select` | `select_content` | `content_type=free_tool`, `content_id` | Directory card click | Per click |
| TradingView link clicked | `outbound_click` (destination `tradingview`) | `tradingview_click` | `tool_id` | Click | Per click |
| Email signup completed | `email_subscribe` | **`generate_lead`** (key event) | `source_page`, `interest`, `tool_id`, `form_id` | GoHighLevel's successful-submission message from our iframe, never a click | Once per form per page |
| Membership CTA clicked | `checkout_intent` | `select_promotion` | `promotion_id=membership`, `creative_slot` = placement | Click | Per click |
| Checkout initiated | `checkout_view` | **`begin_checkout`** (key event) | — | Embedded Whop checkout scrolls into view | Once per page |
| Back from checkout (unverified) | `checkout_return` | `checkout_return` | — | `/welcome` load | Once per browser session |
| Product download | `file_download` | `file_download` | `file_name`, `file_extension`, `link_url` | `/setup` download click | Per click |
| **Subscription payment** (initial and renewals) | — | **`purchase`** (key event; server) | `transaction_id` (Whop `pay_…`), `value`, `currency`, `coupon` (promo id), `purchase_type`, `acquisition_channel`, `items` | Verified Whop `payment.*` webhook, paid and above $0, not QA | `ga_events_sent` per payment; GA4 also dedupes `transaction_id` |
| Refund | — | `refund` (server) | `transaction_id`, `value` | Refund seen on the payment | Once per refunded amount |
| NinjaTrader linked | — | `ninjatrader_linked` (server) | `acquisition_channel` | Member verified their NinjaTrader email | Once per membership |
| Indicators licensed / activation complete | — | `activation_complete` (server) | `acquisition_channel` | Both indicators licensed | Once per membership |
| Subscription cancelled | — | `subscription_cancel` (server) | `acquisition_channel` | Activated member's membership ended | Once per membership |

**Joining server events to the visitor:** at Whop sign-in the activation app reads
GA4's own `_ga` cookie (shared across `*.startuptrading.com`), with the `/welcome`
hand-off as a fallback, and stores the client id per membership (`ga_clients`). A
buyer whose client id never arrives is still counted after 72 hours under a stable
anonymous id (GA4 then shows it as unattributed). Nothing is invented.

## 6. GA4 and Google Tag Manager: install and publish (you)

**Confirmed production identifiers**

| What | ID | Used in |
|---|---|---|
| GTM container | **GTM-ML2LKZ7C** | `sales-site/site.config.json` → `site-tracking.html` / `site-tracking-body.html`; `growth/gtm/` container; Render `GTM_CONTAINER_ID` |
| GA4 measurement ID | **G-S0PT1NK0FK** | GTM container (Google tag, events); Render `GA4_MEASUREMENT_ID` |
| GA4 property ID | **565901572** | Render `GA4_PROPERTY_ID` (dashboard Data API); the service account gets Viewer on this property |
| GA4 account ID | **417508101** | GA4 Admin (reference only) |
| GA4 web stream ID | **16417615246** | GA4 Admin → Data streams (Measurement Protocol secret is created here) |

An earlier GTM container ID was discontinued and must not be used anywhere; only GTM-ML2LKZ7C is valid.

**6.1 GA4 property settings** (analytics.google.com → Admin):
1. Data streams → *startuptrading.com* → **Enhanced measurement** (gear):
   - **on:** page views, scrolls, outbound clicks, site search, video engagement and file downloads;
   - **off:** "Page changes based on browser history events" (it would duplicate page views);
   - **off:** "Form interactions" (it counts clicks as submissions).
2. Same stream → Configure tag settings:
   - **Configure your domains:** add `startuptrading.com` and `activate.startuptrading.com`.
   - **List unwanted referrals:** add `gohighlevel.com`, `leadconnectorhq.com`, `msgsndr.com`, `whop.com`, `stripe.com`, `paypal.com`.
3. Same stream → **Measurement Protocol API secrets** → Create → nickname "licensing app" → copy the secret (step 6.4).
4. Admin → Data settings → Data retention → **14 months**. Data collection: leave **Google signals off**.
5. Admin → Custom definitions → Create custom dimension:
   - **Event scope:** `tool_id`, `source_page`, `interest`, `calculator`, `purchase_type`, `acquisition_channel`.
   - **User scope:** `first_channel`, `last_channel`.
6. Admin → Events (after the first events arrive): mark **`generate_lead`**, **`begin_checkout`**, **`purchase`** and **`activation_complete`** as key events.

**6.2 Import the container** (tagmanager.google.com → GTM-ML2LKZ7C):
1. Admin → **Import container** → choose `growth/gtm/startuptrading-gtm-container.json` → workspace **Default Workspace** → **Merge** → **Overwrite conflicting tags, triggers and variables** → Confirm.
2. Check: **5 tags**, **6 triggers** and **16 variables** were imported, plus the built-in Page URL, Page Hostname, Page Path, Referrer and Event.
3. Admin → Container settings → enable **Consent Overview**. The tags use Google's built-in consent checks; the site sets Consent Mode v2 defaults before GTM loads (`static/gtm.js`).
4. Don't publish yet: test first (section 9).

**6.3 Install on GoHighLevel** (Settings → Tracking code, in **every** website/funnel serving startuptrading.com):
- **Header tracking code:** replace everything with `sales-site/dist/site-tracking.html`. It contains the Consent Mode defaults, GTM-ML2LKZ7C, affiliate capture and attribution. Don't paste Google's own GTM snippet as well (that would load GTM twice).
- **Body / footer tracking code:** `sales-site/dist/site-tracking-body.html` (GTM's noscript fallback).
- Don't add GA4 or GTM anywhere else (page code elements, funnel settings, GHL's "Google Analytics" integration). GA4 must come **only** from GTM, or page views double.

**6.4 Render** (startuptrading-whop-bridge → Environment):

| Variable | Value |
|---|---|
| `GTM_CONTAINER_ID` | `GTM-ML2LKZ7C` (GTM on the activation app's customer pages; never on /admin) |
| `GA4_MEASUREMENT_ID` | `G-S0PT1NK0FK` |
| `GA4_API_SECRET` | the Measurement Protocol secret from 6.1 step 3 |
| `GA4_PROPERTY_ID` | `565901572` |
| `GA4_SERVICE_ACCOUNT_JSON` | see 8.1 (for the dashboard) |
| `GA4_PROPERTY_URL` | optional: your GA4 home URL, linked from the dashboard |

**6.5 Publish:** after section 9 passes in Preview, go to GTM → **Submit** → Version name "v1 GA4 + SUT events" → **Publish**.

**Consent:** there's no banner yet. Default: analytics allowed except in the EEA, UK and Switzerland, where it's denied until consent (Google then uses cookieless pings); ad storage is denied everywhere. When you add a Consent Mode v2 banner (CookieYes or Cookiebot from GTM's template gallery), have its accept and decline also call `window.sutConsent('granted'|'denied')`.

## 7. GoHighLevel CRM (you)

**Goal:** one simple Form 7 workflow, the original acquisition preserved, one welcome
email, and subscribers kept out of sales emails.

### 7.1 Two more hidden fields on Form 7

Add these the same way as the existing 12 (Sites → Forms → Form 7 → Hidden field →
custom field, single-line text, **Query key** exactly):

| Custom field | Query key |
|---|---|
| First acquisition channel | `first_channel` |
| Latest acquisition channel | `last_channel` |

### 7.2 Preserve the ORIGINAL acquisition (fields that never get overwritten)

A later form submission from another device would overwrite Form 7's fields. So
create four more contact custom fields that the workflow fills **once**:
**Original channel**, **Original source**, **Original campaign**, **Original
landing tool**.

### 7.3 The workflow (Automation → Workflows → edit the Form 7 workflow)

Replace the source_page branches with:

1. **Trigger:** Form Submitted. Filter: **Form is "Form 7"**. Workflow settings: **Allow
   re-entry: ON** (needed for step 4), Stop on response: off.
2. **Action: Add Contact Tag** → `free-tools-lead`.
3. **Action: If/Else** "Original not set". Condition: **Original channel** → **Is empty**.
   - **Yes branch → Update Contact Field** (×4):
     - Original channel = `{{contact.first_acquisition_channel}}`
     - Original source = `{{contact.first_utm_source}}`
     - Original campaign = `{{contact.first_utm_campaign}}`
     - Original landing tool = `{{contact.tool_id}}`

     Use the merge-field picker for the exact keys; GoHighLevel names them from your
     custom field names. Then, in the same branch, **If/Else "Channel tag"** on
     **First acquisition channel**:

     | Condition (Is) | Add Contact Tag |
     |---|---|
     | `google_organic` **or** `google_paid` | `source-google` |
     | `tradingview` | `source-tradingview` |
     | `instagram` | `source-instagram` |
     | `youtube` | `source-youtube` |
     | `tiktok` | `source-tiktok` |
     | `affiliate` | `source-affiliate` |
     | `direct` | `source-direct` |
     | None (all others) | no tag |

     Tags are applied once, from the original channel, so they mean "acquired by".
     Add new `source-*` tags only when you'll actually segment on them.
   - **No branch:** nothing (a repeat submission keeps the original).
4. **Action: If/Else** "Welcome not sent". Condition: Contact **Tags** → **Does not
   include** → `welcome-sent`.
   - Yes → **Send Email** "Welcome to the free tools" → **Add Contact Tag**
     `welcome-sent`.
   - No → end.

   Email consent is collected by Form 7's required checkbox; GoHighLevel adds the
   unsubscribe link.
5. Delete the old **Calculator / TradingView / Free Tools / Unknown Source** branches
   and any tags they added only to repeat `source_page` (that's already a field).

### 7.4 Subscribers and lifecycle stage

The licensing app already updates the buyer's contact (by Whop email) when
`GHL_API_KEY` and `GHL_CUSTOM_FIELDS_JSON` are set. Map these keys in
`GHL_CUSTOM_FIELDS_JSON` to GoHighLevel custom-field IDs:
- `membership_status`, `activation_status`, `whop_membership_id`, `subscription_plan`
- `acquisition_first_channel`, `acquisition_last_channel` (new)

Then add a second workflow:

1. **Trigger:** Contact Changed → custom field **Membership status** changed.
2. If **Membership status** is `eligible` → Add Tag `subscriber`; Remove Tag
   `free-tools-lead`. Optional: Opportunity / pipeline stage **Subscriber**.
3. If **Activation status** is `active` → Add Tag `activated` (pipeline stage
   **Activated**).
4. If **Membership status** is `ineligible` → Remove Tag `subscriber`, Add Tag
   `former-subscriber`.

**Exclusion:** every membership-promotion email or campaign uses the filter **Tags →
does not include → `subscriber`**.

The Form 7 contact (lead email) and the Whop contact (buyer email) merge
automatically in GoHighLevel when they're the same email. Different emails stay
separate contacts. The verified join is the membership in section 4, not the
email.

## 8. Marketing dashboard

`https://activate.startuptrading.com/admin/marketing` (admin sign-in), in the
existing app. A status line shows which sources are connected, and every number is
labelled:

| Source | What it supplies | Needs |
|---|---|---|
| Whop + licensing (**verified**, connected) | Subscribers, paying, revenue (initial/renewal), refunds, failed payments, LTV, activation, churn, by first/latest channel, landing page, campaign, affiliate | Nothing more |
| GA4 Data API (**connected when configured**) | Visitors (new/returning), sessions, leads (`generate_lead`) by first channel, landing pages, devices, countries, funnel event counts; lead→subscriber and visitor→subscriber rates (labelled *Mixed sources*) | `GA4_PROPERTY_ID` + `GA4_SERVICE_ACCOUNT_JSON` (8.1) |
| GA4 Measurement Protocol (server events) | `purchase`, `refund`, `ninjatrader_linked`, `activation_complete`, `subscription_cancel` in GA4 | `GA4_MEASUREMENT_ID` + `GA4_API_SECRET` |
| Spend | CAC and ROAS | Not available yet (phase 2: a spend form) |

GA4 data is cached for 6 hours. If GA4 fails or isn't configured, those columns read
"—" with the reason; nothing is estimated in their place.

**8.1 Create the read-only Google credentials (you):**
1. console.cloud.google.com → create (or pick) a project → APIs & Services → Library → enable **Google Analytics Data API**.
2. IAM & Admin → Service accounts → Create, named "startuptrading-dashboard", with **no project roles**.
3. Open it → Keys → Add key → JSON → download.
4. GA4 → Admin → Property access management → **+** → add the service account's email (`…@….iam.gserviceaccount.com`) with role **Viewer**. Leave "Notify" off.
5. Render → `GA4_SERVICE_ACCOUNT_JSON` = the whole JSON file contents, or its base64. Set it as a Render **secret** environment variable, never in GitHub. Also set `GA4_PROPERTY_ID`.
6. Delete the downloaded file from your computer once it's saved in Render.

## 9. Live testing checklist (GTM Preview, Tag Assistant, GA4 DebugView)

**Before testing: check that every live page runs the current scripts.** GoHighLevel
runs each page's embed (in the body) **before** the site-wide header code, so a page
whose embed is older than the header sends an old-shaped `sut_attribution` to GTM
(this is what made `first_channel` / `last_channel` undefined on /free-tools on
26 Nov). Run:

```bash
python growth/gtm/check_live.py
```

Every page must say `OK`. A page marked `STALE` needs its embed re-pasted from
`sales-site/dist/` and published. Whenever `tracking.js` changes, re-paste the
header code **and** every embed.

**Setup:** GTM → **Preview** → enter `https://startuptrading.com/free-tools?utm_source=qa&utm_medium=test&utm_campaign=gtm_check` → Tag Assistant opens the site in a debug window. In GA4 → Admin → **DebugView**, the debug device appears within a minute. Use a fresh browser profile with no ad blocker.

| # | Test | In Tag Assistant | In GA4 DebugView / elsewhere | Pass |
|---|---|---|---|---|
| L1 | GTM loads once | Container GTM-ML2LKZ7C listed **once**; Consent shows defaults (ad_storage denied) | — | |
| L2 | One page view per page | On `sut_attribution`: "GA4 - Google tag (page view)" fired **once**. Navigate to the calculator and the TradingView page: once on each | One `page_view` per page; `page_location` has only the utm_* parameters | |
| L3 | Attribution | On `sut_attribution`, Variables: `DLV - first_channel` and `DLV - last_channel` = `other_referral` in a **fresh** profile; in a browser first seen via ChatGPT: `ai_referral` / `other_referral`. `GA4 user properties` shows the same values (never `unknown` when the Data Layer has them) | User properties `first_channel` / `last_channel` set | |
| L4 | GoHighLevel referrer ignored | Open the page from GoHighLevel's editor (View live page) | `last_channel` unchanged (not gohighlevel) | |
| L5 | Calculator | Change the risk amount | `tool_use` then `calculation_complete` (calculator=position_size), each once | |
| L6 | Free tool selected | On /free-tools click a card | `select_content` (content_id = tool id) | |
| L7 | TradingView click | Click "Open on TradingView" | `tradingview_click` | |
| L8 | Form 7 success only | Click "Keep Me Ahead" with an empty email | **No** `generate_lead` | |
| L9 | Form 7 submission | Submit a real test address | Exactly **one** `generate_lead` with `source_page`; the GoHighLevel contact has `first_channel` / `last_channel` | |
| L10 | Membership CTA | Click "Become a Member" | `select_promotion` (creative_slot = nav, hero…) | |
| L11 | Checkout initiated | Scroll to the embedded checkout on /join | `begin_checkout` once | |
| L12 | /welcome is not a purchase | Load `/welcome`, then reload | `checkout_return` once; **no** `purchase` | |
| L13 | Activation app | Open `activate.startuptrading.com/?sut_fs=qa` | Same GTM container; page_view with `page_location` **without** `sut_` parameters; /admin pages show no GTM | |
| L14 | Verified purchase | One real purchase above $0 (refund afterwards), then activate in the same browser | After the next sync (≤15 min): `purchase` in GA4 Realtime with `transaction_id` = Whop `pay_…`; `ninjatrader_linked` and `activation_complete` follow. DebugView doesn't show server events (use Realtime) | |
| L15 | Duplicate webhook | Whop → Webhooks → Replay that payment's delivery | No second `purchase` (GA4 Realtime and `/admin/marketing`) | |
| L16 | Refund | Refund it in Whop | `refund` in GA4 within about 12 h; net revenue drops on the dashboard | |
| L17 | QA exclusion | Add the test membership to `MARKETING_EXCLUDE_MEMBERSHIPS` **before** L14 if you don't want it in GA4 | No server events for it | |
| L18 | Consent | In the console: `sutConsent('denied')`, reload | Tag Assistant Consent tab: analytics_storage **denied**; `sut_attr` not stored. Then `sutConsent('granted')` | |
| L19 | EEA default | GA4 DebugView with a VPN in Germany (optional) | Events arrive as cookieless pings (no client id persistence) | |
| L20 | No personal data | Tag Assistant → each GA4 hit's parameters | No email, name or affiliate code anywhere | |
| L21 | Mobile | Repeat L2, L5 and L9 on a phone (use GA4 Realtime) | Same results | |
| L22 | Dashboard | `/admin/marketing` | Status line: GA4 reports **connected**, server events **on**; visitors and leads filled | |

Then **Publish** (6.5). The automated tests cover the container structure, loading
GTM once, consent defaults, PII exclusion, the GA client id join, server events
(once each, QA excluded, nothing for $0), the GA4 Data API connector and the
dashboard: `tests/test_ga4.py`, `test_attribution.py`, `test_marketing.py`.

## 10. Your checklist

| # | Where | Action |
|---|---|---|
| 1 | GA4 | 6.1: enhanced measurement settings, domains, unwanted referrals, **API secret**, retention, custom dimensions, key events |
| 2 | GTM | 6.2: import the container, enable Consent Overview (don't publish yet) |
| 3 | GoHighLevel → Settings → Tracking code | 6.3: header = `site-tracking.html`, body = `site-tracking-body.html`, in every website/funnel |
| 4 | GoHighLevel pages | Re-paste the embeds: `/free-tools`, calculator, TradingView page, `/welcome`, `/join` (`ghl-embed.html`). `/setup` waits for the product download links |
| 5 | Render | 6.4 + 8.1: `GTM_CONTAINER_ID`, `GA4_MEASUREMENT_ID`, `GA4_API_SECRET`, `GA4_PROPERTY_ID`, `GA4_SERVICE_ACCOUNT_JSON`; `MARKETING_EXCLUDE_MEMBERSHIPS` / `_EMAILS` |
| 6 | Google Cloud + GA4 | 8.1: service account with Viewer on the property |
| 7 | Whop | Webhook subscribed to **payment.succeeded, payment.failed, payment.created, payment.pending** (+ the membership events); API key has **payment:basic:read** |
| 8 | GoHighLevel → Form 7 and workflows | Section 7 (hidden fields `first_channel`, `last_channel`; Original fields; workflow; subscriber workflow; `GHL_CUSTOM_FIELDS_JSON` keys `acquisition_first_channel`, `acquisition_last_channel`) |
| 9 | Testing | Section 9, then publish GTM |
| 10 | GoHighLevel Media | Upload the two product zips; send me the links for `products.json`. Never upload them to GitHub |
| 11 | Whop + Discord | Section 12: community redirect URL, Discord roles via Whop, channel permissions; then re-paste header + all embeds, import + publish GTM |

## 11. Blockers and limitations

- **Nothing collected before GTM is published.** No historical visitor data exists.
- **Server events need `GA4_API_SECRET`**, and the dashboard's GA4 columns need the service account (8.1).
- **Unattributed buyers:** anyone who buys on Whop's store page or activates on another device is counted after 72 h but unattributed. Phase 2 (Whop checkout metadata) would fix this, but it changes the checkout and needs your approval.
- **Whop:** payment webhooks need `webhook_receive:payments`; the refund refresh needs `payment:basic:read`. There's no refund webhook (refunds are seen within about 12 h), and `billing_reason` values aren't documented, so initial vs renewal is decided by payment order.
- **Consent:** no banner yet, so EEA, UK and Swiss visitors are measured with cookieless pings only, until a Consent Mode v2 banner is added.
- **Safari/ITP** can cap script-set storage at 7 days, so long gaps can lose first-touch data (GA4 has the same limit).
- **No spend data:** CAC and ROAS are unavailable.
- **Product files** are hosted outside GitHub (the repository is public). The `/setup` buttons stay placeholders until both `download_url`s are set.
- **Settings in Render outside the code:** check `/health`. If it reports `"mode":"all_members"`, unrestricted licensing is on in Render; set `LICENSE_ALL_MEMBERS=false` to keep it off (see `PRODUCTION_LICENSING.md`). `membership_open` is off in the site build, reminders are held, and no campaigns or emails were sent.

## 12. Free community (Discord)

**Product (verified against the Whop API on 26 Nov 2026):** "StartUpTrading
Community", product **`prod_QB1IxeSU30Qm6`**, plan **`plan_Nzi6M0goKvcWY`** ($0,
one-time). It's a separate product from the paid membership (`prod_Nr8ggb93WCyC1`).

**Guarantees (in code, tested in `tests/test_community.py`):**
- **No licenses:** community members are never licensed. Licensing, activation and
  emails only consider the paid product and its two plans, and a community-only Whop
  user can't sign in to the activation app.
- **No revenue:** community memberships are never paid subscribers or revenue.
  Revenue and GA4 purchases count only the paid product's payments.
- **Upgrades:** a community member can buy the paid membership as normal. The
  dashboard counts the upgrade (same Whop user) and its revenue.
- **Recorded for marketing only:** verified community joins arrive through Whop's
  `membership.*` webhooks, are stored in `community_members` (IDs, status, join date),
  and appear in `/admin/marketing` → Free community.

**On the site:**
- **Offer:** "Join the free Discord" appears on `/free-tools`, the calculator and the
  TradingView page (`community_join_url` in `site.config.json`).
- **Events:** clicks send `community_join_click` (GA4, with `placement`). Returning
  from Whop with `?community=joined` sends `join_group` (GA4 recommended event,
  `group_id=startuptrading_community`), once per browser, attributed to the visitor's
  channels.

### 12.1 Whop (you)
1. Whop dashboard → **StartUpTrading Community** → plan settings → **Redirect URL after
   checkout**: `https://startuptrading.com/free-tools?community=joined`. Use exactly this:
   the `community=joined` part records the join in GA4.
2. Whop dashboard → Apps → **Discord** (the bot already connected to your server):
   - **StartUpTrading Community** → grant role **Community**.
   - **StartUpTrading** (paid) → grant roles **Member** and **Community**.
   - Turn on "remove roles when access ends" for both.
3. Whop → Developer → Webhooks: your existing webhook is account-wide, so it already
   receives community `membership.*` events. Nothing to add.

### 12.2 Discord (you)
1. Server Settings → **Roles** → create **Community** and **Member**. Drag the **Whop
   bot's role above both**, or Whop can't assign them.
2. Channels:
   - **@everyone:** can see only #welcome and #rules.
   - **Community category** (#announcements, #free-tools-help, #general, #market-talk):
     View Channel for **Community**. #announcements is send-only for staff.
   - **Members category** (#trade-room, #masterclasses, #indicator-support,
     #member-chat): View Channel for **Member** only.
3. Safety:
   - Server Settings → Safety Setup → Verification level **Medium**.
   - **AutoMod** on (spam, mention spam, links in #general).
   - Slow-mode of 10 s in #general.
   - Pin the rules: education only, no trade signals or profit claims.

### 12.3 Re-deploy (you)
This change updates `tracking.js`, so **re-paste the header code and every embed**:
- **Header:** `site-tracking.html`. **Body:** `site-tracking-body.html`.
- **Embeds:** `/free-tools`, calculator, TradingView page, `/welcome`, `/join`,
  `/setup`.

Then import the updated GTM container (Merge → Overwrite) and **Publish**, and run
`python growth/gtm/check_live.py`: every page should say OK.

### 12.4 Annual plan ID fix (found while verifying)

Whop's canonical ID for the annual plan is **`plan_B84PWlvXemyfX`**. The configuration
used `plan_B84PWLvXemyFX`. Whop's checkout tolerated it, because its lookup ignores
letter case, but membership records carry the canonical spelling. That would have
stopped annual buyers being recognised for licensing.

All references now use the canonical ID, and plan matching ignores letter case.
Monthly (`plan_qSXeS0xoDapGU`) was already correct.
