# Move the activation app to `activate.startuptrading.com`

> ⏸ **On hold:** waiting on DNS (Namecheap) access. This runbook is group A of
> the **"Waiting on access"** reminder at the top of `PLAN.md`. Until then the
> app keeps running at `https://startuptrading-whop-bridge.onrender.com`;
> nothing needs to change.

The activation app (Render service `startuptrading-whop-bridge`) currently
answers at `startuptrading-whop-bridge.onrender.com`. This moves it to
**`https://activate.startuptrading.com`**, a trustworthy address to put in Whop,
emails and the sales site.

None of this needs GoHighLevel. It takes about 20 minutes plus DNS and
certificate wait time. **Do the steps in order.** Doing step 4 before step 3
breaks "Sign in with Whop" until step 3 is done.

After each step you can run the read-only checker from any computer with
Python. It tells you exactly what's still missing:

```bash
python scripts/check_activate_domain.py
```

---

## Step 1: Namecheap: add the DNS record

1. Namecheap → **Domain List** → **Manage** next to `startuptrading.com` →
   **Advanced DNS**.
2. **Add New Record**:
   - Type: **CNAME Record**
   - Host: **`activate`**
   - Value: **`startuptrading-whop-bridge.onrender.com`**
   - TTL: **Automatic**
3. Click the green ✓ to save.
4. Make sure there's no other record (A, AAAA or URL redirect) on the host
   `activate`.

Nameservers must be **Namecheap BasicDNS** for this to take effect.

**Check:** the script's first line should say `PASS DNS: domain resolves`.
This usually takes 5–30 minutes.

## Step 2: Render: add the custom domain

1. Render dashboard → **startuptrading-whop-bridge** → **Settings** →
   **Custom Domains** → **Add Custom Domain** → `activate.startuptrading.com`.
2. Render checks the CNAME from step 1 and issues an HTTPS certificate. Wait
   until the domain shows **Verified** and **Certificate Issued**.

**Check:** `PASS HTTPS: /health reachable on the new domain`. The next line
still FAILs until step 4; that's expected.

## Step 3: Whop: allow the new sign-in address (before step 4)

1. Whop → **Developer** → your StartUpTrading OAuth app → **Redirect URIs**.
2. **Add** `https://activate.startuptrading.com/oauth/callback`.
   **Keep** the existing `https://startuptrading-whop-bridge.onrender.com/oauth/callback`
   for now, so nothing breaks mid-switch.
3. Save.

## Step 4: Render: point the app at the new address

1. Render → **startuptrading-whop-bridge** → **Environment**.
2. Set `PUBLIC_BASE_URL` = **`https://activate.startuptrading.com`**
   (no trailing slash). Leave `CANONICAL_REDIRECT` unset for now.
3. Save. Render redeploys automatically.

**Check:** these should now PASS:
- `Render: PUBLIC_BASE_URL points at the new domain`
- `Whop sign-in sends users back to the new domain`
- `Activation page loads on the new domain`

Then open `https://activate.startuptrading.com` in a browser and click
**Sign in with Whop** once to confirm it comes back to the activation page.

## Step 5: Whop: move the webhook

1. Whop → **Developer** → **Webhooks** → edit the
   `StartupTrading-NinjaTrader-Licensing` endpoint.
2. Change the URL to **`https://activate.startuptrading.com/webhooks/whop`**.
   Keep the same signing secret, so `WHOP_WEBHOOK_SECRET` doesn't change.
3. Save, then use Whop's **send test event** if offered. In the app's
   `/admin` dashboard, the event should appear under webhook events.

The old address keeps accepting webhooks too (webhooks are never redirected),
so no events are lost during the switch.

## Step 6: Update links that point at the old address

- Whop member content / navigation: the **"Activate your indicators"** link →
  `https://activate.startuptrading.com/`.
- Any saved bookmarks, docs or support macros that use the `onrender.com` URL.
- The sales site already uses the new address (`sales-site/site.config.json`).

## Step 7 (optional): move visitors off the old address

Once steps 1–6 work, set **`CANONICAL_REDIRECT=true`** in Render → Environment.
Anyone opening a page on `startuptrading-whop-bridge.onrender.com` is then sent
to the same page on `activate.startuptrading.com`. Webhooks, `/health` and the
sign-in callback are never redirected, and form submissions aren't either. To
undo, delete the variable.

**Check:** `Old address: visitors are redirected to the new domain`.

## Step 8 (a week later): tidy up

When nothing has used the old address for a while, remove the old
`…onrender.com/oauth/callback` redirect URI from the Whop OAuth app.
