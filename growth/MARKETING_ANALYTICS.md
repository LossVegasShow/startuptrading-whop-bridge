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
| Google Tag Manager | **Not installed** | No `GTM-` container on any page |
| Google Analytics 4 | **Not installed** | No `G-` measurement ID. Every `dataLayer` event so far went nowhere |
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

All events are pushed to `dataLayer` by `tracking.js` (browser) with
`first_channel`, `last_channel`, `first_touch`, `last_touch` and `affiliate`
attached. No emails, names, license keys or credentials are ever pushed.

| Activity | dataLayer event | GA4 event (set in GTM) | Parameters | Fires | Dedupe |
|---|---|---|---|---|---|
| Free tool page opened | `free_tool_view` | `free_tool_view` | `tool_id` | Page load | Once per page |
| Calculator used | `tool_use` | `tool_use` | `tool_id` | First input | Once per tool per page |
| Calculation completed | `calculation_complete` | `calculation_complete` | `tool_id`, `calculator` (`position_size`, `prop_firm`) | First result after the visitor changes an input (not the page's first render) | Once per calculator per page |
| Free tool selected (directory) | `free_tool_select` | `select_content` | `content_type=free_tool`, `content_id=tool_id` | Card link click | Per click |
| TradingView indicator link | `outbound_click` (`destination=tradingview`) | `tradingview_click` | `tool_id` | Click | Per click |
| Email signup completed | `email_subscribe` | `generate_lead` (key event) | `source_page`, `interest`, `tool_id`, `form_id` | GoHighLevel's own **successful-submission** message from our iframe, never a click | Once per form per page |
| Membership offer clicked | `checkout_intent` | `select_promotion` | `promotion_name=membership`, `creative_slot=placement` | Click | Per click |
| Checkout initiated | `checkout_view` | `begin_checkout` (key event) | — | The embedded Whop checkout scrolls into view (Whop exposes no "started typing" event) | Once per page |
| Returned from checkout (unverified) | `checkout_return` | `checkout_return` | — | `/welcome` load | Once per browser session |
| Product download initiated | `file_download` | `file_download` | `file_name`, `file_extension`, `link_url` | Download button click on `/setup` | Per click |
| Subscription created, renewal, cancellation, failed payment, refund | — (server) | — (phase 2: Measurement Protocol) | — | Whop signed webhooks → `/admin/marketing` | Webhook id + payment id |
| NinjaTrader account linked, indicators licensed, activation completed | — (server) | — | — | Licensing app → `/admin/marketing`, CRM `activation_status` | Engine is idempotent |

Server-side outcomes stay out of GA4 in phase 1 on purpose: the browser can't
verify them, and Whop and the licensing app are the source of truth.

## 6. GA4 and Google Tag Manager setup (you)

1. **Create GA4**: analytics.google.com → Admin → Create property "StartUpTrading" →
   Web stream `https://startuptrading.com`. Copy the **Measurement ID** (`G-…`).
   - In the stream: Enhanced measurement **on**, but turn **off** "Form interactions"
     (it would count clicks as submissions).
   - Admin → Data settings → Data retention → **14 months**.
   - Admin → Data streams → Configure tag settings → **List unwanted referrals**: add
     `gohighlevel.com`, `leadconnectorhq.com`, `msgsndr.com`, `whop.com`,
     `stripe.com`, `paypal.com`.
   - Same screen → **Configure your domains**: `startuptrading.com`,
     `activate.startuptrading.com` (cross-domain).
2. **Create GTM**: tagmanager.google.com → container "startuptrading.com" (Web). Copy
   the two snippets.
3. **Install GTM site-wide** in GoHighLevel: Settings → Tracking code → **Header**:
   paste GTM's `<script>` snippet **above** the existing StartUpTrading
   `site-tracking.html` code. Body: paste GTM's `<noscript>` snippet. Do this in
   every website/funnel serving startuptrading.com.
4. **In GTM**, create:
   - **Variables** (Data Layer Variable): `first_channel`, `last_channel`, `tool_id`,
     `source_page`, `interest`, `form_id`, `placement`, `calculator`, `file_name`,
     `file_extension`, `link_url`, `affiliate`.
   - **Variable "GA4 event name"** (Lookup Table on `{{Event}}`):
     | Input | Output |
     |---|---|
     | `email_subscribe` | `generate_lead` |
     | `checkout_intent` | `select_promotion` |
     | `checkout_view` | `begin_checkout` |
     | `free_tool_select` | `select_content` |
     | `outbound_click` | `tradingview_click` |
     | default | `{{Event}}` |
   - **Tag "GA4 – Google tag"**: Google tag, ID = your `G-…`. Shared event settings
     → user properties `first_channel` = `{{first_channel}}`, `last_channel` =
     `{{last_channel}}`. Trigger: **Initialization – All Pages**.
   - **Tag "GA4 – SUT events"**: GA4 Event, Measurement ID `G-…`, Event Name
     `{{GA4 event name}}`. Parameters: `tool_id`, `source_page`, `interest`,
     `form_id`, `calculator`, `file_name`, `file_extension`, `link_url`,
     `affiliate`, and `creative_slot` = `{{placement}}`. Trigger: Custom Event, event
     name matches RegEx
     `^(free_tool_view|tool_use|calculation_complete|free_tool_select|outbound_click|email_subscribe|checkout_intent|checkout_view|checkout_return|file_download)$`.
     Don't include `sut_attribution`: it's for variables only.
   - **Consent:** in the container settings, enable Consent Overview. If you add a
     consent banner, use one with Google Consent Mode v2 (for example CookieYes or
     Cookiebot from the GTM gallery). On "decline" it should also run
     `window.sutConsent('denied')`, which stops `tracking.js` storing anything (the
     Form 7 embed already respects recognised banners).
   - **Preview**, run tests T1–T8 (section 9), then **Submit → Publish**.
5. **In GA4** (after the first data arrives):
   - Admin → Custom definitions → event-scoped dimensions: `tool_id`, `source_page`,
     `interest`, `calculator`, `affiliate`.
   - User-scoped: `first_channel`, `last_channel`.
   - Admin → Events → mark **`generate_lead`** and **`begin_checkout`** as key events.
6. Optional: set `GA4_PROPERTY_URL` in Render to your GA4 property's home URL, so
   the dashboard links to it.

**Built-in GA4 reports cover:** unique visitors (Users), sessions, landing pages,
channels (Traffic acquisition; use `first_channel` for our taxonomy), new vs
returning, engagement, devices, countries, and campaigns.

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

**Built (phase 1):** `https://activate.startuptrading.com/admin/marketing` (admin
sign-in). It's in the existing app, so there's no new hosting and no new login. Every
number is labelled:
- **Verified:** subscribers, paying subscribers, net revenue, initial and renewal
  revenue, refunds, failed payments, realised LTV, activation and NinjaTrader link
  rates, churn, attribution coverage, and QA exclusions.
- Breakdowns by channel (first or latest touch), landing page and the verified half of
  the funnel.
- **Estimate:** MRR.
- **Unavailable (not copied in):** visitors, leads, spend, CAC and ROAS, which are
  shown as GA4, GoHighLevel or "No spend data".
- **Filters:** date range, first or latest touch, channel, campaign, landing page,
  affiliate, organic or paid.

**Phase 2 (when you want the full funnel in one place):**
1. **Visitors and engagement:** GA4 Data API with a service account (read-only Viewer on
   the property). Daily pull of users, sessions and key events by `first_channel` and
   landing page into a `ga4_daily` table.
2. **Leads:** GoHighLevel API (`contacts` with the `free-tools-lead` tag, by original
   channel), daily.
3. **Spend:** a small "spend" form on the dashboard (channel, month, amount) for CAC and
   ROAS. Ad-platform APIs later, if spend grows.
4. **Coverage:** Whop checkout-configuration metadata (section 4).
5. **Purchases in GA4:** Measurement Protocol `purchase` from the webhook, using the GA
   client id passed in the handoff.

## 9. Testing protocol

Do every browser test in a **fresh private window**. Inspect: GTM Preview (events
and parameters), DevTools → Application → Local Storage → `sut_attr` (first and
last), Form 7 contact fields in GoHighLevel, `/admin/marketing`, and the
membership's Snapshot in `/admin`. "Same window" means continue without closing it.

| # | Scenario | Steps | Expected |
|---|---|---|---|
| T1 | Direct visit | Type `startuptrading.com/free-tools` | first: `(direct)`, channel `direct`; no last |
| T2 | Google | Search Google, click our result | first `google` / `organic`, channel `google_organic` |
| T3 | Instagram UTM | Open a generator link for Instagram | first `instagram` / `social`, campaign as set |
| T4 | YouTube UTM | Generator link for YouTube | channel `youtube`, content kept |
| T5 | TradingView | Click our link from the TradingView profile | channel `tradingview` |
| T6 | ChatGPT | Click a startuptrading.com link in ChatGPT | channel `ai_referral` (the original contaminated case) |
| T7 | Affiliate | `startuptrading.com/join?a=<real affiliate>` | channel `affiliate`; the Whop checkout is credited (PRODUCTION_LICENSING tests A1–A7) |
| T8 | Navigation | From T4, visit the calculator, then `/free-tools`, then the TradingView page | first and last stay `youtube`; each page sends `free_tool_view` once |
| T9 | GoHighLevel referrer | Open any page from inside the GoHighLevel dashboard | first/last **not** changed to `gohighlevel` |
| T10 | Form 7 submission | Submit on the calculator (same window as T4) | GTM: exactly one `email_subscribe` / `generate_lead`; contact: `first_channel=youtube`, Original channel `youtube`, tag `source-youtube`, `free-tools-lead`, one welcome email |
| T11 | Returning visitor | Close the window, reopen the same browser (not private), type the URL | first and last unchanged |
| T12 | Repeat submission | Submit Form 7 again from a new private window with an Instagram link and the same email | Form fields update to `instagram`; **Original channel stays `youtube`**; no second welcome email |
| T13 | Whop checkout | From the T4 window, Join → checkout loads | `checkout_intent` then `begin_checkout`; affiliate kept if set |
| T14 | Successful subscription | Complete with a 100%-off code; land on `/welcome` | `checkout_return` once. In `/admin`: the new membership; its payment row (if Whop sends one for $0) is **not** revenue |
| T15 | Activation with attribution | On `/welcome` click Activate → Whop sign-in → link NinjaTrader | Snapshot audit shows `attribution_captured`; `/admin/marketing` counts the subscriber under `youtube` with capture rate > 0 |
| T16 | Duplicate webhook | Whop → Developer → Webhooks → the delivery → **Replay** (keeps the same webhook-id) | `/admin` shows it as a duplicate; revenue unchanged |
| T17 | Paid payment | One real low-price purchase (or a refunded real one) | Revenue appears under the right channel; after a refund and the next refresh (≤12 h), net revenue drops |
| T18 | Cancellation | End the test membership | Churned +1 for its channel; CRM `former-subscriber` |
| T19 | QA exclusion | Add the test membership to `MARKETING_EXCLUDE_MEMBERSHIPS`, redeploy | It disappears from every number; "QA memberships excluded" +1 |
| T20 | Mobile and desktop | Repeat T3 and T10 on a phone (Safari) and desktop Chrome | Same results; the form fits the screen |
| T21 | Consent declined | In the console run `sutConsent('denied')`, reload with a UTM link | `sut_attr` not stored; events still carry this page's source only |
| T22 | Consent accepted | `sutConsent('granted')`, reload | Stored again |

Automated: `tests/test_attribution.py` covers 41 scenarios in the real browser code,
including every source above and the contaminated case. `tests/test_marketing.py`
covers the handoff, the signed webhook, idempotency, PII exclusion, revenue rules,
QA exclusion and filters. `tests/test_signup_browser.py` covers the real
embedded-form behaviour.

## 10. Your checklist

| # | Where | Action |
|---|---|---|
| 1 | GoHighLevel Media | Upload the two product zips; send me the links for `products.json` (the repository stays public; product files are never committed) |
| 2 | GoHighLevel → Settings → Tracking code | Re-paste the new `site-tracking.html`, then the GTM snippets (section 6) |
| 3 | GoHighLevel pages | Re-paste the embeds: `/free-tools`, calculator, TradingView page, `/welcome`, `/setup` (and `/join` + Home if they use `ghl-embed.html`) |
| 4 | GA4 + GTM | Section 6 |
| 5 | Form 7 | Add hidden fields `first_channel`, `last_channel` (7.1) and the four Original fields (7.2) |
| 6 | GoHighLevel workflows | 7.3 and 7.4 |
| 7 | Render → Environment | `MARKETING_EXCLUDE_MEMBERSHIPS` = your test memberships (comma-separated, e.g. `mem_T1AdJRcFkJNNSk,mem_XN7y9ppQsdx2np`); `MARKETING_EXCLUDE_EMAILS` = QA emails; optional `GA4_PROPERTY_URL`; `GHL_API_KEY`, `GHL_LOCATION_ID`, `GHL_CUSTOM_FIELDS_JSON` if CRM sync isn't on yet |
| 8 | Whop → Developer → Webhooks | Make sure the webhook is subscribed to **payment.succeeded, payment.failed, payment.created, payment.pending** (and the membership events already in use). The API key needs **`payment:basic:read`** for the refund refresh |
| 9 | Testing | Section 9 |

## 11. Blockers and limitations

- **GA4/GTM not installed**: no anonymous visitor data exists until you do section 6.
  Nothing can be backfilled.
- **Product files** are hosted outside GitHub (the repository is public): the /setup buttons stay placeholders until both `download_url`s are set.
- **Attribution coverage**: buyers who purchase on Whop's store page, or activate on
  another device, show as Unknown until phase 2 (checkout metadata).
- **Whop permissions**: payment webhooks need `webhook_receive:payments`; the refund
  refresh needs `payment:basic:read`. Affiliate details on a membership need
  `affiliate:basic:read`, and are never included in webhooks.
- **Whop `billing_reason` values** aren't listed in the public docs, so initial vs
  renewal is determined by payment order instead.
- **No refund webhook** at Whop: refunds appear after the next refresh (up to about
  12 hours).
- **Spend data** doesn't exist yet: CAC and ROAS are shown as unavailable.
- **Consent**: there's no consent banner. If you market to the EU or UK, add a Consent
  Mode v2 banner before turning on GA4 there.
- **Safari/ITP**: browser storage set by scripts can be capped at 7 days in Safari, so
  long gaps can lose first-touch data in Safari. GA4 has the same limit.
- **Live state, unchanged by this work**: licensing for all members and
  `membership_open` were already on. Reminders are still held, and no campaigns or
  emails were sent.
