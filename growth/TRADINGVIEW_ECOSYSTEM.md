# TradingView ecosystem: strategy, branding, compliance and roadmap

Goal: make Jack Gleason a recognised source of genuinely useful futures risk tools
on TradingView. A trader who meets one tool should recognise the next, follow
Jack, and find their way, voluntarily, to the free library, the education and,
for NinjaTrader traders, the membership.

---

## 1. Compliance: what's confirmed, what needs a moderator, what we won't do

**Verification limit:** the four official pages
([House Rules](https://www.tradingview.com/support/solutions/43000591638-our-house-rules/),
[Vendor Requirements](https://www.tradingview.com/support/solutions/43000549951-vendor-requirements/),
[Script Publishing Rules](https://www.tradingview.com/support/solutions/43000590599-script-publishing-rules/),
[Links in signature](https://www.tradingview.com/support/solutions/43000472770-am-i-allowed-to-include-links-to-3rd-party-sites-in-my-signature/))
**could not be opened from the build environment.** I added `www.tradingview.com` to
the environment's allowed hosts, but the page fetcher still couldn't resolve it,
and a direct download was refused. Everything in the "Confirmed" column comes from
search-engine excerpts of those pages, so it's **secondary**. **Read the pages
yourself before publishing**, and change this table if anything differs.

| Status | Item | Basis |
|---|---|---|
| **Confirmed (excerpts)** | No links, website or social references, contact details, payment details or advertising in a script's **title, description, release notes, chart or code** | Script Publishing Rules, House Rules |
| **Confirmed (excerpts)** | The **Signature** field may contain links and solicitation for **Premium and higher** plans. It's shown under every published idea and script | Signature page, House Rules |
| **Confirmed (excerpts)** | Descriptions must be **self-contained**: explain what the script does, how, and what's original | Script Publishing Rules |
| **Confirmed (excerpts)** | Reused open-source code must be credited. Open-source scripts default to MPL 2.0 | Script Publishing Rules |
| **Confirmed (excerpts)** | The original description **can't be edited** after publishing. Limits: 5 public scripts per 24 h, 15 per 30 days | Script Publishing Rules |
| **Confirmed (excerpts)** | Clean chart for the publication; the chart must not misrepresent the script | Script Publishing Rules |
| **Confirmed (excerpts)** | Vendors put business promotion in the Signature, not in publications | Vendor Requirements |
| **Inherent / safe** | The automatic author byline ("by *username*") and the author's profile page | Platform feature |
| **Inherent / safe** | A consistent **visual design** (colours, layout, typography) with no brand name, logo or link | Design, not promotion |
| **Needs a moderator's answer** | A **series name** in titles (e.g. "… · Risk-First Series"). The Vendor Requirements excerpt allows limited brand mentions ("one or two mentions throughout the publication"), but that's written for vendors. For open-source scripts, ask first | Ambiguous |
| **Needs a moderator's answer** | The **method line** in the dashboard footer ("Risk first · stop second · size last"). It's descriptive, not a brand, but confirm it isn't treated as a watermark | Ambiguous |
| **Needs a moderator's answer** | Naming the author's **other scripts** in a description ("pairs with the ATR Expansion Bars by the same author"), with no link | Ambiguous |
| **Needs a moderator's answer** | What the **profile bio** and profile social-link fields may contain on Jack's plan | Ambiguous |
| **We won't do** | Links, QR codes, logos, watermarks, company names, "follow me" or "join" text in titles, code, panels, labels, chart output or screenshots | Prohibited or circumvention |
| **We won't do** | Invite-only or paid scripts before reading the full Vendor Requirements | Out of scope |

**How to ask:** TradingView's support (help center → submit a request), or ask
the moderators on a draft before publishing. Quote the item exactly, and keep the
answer with this file.

**Built-in guard:** `tests/test_tradingview_scripts.py` fails the build if any
`.pine` file, or the public part of the description, contains a link, website,
social handle, company name, "@handle" or QR wording.

---

## 2. Strategic assessment (and the assumptions I'd challenge)

1. **"Free indicator → membership" is a weak direct path.** The membership's tools
   run in **NinjaTrader 8**. Many TradingView futures traders execute elsewhere
   (Tradovate, prop-firm platforms, other brokers). So in year one the indicator's
   job is **reputation and audience**, not sales.
   - Measure followers, favorites and repeat use.
   - Convert the NinjaTrader subset with a precise message: *"Like the planner?
     ATR Order Automation does this automatically inside NinjaTrader."*
2. **"Another ATR sizer" won't stand out.** Several free ATR position sizers already
   exist (section 5), one with almost identical defaults. Differentiation has to be
   **function and finish**, and v1.1 now has it:
   - the micro alternative
   - prop-firm and %-of-account modes with a daily-limit budget
   - commission-aware risk per contract
   - a volatility-regime readout that explains *why* the size changed
   - higher-timeframe and closed-bar ATR
   - entry, stop and R-target levels
   - alerts
   - a distinctive dashboard
3. **The strongest audience is prop-firm traders.** It's a large, active futures
   segment on TradingView, and their pain is exactly risk sizing against drawdown
   rules. Make prop-firm risk the series' recurring theme (roadmap P3), and lead
   chart ideas with prop-firm scenarios.
4. **Ideas and education do more for discovery than scripts alone.** Two or three
   educational chart ideas a week, each using the planner on a real ES, NQ, CL or GC
   chart, put Jack's byline and Signature in the Ideas feed daily. Scripts are the
   proof of expertise; ideas are the reach.
5. **One excellent tool a month beats many.** TradingView rewards originality and
   documentation (Editors' Picks are a curated showcase; never promise one). Use a
   release cadence that never risks a "low-quality or similar scripts" flag.
6. **Use the same name across platforms.** The free NinjaTrader indicator is the
   *ATR Expansion Bar*. A TradingView *ATR Expansion Bars* with the same logic
   (roadmap P2) makes the brand recognisable on both platforms and connects
   naturally to the NinjaTrader tools.

---

## 3. Branding system for the TradingView series

The brand lives in four places the rules allow: **the author, the design, the
method, and the Signature.** It never lives in a link or a logo.

| Element | Standard |
|---|---|
| **Author** | Jack's personal TradingView account (a person builds trust; the company comes through the Signature). Display name "Jack Gleason", the same photo as YouTube. If a new account is needed, the username **JackGleason** |
| **Titles** | Plain and searchable: *function + object*. Examples: "ATR Position Size & Stop Planner", "ATR Expansion Bars", "Prop Firm Drawdown Guard", "Session Volatility Map". No hype words, no brand (until a moderator clarifies a series name) |
| **Short titles** | Two words, consistent: "ATR Size", "ATR Expansion", "DD Guard", "Vol Map" |
| **Dashboard** | `growth/tradingview/_tool-template.pine`:<br>• orange header bar with "TOOL NAME vX.Y" in monospace capitals<br>• grey labels on the left, light values on the right<br>• green / amber / red status colours<br>• muted method line in the footer<br>• dark panel, thin border<br>• Full or Compact view, four positions |
| **Colours** | Panel #0b0e13 · header #fa7b39 · labels #9aa4b2 · values #e8edf3 · good #3ddc97 · caution #ffb454 · bad #ff6b5b · muted #6b7689. These are the same palette as startuptrading.com, so the website feels like the tools' home |
| **Method line** | "Risk first · stop second · size last" (pending moderator confirmation, see section 1) |
| **Versioning** | vMAJOR.MINOR in the header. Every update gets **release notes**: what changed, and why it's useful |
| **Publication chart** | Dark theme, ES or NQ 5-minute, panel top right, levels drawn, nothing else on the chart |
| **Descriptions** | The same section order every time: the problem · how it works (with the formula) · what you see · settings · alerts · limitations · risk line |

---

## 4. TradingView profile and signature strategy

- **Profile:**
  - Photo, "Jack Gleason", and a bio such as *"Futures trader since 2008.
    Risk-first tools: ATR sizing, stops, prop-firm drawdown."*
  - Add profile links only if the plan and rules allow (see section 1).
  - **Pin** the planner.
- **Signature** (Premium and higher, the one link location). Rotate the campaign tag per push:

  ```
  Free futures risk tools, the method behind them and new releases:
  startuptrading.com/free-tools?utm_source=tradingview&utm_medium=signature&utm_campaign=profile
  ```

  It points to the **free library**, not the sales page: it's useful first, and
  it can't break the rules on promotion. The library then leads to the
  calculator, the email updates and, when it's open, the membership.
- **Posting rhythm:**
  - Weekly: 2–3 educational ideas (real chart, ATR stop, size, the reasoning; no calls).
  - Monthly: one script release, or a significant update with release notes.
  - Answer every question in the script comments. That's where recommendations
    start, and it's allowed engagement.
- **Cross-promotion that stays inside the rules:**
  - The YouTube video about each tool says "search *ATR Position Size & Stop
    Planner* on TradingView". That's off-platform and fine.
  - The companion page links to the script and to Jack's profile.
  - The website and email drive TradingView follows, never the reverse through links.

---

## 5. Competitive assessment (free TradingView position sizers)

From a web search on 25 Nov 2026. TradingView's usage counts weren't available,
so popularity isn't ranked.

| Script (author) | What it does | Gap we fill |
|---|---|---|
| [ATR Position Sizer](https://www.tradingview.com/script/sGEH40hF-ATR-Position-Sizer/) (goelon) | Contracts from dollar risk and an ATR stop; symbol point value; defaults $250 / 14 / 1.5× | Very close to v1.0. v1.1 adds the micro alternative, prop-firm and % modes, costs, the volatility regime, HTF and closed-bar ATR, levels, alerts and a distinctive panel |
| [Position Sizing Calculator (Real-Time), Futures Edition](https://www.tradingview.com/script/uM8OopGX-Position-Sizing-Calculator-Real-Time-Futures-Edition/) (Stereotypical) | Account size × risk %, Wilder ATR stop; point value typed in (built for MNQ) | Automatic point value, micro switching, dollar and prop modes |
| [Stop loss and position size calculator (ATR)](https://www.tradingview.com/script/94iuPJJ6-Stop-loss-and-position-size-calculator-ATR/) (oberon2007) | ATR stop line and size; closed-source | Open source, so the method is visible and trusted |
| [Position Size Calculator](https://www.tradingview.com/script/Ldo8gAI1-Position-Size-Calculator/) (fhgfkwicjnw) | Manual risk and stop → lot size; mentions prop accounts | ATR-driven stops, contract awareness |
| [Position Sizing Calculator](https://www.tradingview.com/script/jADDqQph-Position-Sizing-Calculator/) (lern1079) | Table overlay, four stop methods, share-based | Built for futures contracts and ticks |

**Our position:** the most *complete, futures-native, prop-aware* free sizer, with
a recognisable design and a real author who teaches the method on video.

---

## 6. Roadmap (prioritised)

| # | Tool | Platform | Why it ranks here | Bridge to the membership |
|---|---|---|---|---|
| **P1** | ATR Position Size & Stop Planner v1.1 | TradingView | Built; differentiated; establishes the series | ATR Order Automation is the automated NinjaTrader version |
| **P2** | ATR Expansion Bars | TradingView | Same name and logic as the free NinjaTrader indicator: cross-platform recognition. Visual and easy to share in ideas | Free NinjaTrader version → membership |
| **P3** | Prop Firm Drawdown Guard | TradingView + web | The prop-firm audience is large and underserved: distance to max and trailing drawdown, daily loss left, the max contracts the rules allow today | Risk discipline is the membership's thesis |
| **P4** | Session Volatility Map | TradingView | Expected range by session (Asia, London, RTH) versus ATR. Traders keep it installed all day | Context for the Trend Scanner |
| **P5** | Trend Strength (single market) | TradingView | Lite trend read for the chart symbol. **Jack decides**: it previews the paid multi-market Trend Scanner without giving it away | Strongest direct bridge; risk of cannibalising the paid tool |
| Web | Prop-firm drawdown calculator, ATR stop calculator | startuptrading.com | Each is its own search page; reuses the calculator code | Same funnel |

Each release:
1. Start from `_tool-template.pine`.
2. Pass `tests/test_tradingview_scripts.py`.
3. Add a companion page and a `tools.json` entry.
4. Publish a launch idea and a YouTube demo.
5. Write release notes.

---

## 7. The website side (built)

- **Companion page** (`/tradingview/atr-position-size-planner`): the v1.1 features,
  method, worked examples, install steps, limitations and related tools. Optional
  slots, each appearing when its setting has a value:
  - **Follow Jack on TradingView**: `tv_profile_url`
  - **Watch the demo**: `tv_atr_video_url`
  - **Open on TradingView**: `tv_atr_script_url`
- **Free library** (`/free-tools`): the series' home, optional email updates, and
  the membership introduction once it's open.
- Nothing requires registration or payment.

---

## 8. Measuring adoption and acquisition

| Stage | Metric | Where |
|---|---|---|
| Reach | Idea views, script page views, profile followers | TradingView (monthly log) |
| Adoption | Script favorites and "uses", comments, likes; releases followed | TradingView |
| Interest | Sessions from `utm_source=tradingview&utm_medium=signature` (by `utm_campaign`) | GA4 (`sut_attribution`) |
| Engagement | `free_tool_view`, `tool_use` on the companion page and calculator | GA4 |
| Capture | `email_subscribe` with first touch = tradingview; GHL contacts tagged `source-tradingview` | GA4 + GHL |
| Conversion | `checkout_intent`, `checkout_view`, `sut_purchase` with first touch = tradingview; Whop sales by UTM | GA4 + Whop |
| Retention | Members whose first touch was TradingView still active after 3 and 6 months | Whop + licensing records |

**Monthly scorecard (one row a month):** followers · new favorites · idea views ·
signature sessions · email sign-ups (TradingView source) · checkout intents ·
memberships (TradingView first touch).

Early months should be judged on the first four. The rest follow audience size.
