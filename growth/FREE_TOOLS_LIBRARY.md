# Free tools library: setup, SEO, CRM, analytics and testing

Everything lives in `sales-site/`:
- `tools.json` is the tool registry.
- `site.config.json` holds URLs and switches.
- `src/` holds the page templates.
- `build.py` builds the pages; the output is in `dist/`.

After any change run `python sales-site/build.py` and paste the new
`dist/*-embed.html` into the matching GoHighLevel page.

## 1. Pages

| GHL path | File to paste | Index? | Notes |
|---|---|---|---|
| `/` (Home) and `/join` | `ghl-embed.html` | Home yes, `/join` no (duplicate) | The sales page. The homepage switch waits for launch Gate 2 |
| `/free-tools` | `free-tools-embed.html` | Yes | Directory with category filters |
| `/tradingview/atr-position-size-planner` | `tradingview-atr-planner-embed.html` | Yes | Companion page for the Pine script |
| `/futures-position-size-calculator` | `calculator-embed.html` | Yes | Web calculator; publish it **before** `/free-tools` (the directory links to it) |
| `/indicators` | (existing page) | Yes | Keep it. After the homepage switch, confirm it still loads |
| `/learn` | (not built yet) | — | The nav's **Education** link goes to the sales page's education section until `learn_url` is set |
| `/welcome`, `/setup` | existing files | No | Members only |

**Nested path:** if GoHighLevel won't accept `tradingview/atr-position-size-planner`
as a page path, use `tradingview-atr-position-size-planner`. Then change
`tv_atr_page_url` in `site.config.json`, rebuild, and re-paste every page; every
link reads that one setting.

**Adding a tool later:**
1. Add one object to `tools.json`: id, name, platform, categories, status, page,
   summary and call to action.
2. Add its URL to `site.config.json`.
3. Rebuild. The directory, the filters and the structured data update by themselves.
4. A category with no tools shows a "coming soon" note, never a dead link.

## 2. Switches in `site.config.json`

| Setting | Now | Change when |
|---|---|---|
| `membership_open` | `""` (closed) | **Gate 2** (homepage switch): set `"true"`. Free pages then show the full nav, **Become a Member** and "See the membership". While closed, free pages never link to the purchase funnel |
| `sales_page_url` | `https://startuptrading.com/join` | Gate 2: `https://startuptrading.com/` |
| `tv_atr_script_url` | `""` | After the script is published on TradingView. The "Open on TradingView" buttons appear; until then the page says "Coming soon to TradingView" |
| `ghl_subscribe_form_url` | Form 7's embed URL (set) | The optional sign-up section appears on the free pages (section 4). Blank removes it |
| `learn_url` | `""` | When `/learn` exists. The nav's Education link moves to it |
| `tv_profile_url` | `""` | Jack's TradingView profile URL. Shows "Follow Jack on TradingView" on the companion page |
| `tv_atr_video_url` | `""` | The YouTube demo of the planner. Shows a "Watch it in action" section |

Rebuild and re-paste after each change.

## 3. SEO metadata

> **Superseded for the three tool pages by `FLAGSHIP_POSITIONING.md` §6** (the final titles, descriptions, canonicals and alt text). The table below is kept for Home and `/indicators`.

GHL ignores `<title>` and `<meta>` inside a Code element, so set them in each
page's **SEO / meta** settings. GHL uses these for the social-sharing (Open Graph)
title and description too. Add a **social image** (1200×630) where marked.

| Page | Title | Meta description | Social image |
|---|---|---|---|
| Home | Futures Indicators for NinjaTrader 8 \| StartUpTrading | ATR position sizing and trend scanning indicators for NinjaTrader 8, licensed automatically. Every new tool, Jack's trade room and masterclasses. $99/mo. | Brand: "Jack's tools. Your charts." |
| /free-tools | Free Futures Trading Tools for TradingView & NinjaTrader | Free tools from futures trader Jack Gleason: an ATR position size planner for TradingView, a position size calculator and an ATR indicator for NinjaTrader 8. | Three tool cards |
| /tradingview/atr-position-size-planner | ATR Position Size & Stop Planner for TradingView (Free) | Free TradingView indicator: set your dollar risk, place the stop by ATR and see how many futures contracts fit. Method, examples and limitations. | The planner on an ES chart |
| /futures-position-size-calculator | Futures Position Size Calculator & Prop-Firm Risk Planner (Free) | Free futures position size calculator for ES, NQ, MES, MNQ, CL, GC and more. Size from ATR or a fixed stop, and plan risk per trade for a prop-firm drawdown. | The calculator |
| /indicators | Free ATR Indicator for NinjaTrader \| Jack Gleason (keep) | (keep) | (keep) |

