# Sales site: GoHighLevel + Namecheap setup

> ⏸ **On hold:** the owner doesn't have GoHighLevel or DNS (Namecheap)
> access yet, so everything in this guide is parked until access is granted.
> The consolidated reminder list is **"Waiting on access"** at the top of
> `PLAN.md` (groups A–C).

The sales page lives on **GoHighLevel (GHL)**. The member activation app stays
on **Render**. **Namecheap** DNS points the domain at both:

| Address | Serves | DNS record (Namecheap) |
|---|---|---|
| `startuptrading.com` | Sales page (GHL) | `A` record from GHL's domain screen |
| `www.startuptrading.com` | Sales page (GHL) | `CNAME` from GHL's domain screen |
| `startuptrading.com/welcome` | Thank-you page (GHL) | Same domain, no extra DNS |
| `activate.startuptrading.com` | Activation app (Render) | `CNAME` → `startuptrading-whop-bridge.onrender.com` |

> Domain confirmed: `startuptrading.com`. Monthly plan confirmed: `plan_qSXeS0xoDapGU`.

---

## 1. Build the page (only after edits)

The ready-to-paste file is already committed at `sales-site/dist/ghl-embed.html`.
You only need to rebuild after changing `site.config.json` or anything in `src/`:

```bash
python sales-site/build.py
```

- `dist/index.html`: open in a browser to preview the full page.
- `dist/ghl-embed.html`: the block you paste into GHL.

Edit `site.config.json` for the checkout links, activation URL, support email,
YouTube, Terms and Privacy links. Blank optional links are removed from the page.

**Embedded checkout.** With `"embed_checkout": "true"` (the default), the pricing
section contains Whop's checkout itself, so buyers pay without leaving the page.
The Monthly/Annual toggle switches which plan's checkout is shown, and the
page's other Join buttons scroll down to it. After payment, Whop sends the buyer
to the thank-you page (`thank_you_url`, step 2b), which leads into activation. If the embed ever misbehaves
inside GHL, set `"embed_checkout": "false"` and rebuild: the page goes back to
buttons that open Whop's hosted checkout. Nothing else changes.

## 2. Create the page in GoHighLevel

1. **Sites → Websites** (or **Funnels**) → **New** → **From blank**. Name it
   "StartUpTrading", then add a page named "Join" with path **`/join`**.
   (Decided 2026-11-19: the existing home page at `/` stays; the membership page
   lives at `startuptrading.com/join`.)
2. In the builder, delete the default header and footer sections.
3. Add one **Section** → set it to **Full width**. In its settings, set
   padding and margin to **0** and the background to `#07090d`.
4. Inside it, add a **Row** (one column) with padding **0**, then drag in the
   **Code** element (named "Custom JS/HTML" in some accounts).
5. Open the Code element, paste the **entire contents** of
   `dist/ghl-embed.html`, and save. The builder canvas may show a placeholder.
   Use **Preview** to see the real page.
6. **Page settings:**
   - Background colour `#07090d`.
   - **SEO:** title *StartUpTrading: NinjaTrader indicators, trade room and masterclass*.
     Description *Jack's two NinjaTrader indicators, the private StartUpTrading
     Discord and his masterclass. $99/month, cancel anytime.* Add a 1200×630 social
     image (chart plus logo) once you have one.
   - **Tracking code:** paste the Google Analytics or Meta Pixel snippets into
     *Header tracking code* when you're ready. The page needs nothing else.
7. Save, then **Publish**.

Updating later means rebuilding, then replacing the Code element's contents
with the new `dist/ghl-embed.html`.

### 2b. Add the thank-you page (`/welcome`)

After paying in the embedded checkout, Whop sends buyers to
`https://startuptrading.com/welcome` (`thank_you_url` in `site.config.json`).
That page thanks them and walks them through activation, Discord and support.

1. In the same GHL site, **add a page** named "Welcome" with path **`/welcome`**.
2. Build it the same way as step 2: delete the header and footer, add a
   full-width section (padding 0, background `#07090d`), a one-column row, and
   a **Code** element. Paste the contents of **`dist/welcome-embed.html`**.
3. **Page settings:**
   - Background `#07090d`.
   - **SEO:** title *Welcome to StartUpTrading*. Turn on the option to hide
     the page from search engines (noindex) if your GHL plan offers it.
   - **Tracking code:** this is where purchases are counted. Paste your Meta
     Pixel `Purchase` event and/or Google Ads conversion snippet into the
     page's *Header tracking code*. The page also pushes
     `{event: 'sut_purchase'}` to `window.dataLayer` once per visit, for Google
     Tag Manager users.
4. Save and publish. Don't link to `/welcome` from the sales page.
5. **Whop → product / checkout link settings:** set the post-purchase redirect
   URL to `https://startuptrading.com/welcome` as well, so buyers who use the
   hosted-checkout fallback link land on the same page.

### 2c. Link the existing home page to `/join`

On the current home page (`/`) in GHL:
- Change **"Join the Discord"** (now `https://whop.com/startuptrading/`) to
  **`/join`**, so visitors see the membership offer and pay on your site.
- Optional: in the Tools section, add a line under the one-time products such as
  *"Or get both indicators plus the Discord and masterclass: membership from $99/month →"* linking to
  `/join`.
- In Render, set `CHECKOUT_URL=https://startuptrading.com/join#pricing`. It's the
  "rejoin" link in the access-ended email and the "Become a member" button
  on the activation app's no-membership page.

### 2e. Add the install guide (`/setup`)

`INDICATOR_SETUP_URL` in Render is `https://startuptrading.com/setup`, so the
"your tools are ready" email and the welcome page link here.

