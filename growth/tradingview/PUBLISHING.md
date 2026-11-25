# Futures Position Size Calculator - ATR & Prop Firm Risk (StartUpTrading Futures Risk Planner): final release pack

Feature set and design are **frozen**. Only verified problems get fixed from here.

| Item | File |
|---|---|
| Script | `atr-position-size-planner.pine` (plain ASCII, ≤95-character lines) |
| Publication description | `atr-position-size-planner.description.txt` |
| Companion page | `sales-site/dist/tradingview-atr-planner-embed.html` → `/tradingview/atr-position-size-planner` |
| Release history and automated QA | `RELEASE_v1.2.md` |

## 1. Fixes in this final build (from the QA report)
| # | Finding | Resolution |
|---|---|---|
| 1 | Daily allocation formula | Confirmed: cap = remaining daily allowance × (1 − buffer, Prop firm mode only) ÷ planned daily losses. "Planned daily losses" is configurable (default 2), and the tooltip explains it |
| 2 | Zero silently disabled the daily limit | Separate on/off switch. When on, $0 remaining → $0 budget, 0 contracts |
| 3 | Exhausted message | "Risk budget exhausted - no trade." (a plain hyphen keeps the script ASCII-safe) |
| 4 | **Reward inconsistency (verified)** | The reward was **gross** ($552), while the stop risk **included** costs ($281). Now the dashboard shows the hypothetical reward **net** of the same costs ($547), with **gross / costs** on the next row ($552 / $5). The chart label shows the **net** figure. Both come from the same two variables (`grossReward`, `netReward`). With no costs set, the panel says "(no costs set)" |
| 5 | Higher-timeframe ATR and repainting | ATR is `ta.atr`, TradingView's native ATR (Wilder/RMA). Closed bar: previous completed bar with `lookahead_on`, the documented non-repainting form. Live: `lookahead_off`, updates while the bar forms (alerts too). One `request.security` call. Warning shown when the ATR timeframe is below the chart's |
| 6 | Tick boundaries, floats, unsupported, non-USD, missing data | Covered by automated tests (see `RELEASE_v1.2.md`) plus R16–R17 below |
| 7 | Comparison specifications and costs | The script's contract table is tested to equal the verified spec table. Each side uses its own tick, value per point and cost |

## 2. User guide (for the companion page, YouTube demo and comments)

**What it does.** You set a risk budget. ATR sets the stop. The planner shows the
maximum number of contracts that keeps the estimated stop risk inside the budget.

**Quick start**
1. Add it to a futures chart (ES1!, NQ1!, MES1!, MNQ1!…).
2. Pick a risk mode, then enter the risk per trade, account size or prop-firm allowances.
3. Leave the stop at 1.5 × ATR(14), or change the multiple.
4. Read **MAX POSITION**. Check estimated stop risk, budget remaining and budget used.
5. Optional:
   - enter your round-turn costs (standard and micro)
   - a planned entry
   - an R target
   - a chart level style

**Reading the panel**
- **Risk budget:** the most you've decided to lose on this trade.
- **Estimated stop risk:** contracts × (stop × value per point + costs). It never
  exceeds the budget.
- **Budget remaining / used:** what's left of the budget, and how much the size uses.
- **Standard vs micro:** the same stop for both contracts, each rounded to its own tick.
- **At target (hypothetical), net:** the gain *if* the target is reached and filled
  as planned, minus costs. Gross and costs are shown beside it. Not a forecast.
- **Prop-firm rows:** remaining versus original drawdown, used %, and buffer.

**Limitations (state these wherever the tool is described)**
- It's a planning aid, not a signal or an order. Nothing is executed.
- Live-bar ATR, and alerts based on it, change until the bar closes. Use closed-bar
  mode for fixed numbers.
- Contract specs come from the chart symbol and a built-in table. Check them against
  your broker's.
- Amounts are in the symbol's currency.
- Slippage and gaps can make losses larger than the estimate. Costs only count if
  entered.
- Prop-firm rules (static or trailing, daily limits, consistency rules) vary by firm.
  Use the current allowances from your firm's dashboard. Staying within the rules
  remains the trader's responsibility.

## 3. Final regression checklist (TradingView)
Run on the final build. Expected values come from the automated reference tests.

