# Awareness-first growth plan: making Jack Gleason recognisable

**Goal:** futures traders recognise Jack: his face, his voice and his point of view.
The tools and the membership benefit from that recognition; they don't lead it.
This plan replaces the tool-first emphasis of `FLAGSHIP_POSITIONING.md` §8 and §10.
**Updated:** Jack is on camera; the channel is Jack's own; the AI pipeline becomes his visual
engine; collaborations are the primary growth engine; visitor harvesting is §3.
The SEO, tool pages and Risk Lab remain, at a smaller share.

---

## 0. Decisions

| Decision | Status |
|---|---|
| Jack on camera | ✅ **Yes.** Discovery and authority content is Jack on camera, in his own voice |
| YouTube channel | ✅ **A channel in Jack's name**, set up as in §1. **Don't rename `@giannisecchi9682`**: that's your personal channel, and Jack's audience should sit on an account he owns |
| "20 Years at the Screens" | ⏳ **Open.** Jack's stated start is 2008 (about 18 years). Use it only if Jack confirms 20 years; otherwise "From the Screens" or "Since 2008" |
| AI video pipeline | ✅ **Retargeted as Jack's visual engine** (§1). The AI-voiced episode 001 is **on hold** (`"hold": true` in `video/uploads/001-how-many-contracts.json`) so nothing publishes to your channel in the meantime |
| Collaborations | ✅ **The primary growth engine** (§2) |

## 1. Channel and AI automation setup

### Jack's channel (do this first, about 1 hour)
1. **If Jack already has a YouTube channel:** use it. Rename it **"Jack Gleason"** and set
   the handle to **@JackGleason** (or the closest available).
   **If not:** create one from Jack's Google account (or a StartUpTrading Google
   Workspace account Jack owns). Use a **Brand Account** so the team can help.
2. **Access:** in YouTube Studio → Settings → **Permissions**, add yourself as **Manager**.
   Jack stays the Owner.
3. **Channel setup:**
   - Banner and avatar: use the existing `youtube/assets/banner.html` and `avatar.html`
     renders, updated with Jack's photo.
   - About text: verified facts only.
   - Links: Free tools · Newsletter · TradingView (each with UTMs, §3).
   - Playlists, one per series.
   - A 45-second **channel trailer** (Jack on camera: who he is, what the channel
     teaches, "risk first").
4. **Verify the channel by phone** (youtube.com/verify) for custom thumbnails and longer uploads.
5. **Point the automation at Jack's channel.** Re-run `python video/youtube_auth.py`,
   signing in as the **Manager on Jack's channel** and choosing that channel. Then
   replace the GitHub secret `YT_REFRESH_TOKEN`. Until then, keep every upload file on
   `"hold": true`.
6. **Set `youtube_url`** in `sales-site/site.config.json` to the new channel, then
   rebuild. The sales page's "Watch Jack trade on YouTube" link appears automatically.

### Filming setup (minimum viable)
- **Kit:** a phone on a tripod at eye level, a lavalier or USB mic, window light or one
  soft light, and a tidy background with the trading screens visible.
- **One 60–90-minute batch session a week:** 8–10 shorts (read hooks from §7) plus one
  long-form segment. Screen recordings (the planner, the calculator, charts) are
  captured separately and cut in.
- **Editing:** captions on every short; the first frame shows Jack and the hook text.

### Should the AI video automation feed Jack's channel?
**Yes, but as Jack's production assistant, not as a second presenter.**

- **Don't** publish AI-voiced explainers under Jack's name. Viewers would hear a
  different voice from the person on camera. That works against recognition, needs
  synthetic-media disclosure on every upload, and repetitive templated narration is
  the kind of content YouTube's inauthentic-content policy targets.
- **Do** use the pipeline for what it does best:
  1. **Chart and animation segments** (Risk Lab, ATR explainers, MES vs ES cards,
     formula scenes) that drop into Jack's videos as B-roll.
  2. **Captions, chapters and thumbnails** (`video/build.py`, `thumb.js`) for every upload.
  3. **Scheduled uploads:** Jack's edited videos go into `video/uploads/` and the daily
     workflow uploads them **as private, scheduled** videos with captions, chapters and
     thumbnail. Nothing goes public without a `publish_at` you set.
- **How episode 001 moves over:**
  - Keep the visuals.
  - Jack records the narration from `video/episodes/001-how-many-contracts.json` (the
    `say` lines are the script), in about 4 minutes on camera or as voice-over.
  - Drop his audio in place of the AI voice.
  - Set `"contains_synthetic_media": false` if nothing synthetic remains.
  - Remove `"hold"`.
- **Optional, later:** a clone of **Jack's own voice** (with his written consent) for
  quick corrections only. Still disclose it where YouTube asks.

## 2. Collaborations: the primary growth engine

**Why first:** a new channel has no reach. A guest appearance borrows an audience that
already trusts the host, and a good 45-minute conversation yields 5–8 shorts.
Collaborations do three jobs at once: reach, credibility and content supply.

**Effort split:**
- **About 40% of weekly growth time** goes to collaborations (finding, pitching,
  recording, clipping, following up).
- Clips from collaborations count toward the 50% **discovery** bucket in §4, with
  permission.

