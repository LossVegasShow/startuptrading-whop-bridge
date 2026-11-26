# Launch sequence, final tests, SEO and the TradingView funnel

Switching the homepage to the sales page makes the offer fully public. Licensing
has to be ready **before** that, so this runs in gates. Don't open a gate until
the one before it passes.

---

## Gate 0: Today (nothing public changes)

`/join` is already reachable, and Whop's own store page sells the membership.
Anyone who buys right now gets Discord and masterclass access from Whop, but
their tools stay "Activating", because licensing is still limited to the test
allowlist. Keep `/join` unlinked and don't promote anything until Gate 2.

Must be true before Gate 1 (details in `PRODUCTION_LICENSING.md`):
- [ ] NinjaTrader Desktop revocation confirmed (`LIFECYCLE_TEST.md` step 6). The
      cleanup reconcile of `mem_XN7y9ppQsdx2np` doubles as this check.
- [ ] Upload both product zips at `activate.startuptrading.com/admin/products` (members-only downloads; never in GitHub). Screenshots still to add.
- [ ] `ALERT_WEBHOOK_URL` is set in Render and a test alert arrived.
- [ ] Jack has confirmed how current members' 2067/2071 licenses were issued.
- [ ] Whop: TSMS & Fibs removed from the product; Discord and masterclasses
      attached to both plans; promo codes set to first period only.
- [ ] Copy sign-off (`sales-site/COPY_REVIEW.md`): "since 2008", "every new tool
      included", masterclasses.

## Gate 1: Licensing on for everyone (still not promoted)

1. Render: `LICENSE_WRITES_ENABLED=true`, `LICENSE_ALL_MEMBERS=true` → deploy.
   `/health` must show `"mode":"all_members"` and `"circuit_breaker":"ok"`.
2. **Final end-to-end test with a real (non-allowlisted) purchase.** Use a new Whop
   account and a 100%-off code, and do it through `/join`.

   | # | Check | Pass |
   |---|---|---|
   | F1 | Checkout completes and lands on `/welcome` | |
   | F2 | Whop grants Discord and masterclass access | |
   | F3 | Activation: Whop sign-in → NinjaTrader email → code → both tools active | |
   | F4 | Snapshot `overall: consistent`, `write_gate` reason "LICENSE_ALL_MEMBERS is on" | |
   | F5 | "Your tools are ready" email arrives once and links to a working `/setup` | |
   | F6 | Following `/setup`, both tools load on a chart in NinjaTrader | |
   | F7 | Cancel immediately in Whop → Reconcile → both licenses expire → tools stop in NinjaTrader | |
   | F8 | `/admin` Needs attention has no HIGH items. Licensing controls show the expected counts | |

3. Existing paying members who already verified are licensed on the next sync.
   Watch the grant count against `BREAKER_MAX_GRANTS_PER_HOUR`.

## Gate 2: Homepage switch (the offer goes public)

1. Paste `sales-site/dist/ghl-embed.html` into the Sales & Onboarding **Home**
   page. Set the title and description from section "SEO" below. Point the domain
   at this website with Home as the default page.
2. Set `/join` to **hide from search engines** (same content as the homepage).
   In `sales-site/site.config.json`, set `membership_open` to `"true"` and
   `sales_page_url` to `https://startuptrading.com/`. Rebuild and re-paste the free
   pages, so their nav and "See the membership" links go live
   (`growth/FREE_TOOLS_LIBRARY.md`).
3. **Post-switch checks** (private window):

   | # | URL / action | Expect | Pass |
   |---|---|---|---|
   | H1 | `startuptrading.com/` | Sales page, both checkouts load | |
   | H2 | `startuptrading.com/?a=test123` → open monthly checkout | Checkout loads (affiliate passed) | |
   | H3 | `/join`, `/welcome`, `/setup` | Load | |
   | H4 | **`/indicators`** (free indicator) | **Still loads.** If it doesn't, recreate it in Sales & Onboarding before promoting; the sales page links to it | |
   | H5 | `/futures-position-size-calculator` | Loads (publish it, see SEO) | |
   | H6 | Old links you've shared (YouTube descriptions, bios) | Still land somewhere sensible | |
   | H7 | One 100%-off test purchase from the homepage | Lands on `/welcome`, activation works | |