| # | Setup | Expect | Pass |
|---|---|---|---|
| F1 | Paste into an empty Pine Editor → Add to chart | Compiles; the panel renders | |
| F2 | ES1!, Fixed $500, defaults | ticks = ceil(ATR×1.5÷0.25); per = ticks×0.25×50; max = floor(500÷per); remaining = 500 − stop risk | |
| F3 | MES1!, NQ1!, MNQ1! | Same formula at $5 / $20 / $2 per point | |
| F4 | % mode, 50,000 × 1% | Budget 500 | |
| F5 | Prop: remaining 2,500, 10 losses, 10% buffer | 225. Remaining 800 → 72. Remaining 0 → 0 and "Risk budget exhausted - no trade." | |
| F6 | Daily switch on (prop, 2,500 remaining), 2 planned losses: 100 / 200 / 500 / 0 | 45 / 90 / 225 / 0 (no trade) | |
| F7 | Daily switch off with allowance 0 | 225 (the constraint is ignored) | |
| F8 | Daily switch on, 300 remaining, 3 planned losses | 90 | |
| F9 | **MNQ, $500, stop 138 pts, micro costs $5, 2R** | Stop risk $281; net **$547**; gross / costs **$552 / $5**; the chart target label shows **+$547 net** | |
| F10 | Same with costs 0 | "$552 (no costs set)"; label +$552 net | |
| F11 | Pair block on ES1! and on MES1! | Same two columns; each side's costs applied separately | |
| F12 | 6E1! vs M6E1! | Different tick counts for the same ATR | |
| F13 | **ATR check:** 15-minute chart with the built-in Average True Range (14, RMA). Note the value of the last **closed** bar. Switch to 5-minute with the planner set to ATR timeframe 15 and closed bar on | The planner's ATR equals that closed 15-minute value and doesn't change while the 15-minute bar forms | |
| F14 | Closed bar off | ATR updates intrabar (live by design) | |
| F15 | ATR timeframe 1 on a 5-minute chart | "ATR timeframe is below the chart's" | |
| F16 | Non-futures symbol (e.g. AAPL); a non-USD symbol (e.g. FDAX1! or a EUR stock) | No pair block; the currency is labelled when it's not USD | |
| F17 | New listing or very short history | "Waiting for ATR data" or "warming up"; no errors | |
| F18 | Levels Off / Clean / Prices / Prices + risk; Long / Short zones | PLAN labels; risk and net reward only in Prices + risk | |
| F19 | Text size Small / Normal / Large; Compact | The headline stays dominant and readable | |
| F20 | Create Alert | "Position size changed" and "Volatility expanded" listed | |

## 4. Branding and author attribution

**Verification limit:** TradingView's rule pages couldn't be fetched from the build
environment. Read the four official pages before publishing (links in
`../TRADINGVIEW_ECOSYSTEM.md` §1).

| Recommendation | Status |
|---|---|
| Publish from **Jack's own account**, with the same photo and name as YouTube. The author byline is the attribution | Platform feature |
| The **(c) {TradingView username}** line at the top of the code: replace it with Jack's exact username before publishing | Standard Pine header |
| The **design system** (orange header, dark panel, monospace rows, method footer) is the recognisable identity across all tools | Design, no promotion |
| **No** company name, website, handle, logo, QR code or "follow/join" text in the title, code, panel, labels or chart | Prohibited |
| Promotion links **only** in the Premium **Signature**, and on startuptrading.com | Permitted location |
| **Ask a moderator** before using: a series name in titles; the method line as a footer; naming Jack's other scripts in descriptions | Needs confirmation |

**Title (final):** **"Futures Position Size Calculator - ATR & Prop Firm Risk"**, with
short title "Futures Risk" and dashboard "FUTURES RISK PLANNER". It uses a plain hyphen
because the script is kept plain ASCII. The rationale and competitor research are in
`../FLAGSHIP_POSITIONING.md` §2–3.

## 5. Publishing on Jack's account (step by step)
1. **Profile first:** photo, display name "Jack Gleason", and a short bio ("Futures
   trader since 2008. Risk-first tools for futures."). If Jack is on Premium or
   higher, set the **Signature** to the text at the bottom of the description file.
2. Open a **clean ES1! 5-minute chart**, dark theme, with no other indicators or drawings.
3. **Pine Editor:**
   - Open the `.pine` file in Notepad. Select all and copy, then paste into an empty editor.
   - Replace `{TradingView username}` in line 3.
   - **Save**, then **Add to chart**.
4. Set it up for the publication chart:
   - Fixed $500
   - Plan for Long
   - Levels "Prices + risk"
   - Compare standard vs micro on
5. Run checklist F1–F20 one last time on this account.
6. **Publish script** (top right of the Pine Editor):
   - Visibility **Public**, **Open-source**.
   - **Title:** exactly "Futures Position Size Calculator - ATR & Prop Firm Risk" (it comes from the script).
   - **Description:** paste the DESCRIPTION section **as-is**. It **can't be edited
     after publishing**.
   - Category: Indicators. Tags: position sizing, risk management, ATR, futures, prop firm, micro futures, stop loss, risk reward.
   - Check the preview chart shows the panel and levels clearly, then **Publish**.
7. **Afterwards:**
   - Copy the script URL into `site.config.json` → `tv_atr_script_url`.
   - Set the planner's `status` in `tools.json` to `"available"` and its label to
     "Free on TradingView".
   - Add Jack's profile URL to `tv_profile_url`.
   - Rebuild, then re-paste `/free-tools` and the companion page.
   - Replace the screenshot placeholders with real ones.
8. **Launch content:**
   - One educational idea the same day: ES or NQ, the ATR stop and size, the micro
     comparison. No links.
   - A short YouTube demo that says "search *Futures Position Size Calculator - ATR &
     Prop Firm Risk* on TradingView".
   - Reply to every comment for the first two weeks.
9. **Track** (`../TRADINGVIEW_ECOSYSTEM.md` §8): followers, favorites, idea views,
   and signature sessions (`utm_source=tradingview&utm_medium=social`) in GA4.
