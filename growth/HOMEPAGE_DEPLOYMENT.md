# Homepage = membership sales page: deployment

Decision (2026-11-26): in GoHighLevel the website's default page changed from **Home**
to **Join**. `startuptrading.com/` now serves the membership sales page. `/join` still
serves the same page, for old links, affiliate links and bookmarks.

What stays exactly as it was:
- The **Home + VSL funnel**. It is not modified or deactivated. Its `/home` page is only
  taken out of the sitemap (step 4). Redirecting it is optional and your call.
- Checkout (the Whop embed and hosted links), sign-in, licensing and activation.
- `membership_open` stays **off**. The free pages keep hiding membership CTAs until the
  live acceptance tests pass.

> **Purchasing is reachable now.** The homepage carries the live Whop checkout, and
> licensing is set to `all_members`. Anyone who lands on `startuptrading.com/` can buy
> and will be licensed. `membership_open` only controls the CTAs on the free pages,
> not the sales page itself. If purchasing must stay closed until the acceptance tests
> pass, set the GHL default page back to **Home** until then. Every file below works
> either way, because `/join` serves the same page.

## What changed in the code

| Area | Change |
|---|---|
| Logo / Home links | Every page's logo goes to `https://startuptrading.com/`. On the sales page itself it scrolls to the top. |
| Membership CTAs | "Become a Member", "Technology" and the calculator's "See the membership" go to `https://startuptrading.com/#pricing` / `#indicators`. They show only when `membership_open` is on (unchanged). No page links to `/join` any more. |
| Canonical | The sales page: `https://startuptrading.com/`. The free pages keep their own. `/welcome` and `/setup` stay noindex with no canonical. |
| Open Graph / Twitter | Added to the standalone pages (`dist/*.html`). In GHL these come from each page's SEO settings: values below. |
| Structured data | SoftwareApplication `url` = `https://startuptrading.com/`, offers `url` = `https://startuptrading.com/#pricing`, "members-only trade room" wording. |
| Affiliate links | `affiliate.js` now carries `?a=` onto links to `/` as well as `/join`. Share `https://startuptrading.com/?a=CODE`. Old `/join?a=CODE` links keep working. |
| Attribution | Unchanged. UTMs, click IDs, first and last touch, `sut_*` handoff to Whop and activation, Form 7 fields. Root and `/join` behave identically. |
| GTM / GA4 | New variable **Page type**, sent as `content_group` on every page view and as `page_type` on every event. Values: `/` and `/join` → `membership_sales`; `/free-tools` → `free_tools_directory`; calculator and TradingView page → `free_tool`; `/welcome` → `post_checkout`; `/setup` → `member_setup`; activate.startuptrading.com → `activation`; anything else (e.g. `/home`, `/indicators`) → `other`. |
| Campaign link generator | `/admin/campaign-links` → "Homepage (membership sales page)". The `/join` option was removed. |
| llms.txt | Rewritten: `growth/seo/llms.txt`. |
| robots.txt | **No change needed.** The live file allows all crawlers and names the sitemap. Copy kept in `growth/seo/robots.txt`. Don't disallow `/join`: it is already `noindex`, and a disallow would stop Google from seeing that. |

## Deployment steps

### 1. Render (activation app): one environment variable
Render → the service → **Environment** → set
`CHECKOUT_URL=https://startuptrading.com/#pricing` → Save.
It's the "Join StartUpTrading", "Become a member" and "Renew" link in the activation app,
and the rejoin link in the access-ended email. The old `/join#pricing` value would still
work. This is just the clean URL. Render redeploys automatically after the merge.

### 2. GHL: site-wide tracking code (affiliate.js changed)
Sites → Websites → StartUpTrading → **Settings → Tracking code**:
- **Header:** replace everything with `sales-site/dist/site-tracking.html`.
- **Body:** unchanged (`site-tracking-body.html`).
Save.

### 3. GHL: page embeds (paste each file over the existing code element)
| Page (path) | File |
|---|---|
| Join (now serves `/` and `/join`) | `dist/ghl-embed.html` |
| `/free-tools` | `dist/free-tools-embed.html` |
| `/futures-position-size-calculator` | `dist/calculator-embed.html` |
| `/tradingview/atr-position-size-planner` | `dist/tradingview-atr-planner-embed.html` |
| `/welcome` | `dist/welcome-embed.html` |
| `/setup` | `dist/setup-embed.html` |