## Gate 3: Release held reminders

`/admin/reminders`: review the backlog of paying members who never activated
and release in batches (`PRODUCTION_LICENSING.md` section 5). Each activation is
2 grants, so keep batches under the breaker limit.

## Gate 4: Promote

Affiliates (`PRODUCTION_LICENSING.md` tests A1–A7), TradingView (below),
YouTube (the `video/` pipeline), and email to the free-indicator list.

---

## SEO

### Done in the pages (rebuilt files)
- **Titles and descriptions sized for search results:**
  - Homepage: *Futures Indicators for NinjaTrader 8 | StartUpTrading*.
    Description: *ATR position sizing and trend scanning indicators for
    NinjaTrader 8, licensed automatically. Every new tool, Jack's trade room and
    masterclasses. $99/mo.*
  - Calculator: *Futures Position Size Calculator & Prop-Firm Risk Planner (Free)*.
- **Structured data (JSON-LD) in the page code:** the business, the website, the
  membership as a product with both prices, the 10 FAQs, and the free calculator
  as a free web app. It's generated from the same config and copy as the page, so
  it can't drift. It has no ratings or reviews, because none exist yet and
  inventing them breaks Google's rules.
- **Search terms in the copy where they read naturally:** "NinjaTrader 8",
  "futures", "position size", "ATR", "trend". The hero stays punchy.
- Members-only pages (`/welcome`, `/setup`) are `noindex`.

### To do in GoHighLevel (only you can)
GHL ignores `<title>` and meta tags inside a Code element, so set them per page in
the page's **SEO / meta** settings:

| Page | Title | Description | Index? |
|---|---|---|---|
| Home | Futures Indicators for NinjaTrader 8 \| StartUpTrading | (as above) | Yes |
| /join | same as Home | same | **No** (duplicate) |
| /futures-position-size-calculator | Futures Position Size Calculator & Prop-Firm Risk Planner (Free) | Free futures position size calculator for ES, NQ, MES, MNQ, CL, GC and more. Size from ATR or a fixed stop, and plan risk per trade for a prop-firm drawdown. | Yes |
| /indicators | (keep, include "free ATR indicator NinjaTrader") | | Yes |
| /welcome, /setup | (as set) | | No |

