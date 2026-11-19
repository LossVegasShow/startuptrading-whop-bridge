"""Needs-attention panel, alerts, and member lifecycle emails."""
import asyncio
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import alerts
import app as web
import attention
import lifecycle_emails
from clients import IntegrationError
from config import BUSINESS_ID, INDICATORS, PLANS, PRODUCT_ID, Config
from engine import Engine
from store import connect

NOW = int(time.time())


@pytest.fixture
def cfg(tmp_path):
    return Config(db=str(tmp_path / 'a.sqlite'), database_url='', require_database_url=False,
                  public_base_url='https://activate.example.com', resend_api_key='re_test', resend_from='a@b.co',
                  checkout_url='https://startuptrading.com/#pricing', support_email='help@example.com')


def add_customer(db, mid, status='eligible', verified=0, nt=None, updated=NOW, user=None):
    db.execute('INSERT INTO customers(membership_id,whop_user_id,buyer_email,buyer_email_verified,nt_email,verified,status,'
               'paid_through,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',
               (mid, user or f'user_{mid}', f'{mid}@buyer.example', 1, nt, verified, status, '2026-12-19T00:00:00Z', updated))
    return db.execute('SELECT id FROM customers WHERE membership_id=?', (mid,)).fetchone()['id']


def keys(cfg):
    with connect(cfg) as db:
        return {i['key'] for i in attention.find_issues(db, cfg)}


# --- Needs attention ------------------------------------------------------------

def test_all_clear_on_a_healthy_database(cfg):
    with connect(cfg) as db:
        add_customer(db, 'mem_ok', verified=1, nt='ok@nt.example')
    assert keys(cfg) == set()


def test_unrevoked_licenses_are_high_priority(cfg):
    with connect(cfg) as db:
        cid = add_customer(db, 'mem_gone', status='ineligible', verified=1, nt='g@nt.example')
        db.execute("INSERT INTO licenses(customer_id,product_id,license_id,expiration,state,updated_at) VALUES(?,?,?,?,?,?)",
                   (cid, next(iter(INDICATORS)), 1, '2030-01-01T00:00:00Z', 'created', NOW))
        issues = attention.find_issues(db, cfg)
    assert issues[0]['key'] == f'revoke:{cid}' and issues[0]['severity'] == 'high'
    assert issues[0]['link'] == f'/admin/lifecycle/{cid}'


def test_failing_sync_shows_until_a_later_success(cfg):
    with connect(cfg) as db:
        cid = add_customer(db, 'mem_sync', verified=1, nt='s@nt.example')
        db.execute("INSERT INTO audit(at,customer_id,action,details) VALUES(?,?,'sync_error','2067: HTTP 500')", (NOW - 60, cid))
    assert f'sync:{cid}' in keys(cfg)
    with connect(cfg) as db:
        db.execute("INSERT INTO audit(at,customer_id,action,details) VALUES(?,?,'ninjatrader_renewed','2067/1')", (NOW, cid))
    assert f'sync:{cid}' not in keys(cfg)


def test_allowlisted_member_missing_licenses(cfg):
    cfg.license_writes, cfg.allowed_test_membership, cfg.allowed_test_email = True, 'mem_lic', 'l@nt.example'
    with connect(cfg) as db:
        cid = add_customer(db, 'mem_lic', verified=1, nt='l@nt.example', updated=NOW - 3600)
        add_customer(db, 'mem_observe', verified=1, nt='o@nt.example', updated=NOW - 3600)   # not on allowlist
    assert keys(cfg) == {f'licensing:{cid}'}


def test_webhook_problems_and_stalled_worker(cfg):
    with connect(cfg) as db:
        db.execute("INSERT INTO webhook_events(webhook_id,event_type,object_id,received_at,state,last_error) VALUES('w1','payment.succeeded','pay_1',?,'needs_mapping',NULL)", (NOW,))
        db.execute("INSERT INTO webhook_events(webhook_id,event_type,object_id,received_at,state,last_error) VALUES('w2','membership.updated','mem_x',?,'retry','Whop 503')", (NOW,))
        db.execute("INSERT INTO webhook_events(webhook_id,event_type,object_id,received_at,state) VALUES('w3','membership.activated','mem_y',?,'queued')", (NOW - 7200,))
    assert {'webhook:w1', 'webhook:w2', 'worker:stalled'} <= keys(cfg)


def test_failing_email_and_crm(cfg):
    with connect(cfg) as db:
        cid = add_customer(db, 'mem_mail', verified=1, nt='m@nt.example')
        db.execute("INSERT INTO message_outbox(customer_id,kind,target_email,status,attempts,last_error,updated_at) VALUES(?,'activation','m@nt.example','retry',3,'Resend HTTP 422',?)", (cid, NOW))
        db.execute("INSERT INTO crm_sync(customer_id,status,attempts,updated_at) VALUES(?,'retry',4,?)", (cid, NOW))
    assert {f'email:{cid}:activation', f'crm:{cid}'} <= keys(cfg)


