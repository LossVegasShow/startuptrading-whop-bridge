"""Returning members reclaim their NinjaTrader link; one-time codes really stop after 5 tries."""
import asyncio
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from fastapi.testclient import TestClient

import app as web
import lifecycle
from clients import IntegrationError
from config import BUSINESS_ID, INDICATORS, PLANS, PRODUCT_ID
from store import connect

USER, EMAIL = 'user_returning', 'trader@example.com'
OLD, NEW = 'mem_old', 'mem_new'
HTML = {'accept': 'text/html'}


class FakeWhop:
    def __init__(self):
        self.status = {OLD: 'expired', NEW: 'active'}
        self.owner = {OLD: USER, NEW: USER}
        self.down = False

    async def membership(self, mid):
        if self.down:
            raise IntegrationError('Whop HTTP 503')
        return {'id': mid, 'account': {'id': BUSINESS_ID}, 'user_id': self.owner[mid], 'product_id': PRODUCT_ID,
                'variant_id': next(iter(PLANS)), 'status': self.status[mid],
                'current_period_end': (datetime.now(timezone.utc) + timedelta(days=30)).replace(microsecond=0).isoformat()}


class FakeNinja:
    def __init__(self):
        past = (datetime.now(timezone.utc) - timedelta(days=3)).replace(microsecond=0).isoformat()
        self.rows = {pid: [{'id': 7000 + pid, 'email': EMAIL, 'expirationDateUTC': past}] for pid in INDICATORS}
        self.writes = []

    async def licenses(self, pid):
        return [dict(r) for r in self.rows[pid]]

    async def create(self, pid, email, end):
        self.writes.append(('create', pid))
        raise AssertionError('a returning member must reuse licenses, never create new ones')

    async def update(self, pid, lid, email, end):
        next(r for r in self.rows[pid] if r['id'] == lid)['expirationDateUTC'] = end
        self.writes.append(('update', pid))
        return lid


@pytest.fixture
def rig(tmp_path, monkeypatch):
    cfg = web.cfg
    for k, v in dict(database_url='', require_database_url=False, db=str(tmp_path / 'r.sqlite'),
                     admin_password='code-secret', license_writes=True, allowed_test_membership=NEW,
                     allowed_test_email=EMAIL, license_write_allowlist='', nt_username='u', nt_password='p',
                     nt_cid='c', nt_sec='s').items():
        monkeypatch.setattr(cfg, k, v)
    whop, nt = FakeWhop(), FakeNinja()
    monkeypatch.setattr(web.engine, 'whop', whop)
    monkeypatch.setattr(web.engine, 'nt', nt)
    now = int(time.time())
    with connect(cfg) as db:
        # Old record: expired membership that still holds the link and the license rows.
        db.execute("INSERT INTO customers(id,membership_id,whop_user_id,buyer_email,buyer_email_verified,nt_email,verified,status,updated_at) "
                   "VALUES(1,?,?,?,1,?,1,'ineligible',?)", (OLD, USER, 'buyer@example.com', EMAIL, now))
        for pid in INDICATORS:
            db.execute("INSERT INTO licenses(customer_id,product_id,license_id,expiration,state,updated_at) VALUES(1,?,?,?,?,?)",
                       (pid, 7000 + pid, nt.rows[pid][0]['expirationDateUTC'], 'expired', now))
        # New record: the same person's new purchase, signed in with Whop.
        db.execute("INSERT INTO customers(id,membership_id,whop_user_id,buyer_email,buyer_email_verified,verified,status,updated_at) "
                   "VALUES(2,?,?,?,1,0,'buyer_verified',?)", (NEW, USER, 'buyer@example.com', now))
        db.execute('INSERT INTO sessions(token_hash,customer_id,expires_at) VALUES(?,?,?)', (web.hash_token('n' * 40), 2, now + 3600))
    codes = []
    monkeypatch.setattr(web, 'deliver_code', lambda email, code: codes.append(code))
    client = TestClient(web.app, cookies={'sut_session': 'n' * 40})
    return cfg, whop, nt, codes, client, web.csrf('n' * 40)


def request_code(client, csrf, **kw):
    return client.post('/onboarding/nt-code', data={'csrf_token': csrf, 'nt_email': EMAIL, 'path': 'existing'},
                       follow_redirects=False, **kw)


def verify(client, csrf, code, **kw):
    return client.post('/onboarding/nt-verify', data={'csrf_token': csrf, 'code': code}, follow_redirects=False, **kw)


def rows(cfg, sql, *args):
    with connect(cfg) as db:
        return [dict(r) for r in db.execute(sql, args)]


