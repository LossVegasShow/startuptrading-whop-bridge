# ATR Position Size & Stop Planner v1.2: release notes, QA and assessment

## What changed from v1.1
| Area | v1.2 |
|---|---|
| Dashboard | **MAX POSITION** headline in large type. A symbol, timeframe and risk mode line. Risk budget, **estimated stop risk** (was "actual risk"), budget remaining, budget used %. Adjustable text size (Small / Normal / Large). Clearer header and sub-header bands |
| Standard vs micro | An optional block: ES/MES, NQ/MNQ, YM/MYM, RTY/M2K, CL/MCL, GC/MGC, SI/SIL, 6E/M6E, BTC/MBT. The same raw stop is **rounded to each contract's own tick**, with its own value per point and **its own cost**. Shows max contracts, estimated stop risk and remaining budget side by side. Works from either the standard or the micro chart |
| Prop firm | Original vs **remaining** drawdown allowance, a safety buffer %, the losing streak, a static/trailing note, and an optional remaining **daily** allowance (buffered, capped at half). A "check your firm's own rules" line on the panel |
| Planning levels | Off / Clean / Prices / Prices + risk. "PLAN" prefixes on every label. Estimated stop risk at the stop, "hypothetical" reward at the target. Optional shaded zones when planning one side. Line width setting. Settings group titled "planning levels only: no orders are placed" |
| Robustness | Integer-tick math with an epsilon guard, so exact boundaries don't round up and float noise doesn't lose a contract. Handles missing or zero ATR or point value ("Waiting for ATR data" / "Set the value per point"). Warns when the ATR timeframe is below the chart's. Non-USD symbols are labelled in their currency |
| Unchanged | The core rule (ticks up, contracts down), all defaults, closed-bar and higher-timeframe ATR, alerts, the design system |

## Automated QA (`tests/test_tradingview_scripts.py`, runs on every commit)
Pine can't run outside TradingView. So a Python reference copy of the formulas
is tested, and the tests also check that the script's source contains the same
expressions and the same contract table.

- **Validated numbers.** At a $500 budget with ATR × 1.5:
  - **ES:** 24 ticks / 6.00 points, $300 per contract, 1 contract, $200 remaining, 60% used
  - **MES:** 16 contracts, $480
  - **NQ:** 0
  - **MNQ:** 8 contracts, $480, $20 remaining
- **Tick boundaries:**
  - 6.0 → 24 ticks
  - 6.0000000000015 → 24 (not 25)
  - 3.0000000000000004 at a 0.1 tick → 30
  - 6.01 → 25
- **Float floor:** 299.99999999999994 ÷ 100 → 3 (not 2). 599.99 ÷ 300 → 1.
- **Pairs:**
  - ES/MES give the same result from either chart.
  - 6E (0.00005 tick) vs M6E (0.0001 tick): 25 vs 13 ticks for the same raw stop.
  - YM rounds to whole points.
- **Risk modes:**
  - percent: 50,000 × 0.5% = 250
  - prop: 2,000 × 0.9 ÷ 10 = 180, capped to 135 by a 300 daily allowance
  - fixed-mode daily cap: half of what's left
  - zero allowance → 0 contracts
- **Costs:** reduce size, never raise risk; separate standard and micro costs.
- **Unsupported symbols:** no pair block, but the main size still works (ZB example).
- **Invalid data:** zero ATR or point value → 0 contracts and a message, not an error.
- **Lookahead:**
  - closed bar = value shifted one bar **and** `lookahead_on`, the documented non-repainting form
  - live = no shift, `lookahead_off`
  - a single `request.security` call
  - a warning when the ATR timeframe is below the chart's
- **Contract table:** the script's arrays equal the verified spec table.
- **Wording:**
  - no "Actual risk"
  - "Estimated stop risk", "hypothetical" and "PLAN" labels present
  - the prop disclaimer present
- **Compliance:** no links, handles, company names or QR wording in scripts or the
  public description; plain ASCII; lines ≤95 characters.