def test_admin_attention_page_and_banner(cfg, monkeypatch):
    monkeypatch.setattr(web, 'cfg', cfg)
    cfg.admin_password = 'pw-for-attention-tests'
    with connect(cfg) as db:
        cid = add_customer(db, 'mem_page', status='ineligible', verified=1, nt='p@nt.example')
        db.execute("INSERT INTO licenses(customer_id,product_id,license_id,expiration,state,updated_at) VALUES(?,?,?,?,?,?)",
                   (cid, next(iter(INDICATORS)), 1, '2030-01-01T00:00:00Z', 'renewed', NOW))
    with TestClient(web.app) as c:
        assert c.get('/admin/attention').status_code == 401
        page = c.get('/admin/attention', auth=('admin', 'pw-for-attention-tests'))
        assert page.status_code == 200 and 'Access ended but licenses not revoked' in page.text
        assert f'/admin/lifecycle/{cid}' in page.text and 'ALERT_WEBHOOK_URL' in page.text
        dash = c.get('/admin', auth=('admin', 'pw-for-attention-tests'))
        assert 'attention-banner high' in dash.text and '1 item needs attention' in dash.text


# --- Alerts --------------------------------------------------------------------

def test_alerts_once_then_daily_then_forgotten(cfg):
    cfg.alert_webhook_url = 'https://discord.com/api/webhooks/1/abc'
    sent = []

    async def post(url, body):
        sent.append(body)
        return True

    issue = attention._issue('revoke:9', 'high', 'Access ended but licenses not revoked', 'mem_9: 3 license(s)', 9)
    run = lambda issues, now: asyncio.run(alerts.notify(cfg, lambda: connect(cfg), issues, now=now, post=post))
    assert run([issue], NOW) == 'sent' and 'content' in sent[0] and 'mem_9' in sent[0]['content']
    assert run([issue], NOW + 3600) == 'nothing_new'                     # no repeat within a day
    assert run([issue], NOW + 25 * 3600) == 'sent'                       # daily reminder
    assert run([], NOW + 26 * 3600) == 'nothing_new'                     # resolved → forgotten
    assert run([issue], NOW + 27 * 3600) == 'sent'                       # comes back → alerts again
    assert all('@' not in b['content'] for b in sent)                    # never emails


def test_alert_formats_and_failures(cfg):
    assert alerts.payload('https://hooks.slack.com/services/x', 'hi') == {'text': 'hi'}
    assert alerts.payload('https://discord.com/api/webhooks/1/a', 'hi') == {'content': 'hi'}
    assert not alerts.valid_url('http://insecure.example/hook') and not alerts.valid_url('')
    assert asyncio.run(alerts.notify(cfg, lambda: connect(cfg), [])) == 'not_configured'
    cfg.alert_webhook_url = 'https://hooks.slack.com/services/x'

    async def down(url, body):
        raise ConnectionError('slack down')
    issue = attention._issue('k', 'low', 't', 'd')
    assert asyncio.run(alerts.notify(cfg, lambda: connect(cfg), [issue], post=down)) == 'failed'
    with connect(cfg) as db:      # not marked sent, so it retries next cycle
        assert db.execute('SELECT COUNT(*) AS n FROM alert_log').fetchone()['n'] == 0


# --- Lifecycle emails ------------------------------------------------------------

class Outbox:
    def __init__(self):
        self.sent = []

    async def __call__(self, body, headers):
        self.sent.append((body, headers))
        return f'msg_{len(self.sent)}'


def outbox(cfg, cid):
    with connect(cfg) as db:
        return {r['kind']: dict(r) for r in db.execute('SELECT * FROM message_outbox WHERE customer_id=?', (cid,))}


def due_now(cfg, cid, kind):
    with connect(cfg) as db:
        db.execute('UPDATE message_outbox SET next_attempt_at=0 WHERE customer_id=? AND kind=?', (cid, kind))


def test_activation_reminders_at_24h_and_72h(cfg):
    with connect(cfg) as db:
        cid = add_customer(db, 'mem_new')
        add_customer(db, 'mem_done', verified=1, nt='d@nt.example')
        add_customer(db, 'mem_lapsed', status='ineligible')
        lifecycle_emails.schedule_reminders(db, now=NOW)
        lifecycle_emails.schedule_reminders(db, now=NOW + 600)       # idempotent
    box = outbox(cfg, cid)
    assert box['activation_reminder_1']['next_attempt_at'] == NOW + 24 * 3600
    assert box['activation_reminder_2']['next_attempt_at'] == NOW + 72 * 3600
    assert box['activation_reminder_1']['target_email'] == 'mem_new@buyer.example'
    with connect(cfg) as db:
        assert db.execute("SELECT COUNT(*) AS n FROM message_outbox WHERE kind LIKE 'activation_reminder%'").fetchone()['n'] == 2
    post = Outbox()
    assert asyncio.run(lifecycle_emails.send(cfg, cid, 'activation_reminder_1', post=post)) == 'not_due'
    due_now(cfg, cid, 'activation_reminder_1')
    assert asyncio.run(lifecycle_emails.send(cfg, cid, 'activation_reminder_1', post=post)) == 'sent'
    body, headers = post.sent[0]
    assert body['to'] == ['mem_new@buyer.example'] and 'waiting' in body['subject']
    assert 'https://activate.example.com/' in body['text'] and headers['Idempotency-Key'] == f'sut-activation_reminder_1-{cid}-v1'
    assert asyncio.run(lifecycle_emails.send(cfg, cid, 'activation_reminder_1', post=post)) == 'not_due'   # once only