1. In the same GHL site, **add a page** named "Setup" with path **`/setup`**.
2. Build it like step 2, but paste **`dist/setup-embed.html`** into the Code element.
3. **SEO:** title *Install your StartUpTrading tools*. Turn on the option to hide
   the page from search engines (it's for members).
4. The download buttons come from `products.json` at the repo root, one per product,
   using its `download_url`. The files are proprietary and never committed (the repo is
   public): upload them to GoHighLevel Media and paste each link into `download_url`. To
   ship a new version, upload it, update `download_url` and `sha256`, then rebuild and
   paste again. Replace the two screenshot boxes when Jack has them.

### 2d. Add the free calculator page (`/futures-position-size-calculator`)

A free position-size calculator and prop-firm risk planner. It works for traders on
any platform, so it can rank in search and be shared in other communities. Every
button leads to the free indicator (tagged `utm_campaign=calculator`) or `/join`.

1. In the same GHL site, add a page named "Futures position size calculator"
   with path **`/futures-position-size-calculator`**.
2. Build it like step 2, but paste **`dist/calculator-embed.html`** into the Code element.
3. **SEO:** title *Futures Position Size Calculator & Prop-Firm Risk Planner (Free)*.
   Description *Free futures position size calculator for ES, NQ, MES, MNQ, CL, GC
   and more. Size from ATR or a fixed stop, and plan risk per trade for a prop-firm
   drawdown.* Leave it indexable.
4. Share links can preselect a contract: `…/futures-position-size-calculator?c=MES`.
5. Link it from the `/indicators` page and from `@trader`'s bio links.

## 3. Connect the domain in GoHighLevel

1. GHL **Settings → Domains → Add domain** → enter `startuptrading.com`.
   GHL offers to connect `www` too; accept.
2. GHL shows the exact DNS records to create. **Use the values GHL shows on
   that screen.** They differ between accounts and change over time. For
   reference, GHL has commonly used an `A` record for the root and a `CNAME`
   for `www` pointing at a GHL host such as `sites.ludicrous.cloud`.
3. Leave that screen open and do step 4 in Namecheap.
4. Back in GHL, click **Verify**. Then set **Default page / Website** for the
   domain to the StartUpTrading site so `/` serves the sales page. SSL is
   issued automatically after verification. It usually takes a few minutes,
   and can take up to 24 hours.

## 4. Add the records in Namecheap

1. Namecheap → **Domain List** → **Manage** (next to the domain) → **Advanced DNS**.
2. Under **Host Records**, **delete** the Namecheap defaults that would
   conflict:
   - `CNAME Record` · `www` → `parkingpage.namecheap.com`
   - `URL Redirect Record` · `@`
   - Any existing `A` / `AAAA` record on `@` or `www` that points elsewhere.
     Check first that it isn't serving something you still need.
3. **Add new record** for each line GHL showed you:
   - Type `A Record`, Host `@`, Value = the IP from GHL, TTL `Automatic`.
   - Type `CNAME Record`, Host `www`, Value = the host from GHL, TTL `Automatic`.
4. Add the activation subdomain for Render (see `ACTIVATE_DOMAIN.md` step 1):
   - Type `CNAME Record`, Host `activate`,
     Value `startuptrading-whop-bridge.onrender.com`, TTL `Automatic`.
5. Click the green ✓ to save each record.

Don't add both an `A` and a `CNAME` for the same host. Namecheap's
**Nameservers** must be "Namecheap BasicDNS" for these records to take effect.
If the domain uses custom nameservers, add the records wherever those point
instead.

## 5. Move the activation app to `activate.startuptrading.com`

This has its own step-by-step runbook, with a checker script:
**[`ACTIVATE_DOMAIN.md`](../ACTIVATE_DOMAIN.md)** at the repository root. It
covers the Namecheap `activate` record, the Render custom domain, the Whop
OAuth redirect URI, `PUBLIC_BASE_URL`, the Whop webhook URL and redirecting
the old address. It doesn't need GoHighLevel.

## 6. Launch check

- [ ] `https://startuptrading.com` and `https://www.startuptrading.com` load
      the page with a padlock.
- [ ] Every "Join" button opens the Whop checkout for the **monthly plan**
      (`plan_qSXeS0xoDapGU`) and shows $99/month.
- [ ] In Pricing, switching to **Annual** changes the button to the annual
      checkout (`plan_B84PWLvXemyFX`), which shows $495/year in Whop.
- [ ] The embedded checkout loads in the Pricing section for **Monthly**, and
      switching to **Annual** shows the annual checkout ($495/year).
- [ ] The nav, hero and final "Join" buttons scroll down to the checkout.
- [ ] Do one real purchase (then refund it in Whop): after paying, you land on
      `https://startuptrading.com/welcome`, "Activate my indicators" opens
      `https://activate.startuptrading.com/`, Discord access is granted, and the
      purchase shows up in your pixel / conversion tracking.
- [ ] Visiting `/?utm_source=test&a=yourcode`, a purchase shows that UTM source
      and affiliate in Whop's sales view.
- [ ] `https://activate.startuptrading.com` shows the activation page and
      "Sign in with Whop" works.
- [ ] Page checked on a phone: no sideways scrolling, buttons easy to tap.
- [ ] "Not ready yet?" links open `startuptrading.com/indicators` with
      `utm_campaign=not_ready` and the spot in `utm_content` (pricing, final,
      faq, exit). In GHL, those leads can be tagged and nurtured towards the
      membership.
- [ ] On desktop, moving the mouse to leave the tab (after 8 s on the page)
      shows the free-indicator popup once; it doesn't show again that week or
      after clicking Join. To turn it off, set `"exit_offer": "false"` and
      rebuild.
- [ ] **All dashed orange placeholder boxes replaced or removed**
      (see `COPY_REVIEW.md`).