## Manual regression checklist (in TradingView, before publishing)
| # | Check | Expect | Pass |
|---|---|---|---|
| R1 | Compiles with no errors or warnings that matter | Added to chart | |
| R2 | ES1! 5m, Fixed $500, defaults | Hand check: ticks = ceil(ATR×1.5÷0.25), per = ticks×0.25×50, max = floor(500÷per). Remaining = 500 − estimated stop risk | |
| R3 | Same on MES1!, NQ1!, MNQ1! | Same formula with 5 / 20 / 2 per point | |
| R4 | Pair block on ES1! and MES1! | Both show ES and MES columns; MES max ≈ 10× ES (before rounding) | |
| R5 | Costs: standard 4.50, micro 1.20 | Per contract rises by the cost; estimated stop risk ≤ budget | |
| R6 | 6E1! vs M6E1! | Different tick counts for the same ATR | |
| R7 | YM1!, RTY1!, CL1!, GC1! | Ticks of 1.0, 0.1, 0.01, 0.1 respectively | |
| R8 | % mode: 50,000 × 0.5% | Budget 250 | |
| R9 | Prop: original 2,500, remaining 2,000, buffer 10%, streak 10 | Budget 180. DD left "2,000 of 2,500", used 20% | |
| R10 | Add remaining daily 300 (prop) | Budget 135; "Full stops left today" shown | |
| R11 | ATR timeframe 15 on a 5m chart; toggle closed bar | Closed: the value doesn't change while the bar forms. Live: it updates | |
| R12 | ATR timeframe 1 on a 5m chart | Warning "ATR timeframe is below the chart's" | |
| R13 | Chart levels: Off / Clean / Prices / Prices + risk | Labels prefixed PLAN. Risk and "hypothetical" text only in Prices + risk | |
| R14 | Plan for Long, then Short | Shaded red risk zone and green target zone on the right side only | |
| R15 | Text size Small / Normal / Large; Compact | Readable; the headline stays dominant | |
| R16 | A non-futures symbol (e.g. AAPL) | No pair block. Sizing uses its point value. Non-USD symbol shows its currency | |
| R17 | A fresh symbol with little history | "Waiting for ATR data" or "warming up", no errors | |
| R18 | Alerts | Both alert conditions are listed in Create Alert | |
| R19 | Light chart theme | The panel stays readable (dark panel by design) | |

## Is this differentiated enough?
**Yes, for adoption among futures traders, if it's shown well.** Compared with
the free sizers reviewed (`growth/TRADINGVIEW_ECOSYSTEM.md` section 5), v1.2 is
the only one I found that combines:
1. a futures-native **standard-versus-micro** comparison with each contract's own
   tick and costs
2. **prop-firm** planning on the remaining allowance, with a buffer and a daily cap
3. a **budget-utilisation** view: remaining budget and % used
4. on-chart **planning levels** with risk labels

Most competitors do one of these.

Function alone won't carry it. Adoption will come from three things:
- **A strong first impression:** the publication chart and a short demo video show
  the MES/ES comparison on a real NQ or ES day.
- **Educational ideas** that use it in context.
- **Prompt, helpful replies** in the comments.

The micro comparison and the prop-firm view are the two features to lead with.
They're the most likely to be screenshotted and shared.

## Features that would drive daily use (candidates for v1.3+, not built)
- **Session risk tracker:** enter realised P/L today and see the remaining daily
  allowance update. It turns a sizing tool into a daily-limit companion.
- **Watchlist-friendly presets:** saved risk settings per instrument family
  (indices, energy, metals).
- **"Expected range used":** today's range against ATR, so you know when a market
  is already stretched.
- **Event-day reminder:** volatility regime plus a manual "high-impact news today"
  toggle that widens the multiple.

Keep each one optional, and keep the default view simple.

## Branding and attribution: what changed
There's nothing new to report. TradingView's policy pages still couldn't be
fetched from the build environment, so the position in
`growth/TRADINGVIEW_ECOSYSTEM.md` section 1 stands:
- the author byline
- the shared design system
- the method line, pending moderator confirmation
- links only in the Premium Signature and on startuptrading.com

v1.2 adds no names, links or watermarks to the panel or the chart.
