import asyncio, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from config import Config, INDICATORS
from store import connect, request_crm_sync, queue_activation_email
from customer_communications import build_contact, crm_enabled, email_enabled, activation_message, process_pending
from test_v7_lifecycle import setup

def test_crm_optional_and_state_is_durable(tmp_path):
    e,cfg=setup(tmp_path)
    assert not crm_enabled(cfg)
    with connect(cfg) as db:
        request_crm_sync(db,1)
        r=db.execute('SELECT revision,status FROM crm_sync WHERE customer_id=1').fetchone()
        assert r['revision']==1 and r['status']=='pending'
        request_crm_sync(db,1)
        assert db.execute('SELECT revision FROM crm_sync WHERE customer_id=1').fetchone()['revision']==1
    assert asyncio.run(process_pending(cfg))=={'crm_checked':0,'email_checked':0}
    with connect(cfg) as db:assert db.execute('SELECT status FROM crm_sync WHERE customer_id=1').fetchone()['status']=='pending'

def test_email_never_queued_in_observe_mode(tmp_path):
    e,cfg=setup(tmp_path);cfg.license_writes=False
    asyncio.run(e.reconcile(1))
    with connect(cfg) as db:
        assert db.execute('SELECT COUNT(*) FROM message_outbox').fetchone()[0]==0

def test_email_queued_once_only_after_three_licenses(tmp_path):
    e,cfg=setup(tmp_path)
    assert asyncio.run(e.reconcile(1))['writes']==len(INDICATORS)
    with connect(cfg) as db:
        row=db.execute('SELECT * FROM message_outbox').fetchone()
        assert row['status']=='pending' and row['target_email']=='test@example.com'
    assert asyncio.run(e.reconcile(1))['writes']==0
    with connect(cfg) as db:
        assert db.execute('SELECT COUNT(*) FROM message_outbox').fetchone()[0]==1
    assert not email_enabled(cfg)

def test_failed_license_not_treated_as_activation(tmp_path):
    e,cfg=setup(tmp_path)
    # A STILL-ACTIVE license the bridge didn't create that ends BEFORE the membership is
    # ambiguous (manual review), so activation must not be announced. (One that lasts at
    # least as long counts as owned separately, and an already-expired one is adopted;
    # see tests/test_owned_separately.py.)
    soon=(datetime.now(timezone.utc)+timedelta(days=1)).replace(microsecond=0).isoformat()
    e.nt.data[2067].append({'id':999,'email':'test@example.com','expirationDateUTC':soon})
    try:asyncio.run(e.reconcile(1))
    except Exception:pass
    with connect(cfg) as db:assert db.execute('SELECT COUNT(*) FROM message_outbox').fetchone()[0]==0

def test_crm_contact_payload_minimal_and_guide_required(tmp_path):
    e,cfg=setup(tmp_path)
    with connect(cfg) as db:c=dict(db.execute('SELECT * FROM customers WHERE id=1').fetchone())
    payload=build_contact(c,cfg)
    assert payload['email']=='buyer@example.com' and 'customFields' not in payload
    cfg.indicator_setup_url='https://example.com/startuptrading/install'
    cfg.resend_api_key='test';cfg.resend_from='test@example.com'
    assert email_enabled(cfg)
    body=activation_message(c,cfg)
    assert all(name in body for name in INDICATORS.values())
    assert 'https://example.com/startuptrading/install' in body