Open the code element → select all → delete → paste the whole file → Save → **Publish**.

### 4. GHL: SEO settings (page → ⚙ Settings → SEO meta data / Social)
**Join page (serves the homepage)**. This replaces the old "exclusive Discord community" description.
- Title: `Futures Indicators for NinjaTrader 8 | StartUpTrading`
- Description: `ATR position sizing and trend scanning indicators for NinjaTrader 8, licensed automatically. Every new tool, Jack's trade room and masterclasses. $99/mo.`
- Social / Open Graph title and description: the same two values. Social image: a 1200×630 image if you have one (none set yet).
- Canonical (if GHL shows the field): `https://startuptrading.com/`
- Indexing: **allowed**. The root must not be noindex.

**`/join`**: no change. Checked live on 2026-11-26: `/` has no robots tag (indexable),
and `/join` returns `noindex`. That's the right split, with one indexed URL. After you
save the SEO settings, re-check that `/` still has no `noindex`.

**Free pages**: titles and descriptions unchanged:
- `/free-tools`: `Free Futures Trading Tools & Indicators | StartUpTrading`. Description: `Explore free TradingView indicators, NinjaTrader tools, futures position size calculators and risk management resources from StartUpTrading.`
- `/futures-position-size-calculator`: `Free Futures Position Size Calculator | ES, NQ, MES, MNQ`. Description: `Calculate futures contract size, ATR stops and estimated trade risk for ES, NQ, MES and MNQ. Free prop firm risk planner. No sign-up required.`
- `/tradingview/atr-position-size-planner`: `Free TradingView Futures Position Size & Risk Indicator`. Description: `Free TradingView indicator for ATR position sizing, prop firm drawdown planning, micro futures comparison and visual trade risk management.`
- `/welcome`, `/setup`: noindex (unchanged).

### 5. GHL: sitemap and the old `/home` page
The live sitemap lists only `/home`, `/indicators` and `/policies-terms`. It should list:
`/`, `/free-tools`, `/futures-position-size-calculator`,
`/tradingview/atr-position-size-planner`, `/indicators`, `/policies-terms`.
- Settings → **Sitemap** (or each page's "include in sitemap" toggle): include those pages, and exclude `/home`, `/join`, `/welcome` and `/setup`.
- `/home` (the Home + VSL funnel page): it's an indexable duplicate of the old homepage. **Without touching the funnel**, either leave it alone or, if you agree, add a 301 redirect `/home` → `/` under Settings → URL Redirects. That's reversible: delete the redirect to undo it.
- Google Search Console → Sitemaps → resubmit `https://startuptrading.com/sitemap.xml`. URL Inspection → `https://startuptrading.com/` → **Request indexing**.

### 6. llms.txt
GHL serves `/llms.txt`. Replace its contents with `growth/seo/llms.txt`. If it's a GHL
page or file upload, re-upload it. If it's hosted elsewhere, update it there. Check:
which one-time product pages are still for sale? The old file listed
`/atr-checkout` ($297) and `/tsms-checkout` ($497). The new file leaves them out
because TSMS is no longer part of the subscription. Add them back if they're still on sale.

### 7. GTM: import and publish the container
GTM → Admin → **Import container** → `growth/gtm/startuptrading-gtm-container.json` →
workspace *Default* → **Merge** → *Overwrite conflicting tags, triggers and variables* →
Confirm. Preview on `https://startuptrading.com/` and check that the page_view carries
`content_group = membership_sales`. Then **Submit → Publish**.
GA4: content groups appear under Reports → Engagement → Pages and screens → dimension
"Content group". For events, register `page_type` as an event-scoped custom dimension
(Admin → Custom definitions).

### 8. Check
```bash
python3 growth/gtm/check_live.py
```
Then by hand, in a private window:
- `https://startuptrading.com/?a=test`: hover a Join button. The Whop link ends `?a=test`.
- `https://startuptrading.com/`: view source. You should see the new title and description, and no `noindex`.
- `https://startuptrading.com/join`: same page, still loads, checkout still loads.
- Free pages: the logo goes to `/`. No "Become a Member" while `membership_open` is off.

## Still gated
- `membership_open`: off until the live acceptance purchase test passes (PRODUCTION_LICENSING.md).
- Held reminders and promotional campaigns: on hold.
