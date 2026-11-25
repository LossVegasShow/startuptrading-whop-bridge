# Flagship positioning, SEO and organic discovery: StartUpTrading Futures Risk Planner

> **Content allocation and the 30-day social plan are superseded by `AWARENESS_FIRST_PLAN.md`** (personality-led, 50/30/15/5). The SEO, keyword map, tool pages and measurement below still apply.

**What this covers:**
- the naming, positioning and keyword strategy
- the TradingView publication package
- the site SEO
- the content plan, the 30/90-day plans
- measurement

The tool's feature set is frozen. The QA fixes from the final report are done:
- the daily-loss switch, where 0 means exhausted
- the "Risk budget exhausted - no trade." message
- the net/gross reward
- the higher-timeframe ATR review

They're covered by tests and by checklist F1–F20 in `tradingview/PUBLISHING.md`.

---

## 1. Research basis and limits

| Source | Used for | Access |
|---|---|---|
| Web search results (TradingView script listings, guides, calculators) | Competitor titles, features and audience | ✅ |
| TradingView rule pages | Compliance | ❌ Blocked from the build environment. Excerpts only (see `TRADINGVIEW_ECOSYSTEM.md` §1) |
| TradingView engagement (boosts, uses, comments) | Competitor traction | ❌ Not visible in search results. **Not reported** |
| Google Keyword Planner / Google Trends | Search volumes | ❌ No access. **No volumes are given in this document.** Priorities below are qualitative |

**To measure (you, about 30 minutes):**
1. In Google Ads → Keyword Planner → "Get search volume and forecasts", paste the keyword list in §4, set the location to United States (and any other key markets), and export.
2. Check Google Trends for "futures position size calculator" vs "prop firm calculator" vs "MNQ".
3. Add the numbers to the "Measured volume" column in §4, then re-rank the 90-day plan if a cluster is much larger than expected.

## 2. Competitive landscape (from public listings)

