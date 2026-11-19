import os
from pathlib import Path
from dataclasses import dataclass

BUSINESS_ID = 'biz_a1txPozoELC3Yc'
PRODUCT_ID = 'prod_Nr8ggb93WCyC1'
PLANS = {
    'plan_qSXeS0xoDapGU': 'Monthly · $99',
    'plan_B84PWLvXemyFX': 'Annual · $495'
}
INDICATORS = {2067:'ATR Order Automation', 2071:'Trend Scanner & Market Selector', 2205:'TSMS & Fibs'}
EVENTS = {'membership.activated','membership.deactivated','membership.cancel_at_period_end_changed','membership.updated','payment.succeeded','payment.failed'}

@dataclass
class Config:
    database_url: str = os.getenv('DATABASE_URL','')
    require_database_url: bool = os.getenv('REQUIRE_PERSISTENT_DB','false').lower()=='true'
    resend_api_key: str = os.getenv('RESEND_API_KEY','')
    resend_from: str = os.getenv('RESEND_FROM','')
    db: str = os.getenv('DATABASE_PATH', str(Path(__file__).resolve().parent/'data'/'startuptrading.db'))
    whop_api_key: str = os.getenv('WHOP_API_KEY','')
    whop_client_id: str = os.getenv('WHOP_CLIENT_ID','')
    whop_client_secret: str = os.getenv('WHOP_CLIENT_SECRET','')
    whop_webhook_secret: str = os.getenv('WHOP_WEBHOOK_SECRET','')
    whop_api_version: str = os.getenv('WHOP_API_VERSION','2026-11-17-3')
    nt_username: str = os.getenv('NT_USERNAME','')
    nt_password: str = os.getenv('NT_PASSWORD','')
    nt_app_id: str = os.getenv('NT_APP_ID','StartUpTradeLicensing')
    nt_app_version: str = os.getenv('NT_APP_VERSION','1.0')
    nt_cid: str = os.getenv('NT_CID','')
    nt_sec: str = os.getenv('NT_SEC','')
    # Vendor token endpoint. Confirm with the NinjaTrader vendor contact whether
    # production licensing should use the demo or live Tradovate auth host.
    nt_auth_url: str = os.getenv('NT_AUTH_URL','https://demo.tradovateapi.com/v1/auth/accesstokenrequest')
    admin_password: str = os.getenv('ADMIN_PASSWORD','')
    allowed_test_email: str = os.getenv('ALLOWED_TEST_EMAIL','').strip().lower()
    allowed_test_membership: str = os.getenv('ALLOWED_TEST_MEMBERSHIP','')
    license_writes: bool = os.getenv('LICENSE_WRITES_ENABLED','false').lower()=='true'
    # Extra membership/email pairs allowed to receive real license writes, for the
    # staged rollout after the single-account test: "mem_a:a@x.com,mem_b:b@y.com".
    # Both the Whop membership AND the verified NinjaTrader email must match.
    license_write_allowlist: str = os.getenv('LICENSE_WRITE_ALLOWLIST','')
    public_base_url: str = os.getenv('PUBLIC_BASE_URL','http://127.0.0.1:8000').rstrip('/')
    # Send visitors on any other hostname (e.g. the old *.onrender.com address)
    # to PUBLIC_BASE_URL. Turn on only after the custom domain works over HTTPS.
    canonical_redirect: bool = os.getenv('CANONICAL_REDIRECT','false').lower()=='true'
    affiliate_url: str = os.getenv('NINJATRADER_REFERRAL_URL','')
    smtp_host: str = os.getenv('SMTP_HOST','')
    smtp_port: int = int(os.getenv('SMTP_PORT','587'))
    smtp_username: str = os.getenv('SMTP_USERNAME','')
    smtp_password: str = os.getenv('SMTP_PASSWORD','')
    smtp_from: str = os.getenv('SMTP_FROM','')
    admin_test_enabled: bool = os.getenv('ADMIN_TEST_ENABLED','false').lower()=='true'
    admin_test_user_id: str = os.getenv('ADMIN_TEST_WHOP_USER_ID','').strip()
    admin_test_email: str = os.getenv('ADMIN_TEST_WHOP_EMAIL','').strip().lower()
    debug_otp: bool = os.getenv('LOCAL_DEMO_OTP','false').lower()=='true'
    poll_seconds: int = int(os.getenv('RECONCILE_INTERVAL_SECONDS','900'))
    run_reconciler: bool = os.getenv('RUN_RECONCILER','false').lower()=='true'

    ghl_api_key: str = os.getenv('GHL_API_KEY','')
    ghl_location_id: str = os.getenv('GHL_LOCATION_ID','')
    ghl_custom_fields_json: str = os.getenv('GHL_CUSTOM_FIELDS_JSON','')
    indicator_setup_url: str = os.getenv('INDICATOR_SETUP_URL','')
    support_email: str = os.getenv('SUPPORT_EMAIL','')
    # Discord or Slack incoming-webhook URL for "needs attention" alerts.
    alert_webhook_url: str = os.getenv('ALERT_WEBHOOK_URL','')
    # Customer-facing links. Each is hidden from the UI when unset.
    discord_url: str = os.getenv('DISCORD_URL','')
    checkout_url: str = os.getenv('CHECKOUT_URL','')
    whop_hub_url: str = os.getenv('WHOP_HUB_URL','')

    def write_allowlist(self):
        """Set of (membership_id, casefolded email) pairs that may receive license writes."""
        pairs=set()
        if self.allowed_test_membership and self.allowed_test_email:
            pairs.add((self.allowed_test_membership.strip(),self.allowed_test_email.strip().casefold()))
        for item in self.license_write_allowlist.split(','):
            mem,sep,email=item.strip().partition(':')
            if sep and mem.strip().startswith('mem_') and '@' in email:
                pairs.add((mem.strip(),email.strip().casefold()))
        return pairs