### Targets for the first 30 days
| Activity | Target |
|---|---|
| Personalised pitches sent | 40 (10 a week) |
| Bookings | 6–10 |
| Recorded appearances | 2–4 (podcasts and live streams book weeks out) |
| Shorts cut from appearances (with host permission) | 10–20 |
| "Jack Talks To" episodes recorded (Jack as host, §2.3) | 2 |
| Joint content with creators (duet, stitch, joint Risk Lab) | 2–4 |

### 2.1 Tiered approach
- **Tier 1, start now (more accessible):**
  - smaller futures and prop podcasts and YouTubers
  - TradingView Ideas comments on others' educational posts
  - r/FuturesTrading and NexusFi answers
  - roundtables (2 Bulls in a China Shop, Diary Of A Trader, Trading Nut, Optimus
    Futures Podcast, Futures Radio Show)
- **Tier 2, once 2–3 appearances exist as proof:**
  - prop-firm media (Funded: A Tradeify Podcast / TradeifyTV, The Day Trading Show,
    Speculators Podcast)
  - mid-size creators (1 Minute Futures Trader, Damn Good Trading)
  - the NinjaTrader Ecosystem vendor webinar (Jack is already a vendor)
- **Tier 3, once there's a body of appearances and clips:**
  - TopstepTV
  - NinjaTrader Live
  - Chat With Traders
  - Benzinga shows
  - RealSimpleAriel

Full list, with sources, in §8.

### 2.2 Guest kit (build once, about 2 hours, reuse for every pitch)
A one-page PDF or web page at `startuptrading.com/press`, containing:
- Jack's headshot (2 sizes)
- a short bio and a long bio (verified facts only)
- 5 talk topics with one-line descriptions:
  - "Size from the drawdown you have left"
  - "NQ vs MNQ: the 10× mistake"
  - "What changes on CPI/FOMC days"
  - "Why traders blow prop accounts on good days"
  - "Building your own trading tools"
- 2–3 sample clips
- a listener offer: the **free** tools, with no sign-up required
- a contact email

### 2.3 Jack as host: "Jack Talks To…" (a sixth series)
- **What:** Jack interviews other traders, prop-firm educators and developers on his
  channel.
- **Why it works:** guests share their episode with their own audience, so it's a
  collaboration that also builds Jack's catalogue. Hosting positions Jack as a peer of
  established names.
- **Cadence:** two a month to start.
- **Format:** recorded remotely (Riverside, or StreamYard with separate tracks), 30–45
  minutes, 3–5 clips each.

### 2.4 How collaborations are tracked
- **A vanity redirect per appearance,** read out on air. For example,
  `startuptrading.com/tradingnut` → `/free-tools?utm_source=podcast&utm_medium=referral&utm_campaign=tradingnut`.
  GoHighLevel can create URL redirects (Sites → Settings → URL redirects). Name every
  campaign after the show.
- **A log, `growth/collabs.csv`:** date, show, tier, status (pitched / booked /
  recorded / live), episode link, clip count, vanity URL, and the sessions, sign-ups and
  follows it brought in (from GA4 and the platforms).

## 3. Harvesting visitors: turning attention into an owned audience

Followers belong to the platforms. Email addresses and website visits belong to
StartUpTrading. Each item below turns a viewer into someone Jack can reach again.

