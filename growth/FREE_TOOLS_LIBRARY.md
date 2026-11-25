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
| `ghl_subscribe_form_url` | `""` | After the GHL form exists (section 4). The optional sign-up section appears on the free pages |
| `learn_url` | `""` | When `/learn` exists. The nav's Education link moves to it |

Rebuild and re-paste after each change.

## 3. SEO metadata

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
is an extra section near the bottom of the free pages.

1. **Create the form:** Sites → **Forms** → New, named "Free tools updates".
   - Fields:
     - First name (optional)
     - **Email** (required)
     - **Consent checkbox** (required). Text: *"Email me about new free tools,
       education and StartUpTrading releases. I can unsubscribe at any time."*
   - **Hidden fields**, each with a matching **query key**, so the page can fill them:

     | Hidden field (custom field) | Query key | Filled with |
     |---|---|---|
     | Source page | `source_page` | `free_tools`, `tv_atr` or `calculator` |
     | Interest | `interest` | `free-tools`, `tradingview` or `calculators` |
     | UTM source | `utm_source` | The visitor's first-touch source |
     | UTM medium | `utm_medium` | First-touch medium |
     | UTM campaign | `utm_campaign` | First-touch campaign |
     | Affiliate | `affiliate` | Whop affiliate code, if any |

   - **On submit:** redirect to `https://startuptrading.com/free-tools?subscribed=1`.
     That lets analytics count the sign-up.
   - Style it dark (background `#10151d`, text `#ecf0f5`, button `#fa7b39`) to match.
2. **Copy the form's embed URL** (Share → Embed → the iframe `src`, for example
   `https://api.leadconnectorhq.com/widget/form/XXXX`) into `ghl_subscribe_form_url`.
   Then rebuild and re-paste the free pages.
3. **Workflow** (Automation → Workflows), triggered by *Form submitted = Free tools updates*:
   - Add tags `free-tools-subscriber` and `interest-{{interest}}` (or one
     If/Else branch per interest value).
   - Add tag `source-{{utm_source}}` when it's present.
   - Optionally send a welcome email listing the free tools. Use GHL's email
     builder, which adds the **unsubscribe link** automatically.
   - Optionally use **double opt-in** (send a confirm-link email, and tag
     `confirmed` on click). Recommended for deliverability.
4. **Unsubscribes:** GHL handles them. Every marketing email has its unsubscribe
   link, and an unsubscribed contact gets DND for email and is excluded from
   campaigns. Never re-add unsubscribed contacts to lists.
5. **Keep it separate from member data.** These contacts are prospects. Members
   are synced by the licensing app with their own tags. A subscriber who later
   buys is merged by email in GHL, and both tag sets remain.

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
| `email_subscribe` | The sign-up form submitted (redirect with `?subscribed=1`) | `source_page` |
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
- [ ] Optional: GHL form + workflow (section 4), then set `ghl_subscribe_form_url`, rebuild and re-paste.

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
| T10 | Optional sign-up (if configured) | Submit → redirected to `/free-tools?subscribed=1` → `email_subscribe`; GHL contact has source_page, interest, UTM and the tags; unsubscribe link in the welcome email works | |
| T11 | Phone width (390px) | No sideways scrolling on any page | |
| T12 | `sitemap.xml` | Lists Home, /free-tools, the TradingView page and the calculator | |
| T13 | Google Rich Results Test on each page | Structured data detected with no errors | |
| T14 | Affiliate check | `/free-tools?a=test123`, then later the sales page: the checkout still gets the code (PRODUCTION_LICENSING tests A1–A7) | |

**At Gate 2 (homepage switch)**, set `membership_open` to `"true"` and
`sales_page_url` to `https://startuptrading.com/`. Rebuild and re-paste the free
pages, then re-run T6 (the nav should now show the full menu and Become a Member).
