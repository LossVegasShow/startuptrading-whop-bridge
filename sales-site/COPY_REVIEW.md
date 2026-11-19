# Sales page: copy review and assets checklist

Jack (or whoever owns the product) should sign off on every item here before
the page is promoted. Nothing on the page invents results, testimonials or
member numbers. Where facts weren't available, the page has a dashed orange
placeholder box instead.

## A. Claims to confirm (edit `src/page.html` if any are wrong)

| # | Where | Current copy | Why it needs checking |
|---|---|---|---|
| 1 | Indicators → TSMS | "Reads trend direction and momentum together and shows you when they agree" | Written from the indicator's name. Describe what it actually plots. |
| 2 | Indicators → TSMS & Fibs | "Everything TSMS does, with Fibonacci levels drawn for you" | Written from the name. Confirm Fibs are automatic and what they anchor to. |
| 3 | Indicators → ATR Order Automation | "Sets your order distances from the Average True Range" | Written from the name. Confirm it manages stops and targets, and whether it places orders. |
| 4 | Hero, strip, FAQ | "Licensed … minutes after you join" / "~3 min" | True once live license writes are enabled (Phase 3). Until then, licensing isn't automatic. |
| 5 | Hero, pricing, FAQ | "Cancel anytime … keep access until the end of the period you've paid for" | Matches the bridge's logic. Confirm it's the business policy, and add a refund line if there is one. |
| 6 | FAQ | "NinjaTrader 8 on a Windows computer" | Confirm the indicators are NT8 desktop only. |
| 7 | Trade room | "Direct line to Jack", "Ask about setups and how he uses each indicator" | The status report says direct access is "subject to the team's defined support offering". Tighten if access is limited (for example "weekly Q&A"). |
| 8 | Trade room | "Education & walkthroughs", "Setup help" | Confirm these happen. Specifics (for example "live sessions every weekday at 9:30 ET") convert better than generalities. |
| 9 | Hero | "Jack's indicators" | Confirm Jack is the right name to lead with, and that he's comfortable being the face of the page. |
| 10 | Footer | Risk disclosure, "not affiliated with NinjaTrader" | Have whoever handles compliance approve the wording. |

## B. Assets to supply (replace the dashed boxes)

| Placeholder | What to supply | Notes |
|---|---|---|
| Hero "Demo video goes here" | 30–60 s screen recording, all three indicators on one live chart | Upload to YouTube (unlisted) or Vimeo and swap the overlay for an embed, or send the file and I'll wire it in. No audio needed; captions help. |
| TSMS / TSMS & Fibs / ATR screenshots | One 1600×1000 chart capture each, lightly annotated | Real charts only. Crop out account balances and P&L. |
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