| Tool | Where | What it does (per its listing) | Audience |
|---|---|---|---|
| [Futures ATR Risk & Position Sizer](https://www.tradingview.com/script/sJMxF85z-Futures-ATR-Risk-Position-Sizer/) (pascallapointe) | TradingView | ATR stop, size shrinks as volatility rises, 1.5× default, no signals | Futures, volatility-aware |
| [ATR Position Sizer](https://www.tradingview.com/script/sGEH40hF-ATR-Position-Sizer/) (goelon) | TradingView | Dollar risk + ATR stop, symbol point value | Futures |
| [Futures Position Size Calculator](https://www.tradingview.com/script/BdIe7nKH-Futures-Position-Size-Calculator) (vmkhats) | TradingView | Stop in ticks, risk per contract, rounded-down size | Futures; **ranks for the exact phrase on Google** |
| [NQ Position Size Calculator](https://www.tradingview.com/script/5EbUut3V-NQ-Position-Size-Calculator/) (birdmanx) | TradingView | NQ/MNQ table, long and short lines | Nasdaq traders |
| [MNQ/NQ Risk Management Tool](https://www.tradingview.com/script/4b9e4dC5-MNQ-NQ-Risk-Management-Tool/) (nathanwaymire25) | TradingView | Fixed $ or % risk, MNQ/NQ | Nasdaq traders |
| [Index Futures Position Size Calculator](https://www.tradingview.com/script/RRz9MEkF-Index-Futures-Position-Size-Calculator/) (Green_Room) | TradingView | Click entry and stop → contracts; ES/NQ/MES/MNQ | Index futures |
| [Stop Loss & Position Size Calculator](https://www.tradingview.com/script/WRsJgxd6-Stop-Loss-Position-Size-Calculator/) (Calibra79) | TradingView | Stop for a given size; ES/NQ/YM and micros | Index futures |
| Prop Firm Risk Guard (EonMetrics; [listing](https://in.tradingview.com/scripts/ftmo/)) | TradingView | Prop dashboard and sizing, daily and max drawdown, static or trailing | Prop / funded |
| [Prop firm risk panel](https://github.com/PropSim-Enterprise/prop-firm-tradingview-indicator) (open source) | GitHub / TradingView | Size by risk, losses left to the daily and max limits | Prop |
| [Aurafy position size calculator](https://w1337-cyber.github.io/aurafy-growth-assets/tools/position-size-calculator/) | Web | Sizes against the trailing-drawdown buffer; tied to a paid journal | Prop (web) |
| [StoneX](https://futures.stonex.com/blog/calculate-optimal-position-size), [NexusFi](https://nexusfi.com/a/prop-firms/prop-firm-position-sizing) guides | Web | Explain the formula, prop sizing | Education intent |

**What this shows**
1. **The category is crowded and fragmented.** Most tools do one job: ATR sizing,
   *or* an NQ/MNQ table, *or* prop limits.
2. **The exact title "Futures Position Size Calculator" is taken** and already ranks
   on Google. Our title keeps the phrase for search and differentiates with "ATR &
   Prop Firm Risk".
3. **The prop-firm segment is active** on both TradingView and the web. Web tools
   already make the point that "static calculators ignore trailing drawdown", so
   the *remaining-allowance* framing is the credible one.
4. **The gaps we can honestly occupy:** we combine, in one open-source tool,
   - ATR sizing
   - fixed, % and prop modes with a remaining-allowance budget and a daily cap
   - a standard-vs-micro comparison using each contract's own tick and costs
   - net-of-cost risk and reward
   - planning levels
   - a closed-bar or higher-timeframe ATR

   We say *"combines"*, never *"first"* or *"best"*.

**Positioning statement (use on the site and in the video; not a claim of superiority)**
> An open-source futures risk planner for TradingView that combines ATR position sizing, prop-firm drawdown and daily-loss planning, and a standard-versus-micro comparison in one dashboard: built around Jack Gleason's rule, risk first, stop second, size last.

## 3. Naming (final)

| Surface | Name |
|---|---|
| TradingView title (`indicator()` title) | **Futures Position Size Calculator - ATR & Prop Firm Risk** |
| Short title | **Futures Risk** |
| Dashboard header | **FUTURES RISK PLANNER** |
| Website product name | **StartUpTrading Futures Risk Planner** |
| Directory card | **Futures Risk Planner for TradingView** |
| Philosophy | **Risk first. Stop second. Size last.** |

- **One deviation:** a plain hyphen instead of the em dash. The publication title
  comes from the script, which is kept plain ASCII; a non-ASCII character broke the
  first paste.
- **The company name appears only on our website,** never in the TradingView title,
  panel or description.
- **The companion URL stays `/tradingview/atr-position-size-planner`,** which keeps
  existing links working. The page title and H1 carry the new name.

## 4. Keywords: priority and page mapping (qualitative; measured volume TBD)

| Cluster | Keywords | Intent | Target page | Priority | Measured volume |
|---|---|---|---|---|---|
| Core tool (web) | futures position size calculator · futures risk calculator · position size calculator futures | Use a tool now | `/futures-position-size-calculator` | **1** | — |
| Instrument | MNQ / MES / NQ / ES position size calculator · ES futures risk calculator · micro futures position sizing | Use a tool, instrument-specific | `/futures-position-size-calculator` (instrument sections). Later, articles for the comparisons | **1** | — |
| TradingView tool | TradingView position size calculator · futures position sizing indicator · TradingView futures indicators · TradingView risk reward indicator · ATR risk management indicator | Install an indicator | `/tradingview/atr-position-size-planner` | **1** | — |
| Prop firm | prop firm position size calculator · prop firm drawdown calculator · trailing drawdown risk planning · daily loss limit calculator · funded account risk management | Learn + calculate | Calculator (tool) **plus** the article "Prop firm drawdown planning" (learn) | **2** | — |
| Comparisons | NQ vs MNQ risk · ES vs MES position sizing | Learn | Articles (§6) linking to the calculator | **2** | — |
| Method | ATR position sizing · ATR stop loss calculator · volatility-based position sizing | Learn + calculate | Article "ATR stop-loss method" → calculator and TradingView page | **2** | — |
| Risk/reward and costs | futures risk reward calculator | Learn | Article on costs and risk-reward | **3** | — |
| Directory and brand | free futures trading tools · StartUpTrading | Browse | `/free-tools` | **3** | — |
| NinjaTrader | free ATR indicator NinjaTrader | Download | `/indicators` | Keep | — |

**Cannibalisation rules:**
- **Each page owns one intent.** "Calculator" phrases → the web calculator.
  "TradingView / indicator" phrases → the companion page. Comparisons and methods →
  articles that **link** to the tools instead of duplicating them.
- **The free tools directory never targets a tool keyword.**

## 5. TradingView publication package

- **Title, description, risk-mode instructions, supported instruments, examples,
  limitations:** `tradingview/atr-position-size-planner.description.txt`. The opening
  paragraph matches what people search for. It has no links or company names.
- **Category:** Indicators.
- **Tags** (pick the closest TradingView offers):
  - position sizing
  - risk management
  - ATR
  - futures
  - prop firm
  - micro futures
  - stop loss
  - risk reward

  Don't add unrelated tags: moderators penalise irrelevant tags.
- **Publication chart:**
  - **Setup:** ES1! or NQ1!, 5-minute, dark theme, clean chart.
  - **Settings:** Fixed $500, Plan for Long, levels "Prices + risk", shaded zones on,
    compare standard vs micro on, panel top right, text Normal.
  - **What should show:** the MAX POSITION headline, the pair block, and the PLAN
    labels clearly readable.
- **Demo video (60–90 s):**
  1. The problem: size first, stop squeezed.
  2. Add the indicator; the MAX POSITION number.
  3. Volatility rises → the stop widens, the size drops.
  4. The NQ shows 0 → the MNQ column shows 8.
  5. Prop mode with remaining drawdown and the daily switch → "Risk budget exhausted - no trade."
  6. Planning levels with net and gross reward, "planning only".
  7. "Search *Futures Position Size Calculator - ATR & Prop Firm Risk* on TradingView."

## 6. Website SEO: what's implemented, and the native GoHighLevel fields

**Implemented in the pages:**
- unique titles, descriptions and H1s, exactly as specified; tests enforce them
- canonical URLs in the standalone builds
- crawlable `<a href>` internal links between the directory, the companion page, the
  calculator, `/indicators` and the footer
- structured data matching the visible content: SoftwareApplication with the author
  "Jack Gleason" (shown as a visible byline), CollectionPage, BreadcrumbList,
  WebApplication
- noindex on `/welcome` and `/setup`
- one tracking bundle per page; tests enforce no duplicates
- mobile layout checked at 390 px

**Enter these in each GHL page's SEO settings** (GHL ignores meta tags inside Code elements):

| Page (path) | Title | Meta description | Canonical | Social image (1200×630) and alt text | Index |
|---|---|---|---|---|---|
| `/tradingview/atr-position-size-planner` | Free TradingView Futures Position Size & Risk Indicator | Free TradingView indicator for ATR position sizing, prop firm drawdown planning, micro futures comparison and visual trade risk management. | https://startuptrading.com/tradingview/atr-position-size-planner | Panel on an ES chart. Alt: "Futures Risk Planner dashboard on an ES chart showing maximum position, estimated stop risk and ES vs MES comparison" | Yes |
| `/futures-position-size-calculator` | Free Futures Position Size Calculator \| ES, NQ, MES, MNQ | Calculate futures contract size, ATR stops and estimated trade risk for ES, NQ, MES and MNQ. Free prop firm risk planner. No sign-up required. | https://startuptrading.com/futures-position-size-calculator | Calculator form and result. Alt: "Futures position size calculator showing contracts for ES and MES from risk and stop" | Yes |
| `/free-tools` | Free Futures Trading Tools & Indicators \| StartUpTrading | Explore free TradingView indicators, NinjaTrader tools, futures position size calculators and risk management resources from StartUpTrading. | https://startuptrading.com/free-tools | The three tool cards. Alt: "StartUpTrading free tools: TradingView risk planner, web calculator and NinjaTrader ATR indicator" | Yes |
| `/indicators` | (keep) | (keep) | https://startuptrading.com/indicators | (keep) | Yes |

**GHL settings:**
- **Site-wide:** favicon (the candle logo). `site-tracking.html` once in the header,
  replacing the old affiliate snippet. Don't add it twice.
- **Sitemap:** confirm the three pages appear in `startuptrading.com/sitemap.xml`,
  submit it in Search Console, and request indexing for each page.

## 7. Artwork and screenshot specs

| Asset | Size | Content | Rules |
|---|---|---|---|
| Social card, companion page | 1200×630 | Panel cropped from a real ES chart. Headline "Futures Risk Planner for TradingView". Dark #07090d, orange #fa7b39 accent | No profit numbers; real chart; legible at 600 px wide |
| Social card, calculator | 1200×630 | Calculator UI, "ES · NQ · MES · MNQ" | Same |
| Social card, directory | 1200×630 | Three tool cards | Same |
| TradingView publication chart | Native chart | As in §5 | Clean chart; nothing misleading |
| Companion screenshots (replace placeholders) | 1600×1000 | 1: dashboard with the pair block. 2: Long plan with zones and labels. 3: prop mode with remaining drawdown | Descriptive alt text; crop out account balances and P&L |
| YouTube thumbnail | 1280×720 | "NQ says 0. MNQ says 8." on the panel | Matches the video, no hype |

## 8. Educational content architecture

**Hub and spoke.**
- The hub is `/free-tools`.
- The spokes are the tools: the calculator, the TradingView page and `/indicators`.
- Articles (GHL Blog) teach one idea each and link to the right tool.
- Each video (from the `video/` pipeline) is embedded in its article.

| # | Article (one idea, original) | Links to | Source |
|---|---|---|---|
| 1 | How many futures contracts should you trade? Sizing from risk | Calculator, TradingView page | Video 001 |
| 2 | NQ vs MNQ: same stop, different risk | Calculator (MNQ), TradingView page | New |
| 3 | ES vs MES position sizing | Calculator (MES) | New |
| 4 | The ATR stop-loss method (and why it's rounded up to a tick) | TradingView page, `/indicators` | Video 002 |
| 5 | Prop firm drawdown planning: remaining allowance, buffer, losing streak | Calculator (prop), TradingView page | Video 004 |
| 6 | Daily loss limits: how many full losses fit today? | TradingView page | New |
| 7 | Trading costs and risk-to-reward: gross vs net | TradingView page | New |
| 8 | How to add and set up the Futures Risk Planner on TradingView | TradingView page | Tutorial |
| 9 | NinjaTrader tools: from the free ATR indicator to ATR Order Automation | `/indicators`, membership (once open) | Product |
| 10 | Volatility-based risk management: quiet vs elevated days | TradingView page, calculator | Video 003 |

**Rules:**
- One article per real question, with Jack's byline and his reasoning.
- No near-duplicate "X position size calculator" pages per instrument. The
  calculator handles instruments; articles handle explanations.
- Each article links to 1–2 tools and 1–2 related articles. Each tool page links back
  to its two most relevant articles once they exist.
- **`/learn`:** create it once 3 or more articles exist, then set `learn_url`. The nav's
  Education link moves there automatically.

## 9. Jack's authority

- **About Jack page (`/about-jack`):** photo, the bio below, how he trades (the
  method), what he builds, and links to YouTube and TradingView. Once it exists,
  point the nav's "About Jack" link there instead of the sales-page section (a small
  config change).
- **Bio template.** Fill it with **verified facts only**: Jack confirms each bracket.
  > Jack Gleason is a futures trader [since YEAR, confirmed]. He trades [instruments, confirmed] and builds the tools he uses for his own trading: [tools]. His approach is simple: risk first, stop second, size last. He shares the method on [YouTube channel] and publishes free tools for TradingView and NinjaTrader at StartUpTrading.
  - Don't state a trading track record, income or performance.
  - "Since 2008" is in `COPY_REVIEW.md` pending Jack's confirmation; "20 years" isn't supported.
- **Attribution:** "By Jack Gleason" on every tool page and article (structured data
  `author` = Person, matching the visible byline). The same name and photo on
  TradingView and YouTube.
- **Version history:** each tool page gets a short changelog (v1.2: …), and each
  TradingView update gets release notes. Transparency builds trust.

## 10. TradingView acquisition

**Signature (the only link location):**
1. **Check the plan:** on Jack's account, Profile → Settings. If there's no
   **Signature** field, the plan doesn't include it (excerpts say Premium and higher).
   Upgrade or skip.
2. **Use this text:**
   *"Free futures risk tools, the method behind them and new releases:
   startuptrading.com/free-tools?utm_source=tradingview&utm_medium=social&utm_campaign=futures_risk_planner&utm_content=signature"*

**About the suggested `utm_medium=organic`:** I recommend **`social`** instead. GA4
puts `medium=organic` in the **Organic Search** channel, which would blend TradingView
clicks into Google traffic and corrupt the "Google search clicks" metric.
`utm_source=tradingview&utm_medium=social` lands in **Organic Social**, clearly
separated. `utm_content=signature` distinguishes the signature from other placements
later.

**30-day plan.** These are real capabilities only, with no artificial engagement, and
ideas contain no links.

| Days | TradingView | YouTube / site | Email |
|---|---|---|---|
| 1 | Publish the script. Launch idea: "NQ says 0, MNQ says 8" on a real chart | Demo video; companion page set to Available | Notify subscribers (if the form is live) |
| 2–7 | 3 ideas: ES ATR stop and size; quiet vs elevated volatility; prop budget from remaining drawdown | Article 1 (from video 001) | — |
| 8–14 | 3 ideas: daily loss constraint and "no trade" day; net vs gross reward at 2R; MES vs ES | Article 2 (NQ vs MNQ) + short | Weekly tip |
| 15–21 | 3 ideas: CL and GC sizing (different ticks); higher-timeframe ATR on a 1-minute chart; trailing vs static drawdown | Article 5 (prop drawdown) | — |
| 22–30 | 3 ideas + reply round-up; v1.2.x release notes if fixes are needed | Article 4 (ATR stop) + tutorial video | Monthly round-up |

Every day: answer comments on the script and ideas. Never ask for boosts or follows.

## 11. 90-day organic search roadmap

| Weeks | Work |
|---|---|
| 1–2 | Publish the calculator, the companion page and the directory with GHL SEO fields. Search Console and Bing verified, sitemap submitted, indexing requested. Keyword volumes measured (§1) |
| 3–4 | Articles 1–2. Internal links tool ↔ article. Replace placeholders with real screenshots and alt text |
| 5–6 | Articles 3, 5. NinjaTrader Ecosystem vendor listing (backlink). YouTube descriptions link to the matching tool page with UTMs |
| 7–8 | Articles 4, 6. Create `/learn` (3+ articles) and set `learn_url`. About Jack page |
| 9–10 | Articles 7–8. Search Console review: which queries show impressions with a low click-through rate → refine titles and descriptions (one change at a time) |
| 11–12 | Articles 9–10. Second TradingView tool (ATR Expansion Bars) with its companion page, so the series begins |

## 12. Measurement

| Stage | Metric | Source | Event / filter |
|---|---|---|---|
| TradingView engagement | Boosts, comments, favorites/uses, idea views | TradingView (monthly log) | — |
| TradingView followers | Count, growth per month | TradingView | — |
| Referral traffic | Sessions from TradingView | GA4 | `sut_attribution` first/last touch: source `tradingview`, medium `social` |
| Google search | Impressions, clicks, CTR, position per page | Search Console | Page filter |
| Non-branded discovery | Queries **without** "startuptrading" or "jack" | Search Console | Query filter excludes brand terms |
| Free tool use | `free_tool_view`, `tool_use` | GA4 | `tool_id` |
| Returning visitors | Returning users on tool pages | GA4 | New vs returning |
| Email | `email_subscribe` | GA4 + GHL tags | source, interest |
| Free → paid | `checkout_intent`, `checkout_view` → `sut_purchase` | GA4 | first_touch source |
| Confirmed purchases | New memberships by UTM / first touch | Whop + licensing records | Weekly reconciliation with GA4 |

The existing event architecture, affiliate attribution and first/last-touch storage
are unchanged.

## 13. Implementation and validation checklist

- [ ] **Recompile** the final script. Run F1–F20 (`tradingview/PUBLISHING.md`), including
      F6–F8 (daily switch), F9–F10 (net/gross) and F13 (native ATR comparison).
- [ ] Jack approves the title, description and publication chart. Replace
      `{TradingView username}` in the code.
- [ ] Publish (Public, Open-source). Set `tv_atr_script_url`, `tv_profile_url` and the
      `tools.json` status; rebuild; re-paste the companion page and directory.
- [ ] GHL: paste the updated `tradingview-atr-planner-embed.html`,
      `free-tools-embed.html` and `calculator-embed.html`. Set §6 SEO fields, canonicals,
      social images and alt texts.
- [ ] Sitemap and Search Console; request indexing.
- [ ] Signature with the tracked URL (§10), after confirming the plan supports it.
- [ ] GA4: confirm TradingView visits appear under Organic Social with
      `utm_campaign=futures_risk_planner`.
- [ ] Start the 30-day plan; begin the monthly measurement log.
- [ ] Unchanged: licensing, pricing, checkout, entitlements and launch gates
      (`LAUNCH_AND_GROWTH.md`).
