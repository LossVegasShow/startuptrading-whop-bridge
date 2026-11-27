# Trend-jacking playbook: be in the conversation within the hour

**Goal:** whenever the internet is talking about something, StartUpTrading has the funniest
trader take on it, posted while it's still hot. A non-trader laughs and shares it; a trader
laughs, nods and follows Jack. It serves the awareness offensive (`AWARENESS_FIRST_PLAN.md`):
**reach first, recognition second, and no selling.**

The engine is the **trend desk** (`marketing/trend_desk.py`, workflow `trend-radar`). It
watches the feeds every 30 minutes, drafts the posts and pings a phone. A person approves
every post.

---

## 1. Three lanes

| Lane | What | Lead time | Where it comes from |
|---|---|---|---|
| **Calendar** | Known moments: Black Friday, Super Bowl, Valentine's, Halloween, Christmas, Fed days, jobs reports, expiry, the futures roll, clock changes | Drafted 1 to 4 days early, scheduled, then refreshed on the day | `marketing/moments.py`: dates plus hand-written, rule-checked lines |
| **Live viral** | Whatever blows up today: a meme, a sports moment, a product launch, a celebrity moment, a weird news story | **Post within 60 minutes** of the alert | Google Trends, Reddit, Wikipedia most-read, plus AI web search for X, TikTok and Instagram |
| **Market-moving** | Viral stories that move markets: a surprise Fed comment, a stock jumping 20%, an exchange outage, a tariff headline | Within 30 minutes, after checking 2 credible sources | Same feeds; the desk tags these "caution" and writes a market-only angle |

Rough mix each week: about 3 calendar posts, 3 to 5 live-viral posts, and market-moving
posts only when they happen. Live-viral posts count toward the 50% discovery bucket in
`AWARENESS_FIRST_PLAN.md` §4.

## 2. The 60-minute clock

Viral moments peak in hours. Third place is fine; third day isn't.

| Minute | Who | What |
|---|---|---|
| 0 | Radar | The alert lands on the phone: trend, why it's viral, a ready X post |
| 0–10 | Approver | Run the **five-second filter** (§3). If any answer is wrong, skip it. No debate |
| 10–20 | Approver | Pick or tweak the best line. Post it on X/Threads. Drop the **reply line** under the 2–3 biggest posts about the trend |
| 20–60 | Jack (optional) | Film the 10–20 s short on his phone: hook on screen, one take, captions on. Post it to Shorts, Reels and TikTok |
| Next day | Approver | Log it in `growth/trends-log.csv` (§7) |

**One approver.** Name one person, plus one backup, who can approve without asking anyone
else. A post that needs a meeting is already late.

## 3. The five-second filter

Every answer must be **yes**:

1. **Is it light?** Nobody died, nobody was hurt, and it isn't a disaster, a crime, war, an
   illness, politics or religion. (The desk drops most of these automatically. If one gets
   through, skip it.)
2. **Is the joke about the situation, not a person?** Never laugh at someone who went viral
   by accident.
3. **Would someone who doesn't trade get it?**
4. **Does the twist land on trading?** FOMO, sizing, stops, patience, revenge trading.
5. **Is it rule-clean?** No profits, P&L, income, win rates, guarantees or trade calls,
   with the risk line at the end. The desk checks this; you check it again.

When in doubt, skip it. Missing a trend costs nothing; a bad joke about the wrong story
costs months.

## 4. How the jokes work

**The two-layer joke.** Layer one is about the trend and works for anyone. Layer two lands
on a habit every trader recognises. Name the trend in the first five words. One idea.
Short beats clever.

| Formula | Pattern | Example |
|---|---|---|
| **The missing feature** | "[Thing] has [safety feature]. [Market] does not." | "The Super Bowl has a two-minute warning. NQ does not." |
| **The reframe** | "[Trend] is just [trader emotion] with [mundane detail]." | "Black Friday is just FOMO with a parking problem." |
| **The honest version** | Say the quiet part about trading out loud | "Best April Fools' joke in trading: 'I'll just hold it until it comes back.'" |
| **Same energy** | "[Viral behaviour] has the same energy as [trader habit]." | "'Add to cart' has the same energy as 'add to a losing position.'" |
| **The rule** | "[Trend] rule: [funny truth]. Same goes for [trading thing]." | "If a deal needs a countdown timer to convince you, it isn't a deal. Same goes for a setup." |
| **Things that should never be…** | Take the trend's word, apply it to risk | "Things that should never be a doorbuster: your position size." |
| **The calm adult** | Everyone's panicking; Jack gives the one useful thing | "Exchange outage this morning. When it comes back, the first minutes are chaos. Wait for a normal spread before you size up." |

**Voice:** dry, self-aware, a working trader. Laugh at the market and at our own habits.
At most one emoji and one hashtag. No "🚀💰", no lifestyle, no money.

**Visuals:**
- **Best:** Jack's face reacting, with the hook as on-screen text.
- **Next best:** an original chart graphic.
- **Never:** a company's logo, someone else's footage or a celebrity's photo.
- **Meme formats:** recreate the format with Jack in it rather than reposting someone
  else's image.

## 5. Platform moves

- **X / Threads:** post the line, then reply under the biggest posts about the trend
  (the desk writes a `reply_line`). Replies under a viral post often reach more people
  than the post itself.
