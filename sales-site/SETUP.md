# Sales site: GoHighLevel + Namecheap setup

> ⏸ **On hold:** GoHighLevel access hasn't been granted yet, so the GHL steps
> (2, 2b, 3, the `@`/`www` records in 4, and 6) are deferred to the end of the
> build. See "Deferred: waiting on GoHighLevel access" in `PLAN.md`. Steps 4.4
> and 5 (the `activate` subdomain for the activation app) don't need GHL and
> can be done now.

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
   "StartUpTrading", then add a page named "Home" with path `/`.
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
   - **SEO:** title *StartUpTrading: NinjaTrader indicators and private trade room*.
     Description *Jack's three NinjaTrader indicators and the private
     StartUpTrading Discord. $99/month, cancel anytime.* Add a 1200×630 social
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
4. Add the activation subdomain for Render:
   - Type `CNAME Record`, Host `activate`,
     Value `startuptrading-whop-bridge.onrender.com`, TTL `Automatic`.
5. Click the green ✓ to save each record.

Don't add both an `A` and a `CNAME` for the same host. Namecheap's
**Nameservers** must be "Namecheap BasicDNS" for these records to take effect.
If the domain uses custom nameservers, add the records wherever those point
instead.

## 5. Move the activation app to `activate.startuptrading.com`

1. **Render** → `startuptrading-whop-bridge` → **Settings → Custom Domains →
   Add** → `activate.startuptrading.com`. Render verifies the Namecheap
   `CNAME` from step 4 and issues SSL.
2. **Render → Environment:** set `PUBLIC_BASE_URL=https://activate.startuptrading.com`,
   and fill in the Phase 2 links (`SUPPORT_EMAIL`, `DISCORD_URL`,
   `INDICATOR_SETUP_URL`, `WHOP_HUB_URL`, and
   `CHECKOUT_URL=https://startuptrading.com/#pricing`).
3. **Whop → Developer:**
   - OAuth app: add `https://activate.startuptrading.com/oauth/callback` as an
     allowed redirect URI. Keep the old onrender.com one until the new one
     works.
   - Webhook: change the endpoint to `https://activate.startuptrading.com/webhooks/whop`.
4. **Whop → product settings:** set the post-purchase redirect / "Activate
   your indicators" link to `https://activate.startuptrading.com/`.

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
- [ ] **All dashed orange placeholder boxes replaced or removed**
      (see `COPY_REVIEW.md`).