- **Social image:** a 1200×630 image (chart plus logo plus "Jack's tools. Your
  charts.") on Home and the calculator. It shows when links are shared on
  Discord, X or Facebook.
- **Favicon:** the candle logo.
- **Publish the calculator page** (`sales-site/dist/calculator-embed.html`,
  `sales-site/SETUP.md` step 2d). It's the strongest search magnet: people search
  "futures position size calculator" and "ES position size" every day.
- **Google Search Console:** add `startuptrading.com` as a Domain property,
  verify with the DNS TXT record in Namecheap, then submit the sitemap
  (`startuptrading.com/sitemap.xml`; GHL generates it, check under the site's SEO
  settings). Do the same in Bing Webmaster Tools (it can import from Search Console).

### Content that ranks (and feeds TradingView and YouTube)
One topic, four formats. Each piece links to the calculator, and the calculator
links to the membership.

| Search intent | Page / post | Source material |
|---|---|---|
| futures position size calculator; ES/NQ position size | `/futures-position-size-calculator` | built |
| how many contracts should I trade | Blog post from video 001 (transcript → article) | `video/episodes/001…` |
| ATR stop loss futures | Blog post + video 002/004 | `youtube/production/…` |
| prop firm risk per trade / trailing drawdown | Blog post + video 004 | `youtube/production/004…` |
| micro vs E-mini vs E-nano | Blog post + video 003 | `youtube/production/003…` |
| NinjaTrader 8 ATR indicator / trend scanner | Homepage sections + `/indicators` | built |

GHL has a **Blogs** tab: one post per finished video, with the video embedded, a
written walkthrough, and the calculator linked at the end. Aim for one a week.

**Backlinks that matter in this niche** (each one honest and on-topic):
- **NinjaTrader Ecosystem vendor listing:** Jack is already a NinjaTrader vendor,
  so get the tools listed with a link to startuptrading.com.
- YouTube channel About and every video description: link the calculator with
  `?utm_source=youtube`.
- Podcast or guest appearances, and interviews in futures newsletters.
- Forums and Reddit only where their rules allow vendor links (most require
  disclosure and limit self-promotion). Answering questions with the free
  calculator is the safe pattern.

---

## TradingView funnel

### The rules that shape it (verify before posting)
- Publications (scripts, ideas, their titles, descriptions, charts and code)
  **may not contain links or references to websites, social media or company
  names.** Moderators hide violations, and repeated solicitation can get the
  account banned. ([House Rules](https://www.tradingview.com/house-rules/),
  [Script publishing rules](https://www.tradingview.com/support/solutions/43000590599-script-publishing-rules/))
- The **Signature** field is the one exception. With a Premium plan or higher it can
  carry a link, and it's shown under every idea and script.
  ([Signature](https://in.tradingview.com/support/solutions/43000472770),
  [Vendor requirements](https://www.tradingview.com/support/solutions/43000549951-vendor-requirements/))
- Public script limits: 5 per 24 hours, 15 per 30 days. A description can't be
  edited after publishing, so get it right first time.

### The honest fit
The paid tools run in **NinjaTrader 8**, not TradingView. Target TradingView
users who trade **futures** and execute (or would execute) on NinjaTrader or
Tradovate. Message: *"Chart anywhere. Size and manage the trade in NinjaTrader."*
Say "NinjaTrader 8" plainly on the homepage so nobody buys expecting TradingView
indicators.

### The funnel
```
Free open-source script / educational idea on TradingView (no links)
   → Jack's profile + Premium Signature (the only link)
      → startuptrading.com/futures-position-size-calculator?utm_source=tradingview&utm_medium=signature
         → free ATR indicator (email capture) → membership (homepage)
```

### Assets (in `growth/tradingview/`)
- **`atr-position-size-planner.pine`:** open-source Pine v6 indicator, the same
  method the paid ATR tool automates. You set the dollar risk, the stop is a
  multiple of ATR rounded up to a tick, and contracts are rounded down. It shows
  ATR, stop in points and ticks, $/point, risk per contract, contracts and
  actual risk, and suggests the micro when the answer is 0. It uses the symbol's
  point value automatically. **Paste it into TradingView's Pine Editor and click
  "Add to chart" to compile before publishing.** It couldn't be compiled
  outside TradingView.
- **`atr-position-size-planner.description.txt`:** the title, a rule-compliant
  description (no links, no company names), and the Signature text.

### Posting plan (Jack's account)
1. **Profile:** real name, photo, short bio ("Futures trader since 2008. ATR
   sizing and trend scanning."). Turn on Premium and set the Signature.
2. **Week 1:** publish the ATR Position Size & Stop Planner as an open-source,
   public script.
3. **Every week, 2–3 educational ideas** on ES, NQ, CL or GC. Each one is a real
   chart, the ATR stop, the size the planner gives, and why. No calls, no "buy
   here". These rank inside TradingView's Ideas feed and carry the Signature.
4. **Reuse the YouTube lessons as ideas:** each video's chart and explanation
   becomes an idea (in text; no link to the video).
5. **Later (optional):** TradingView's invite-only scripts are a paid-script
   channel with their own Vendor Requirements. Consider it only once the funnel
   above is proven.

### Measure it
- Signature link `?utm_source=tradingview&utm_medium=signature` (and
  `utm_campaign=<script-or-idea-name>` when you change the signature for a push).
- GHL page analytics and Whop sales by UTM. Watch for calculator visits → free
  indicator signups → memberships.
- Monthly: script likes and uses, idea views, profile followers.
