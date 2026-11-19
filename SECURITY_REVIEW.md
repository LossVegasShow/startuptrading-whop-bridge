# Security review: activation app (bridge)

Date: 2026-11-19 · Scope: everything in this repository that serves customers
or operators (`app.py`, `security.py`, `store.py`, `engine.py`,
`returning_member.py`, `lifecycle.py`, templates). The sales page
(`sales-site/`) is static and runs on GoHighLevel, so it's out of scope.

Each fix below has tests in `tests/test_security_hardening.py`,
`tests/test_returning_member.py` or `tests/test_store_rows.py`, and the suite
runs on SQLite and PostgreSQL in CI.

## Fixed

| # | Severity | Issue | Fix |
|---|---|---|---|
| 1 | **High** | **One-time codes could be guessed without limit.** A wrong code raised an error inside the database transaction, which rolled back the attempt counter, so the 5-try limit never applied. | The attempt is committed before the error is raised (membership and NinjaTrader codes). Merged in #12. |
| 2 | **High** | **Admin login had no brute-force protection.** `/admin` controls every customer record and licensing action. | After 10 failed logins from one client in 15 minutes, that client is locked out for 15 minutes. 50 failures from all clients together lock admin login for everyone (stops IP rotation). Client identity uses the last `X-Forwarded-For` entry, which Render's proxy sets and a client can't forge. |
| 3 | Medium | **No daily cap on verification codes.** With 5 tries per code, a new code every 60 s still allowed slow guessing. It also let a logged-in member send code emails to any inbox repeatedly. | At most 10 codes per customer per purpose per 24 hours. Friendly "Too many codes today" message. |
| 4 | Medium | **Invite links were used up by email security scanners.** Opening `/activate/<token>` consumed the one-time invite. Outlook Safe Links and Gmail fetch links automatically, so customers saw "expired". | Opening the link shows a confirm page. The invite is used only when the person clicks **Continue** (POST). |
| 5 | Medium | **Admin purchaser-intake page crashed on PostgreSQL** (`fetchone()[0]` on a dict row). | Postgres rows now support access by name and by position, like SQLite. Merged in #13. |
| 6 | Low | **Unbounded growth of sign-in records.** Anyone could create OAuth state rows by visiting `/oauth/login`, and expired rows were never deleted. | Expired OAuth state, sessions and old invites are purged on each sign-in and by the background worker. |
| 7 | Low | **Non-ASCII admin password attempts caused a 500** (`hmac.compare_digest` on non-ASCII text). | Compared as bytes; returns a normal 401. |
| 8 | Low | No HSTS header. | `Strict-Transport-Security: max-age=31536000` on HTTPS deployments (this host only, not subdomains), plus a restrictive `Permissions-Policy`. |
| 9 | Low | The webhook endpoint read the whole body before checking its size. | Rejects a declared `Content-Length` over 256 KB before reading. |

## Checked and fine

- **Whop webhooks:** HMAC-SHA256 signature compared in constant time;
  timestamps older than 5 minutes rejected; replays rejected by unique event
  ID; events are stored and processed from a fresh Whop lookup, never trusted
  from the payload.
- **Whop sign-in (OAuth):** PKCE, single-use 10-minute state, nonce check;
  identity comes from Whop's `userinfo` with the exchanged access token, not
  from anything the browser sends; `email_verified` is respected.
- **Sessions:** random 36-byte tokens stored only as SHA-256 hashes; cookies are
  `HttpOnly`, `Secure` (outside local dev) and `SameSite=Lax`.
- **CSRF:** customer forms carry a token tied to the session; admin
  POSTs require a matching `Origin`/`Referer` plus HTTP Basic auth.
- **SQL injection:** every query is parameterised. The PostgreSQL translation
  only rewrites the app's own fixed SQL.
- **XSS:** Jinja auto-escaping is on; the Content-Security-Policy allows no
  inline scripts or styles; emails escape user content.
- **Licensing safety:** writes need `LICENSE_WRITES_ENABLED` plus an exact
  membership + verified-email allowlist match. A Whop outage or incomplete
  response never revokes. The returning-member transfer only works for the
  same Whop user after Whop confirms the old membership ended.
- **Clickjacking:** `X-Frame-Options: DENY` and `frame-ancestors 'none'`.

## Recommendations (operator actions, no code needed)

1. **`ADMIN_PASSWORD`:** use a random password of at least 20 characters,
   stored in a password manager. It also keys the one-time-code hashes, so
   changing it invalidates codes already sent (members just request a new one).
2. **Turn on two-factor authentication** on every account that controls the
   system: Whop, Render, GitHub, Namecheap, Resend, and GoHighLevel when access
   arrives.
3. **Limit Render and Whop dashboard access** to the people who need it.
   Environment variables there are the keys to licensing.
4. **Paid PostgreSQL with backups,** and a test restore once (already in
   `PLAN.md`).
5. **Later:** the admin panel uses one shared password. If more people need
   admin access, move to individual logins (for example Whop OAuth with an
   allowlist, as the admin preview already does) so actions are attributable.