**Already built into the pages:**
- **Structured data:**
  - Home: Organization, WebSite, SoftwareApplication with both prices, FAQPage
  - `/free-tools`: CollectionPage with an ItemList, BreadcrumbList
  - TradingView page: free SoftwareApplication (with the script link once published), BreadcrumbList
  - Calculator: free WebApplication
- **Unique titles, descriptions and H1s** on every page.
- **Original copy** on each page.
- **Internal links:**
  - every page → /free-tools (footer)
  - calculator ↔ TradingView page ↔ free indicator
- **No unsupported claims.** The phrase rules pass on every page.

**Sitemap:** GHL generates `startuptrading.com/sitemap.xml` from published pages.
- After publishing, open it and confirm the four indexable pages are listed.
- Submit it in Google Search Console and Bing Webmaster Tools.
- Use **URL Inspection → Request indexing** for each new page.

**Existing URLs:** `/indicators`, `/welcome` and `/join` keep their paths. No URL
that's already indexed is removed.

## 4. Optional email sign-up (GoHighLevel CRM)

Email is never needed to use the script, calculator or indicator page. The sign-up
is the last section of each free page (below every tool), and it loads only when the
reader scrolls near it.

**The form:** "Form 7", embed URL
`https://api.leadconnectorhq.com/widget/form/sBZe4CvOR4NBkd0oioTZ`, set as
`ghl_subscribe_form_url`. It carries its own headline ("Be first to access what we
build next.") and description, so the page adds only an "Optional · Everything on
this page works without an email" line above it.

### 4.1 How attribution reaches GoHighLevel (checked against GHL's code, Nov 2026)

- `tracking.js` builds the iframe URL with the parameters below, then loads
  GoHighLevel's `form_embed.js` once.
- `form_embed.js` merges the page URL's query string with the iframe's and sends
  them, the page URL and the referrer to the form (its `query-params` message).
- The form fills each **hidden field whose query key matches** a parameter, and
  sends the page URL's own `utm_*` to GoHighLevel's built-in contact attribution
  (First / Latest Attribution).

So there are two layers:
1. **Built in, no setup:** GoHighLevel records the UTMs on the page where the
   person signs up (and its own first-visit session) on the contact.
2. **Ours, needs the hidden fields below:** the first touch across visits (from
   `tracking.js`, which remembers it in the browser), the latest touch, the Whop
   affiliate code and the page and tool. Without these fields, GoHighLevel receives
   the values but has nowhere to store them.

**Add these hidden fields to the form** (Sites → Forms → Form 7 → add field →
Hidden; create each as a contact custom field, single-line text, and set its
**Query key** exactly as shown):

| Custom field | Query key | Example value |
|---|---|---|
| Signup page | `source_page` | `tv_atr`, `calculator`, `free_tools` |
| Signup interest | `interest` | `tradingview`, `calculators`, `free-tools`, `education` |
| Signup tool | `tool_id` | `atr-position-size-planner` |
| Affiliate code | `affiliate` | the Whop affiliate code, if any |
| First UTM source | `first_utm_source` | `youtube` |
| First UTM medium | `first_utm_medium` | `social` |
| First UTM campaign | `first_utm_campaign` | `risk_lab` |
| First UTM content | `first_utm_content` | `short25` |
| Latest UTM source | `last_utm_source` | `tradingview` |
| Latest UTM medium | `last_utm_medium` | `social` |
| Latest UTM campaign | `last_utm_campaign` | `risk_planner` |
| Latest UTM content | `last_utm_content` | |

A visit with no UTMs but an outside referrer is recorded as source = the referring
site (for example `youtube.com`) with medium `referral`. Direct visits leave them blank.

### 4.2 Form settings to change in GoHighLevel

| Setting | Change to | Why |
|---|---|---|
| **On submit** | Keep **"Show thank-you message"** (don't redirect). Text: *"You're in. Watch your inbox for the next free tool."* | The current text is GHL's default "We appreciate your feedback!". A redirect would leave the free tool the person was using |
| Form **border** | Colour `#1d2530` (or none), radius 12 | The white border clashes with the site |
| Field **label** colour | `#b3bcc9` | The current grey labels are hard to read on the dark card |
| Email label | "Email" | "Email Required" reads oddly; the field is already marked required |
| Consent checkbox | Above the button | People should see what they agree to before submitting |
| Background / button | Keep `#141922` / orange | Already matches |
| Name | "Free tools updates" | Easier to find in reports and workflows |

### 4.3 Workflow (Automation → Workflows)

Trigger: *Form submitted = Free tools updates*.
- Add tag `free-tools-subscriber`, plus `interest-<value>` (one If/Else branch per
  Signup interest value) and `source-<value>` when First UTM source is set.
- Optionally send a welcome email listing the free tools. GHL's email builder adds
  the **unsubscribe link** automatically. Double opt-in (a confirm-link email, tag
  `confirmed` on click) is recommended for deliverability.
- **Unsubscribes:** GHL handles them. Every marketing email has its unsubscribe
  link, and an unsubscribed contact gets DND for email and is excluded from
  campaigns. Never re-add unsubscribed contacts to lists.
- **Keep it separate from member data.** These contacts are prospects. Members are
  synced by the licensing app with their own tags. A subscriber who later buys is
  merged by email in GHL, and both tag sets remain.

### 4.4 Cookie consent, mobile and loading

- The embed sets `data-cookie-consent="true"` with provider `auto`. GoHighLevel's
  script looks for a consent banner it recognises (Cookiebot, OneTrust, CookieYes,
  Osano, Usercentrics, Complianz, Termly, iubenda or any TCF banner). **Until a
  visitor accepts marketing cookies in one, the form sets no marketing or ad
  cookies.** With no banner on the site, that means never. The submission and
  hidden fields work either way. If you add a banner later, nothing here changes.
- `tracking.js` itself sets no cookies; it keeps attribution in the visitor's browser
  storage.
- The form is full width on phones (checked at 390 px and 1280 px, no sideways
  scrolling). Its height is reserved while it loads, so the page doesn't jump, and
  GHL's script then sets the exact height.
- The form starts loading only when the reader scrolls within about 800 px of
  it, so it never slows the tools above it. With JavaScript off, a link to
  the form appears instead.

### 4.5 Counting sign-ups (successful submissions only)

`email_subscribe` fires when the form tells the page that **GoHighLevel accepted
the submission**. That's the form's own success message, sent only after the
submit succeeds. Button clicks and failed validation don't count. It fires at most
once per form per page view, and only for messages from our own form iframe. The
old `?subscribed=1` redirect method has been removed, so nothing double-counts.

### 4.6 Verify it end to end (5 minutes, after adding the hidden fields)

1. Open in a private window:
   `https://startuptrading.com/tradingview/atr-position-size-planner?utm_source=test&utm_medium=qa&utm_campaign=form_check&a=<a real affiliate code, or leave out>`
2. Scroll to the form and sign up with an address you control.
3. In GTM Preview (or the browser console: `dataLayer.filter(e => e.event === 'email_subscribe')`),
   check there is **exactly one** `email_subscribe`.
4. In GHL → Contacts, open the new contact:
   - the custom fields show Signup page `tv_atr`, Signup interest `tradingview`,
     First/Latest UTM source `test`, medium `qa`, campaign `form_check`, and the
     affiliate code if you used one;
   - the contact's **Attribution** shows source `test` / `qa` / `form_check`.
5. Repeat once on `/futures-position-size-calculator` with different UTMs. Latest
   UTM should change, First UTM should stay `test` (same browser).
6. Delete the test contacts.

## 5. Analytics

`dist/site-tracking.html` is the **site-wide tracking code**. It replaces
`affiliate-tracking.html`, because it includes the affiliate capture.
1. Paste it into **Settings → Tracking code → Header** in **every** GHL website
   that serves startuptrading.com.
2. Remove the old affiliate snippet.

It writes events to `dataLayer`. To see them in reports, add **Google Tag
Manager** in the same Header box. Then in GTM, create a GA4 Configuration tag
plus one GA4 Event tag per event below, each with a *Custom Event* trigger
matching the event name.

| Event | When | Useful parameters |
|---|---|---|
| `sut_attribution` | Every page view | `first_touch`, `last_touch` (utm_source/medium/campaign or referrer), `affiliate` |
| `free_tool_view` | A free tool page or the directory opened | `tool_id` |
| `tool_use` | First input in a tool on the page | `tool_id` |
| `outbound_click` | A TradingView script link clicked | `destination`, `tool_id` |
| `email_subscribe` | GoHighLevel accepted a sign-up (section 4.5) | `source_page`, `interest`, `tool_id`, `form_id` |
| `checkout_intent` | Become a Member / Join clicked | `placement` (nav, hero, final, free_page) |
| `checkout_view` | The on-page Whop checkout scrolled into view | — |
| `sut_purchase` | `/welcome` loaded after checkout (once per session) | — |

Mark `sut_purchase` and `email_subscribe` as **key events (conversions)** in GA4.
**Confirmed purchases:** `sut_purchase` measures arrivals on `/welcome`. Whop's
dashboard (and the licensing app's records) are the source of truth for paid
memberships and revenue. Reconcile the two weekly.

Attribution stays in the visitor's browser. First touch is kept, last touch
updates on each new campaign or referrer. No cookies are set and no personal
data is read. Affiliate attribution, licensing and onboarding are unchanged.

## 6. TradingView script: path to publication

1. **Compile:** paste `growth/tradingview/atr-position-size-planner.pine` into
   TradingView's Pine Editor and click **Add to chart**. Fix any compiler message.
2. **Validate the math** on an ES chart. Set risk 500, ATR length 14, multiple 1.5,
   then check the panel by hand:
   - stop points = ceil(ATR × 1.5 ÷ 0.25) × 0.25
   - risk per contract = stop × 50
   - contracts = floor(500 ÷ risk per contract)

   Repeat on NQ1! ($20 a point) and MNQ1! ($2 a point). The companion page's worked
   examples use this same arithmetic.
3. **Jack's approval** of the script, title and description
   (`atr-position-size-planner.description.txt`).
4. **Publish** from the Pine Editor:
   - Publish script → **Public**, **Open-source**.
   - Paste the description. It contains no links or company names, as TradingView
     requires, and it can't be edited after publishing.
   - Add a clean chart screenshot.
5. **Profile:** Premium plan, with the **Signature** set to the text in the
   description file. The signature is the only place a link is allowed.
6. **Wire it up:**
   - Put the published script URL in `tv_atr_script_url`.
   - Change the planner's `status` in `tools.json` to `"available"` and its
     `status_label` to `"Free on TradingView"`.
   - Rebuild, then re-paste `/free-tools` and the companion page.
   - Add the real screenshots.

## 7. Installation and testing checklist

**Install, in this order:**
- [ ] Publish `/futures-position-size-calculator` (`calculator-embed.html`).
- [ ] Publish `/tradingview/atr-position-size-planner` (`tradingview-atr-planner-embed.html`).
- [ ] Publish `/free-tools` (`free-tools-embed.html`).
- [ ] Set SEO titles, descriptions and social images (section 3).
- [ ] Replace the header tracking code with `site-tracking.html` in every GHL website.
- [ ] GTM + GA4 events (section 5).
- [x] GHL form created; `ghl_subscribe_form_url` set.
- [ ] Add the hidden fields and change the form settings (sections 4.1 and 4.2), then the workflow (4.3).
- [ ] Re-paste the three free pages and the header tracking code, then verify (4.6).

**Test (private window):**

| # | Test | Expect | Pass |
|---|---|---|---|
| T1 | `/free-tools` | Three cards with platform and status; filters work; **Education** shows "on the way", no dead link | |
| T2 | Every card button | Opens the right page; the planner card says "Coming soon to TradingView" with no TradingView link | |
| T3 | `/tradingview/atr-position-size-planner` | Method, examples, install, limits, related links; "Coming soon to TradingView" plus "Use the web calculator now" | |
| T4 | `/futures-position-size-calculator` | Works with **no email**; related links at the bottom | |
| T5 | `/indicators` | Loads, before **and after** the homepage switch | |
| T6 | Nav on free pages (membership closed) | Only Free Tools (plus "Get updates" if the form is set); **no links to /join** | |
| T7 | Nav on the sales page | Technology, Free Tools, Education, Community, About Jack, Become a Member; each anchor scrolls to its section | |
| T8 | GTM Preview on `/free-tools?utm_source=test&utm_medium=qa` | `sut_attribution` with first_touch utm_source=test; `free_tool_view` | |
| T9 | Type in the calculator | One `tool_use` | |
| T10 | Optional sign-up | The steps in section 4.6: exactly one `email_subscribe`; the GHL contact has the hidden fields, attribution and tags; the page stays on the tool (thank-you message); unsubscribe link in the welcome email works | |
| T11 | Phone width (390px) | No sideways scrolling on any page | |
| T12 | `sitemap.xml` | Lists Home, /free-tools, the TradingView page and the calculator | |
| T13 | Google Rich Results Test on each page | Structured data detected with no errors | |
| T14 | Affiliate check | `/free-tools?a=test123`, then later the sales page: the checkout still gets the code (PRODUCTION_LICENSING tests A1–A7) | |

**At Gate 2 (homepage switch)**, set `membership_open` to `"true"` and
`sales_page_url` to `https://startuptrading.com/`. Rebuild and re-paste the free
pages, then re-run T6 (the nav should now show the full menu and Become a Member).
