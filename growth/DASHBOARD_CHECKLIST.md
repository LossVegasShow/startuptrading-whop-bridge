# Remaining dashboard tasks (one list)

Updated 2026-11-26. Everything in code is done and merged; these are the clicks left.
`membership_open`, held reminders and promotional campaigns stay **off** throughout.

## Decide first
- [ ] **Purchasing is reachable now.** The homepage carries the live Whop checkout and licensing is `all_members`. If you want purchasing closed until the acceptance test passes, set the GHL default page back to **Home** (everything works either way; `/join` serves the same page).

## GA4 (analytics.google.com, property 565901572)
- [ ] **Root cause of the missing `content_group`:** Admin → Data streams → *startuptrading.com* → **Configure tag settings** → *Show all* → **Ignore duplicate instances of on-page configuration** → **Off**. With it on, the property's gtag.js configures itself on load and sends its own page_view (raw URL incl. `gtm_debug`, no content group, no user properties), discarding the configuration from GTM. Tell me when it's off: I'll re-fetch the tag and re-run the network check (it changes within minutes).
- [ ] Admin → Data collection → **User-provided data collection** → turn **automatic detection off** (the tag currently auto-collects email, phone and address from pages; we send no PII).
- [ ] Data streams → *startuptrading.com* → **Enhanced measurement** → turn off **Form interactions** and **File downloads** (the site sends its own `generate_lead` and `file_download`; leaving them on double-counts).
- [ ] Admin → Custom definitions → **Create custom dimension**: *Page type*, scope **Event**, parameter `page_type`. (Content group needs no setup.)
- [ ] Admin → Data streams → *startuptrading.com* → **Measurement Protocol API secrets** → Create → put the value in Render as `GA4_API_SECRET` (server-side purchase, refund and activation events).

## GTM (GTM-ML2LKZ7C)
- [ ] Admin → **Import container** → `growth/gtm/startuptrading-gtm-container.json` → workspace *Default* → **Merge** → *Overwrite conflicting* → Confirm. (Adds `content_group` and the clean `page_location` to every GA4 event, so events are classified even before the GA4 setting above is changed.)
- [ ] **Preview** on `https://startuptrading.com/` → **Submit → Publish** (version 6).

## GoHighLevel
- [ ] **`/join` is indexable and in the sitemap** (duplicate of `/`): turn noindex on for `/join` if GHL lets you without affecting `/`; otherwise just exclude it from the sitemap.
- [ ] **Sitemap:** exclude `/welcome`, `/setup` (they're noindex) and `/join`; include `/indicators` and `/policies-terms` if still published. Keep `/`, `/free-tools`, the calculator and the TradingView page.
- [ ] Google Search Console → Sitemaps → resubmit `sitemap.xml`; URL Inspection → `https://startuptrading.com/` → Request indexing.
- [ ] Optional: `/home` (old Home + VSL page, still indexable) → 301 to `/` under Settings → URL Redirects. The funnel itself stays untouched.
- [ ] Optional: homepage description wording: "Access proprietary NinjaTrader and TradingView indicators, advanced futures trading tools…".
- [ ] CRM workflows for Form 7 leads (tag by `interest`, nurture email) — still to build.

## Whop
- [ ] Community product (plan_Nzi6M0goKvcWY) → after-checkout redirect `https://startuptrading.com/free-tools?community=joined`.
- [ ] Discord app: free community product → *Community* role; paid product → *Member* role (trade room + members-only channels).

## Activation app (activate.startuptrading.com)
- [ ] `/admin/products` → upload `SUT_ATR_Orders_2026.zip` and `StartupTrading_Tools_Scanner_2026.zip`; both must show **verified**.
- [ ] Run the live acceptance purchase test (PRODUCTION_LICENSING.md, sections C and A). When it passes, tell me and I'll turn `membership_open` on.

## Jack
- [ ] Sign off the sales page copy; send real screenshots for the tools section.
