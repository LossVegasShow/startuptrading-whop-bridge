# StartUpTrading Admin Preview — GitHub/Render update

This update keeps the existing `/oauth/login` paid-customer path intact. A separate `/admin-test/login` starts Whop OAuth and allows **only** the exact `user_...` configured as `ADMIN_TEST_WHOP_USER_ID`. It expires after one hour and cannot initiate licensing, issue invitation links, create membership records, or grant paid entitlements.

## Configure in Render → service → Environment

- `ADMIN_TEST_ENABLED=true`
- **Preferred simple setup:** `ADMIN_TEST_WHOP_EMAIL=your-verified-whop-login-email@example.com`
- **Alternative:** `ADMIN_TEST_WHOP_USER_ID=user_...` (your **Whop user ID**, not business ID or app ID).
- Configure *one* allowlist method. Email allowlisting works only if Whop userinfo explicitly reports `email_verified=true`.
- Keep `LICENSE_WRITES_ENABLED=false`.
- Keep your existing `PUBLIC_BASE_URL`, `WHOP_CLIENT_ID`, `WHOP_CLIENT_SECRET`, and `WHOP_API_KEY` settings unchanged.
- Optional: `ALLOWED_TEST_EMAIL` to restrict preview email entry to your own NinjaTrader test email.

If using the user-ID option, find it through your own Whop account details or an authenticated Whop userinfo response. Do **not** guess IDs or share access tokens.

After redeploy, visit `/` and choose **Authorized admin preview**. Sign in with your allowlisted Whop account. You should reach `/admin-test`, which previews both funnels without needing a paid Whop membership.

The admin preview is deliberately **not a real email verification or license activation test**. To test actual licensing you still need a properly authorized test membership and the existing stringent test-account allowlist. No paid subscriber is affected by this admin preview.

Disable after testing by setting `ADMIN_TEST_ENABLED=false` and redeploying. Free Render instances have ephemeral SQLite; admin preview sessions may disappear after restarts. Never store actual customer records there.