def test_returning_member_gets_their_indicators_back(rig):
    cfg, whop, nt, codes, client, csrf = rig
    with client:
        assert request_code(client, csrf).status_code == 303
        r = verify(client, csrf, codes[-1])
    assert r.status_code == 303 and r.headers['location'] == '/onboarding?message=nt_verified'
    old, new = rows(cfg, 'SELECT * FROM customers ORDER BY id')
    assert old['verified'] == 0 and old['status'] == 'transferred'
    assert new['verified'] == 1 and new['nt_email'] == EMAIL
    assert {r['customer_id'] for r in rows(cfg, 'SELECT customer_id FROM licenses')} == {2}
    # Same NinjaTrader licenses extended (never new ones), and they now match Whop.
    assert nt.writes == [('update', pid) for pid in INDICATORS]
    snap = asyncio.run(lifecycle.snapshot(cfg, web.engine, 2))
    assert snap['overall'] == 'consistent'
    actions = {(a['customer_id'], a['action']) for a in rows(cfg, 'SELECT customer_id,action FROM audit')}
    assert (1, 'ninjatrader_link_transferred_out') in actions and (2, 'ninjatrader_link_transferred_in') in actions


def test_different_whop_user_is_still_refused(rig):
    cfg, whop, nt, codes, client, csrf = rig
    with connect(cfg) as db:
        db.execute("UPDATE customers SET whop_user_id='user_someone_else' WHERE id=1")
    with client:
        assert request_code(client, csrf).status_code == 409
    assert rows(cfg, 'SELECT verified FROM customers WHERE id=1')[0]['verified'] == 1 and nt.writes == []


def test_new_record_without_whop_identity_is_refused(rig):
    cfg, whop, nt, codes, client, csrf = rig
    with connect(cfg) as db:
        db.execute('UPDATE customers SET whop_user_id=NULL WHERE id=2')
    with client:
        assert request_code(client, csrf).status_code == 409


def test_old_membership_still_active_is_never_drained(rig):
    cfg, whop, nt, codes, client, csrf = rig
    whop.status[OLD] = 'active'
    with client:
        request_code(client, csrf)
        r = verify(client, csrf, codes[-1])
        assert r.status_code == 409
        page = verify(client, csrf, codes[-1], headers=HTML)
    assert page.headers['location'] == '/onboarding?error=nt_active_elsewhere'
    assert {r['customer_id'] for r in rows(cfg, 'SELECT customer_id FROM licenses')} == {1}
    assert rows(cfg, 'SELECT verified FROM customers WHERE id=1')[0]['verified'] == 1
    # The code was not used up, so it still works once the old membership ends.
    whop.status[OLD] = 'expired'
    with client:
        assert verify(client, csrf, codes[-1]).status_code == 303
    assert {r['customer_id'] for r in rows(cfg, 'SELECT customer_id FROM licenses')} == {2}


def test_whop_outage_moves_nothing(rig):
    cfg, whop, nt, codes, client, csrf = rig
    whop.down = True
    with client:
        request_code(client, csrf)
        assert verify(client, csrf, codes[-1]).status_code == 502
    assert {r['customer_id'] for r in rows(cfg, 'SELECT customer_id FROM licenses')} == {1}
    assert rows(cfg, 'SELECT attempts FROM codes')[0]['attempts'] == 0


def test_old_membership_changed_owner_is_refused(rig):
    cfg, whop, nt, codes, client, csrf = rig
    whop.owner[OLD] = 'user_someone_else'
    with client:
        request_code(client, csrf)
        assert verify(client, csrf, codes[-1]).status_code == 502
    assert {r['customer_id'] for r in rows(cfg, 'SELECT customer_id FROM licenses')} == {1}


def test_sync_in_progress_on_old_record_blocks_transfer(rig):
    cfg, whop, nt, codes, client, csrf = rig
    with client:
        request_code(client, csrf)
        assert web.engine.acquire(1, 'someone-else')
        try:
            assert verify(client, csrf, codes[-1]).status_code == 409
        finally:
            web.engine.release(1, 'someone-else')
        assert verify(client, csrf, codes[-1]).status_code == 303


def test_wrong_codes_count_and_lock_after_five(rig):
    cfg, whop, nt, codes, client, csrf = rig
    with client:
        request_code(client, csrf)
        wrong = '000000' if codes[-1] != '000000' else '111111'
        for _ in range(6):
            assert verify(client, csrf, wrong).status_code == 400
        assert rows(cfg, 'SELECT attempts FROM codes')[0]['attempts'] == 5
        assert verify(client, csrf, codes[-1]).status_code == 400     # locked: needs a new code
    assert rows(cfg, 'SELECT verified FROM customers WHERE id=2')[0]['verified'] == 0


def test_buyer_code_attempts_are_counted_too(rig):
    cfg, whop, nt, codes, client, csrf = rig
    with connect(cfg) as db:
        db.execute('UPDATE customers SET buyer_email_verified=0 WHERE id=2')
    with client:
        client.post('/onboarding/buyer-code', data={'csrf_token': csrf}, follow_redirects=False)
        wrong = '000000' if codes[-1] != '000000' else '111111'
        for _ in range(5):
            client.post('/onboarding/buyer-verify', data={'csrf_token': csrf, 'code': wrong}, follow_redirects=False)
        r = client.post('/onboarding/buyer-verify', data={'csrf_token': csrf, 'code': codes[-1]}, follow_redirects=False)
    assert r.status_code == 400
    assert rows(cfg, "SELECT attempts FROM codes WHERE purpose='buyer'")[0]['attempts'] == 5
