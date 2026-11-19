import os
from pathlib import Path
from dataclasses import dataclass

BUSINESS_ID = 'biz_a1txPozoELC3Yc'
PRODUCT_ID = 'prod_Nr8ggb93WCyC1'
PLANS = {'plan_qSxeS0xoDapGU': 'Monthly · $99', 'plan_B84PWLvXemyFX': 'Annual · $495'}
INDICATORS = {2067:'ATR Order Automation', 2071:'Trend Scanner and Momentum Selector', 2205:'TSMS & Fibs'}
EVENTS = {'membership.activated','membership.deactivated','membership.cancel_at_period_end_changed','membership.updated','payment.succeeded','payment.failed'}

@dataclass
class Config:
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
    admin_password: str = os.getenv('ADMIN_PASSWORD','')
    allowed_test_email: str = os.getenv('ALLOWED_TEST_EMAIL','').strip().lower()
    allowed_test_membership: str = os.getenv('ALLOWED_TEST_MEMBERSHIP','')
    license_writes: bool = os.getenv('LICENSE_WRITES_ENABLED','false').lower()=='true'
    public_base_url: str = os.getenv('PUBLIC_BASE_URL','http://127.0.0.1:8000').rstrip('/')
    affiliate_url: str = os.getenv('NINJATRADER_REFERRAL_URL','')
    smtp_host: str = os.getenv('SMTP_HOST','')
    smtp_port: int = int(os.getenv('SMTP_PORT','587'))
    smtp_username: str = os.getenv('SMTP_USERNAME','')
    smtp_password: str = os.getenv('SMTP_PASSWORD','')
    smtp_from: str = os.getenv('SMTP_FROM','')
    debug_otp: bool = os.getenv('LOCAL_DEMO_OTP','false').lower()=='true'
    poll_seconds: int = int(os.getenv('RECONCILE_INTERVAL_SECONDS','900'))
