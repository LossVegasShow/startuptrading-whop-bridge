# v7.3 read-only integration readiness

Apply the patch at the repository root and deploy to Render.
Open `https://startuptrading-whop-bridge.onrender.com/admin-test/login` using the allowlisted Whop admin, then open `https://startuptrading-whop-bridge.onrender.com/admin-test/diagnostics`.

This checks the *deployed* PostgreSQL schema, Whop membership API read access, and NinjaTrader vendor authentication plus access to product IDs 2067, 2071 and 2205. It also reports whether the webhook signing secret is configured; **it cannot verify webhook delivery**.

Keep `LICENSE_WRITES_ENABLED=false`. These diagnostics do not call license write endpoints, create customers, send email or expose credentials. Results are returned only to an authenticated admin-preview OAuth session; `/health` remains publicly safe and unchanged.

A pass still does not validate a real paid-member-to-license journey. Do not enable customer-wide write access based on this test.
