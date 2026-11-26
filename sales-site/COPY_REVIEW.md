# Sales page: copy review and assets checklist

Jack (or whoever owns the product) should sign off on every item here before
the page is promoted. Nothing on the page invents results, testimonials or
member numbers. Where facts weren't available, the page has a dashed orange
placeholder box instead.

## A. Claims to confirm (edit `src/page.html` if any are wrong)

| # | Where | Current copy | Why it needs checking |
|---|---|---|---|
| 1 | Indicators → Trend Scanner & Market Selector | Copy taken from startuptrading.com's Tools section ("Daily trend strength and direction for every market on your watchlist…") | ✅ Jack's own wording. |
| 2 | What's included → masterclass | "Jack's masterclass", included with the membership and granted through Whop | TSMS & Fibs was removed from the membership (Nov 2026). Confirm the masterclass name, what it covers and that Whop grants it on checkout. |
| 3 | Indicators → ATR Order Automation | Copy taken from startuptrading.com's Tools section ("Sizes each trade from ATR and places your stop and target…") | ✅ Jack's own wording. |
| 2a | Hero | "Jack has traded futures since 2008" | Your brief said "20 years"; 2008 to 2026 is about 18. "Since 2008" matches what Jack has said elsewhere. Confirm the start year before using "20 years" anywhere. |
| 2b | Hero, strip, tools, pricing, FAQ | "Every new tool he releases is added to your membership and licensed to you automatically … No extra purchase" | A firm promise customers will hold you to (stronger than the earlier "eligible new tools"). Confirm every new tool Jack releases will be included in the membership at no extra cost. If some will be sold separately, say so and the copy goes back to "eligible". |
| 2c | Community | "Discord tools, in development: custom bots and utilities … released to members as they're ready" | Shown as in development, not as included today. Keep it that way until they ship. |
| 2d | Community, pricing, FAQ | "Masterclasses & trading education", granted at checkout through Whop | Confirm the masterclasses exist on Whop and are attached to both plans. |
| 4 | Hero, strip, FAQ | "Licensed … minutes after you join" / "~3 min" | True once live license writes are enabled (Phase 3). Until then, licensing isn't automatic. |
| 5 | Hero, pricing, FAQ | "Cancel anytime … keep access until the end of the period you've paid for" | Matches the bridge's logic. Confirm it's the business policy, and add a refund line if there is one. |
| 6 | FAQ | "NinjaTrader 8 on a Windows computer" | Confirm the indicators are NT8 desktop only. |
| 7 | Trade room | "Direct line to Jack", "Ask about setups and how he uses each indicator" | The status report says direct access is "subject to the team's defined support offering". Tighten if access is limited (for example "weekly Q&A"). |
| 8 | Trade room | "Education & walkthroughs", "Setup help" | Confirm these happen. Specifics (for example "live sessions every weekday at 9:30 ET") convert better than generalities. |
| 9 | Hero | "Jack's indicators" | Confirm Jack is the right name to lead with, and that he's comfortable being the face of the page. |
| 10 | Footer | Risk disclosure, "not affiliated with NinjaTrader" | Have whoever handles compliance approve the wording. |
| 11 | Thank-you page, step 3 | "Open StartUpTrading in your Whop account and connect Discord" | Confirm that's how members get Discord access in your Whop setup. Set `whop_hub_url` in `site.config.json` to show an "Open my Whop membership" button. |
| 13 | Pricing "Not ready yet?", FAQ, exit popup | "Jack's free ATR Headliner Indicator" … "Free, no card needed" | ✅ Name taken from the live site. Confirm `/indicators` asks for no card. |
| 14 | Free vs Membership table | Members also get the free ATR indicator (✓ in both columns) | Confirm it's included or available to members; otherwise change that row. |
| 12 | Thank-you page, step 4 | "As soon as activation finishes, we email install instructions" | True once `INDICATOR_SETUP_URL` is set in Render and live license writes are on (Phase 3). |
| 15 | FAQ | "I already bought ATR Order Automation or the Trend Scanner. Can I join?" … "You keep the license you bought" | Matches the app: one-time licenses are never changed or revoked. Confirm there's no discount or upgrade path you'd rather offer. |

## B. Assets to supply (replace the dashed boxes)

| Placeholder | What to supply | Notes |
|---|---|---|
| Hero "Demo video goes here" | 30–60 s screen recording, both indicators on one live chart | Upload to YouTube (unlisted) or Vimeo and swap the overlay for an embed, or send the file and I'll wire it in. No audio needed; captions help. |
| Trend Scanner / ATR screenshots | One 1600×1000 chart capture each, lightly annotated | Real charts only. Crop out account balances and P&L. |
| Discord screenshot | One channel view: Jack's chart post plus member replies | Blur usernames and avatars unless members agree. |
| Photo of Jack | At his actual desk, landscape or 4:5 | No stock photos. This is the most trusted element on the page. |
| Jack's bio | 3–4 sentences in his voice | How long he's traded, what he trades, why he built these, where to watch him. Facts only. |
| Member quotes | 3 real quotes with permission (first name + "member since …") | **No profit or income figures.** If you don't have three yet, delete the whole "From members" section. |
| Logo | SVG or PNG | Replaces the placeholder candlestick mark in the nav. |
| Social image | 1200×630 | Set in GHL page SEO settings. |

## C. Decisions

- **Annual plan ($495/yr):** approved and live on the page as a Monthly/Annual
  toggle in pricing ("Save 58%", $41.25/month equivalent). Make sure the annual
  plan is set to visible/purchasable in Whop.
- **Domain:** `startuptrading.com` (confirmed).
- **Terms and Privacy pages:** add the URLs to `site.config.json` and they
  appear in the footer. These are expected on any page that takes payment.
- **YouTube channel URL:** add it to `site.config.json` to show the
  "Watch Jack trade on YouTube" link.

## Visual upgrade (2026-11-26): new copy for Jack's sign-off

Placeholders were replaced with content built only from facts already on record (llms.txt,
products.json, the existing page). Please confirm or correct:

- **Bio + credential card** (#jack): traded since 2008; own tastytrade show from 2012; traded at a
  proprietary firm; Series 56; trades on NinjaTrader Live several times a week; the ATR rule.
- **Channel preview** (#room): channel names `trade-room`, `masterclasses`, `chart-reviews`,
  `tool-releases` (members) and `free-tools-help`, `market-talk` (free). Rename to match the real server.
- **Tool windows**: labelled "Illustration". The scanner values are examples, not readings. Swap in real
  captures by setting `scanner_media_url` / `atr_media_url` (MP4/WebM loop or an image) in site.config.json.
- **"Inside the membership"** replaces the member-quote placeholders. Real, permissioned quotes can go
  back in later; none were invented.
- **ATR demo**: the math is the page's own example ($180, MES, 1.5 × ATR stop: 3 contracts at ATR 8,
  1 at ATR 24). Labelled "Example only, not a recommendation."
- **Contract-spec ticker**: CME tick sizes and values (ES, MES, NQ, MNQ, YM, MYM, RTY, M2K, CL, MCL, GC, MGC).
- **Site-wide (2026-11-26):** the same visual layer now runs on every page. New labelled illustrations:
  the TradingView planner on an ES chart (size panel, entry/stop/2R lines, arithmetic as in the script),
  the NinjaTrader Control Center Tools → Import → NinjaScript Add-On menu (/setup), and an ES chart with
  ATR brackets (/setup step 4). Replace with real screenshots whenever Jack has them.