def test_reminder_dropped_once_member_activates(cfg):
    with connect(cfg) as db:
        cid = add_customer(db, 'mem_act')
        lifecycle_emails.schedule_reminders(db, now=NOW)
        db.execute('UPDATE customers SET verified=1,nt_email=? WHERE id=?', ('a@nt.example', cid))
    due_now(cfg, cid, 'activation_reminder_1')
    post = Outbox()
    assert asyncio.run(lifecycle_emails.send(cfg, cid, 'activation_reminder_1', post=post)) == 'cancelled'
    assert post.sent == [] and outbox(cfg, cid)['activation_reminder_1']['status'] == 'cancelled'


class FakeWhop:
    def __init__(self):
        self.status, self.cancel = 'active', False

    async def membership(self, mid):
        return {'id': mid, 'account': {'id': BUSINESS_ID}, 'user_id': f'user_{mid}', 'product_id': PRODUCT_ID,
                'variant_id': next(iter(PLANS)), 'status': self.status, 'cancel_at_period_end': self.cancel,
                'current_period_end': (datetime.now(timezone.utc) + timedelta(days=12)).replace(microsecond=0).isoformat()}


def test_cancel_then_uncancel_then_expire_emails(cfg):
    with connect(cfg) as db:
        cid = add_customer(db, 'mem_life', verified=1, nt='life@nt.example')
    eng = Engine(cfg)
    eng.whop = FakeWhop()
    rec = lambda: asyncio.run(eng.reconcile(cid))
    rec()
    assert outbox(cfg, cid) == {}                                        # active: nothing to say

    eng.whop.status, eng.whop.cancel = 'canceling', True                 # member cancels
    rec()
    assert outbox(cfg, cid)['access_ending']['status'] == 'pending'
    post = Outbox()
    assert asyncio.run(lifecycle_emails.send(cfg, cid, 'access_ending', post=post)) == 'sent'
    assert 'ends on' in post.sent[0][0]['subject'] and post.sent[0][0]['to'] == ['mem_life@buyer.example']

    eng.whop.status = 'expired'                                          # period runs out
    rec()
    assert outbox(cfg, cid)['access_ended']['status'] == 'pending'
    assert asyncio.run(lifecycle_emails.send(cfg, cid, 'access_ended', post=post)) == 'sent'
    assert 'switched off' in post.sent[1][0]['subject'] and 'https://startuptrading.com/#pricing' in post.sent[1][0]['text']


def test_uncancel_drops_the_ending_email(cfg):
    with connect(cfg) as db:
        cid = add_customer(db, 'mem_undo', verified=1, nt='u@nt.example')
    eng = Engine(cfg)
    eng.whop = FakeWhop()
    eng.whop.status, eng.whop.cancel = 'canceling', True
    asyncio.run(eng.reconcile(cid))
    eng.whop.status, eng.whop.cancel = 'active', False                   # changed their mind
    asyncio.run(eng.reconcile(cid))
    assert outbox(cfg, cid)['access_ending']['status'] == 'cancelled'


def test_ended_email_only_for_members_who_had_activated(cfg):
    with connect(cfg) as db:
        cid = add_customer(db, 'mem_never')                               # paid, never activated, then lapsed
    eng = Engine(cfg)
    eng.whop = FakeWhop()
    eng.whop.status = 'expired'
    asyncio.run(eng.reconcile(cid))
    assert 'access_ended' not in outbox(cfg, cid)


def test_not_configured_without_resend(cfg):
    cfg.resend_api_key = ''
    assert asyncio.run(lifecycle_emails.send(cfg, 1, 'access_ended')) == 'not_configured'


def test_failed_send_retries_with_backoff(cfg):
    with connect(cfg) as db:
        cid = add_customer(db, 'mem_retry')
        lifecycle_emails.schedule_reminders(db, now=NOW)
    due_now(cfg, cid, 'activation_reminder_1')

    async def broken(body, headers):
        raise RuntimeError('Resend HTTP 500')
    assert asyncio.run(lifecycle_emails.send(cfg, cid, 'activation_reminder_1', post=broken)) == 'retry'
    row = outbox(cfg, cid)['activation_reminder_1']
    assert row['status'] == 'retry' and row['attempts'] == 1 and row['next_attempt_at'] > int(time.time())