- **TikTok / Reels / Shorts:**
  - Jack on camera, 10–20 s, with the hook in the first 2 seconds.
  - If the trend comes with a sound or format, use the sound in TikTok's own editor.
  - Captions always on.
- **Instagram Stories:** the X line as a text card. It's the fastest format to make.
- **TradingView:** never. Ideas there are education only (`TRADINGVIEW_ECOSYSTEM.md`).
- **Links:** none in trend posts. The profile link is the call to action.

## 6. The no-go list

The desk blocks these automatically (`compliance.BLOCKED_TOPICS`), and people don't post
them either:
- deaths, disasters, violence, war, terrorism
- illness, crimes with victims, missing people
- anything involving minors
- sexual content

**Caution:** politics, tariffs, shutdowns, layoffs, outages, hacks. These get a
market-impact angle only, with no joke at anyone's expense and no side taken.

**Market rumours:** never repeat one as fact. Two credible sources, or it waits.

**Remembrance days:** Memorial Day and Juneteenth get a markets-closed notice. No humor,
no promotion.

The phrase rules and the risk line from `marketing/compliance.py` apply to every post.

## 7. Measurement

Keep one row per trend post in `growth/trends-log.csv`:

```
date,lane,trend,platform,minutes_from_alert,impressions,engagements,follows,profile_clicks,notes
```

**Targets for the first 30 days:**
- 15 trend posts
- a median of 45 minutes or less from alert to post for live-viral posts
- 2 posts at **3×** the account's median impressions or more

**After 30 days:**
- Keep the joke formulas (§4) behind the outliers.
- Drop the lanes that don't move follows.
- Tell the desk by editing `TREND_JOCKEY` in `marketing/agents.py`.

## 8. Setup (once, about 15 minutes)

1. The `ANTHROPIC_API_KEY` repository secret is already used by `marketing-weekly`.
2. **Phone alerts:** create a private Discord channel called `#trend-desk`. Open Edit
   channel → Integrations → Webhooks → New webhook, copy the URL and add it as the
   repository secret **`TREND_ALERT_WEBHOOK`**. Slack incoming webhooks work too. Turn on
   push notifications for that channel on the approver's phone.
3. **Actions → trend-radar → Run workflow** once, with "dry run" ticked, to check the feeds.
   Then let the schedule take over.
4. **Cost:**
   - The AI is called only when a trend is new, at most 16 times a day (`--max-ai-runs`),
     with up to 6 web searches each.
   - Check the first day's cost in the Anthropic console, and lower the cap if needed.
   - Quiet nights cost nothing.

**Day to day:**
- The alert is the queue.
- The full drafts are on the run page (Actions → trend-radar → latest run).
- For the calendar, run `python -m marketing.trend_desk --calendar 30`.
- To change a calendar line, edit `marketing/moments.py`. The tests check every line
  against the phrase rules.

---

## Today: Black Friday (Friday, November 27, 2026)

CME equity index futures close early today, at **12:15 pm CT (1:15 pm ET)**. Confirm on
[CME's holiday calendar](https://www.cmegroup.com/trading-hours.html) before posting the
session line. Every post ends with: *Futures trading involves substantial risk of loss.
Education only, not financial advice.*

**X / Threads** (pick 2 or 3 and space them through the day):
1. "Black Friday: people line up at 5 am to buy things 40% off, then panic when the market is 5% off."
2. "Black Friday is just FOMO with a parking problem."
3. "Doorbusters at 6 am. Futures close early at 12:15 pm CT. Half-day session, full-size emotions. Size down."
4. "Things that should never be a doorbuster: your position size."
5. "The checkout screen says 'You saved $212.' Nobody ever gets that pop-up for the trade they didn't take. So here it is: you did."

**Short (Jack on camera, 15 s):**
- **Hook on screen:** "Black Friday rules for traders"
- **Jack, holding up a long receipt:** "Retailers want you to buy fast because the deal ends
  soon. That's a sales tactic. In trading it's a warning sign. Half-day session today, thin
  volume. Smaller size, defined stop, and if you miss it, there's always another setup
  Monday."

**Reply line under big Black Friday posts:** "The only doorbuster I want today is a clean stop."

## Next up

**Cyber Monday, November 30:**
- "If a deal needs a countdown timer to convince you, it isn't a deal. Same goes for a setup."
- "'Add to cart' has the same energy as 'add to a losing position.' Both feel great for
  about four seconds."

**Jobs report, Friday, December 4:**
- "Jobs report at 8:30. The only job I have at 8:29 is not having a position."
- Confirm the date on the [BLS schedule](https://www.bls.gov/schedule/news_release/empsit.htm)
  first.

**FOMC decision, Wednesday, December 9:**
- Statement at 2:00 pm ET; press conference at 2:30.
- "FOMC at 2:00. The market spends six hours pretending it doesn't care, then six seconds
  proving it does."
- Dates per the [Fed calendar](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm).

**Index futures roll, around December 10:**
- "Roll week. Your chart didn't break, the contract changed."

**Quad witching, December 18:**
- "Quad witching: it isn't Halloween, but the candles still get scary."

**Christmas Eve and Christmas Day:**
- "The Santa Claus rally is real in the same way Santa is: a lovely tradition and a
  terrible risk plan."

**Worth planning early: Super Bowl LXI falls on Valentine's Day, Sunday, February 14, 2027.**
- "The Super Bowl has a two-minute warning. NQ does not."
- Two culture moments on one day is the biggest calendar opportunity of the quarter.