| # | Action | Where | Status |
|---|---|---|---|
| H1 | **Switch on the email list.** Create the GHL form and workflow (`FREE_TOOLS_LIBRARY.md` §4) and set `ghl_subscribe_form_url`. The optional sign-up then appears on every free page | GHL + config | Form live on the free pages; add its hidden fields and fix its settings (`FREE_TOOLS_LIBRARY.md` §4.1–4.2) |
| H2 | **A weekly email, "The Opening Bell with Jack":** the week's volatility context, one lesson, one new clip or tool. It's the recurring reason to subscribe | GHL email | To do |
| H3 | **A "Start here" page (`/start`)** for link-in-bio: Jack's photo, one line, then Free tools · Weekly email · YouTube · TradingView. Every social bio links here with platform UTMs | New GHL page (I can build it the same way as the others) | Proposed |
| H4 | **A pinned comment and description template on every video:** one free-tool link matched to the topic, with `utm_source=youtube&utm_campaign=<series>`. End screen → the series playlist plus subscribe | YouTube | To do |
| H5 | **A verbal call to action in each video, once, near the end:** "The calculator I used is free on the site; no sign-up." Never mid-content | Scripts | To do |
| H6 | **A vanity URL per collaboration** (§2.4) | GHL redirects | To do |
| H7 | **Reply to comments in the first hour** after each upload. It's the cheapest reach multiplier, and it shows Jack is real | Jack (15 min/day) | To do |
| H8 | **Measurement pixels for later amplification:** Meta and Google tags via GTM, with consent. When an organic short over-performs, a small paid boost to similar audiences can follow, but only after month 1 shows what works | GTM | Later |
| H9 | **A tagged nurture sequence** (after launch Gate 2): 5 emails, education first, then one honest membership email. GHL tags by source and interest decide which tool each subscriber hears about | GHL | After Gate 2 |
| H10 | **A free Discord "lobby" channel (optional, Jack's call):** a public channel inside the existing server for questions and announcements, with members-only channels kept for paying members. It captures community-minded visitors, but it costs moderation time | Discord | Decide |

**Order of execution:**
- **First:** H1, H2, H4, H5 and H7.
- **Then:** H3 and H6 alongside the first collaborations.
- **Later:** H8 and H9.

## 4. Content allocation

| Share | Bucket | Purpose | Series |
|---|---|---|---|
| **50%** | High-reach discovery | Reach traders who've never heard of Jack | Jack Reacts, From the Screens, broad-appeal shorts |
| **30%** | Professional authority and market analysis | Show competence, consistently | The Opening Bell, method explainers |
| **15%** | Technology demos and Risk Lab | Prove the method; introduce the free tools | The Risk Lab, Inside StartUpTrading |
| **5%** | Direct membership promotion | Tell viewers what the membership is; never pushy | Inside StartUpTrading (offer episodes) |

**Weekly rhythm:**
- 7–8 shorts, spread across YouTube Shorts, Instagram Reels and TikTok
- 1–2 long-form episodes
- 2 TradingView ideas
- **10 collaboration pitches** plus recordings and follow-ups (§2): about 40% of weekly growth time

**Promotion runs only after launch Gate 2.** `growth/LAUNCH_AND_GROWTH.md`: the
membership must be open and licensing working before promoting it.

---

## 5. Competitive intelligence

### What I could and couldn't establish
- **Could:** who the visible futures creators, podcasts, prop-firm media and
  NinjaTrader educators are (sources in §8), and title and topic patterns visible in
  public listings.
- **Couldn't:** view counts relative to each channel's normal performance. That needs
  per-video data. **No performance metrics appear in this plan.**

### How to do the outlier analysis (about 2 hours, then monthly)
1. **List 10–15 futures creators.** Start with §8 and add the ones Jack watches.
2. **Get the data.** For each channel, export the last ~50 videos with their views,
   publish date and title. YouTube's channel "Popular" tab, or a third-party tool
   such as vidIQ or ViewStats, gives this. Do the same manually for Reels and TikToks.
3. **Score each video:** outlier score = views ÷ the channel's median views over the
   same period. A score of **3× or more** marks an outlier.
4. **Tag each outlier** with:
   - topic
   - title pattern
   - thumbnail pattern (face/no face, text, emotion)
   - opening line (the first 5 seconds)
   - format (reaction, story, chart breakdown, live, interview)
   - pain point
5. **Count the tags.** The patterns that repeat across **several** creators are what to
   test first. Record everything in `growth/outliers.csv`, the baseline for month 2.

### Patterns visible in public listings (qualitative, to be tested)
- **The credibility-plus-reveal framing:** "20-Year Pro Trader Reveals His…" and
  "Millionaire Day Trader Reveals…" both appear among the podcast and media titles.
  - Jack can use the **credibility half honestly** ("A futures trader since 2008
    explains…").
  - **Skip the money half.** No "millionaire" or earnings framing.
- **Prop-firm success and failure stories:** a dominant topic across Topstep, Apex and
  Tradeify media and independent channels. The pain points are blown accounts,
  trailing drawdown, consistency rules, and overtrading after a win.
- **NQ/ES and micros:** many channels narrow to NQ and ES. Beginners are steered to
  MES and MNQ. The risk confusion between the two sizes recurs.
- **Live and real-time:** daily live trading streams are common. This is a crowded
  space, but it's also where trust is built.
- **Risk management as the "real secret":** prop-firm stories regularly conclude that
  "risk management beats strategy". That's Jack's home ground.

### Jack's distinctive position
**"The adult in the room": a long-time futures trader who talks about risk the way
professionals do, builds his own tools, and never sells a lifestyle.**

- **Against hype:** no screenshots of P&L, no cars, no "I made $X today".
- **Specific and practical:** every piece answers one question a trader actually has.
- **Tool-backed:** when Jack says "size from risk", he can show it in the planner.
- **Fair:** Jack Reacts critiques *advice and concepts*, never mocks people.

---

## 6. The six series

| Series | Bucket | Format | What it is | Guardrails |
|---|---|---|---|---|
| **Jack Reacts** | Discovery | 30–60 s shorts; 15–25 min long-form | Jack responds to popular trading advice, claims and memes: what's right, what's missing, what he'd do instead | React to **ideas**. Quote claims as text on screen, or use short clips under fair use with commentary, with credit. Ask permission for longer clips. No dunking on individuals; no "exposed" titles |
| **From the Screens** (or "20 Years at the Screens" if confirmed) | Discovery | 45–90 s stories; occasional 10–15 min | Experience, mistakes and lessons from Jack's years trading | Only true stories Jack confirms. No P&L figures or income |
| **The Opening Bell** | Authority | 60 s pre-market short; weekly 10–15 min "week ahead"; TradingView ideas | Timely commentary: the session's events, volatility regime, levels Jack watches, and what that means for risk | Educational, not signals. No "buy here / sell there". Disclaimers |
| **The Risk Lab** | Tech / Risk Lab | 45–60 s shorts; 8–12 min episodes | Measurable experiments **about risk and process**, using the free tools | Measure risk variability, rounding, cost effects and drawdown survival. **Not** profit results or backtested returns |
| **Jack Talks To…** | Discovery (collaboration) | 30–45 min long-form; 3–5 clips each | Jack interviews traders, prop-firm educators and developers; guests share it with their audiences (§2.3) | Guests' claims are theirs; no performance claims presented as fact; permission for clips is part of the booking |
| **Inside StartUpTrading** | Tech / Promotion | 60 s shorts; occasional 8–10 min | How the tools are built, why, what's next. The membership explained plainly | Promotion episodes only after Gate 2. Honest about who it's *not* for |

---

## 7. First 30 days: production calendar

**Legend:**
- **Bucket:** D = discovery · A = authority · T = tech/Risk Lab · P = promotion.
- **Audience:** N = new futures traders · P = prop-firm traders · I = intermediate.
- **Production:** C = Jack on camera · V = Jack's voice over a chart or screen ·
  S = screen recording (the planner, the calculator) · AI = the `video/` pipeline for
  visuals.

**Ecosystem links** go in the profile and description only. They point to the free
tools (calculator, TradingView planner, `/indicators`), never directly to checkout.

### 30 short-form concepts
| # | Series | B | Hook (first line) | Aud. | Format | Prod. | Ecosystem connection |
|---|---|---|---|---|---|---|---|
| 1 | Jack Reacts | D | "'Risk 1% per trade.' Here's the part nobody tells you." | N | Reaction to on-screen quote | C | Calculator (% mode) |
| 2 | Jack Reacts | D | "'Just trade micros until you're profitable.' Good advice? Half of it." | N | Reaction | C | Calculator (MES/MNQ) |
| 3 | Jack Reacts | D | "The prop-firm tip that quietly fails accounts." | P | Reaction | C | Planner prop mode |
| 4 | From the Screens | D | "The trade that taught me more than any book." | N/I | Story | C | — (pure brand) |
| 5 | From the Screens | D | "What I'd tell myself the year I started." | N | Story | C | — |
| 6 | Discovery | D | "NQ says zero. MNQ says eight." | N/P | Chart reveal | V+S | TradingView planner |
| 7 | Discovery | D | "Why traders blow prop accounts on their *good* days." | P | Explainer | C+S | Calculator (prop) |
| 8 | Discovery | D | "Most traders size their trades backwards." | N | Explainer | C | Calculator |
| 9 | Jack Reacts | D | "'Win rate is everything.' Let's check that." | N/I | Reaction + whiteboard | C | — |
| 10 | From the Screens | D | "The day I stopped looking at my P&L during the session." | I | Story | C | — |
| 11 | Discovery | D | "Three numbers to know before you click buy." | N | List | C+S | Planner dashboard |
| 12 | Discovery | D | "Your stop isn't too tight. Your size is too big." | N/P | Explainer | C | Calculator |
| 13 | Jack Reacts | D | "The 'revenge trade' meme, from someone who's been there." | N/I | Reaction | C | — |
| 14 | From the Screens | D | "A losing week that made me a better trader." | I | Story | C | — |
| 15 | Jack Reacts | D | "'Move your stop to break-even fast.' When it helps, when it hurts." | N/I | Reaction | C+S | Planner levels |
| 16 | Opening Bell | A | "CPI morning. Here's why today's range is different." | I/P | Pre-market | C+S | Planner volatility row |
| 17 | Opening Bell | A | "ES or NQ this week? Here's what's actually moving." | I | Pre-market | V+S | — |
| 18 | Opening Bell | A | "Monday open: the first level I mark." | I | Chart | V+S | TradingView idea (same day) |
| 19 | Opening Bell | A | "Volatility is elevated. Here's what that does to your size." | I/P | Pre-market | C+S | Planner regime |
| 20 | Authority | A | "How I plan a trade in 30 seconds." | I | Walkthrough | S+V | Planner |
| 21 | Opening Bell | A | "FOMC day: what changes in my process." | I/P | Pre-market | C | — |
| 22 | Authority | A | "What ATR actually measures, in 40 seconds." | N | Explainer | AI+V | `/indicators` (free ATR) |
| 23 | Authority | A | "Crude oil's tick size catches people out." | I | Explainer | V+S | Calculator (CL) |
| 24 | Authority | A | "Static vs trailing drawdown, on one chart." | P | Explainer | AI+V | Calculator (prop) |
| 25 | Risk Lab | T | "Fixed 2 contracts vs ATR size: how much did the risk swing?" | I | Experiment | S+AI+V | Planner |
| 26 | Risk Lab | T | "How often does a 4-point ES stop sit inside normal noise?" | I | Experiment | S+AI+V | Planner ATR |
| 27 | Risk Lab | T | "Rounding down vs rounding up contracts: what it does to risk." | N/I | Experiment | AI+V | Calculator |
| 28 | Risk Lab | T | "How many losses can a $2,500 trailing drawdown survive?" | P | Experiment | S+V | Planner prop mode |
| 29 | Inside StartUpTrading | T | "Why we built a free TradingView risk tool." | All | Behind the scenes | C+S | `/free-tools` |
| 30 | Inside StartUpTrading | P | "What's in the membership, and who it's *not* for." (after Gate 2) | I | Plain offer | C | Homepage |

**Risk Lab rule:** episodes measure risk, rounding, costs, noise or drawdown survival
on real charts. They never show or imply trading profits, and they aren't backtests
presented as results.

### Long-form YouTube (6 episodes in 30 days)
| # | Series | Title idea | Length | Prod. | Connection |
|---|---|---|---|---|---|
| L1 | Jack Reacts | "Reacting to the most common prop-firm advice" | 15–20 min | C + on-screen quotes | Planner prop mode |
| L2 | From the Screens | "My trading story: what changed and what didn't" (verified facts only) | 15–20 min | C | About Jack page |
| L3 | Opening Bell | "Week ahead in ES and NQ: events, volatility, levels" (weekly) | 10–12 min | C+S | TradingView ideas |
| L4 | Opening Bell | "Week ahead" (second week) | 10–12 min | C+S | — |
| L5 | Risk Lab | "Fixed size vs ATR size across a month of ES: the risk you didn't see" | 10–12 min | S+AI+V | Planner, calculator |
| L6 | Inside StartUpTrading | "Building a free futures risk tool, from idea to TradingView" | 8–10 min | C+S | `/free-tools`, the planner |

**Collaborations can take long-form slots.** A recorded "Jack Talks To…" episode, or a
podcast appearance published with permission, replaces any of L1–L6 that week.
Episode 001 ("How many contracts…") is re-cut with Jack's voice before it goes up (§1).

### 8 TradingView publications (ideas, not scripts)
All are educational and use a clean chart. There are no links, handles or company
names; the Signature carries the link (Premium). See
`TRADINGVIEW_ECOSYSTEM.md` §1 for the rules.

1. ES week ahead: volatility regime and the levels Jack watches
2. NQ vs MNQ on a real chart: same stop, different risk
3. CPI morning: why ATR jumps and what it does to position size
4. CL: tick size and contract value, explained on the chart
5. Prop-firm budgeting from the remaining drawdown (planner on chart)
6. GC: volatility expansion and stop placement
7. FOMC preparation: a process, not a prediction
8. Month in review: how the volatility regime shifted, and how sizing adapted

### Repurposing Jack's existing appearances
I don't have a list of Jack's past podcasts, streams or interviews. Send them over.
For each one:
1. Ask the host for **written permission** to clip it.
2. Cut 30–60 s self-contained moments.
3. Credit the show on screen and in the caption.
4. Tag the series (usually From the Screens or Jack Reacts).

---

## 8. Borrowed audiences: the full outreach list (20 opportunities; strategy in §2)

Priority is a qualitative judgement of relevance to futures and risk, credibility, and
access for a first-time guest. No relationships are implied. Each one needs a fresh
check of current guest policies.

| # | Opportunity | Type | Why it fits | Access | Priority |
|---|---|---|---|---|---|
| 1 | [Chat With Traders](https://rephonic.com/podcasts/chat-with-traders) | Podcast | Long-form trader interviews; futures guests | Medium–hard | A |
| 2 | [Trading Nut](https://tradingnut.com/episodes/) | Podcast | Interviews with practising traders, including futures | Medium | A |
| 3 | [Optimus Futures Podcast](https://optimusfutures.com/podcast/tag/futures-trading/) | Podcast (broker) | Futures-only audience; past ES trader guests | Medium | A |
| 4 | [Futures Radio Show](https://rephonic.com/podcasts/futures-radio-show) | Podcast | Futures-specific | Medium | A |
| 5 | TopstepTV / [Topstep community](https://www.topstep.com/blog/best-free-trading-community) | Prop-firm media | The largest prop community; daily streams | Medium–hard | A |
| 6 | [Funded: A Tradeify Podcast](https://podcasts.apple.com/us/podcast/id1895323589) / TradeifyTV | Prop-firm media | A prop audience that needs risk education | Medium | A |
| 7 | NinjaTrader Live ([relaunch](https://ninjatrader.com/News/NinjaTrader-Unveils-NinjaTrader-Live)) | Platform livestream | Plans to add industry experts; NinjaTrader users | Hard | A |
| 8 | NinjaTrader Ecosystem vendor webinars ([education](https://ninjatrader.com/futures/blogs/level-up-your-futures-trading-with-expert-education/)) | Platform education | Jack is already a vendor; webinars are part of NinjaTrader education | Medium | A |
| 9 | Benzinga "Trader Bacon" (Apex, [source](https://www.benzinga.com/amp/content/33131339)) | Media show | Prop and futures audience | Hard | B |
| 10 | [Speculators Podcast](https://chartable.com/podcasts/speculators-podcast/episodes/144977517-futures-prop-trading-mastery-exclusive-interview-with-topstep-ceo) | Podcast | Futures and prop topics | Medium | B |
| 11 | [The Day Trading Show](https://pocketcasts.com/podcast/the-day-trading-show/8484c440-4517-0138-975e-0acc26574db2/millionaire-day-trader-reveals-the-secret-to-future-prop-firm-success/b564f16b-9247-4fdc-96ee-e6d557a6ff73) | Podcast | Prop-firm and risk stories | Medium | B |
| 12 | [2 Bulls in a China Shop](https://redcircle.com/shows/2-bulls-in-a-china-shop/ep/35e54e11-d87d-4397-ba20-97529e43dde0) | Roundtable podcast | Candid prop-firm discussion | Easy–medium | B |
| 13 | [Desire To Trade](https://rephonic.com/podcasts/desire-to-trade-podcast-forex-trading-tips-intervi) | Podcast | Large trader-interview catalogue (multi-asset) | Medium | B |
| 14 | [Diary Of A Trader](https://diaryofatrader.substack.com/p/mastering-futures-insights-from-a) | Podcast / Substack | Futures interviews | Easy–medium | B |
| 15 | [1 Minute Futures Trader](https://www.youtube.com/@1minutefuturestrader) | YouTube creator | NQ/ES scalping, prop tips, risk | Medium | B |
| 16 | Damn Good Trading (Kyle Kozlowski, [Damn Prop Firms](https://damnpropfirms.com/?p=235)) | YouTube / review site | Prop-firm audience. Note the affiliate ties | Medium | B |
| 17 | RealSimpleAriel ([cited by a funded-trader guide](https://fortraders.com/blog/top-5-best-trading-youtubers-in-2025-curated-by-expert)) | YouTube creator | NQ/ES execution-focused audience | Hard | B |
| 18 | TradingView Ideas community (Jack's own ideas, plus comments on others' educational ideas) | Platform | Daily discovery; Editors' Picks for strong education | Easy | A |
| 19 | r/FuturesTrading, [NexusFi](https://nexusfi.com/a/prop-firms/prop-firm-position-sizing) | Communities | Futures practitioners. **Follow each community's self-promotion rules**: answer questions, disclose, use links only where allowed | Easy | B |
| 20 | Futures creator lists ([Feedspot](https://videos.feedspot.com/futures_trading_youtube_channels/)) | Discovery list | Source for smaller NQ/ES creators open to collabs (duets, joint Risk Lab) | Easy | C |

**Pitch template (education first, no subscription pitch):**

> Subject: A risk-first segment for your [show] audience
>
> Hi [name], I've followed [specific episode/topic]. I'm Jack Gleason, a futures trader [since YEAR, confirmed] who builds his own risk tools for NinjaTrader and TradingView.
> Your audience talks a lot about [pain point, e.g. trailing drawdown]. I'd love to walk through one practical idea: [e.g. "how to size a trade from the drawdown you have left, not the account size"], with real examples. No pitch. Happy to share a free calculator your listeners can use without signing up.
> Topics I can cover: sizing from risk; NQ vs MNQ risk; surviving trailing drawdown; what changes on CPI/FOMC days.
> [Two recent clips or ideas as proof]
> Jack

**Collaboration formats for creators:**
- a joint Risk Lab episode (the same chart, two approaches)
- a duet or stitch reaction (with permission)
- a guest Opening Bell segment
- a podcast swap

---

## 9. Measurement: a 30-day baseline, then adapt

| Metric | Where | How |
|---|---|---|
| Non-follower reach | YouTube Studio (new vs returning viewers; impressions from non-subscribers), Instagram Insights (accounts reached: non-followers), TikTok analytics (For You traffic %) | Per video; median per series |
| Retention | YouTube (average % viewed; the first-30-seconds curve), Reels and TikTok (average watch time, completion) | Shorts: % watched past 3 s and to the end |
| Shares and saves | Platform analytics | Per 1,000 views |
| Profile visits | Instagram, TikTok, YouTube (channel page views) | Per 1,000 views |
| **Followers per 1,000 views** | New followers ÷ views × 1,000 | **The headline awareness metric**, per series and format |
| Branded search | Search Console (queries containing "jack gleason" or "startuptrading"), Google Trends (Jack's name, if there's enough volume) | Monthly |
| Free tool adoption | GA4 `free_tool_view`, `tool_use`; TradingView script users and favorites | Weekly |
| Website referrals | GA4 sessions by `utm_source` (youtube, instagram, tiktok, tradingview) with `utm_medium=social` and `utm_campaign=<series>` | Weekly |
| Collaboration yield | `growth/collabs.csv` + GA4 by vanity-URL campaign | Sessions, sign-ups and follows per appearance; clips produced |
| Qualified subscribers | GA4 `email_subscribe` and GHL contacts with source tags; later `sut_purchase` and Whop memberships by first touch | Monthly |

**Link conventions** (in bios and descriptions only):
`?utm_source=youtube|instagram|tiktok&utm_medium=social&utm_campaign=jack_reacts|from_the_screens|opening_bell|risk_lab|inside_sut`

**Rules for month 2:**
1. Rank series and formats by **followers per 1,000 views**, then by shares and saves
   per 1,000.
2. **Double** the top quartile, **keep** the middle half, and **rework or drop** the
   bottom quartile (change the hook or format once before dropping).
3. Re-run the outlier analysis (§5) with month-1 data from your own channel.
4. Only then revisit the 50/30/15/5 split. If authority content wins on followers per
   1,000 views, shift toward it.

---

## 10. Guardrails (unchanged and non-negotiable)

- **No earnings or P&L claims,** no "millionaire" or lifestyle framing, and no
  fabricated or hypothetical trading results.
- **No misleading controversy,** clickbait the content doesn't deliver, mocking of
  individuals, or "exposed" framing.
- **No artificial engagement:** no bought views, follows or comments, and no
  engagement pods.
- **TradingView:** no links or company names in ideas or scripts; links in the Premium
  Signature only.
- **Platform disclosures:** mark AI-generated or synthetic media where required
  (YouTube's altered-content setting).
- **Risk disclosure** in descriptions: "Educational content. Futures trading involves
  substantial risk of loss."
- **Website, licensing, checkout, affiliate attribution and launch gates are
  unchanged.** Promotion waits for Gate 2.

---

## 11. Signal listening: find traders asking for help, and help them in public

Added 2026-11-28. **The idea:** traders describe the exact problems Jack's tools solve
in public every day ("how many contracts should I trade?", "blew my eval on the trailing
drawdown", "my stop keeps getting hit on NQ"). Instead of cold outreach, we find those
posts quickly and answer them well, in public, as Jack. Help comes first. A link appears
only when a free tool genuinely answers the question.

**What's automated and what isn't:**
- **Automated:** finding the posts, sorting them, drafting the reply, the compliance
  check, and a daily digest.
- **A person decides and posts:** every reply, from Jack's own account.
- **Same rule as the rest of the marketing system:** nothing is ever posted
  automatically.

### 11.1 Why public replies, not automated DMs

| | Public reply as Jack | Automated cold DMs |
|---|---|---|
| Reach | The asker, everyone who reads the thread later, and search engines | One person |
| Trust | Visible expertise. Others can see the answer is good | Reads as spam; people screenshot it |
| Platform risk | Fine within each community's rules | Against X and Reddit rules on automated or unsolicited messaging; account limits or bans |
| Compounding | Threads rank on Google and in AI answers for months | None |

DMs are only for continuing a conversation **the other person started**: they replied,
asked, or DMed first.

### 11.2 The Listening desk (a new desk in `marketing/`)

```
Sources ──► Signal filter ──► Claude: classify ──► Claude: draft reply ──► compliance.py ──► Daily digest ──► Jack posts
(APIs)      (keywords)        (topic, intent,      (Jack's voice,          (phrase rules,      (Discord bot,       (own account,
                               fit, sensitivity)    brand_brief.md)         no advice)          top 10 + drafts)    edits freely)
```

**Sources** (official APIs only; no scraping, no logged-in bots):

| Source | Where | Access |
|---|---|---|
| Reddit | r/FuturesTrading, r/Daytrading, r/NinjaTrader, r/Trading, prop-firm subreddits | Reddit Data API. **Check Reddit's terms for commercial use first; approval may be needed** |
| YouTube comments | NinjaTrader Live episodes (Jack's own appearances first), prop-firm and futures-education channels | YouTube Data API (comment threads), quota-limited |
| X | Keyword searches on the same signals | X API search needs a paid tier. Until then, saved searches checked by hand in the digest |
| Jack's own channels | Comments and replies on his videos and TradingView scripts | Already his; reply to every question within a day |
| Forums (NinjaTrader forum, futures.io, TradingView comments) | Manual only: no API, and their rules limit promotion | Listed in the digest as "check by hand" |

Never collect from private Discords or groups, and never store more than the post's
public link, text and handle. Delete digest data after 30 days.

**Signals** (starting keywords; the weekly review tunes them):
- **Sizing:** "how many contracts", "position size", "risk per trade", "MES or ES", "micro vs mini"
- **Stops:** "ATR stop", "stop too tight", "keep getting stopped out", "stop loss NQ"
- **Prop firms:** "trailing drawdown", "failed my eval", "daily loss limit", "funded account rules"
- **Platform:** "NinjaTrader ATM strategy", "NinjaTrader position size", "TradingView position size indicator"

**Classification** (Claude, one call per post), scoring each post on:
- **Topic:** sizing, stops, prop rules, platform or other.
- **Intent:** asking for help, discussing, venting, or selling.
- **Fit:** does a free tool or a short answer fully solve it?
- **Sensitivity:** see 11.3.

Only *asking for help* with a fit of 4–5 out of 5 reaches the digest.

**Drafting:** Claude writes a reply in Jack's voice from `brand_brief.md`:
- It answers the question in the reply itself, with the arithmetic where it helps.
- It links a free tool only if the tool does exactly what was asked. The link carries
  tracking: `?utm_source=reddit|youtube|x&utm_medium=reply&utm_campaign=listening&utm_content=<topic>`.
- It says who's replying when there's a link: "I built this calculator".
- It **never** mentions the paid membership.

**Compliance:** the existing phrase rules apply. In addition, every draft is checked for
two things, and fails if either is present:
- **No individualised advice:** nothing like "you should trade 2 MNQ".
- **No performance claims.**

**Digest:** each morning, at most 10 threads, sent by the Discord bot that already posts
the attention alerts. Each item has:
- the link, a one-line summary and the draft reply;
- the platform's self-promotion rule for that community;
- a "skip" button.

### 11.3 Who we never pitch

The sensitivity score excludes, or reduces to a link-free general answer:
- posts about **large losses, debt, borrowing to trade, or wanting to "win it back"**;
- signs of distress or gambling-like behaviour;
- anyone who appears to be under 18.

People in that situation get, at most, a kind public answer about risk limits. Never a
product link, never a DM. That's partly ethics. It's also practical: pitching a trading
product to someone who just lost money is the fastest way to be called a predator in
public, and to attract a regulator's attention.

### 11.4 Daily limits and etiquette

- At most **5 replies a day per platform**, and never more than 1 per community per day.
- Never reply twice to the same person in 30 days unless they reply first.
- Follow each subreddit's self-promotion rules; many forbid links entirely. There, the
  reply is the answer with no link, and the profile does the rest.
- **No other accounts:** no sockpuppets, no "I had the same problem and this tool fixed
  it", no friends posting on Jack's behalf, no undisclosed affiliates. Only Jack's own
  disclosed account.
- Replies are written as Jack and approved by Jack. If someone else on the team posts,
  the profile says so.

### 11.5 The bigger payoff: a "pain-point index"

Every classified post, including the ones we never reply to, is counted by topic. Each
week the index shows which problems are most common, and feeds:
1. **Content:** the top 3 problems become that week's Shorts and the Strategist's theme.
   It answers the question "what should Jack make next?" with data instead of guesses.
2. **`/learn` pages:** recurring questions become answer pages with the calculator built
   in, so search engines and AI answer engines send those people to us without anyone
   replying at all.
3. **Product:** recurring requests become the next free tool or member tool.

### 11.6 How it fits the funnel and how we measure it

The flow: a public answer, then the free tool (no sign-up), then the optional email
sign-up or the free Discord. The membership is offered later, through the normal pages
and emails, never in the reply.

| Metric | Source |
|---|---|
| Replies posted / skipped | Digest log |
| Upvotes and replies per answer | Platform |
| Sessions, tool use, sign-ups from `utm_campaign=listening` | GA4 (already tracked by channel) |
| Members whose first touch was `listening` | `/admin/marketing` attribution |
| Top problems this week | Pain-point index |

**Go or stop after 30 days:** keep it only if listening replies drive at least as many
email sign-ups per hour of Jack's time as making short videos, and draw no community
complaints or removals.

### 11.7 Before building

1. **Jack's time:** about 20 minutes a day to read the digest, edit and post. Without
   that, it's only the pain-point index (still useful).
2. **Compliance check:** confirm with an NFA compliance contact that public educational
   replies from Jack (Series 56) fit NFA Rule 2-29, and keep the digest log as the record.
3. **API access:** Reddit Data API terms for commercial use; whether an X API paid tier
   is worth it after month 1; a YouTube Data API key.
4. **Build order:**
   - first YouTube comments and Jack's own channels (lowest risk, highest fit);
   - then Reddit, once its API terms are confirmed;
   - then X.

### 11.8 Competitor complaints as a buying signal (adapted from the "1-star review" cold-email tactic)

**The source tactic:** scrape competitors' 1- and 2-star reviews, find each reviewer's
email, and cold-email them within 72 hours. **We don't do it as written:**
- **The recipients are individuals.** Retail traders, not businesses: the EU, UK and
  Canada require consent for marketing email to individuals.
- **Scraping:** Trustpilot's and LinkedIn's terms prohibit scraping their reviewers and
  profiles.
- **Who's reviewing:** many reviewers of trading products just lost money (§11.3).
- **Jack's registration:** Series 56 means NFA rules on public communications apply.
- **The economics:** a sales-call model doesn't fit a $99 subscription.

**What we keep:** a complaint about a competitor shows someone already buys this kind of
product, is unhappy, and is shopping now. We meet that intent where people show it
themselves.

| Version | How | Permission basis |
|---|---|---|
| **1. Complaint map** (insight, not outreach) | Monthly, read the public 1–3★ reviews of the top trade rooms and NinjaTrader indicator vendors (Trustpilot, Whop, Reddit "is X legit?" threads). By hand or with the Listening desk; text only, no reviewer data kept. Tally the complaints: hype or signal-selling, repainting, upsells, hard cancellation, licensing hassle, no real education | Reading public reviews; no contact |
| **2. Answer the complaints on our own pages** | Each top complaint becomes proof on the site or the FAQ, **only where true and in the brand brief:** "No tiers, no upsells", "Cancel anytime in Whop", "Licensed automatically", "Tools, not signals". Add a "What we don't do" block, and a `/switching` page for traders leaving another room. **No competitor names**, nothing we can't prove | Our own site |
| **3. Intercept the search, not the person** | Paid search on intent phrases such as "trading room alternative", "best NinjaTrader position size indicator" and "[category] review", sending people to `/switching` or the free tools. Bidding on competitor names is a later, legal-reviewed decision (trademark rules on ad text) | The person searched |
| **4. Be the helpful voice in public complaint threads** | When someone asks on Reddit "is X worth it?" or "alternatives to X?", Jack answers through the Listening desk (11.2): honest criteria for judging any trade room or tool, with a disclosure, and no attacks on the competitor | They asked publicly |
| **5. Do the same for our own unhappy users** | Whop cancellation (`subscription_cancel` is already tracked): a one-question exit survey email, a personal reply from Jack to every answer, and fixes fed back into the product. Reply publicly to every StartUpTrading review on Whop or Trustpilot within 48 hours | They're our customers |

**Measure:**
- **`/switching` and the paid-search campaigns:** conversions tagged
  `utm_campaign=switching`.
- **Cancellation:** churn rate before and after the exit-survey loop.

**Never:**
- build lists of reviewers or look up their emails or profiles;
- message someone because they reviewed a competitor;
- name competitors in comparisons;
- use "I was about to switch to X" style testimonials we can't verify.
