# v7.2 — Safe account linking / member onboarding

## Deploy
Upload the patch into the existing GitHub repo, preserving paths, and let Render deploy.
**No new environment variables. Keep `LICENSE_WRITES_ENABLED=false` until a real end-to-end allowlisted test.** PostgreSQL migration adds `buyer_email_verified` automatically.

## Behavior
- Whop OAuth userinfo with verified email + eligible membership permanently records verified buyer identity; avoids redundant purchase-email step.
- User provides only NinjaTrader email (never password), receives OTP and links it to the Whop membership.
- Once verified, user cannot change NinjaTrader email self-service. If license records exist, even unverified users cannot overwrite the link. Support-managed change requires manually reviewing/revoking/migrating licenses first.
- A verified NinjaTrader email cannot be linked to two customers. Existing installation conflicts should be resolved manually before enabling the unique index.
- New account route uses optional `NINJATRADER_REFERRAL_URL` only when approved; otherwise official signup link.
- OAuth operates as redirect and return in the same browser tab, not a NinjaTrader password login.

## Limitations
- OTP proves control of the email inbox, NOT ownership of an existing NinjaTrader account. Independent ownership verification requires an authorized NinjaTrader mechanism not present in this bridge.
- Live Whop/NinjaTrader membership-to-license end-to-end call remains untested; all write allowlists remain required.
- Preexisting records with a lost/ambiguous buyer verification status may require buyer-email OTP one time following migration.
- Do not let a customer change NinjaTrader email without support-managed license review.
