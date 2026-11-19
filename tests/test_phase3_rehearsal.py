"""Offline dress rehearsal of the Phase 3 live lifecycle test (LIFECYCLE_TEST.md).

Same steps as the live test, with fake Whop and NinjaTrader. After every step
the read-only snapshot must agree with what actually happened, so the snapshot
can be trusted as the pass/fail signal during the real run.
"""
import asyncio
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest

import lifecycle
from clients import IntegrationError
from config import BUSINESS_ID, INDICATORS, PLANS, PRODUCT_ID, Config
from engine import Engine
from store import connect

MEM, USER, EMAIL = 'mem_phase3', 'user_phase3', 'tester@example.com'


class FakeWhop:
    def __init__(self):
        self.status, self.days, self.down = 'active', 30, False

    async def membership(self, mid):
        if self.down:
            raise IntegrationError('Whop membership HTTP 503')
        return {'id': mid, 'account': {'id': BUSINESS_ID}, 'user_id': USER, 'product_id': PRODUCT_ID,
                'variant_id': next(iter(PLANS)), 'status': self.status,
                'cancel_at_period_end': self.status == 'canceling',
                'current_period_end': (datetime.now(timezone.utc) + timedelta(days=self.days)).replace(microsecond=0).isoformat()}


class FakeNinja:
    def __init__(self):
        self.rows = {pid: [] for pid in INDICATORS}
        self.writes, self.fail_on = [], set()

    async def licenses(self, pid):
        return [dict(r) for r in self.rows[pid]]

    async def create(self, pid, email, end):
        if pid in self.fail_on:
            raise IntegrationError('NinjaTrader POST HTTP 500')
        lid = 90000 + pid
        self.rows[pid].append({'id': lid, 'email': email, 'expirationDateUTC': end})
        self.writes.append(('create', pid))
        return lid

    async def update(self, pid, lid, email, end):
        next(r for r in self.rows[pid] if r['id'] == lid)['expirationDateUTC'] = end
        self.writes.append(('update', pid))
        return lid


@pytest.fixture
def rig(tmp_path):
    cfg = Config(db=str(tmp_path / 'p3.db'), database_url='', require_database_url=False,
                 license_writes=True, allowed_test_email=EMAIL, allowed_test_membership=MEM,
                 nt_username='u', nt_password='p', nt_cid='c', nt_sec='s')
    with connect(cfg) as db:
        db.execute('INSERT INTO customers(membership_id,whop_user_id,buyer_email,buyer_email_verified,nt_email,verified,status,updated_at) '
                   'VALUES(?,?,?,?,?,?,?,?)', (MEM, USER, 'buyer@example.com', 1, EMAIL, 1, 'pending', int(time.time())))
    eng = Engine(cfg)
    eng.whop, eng.nt = FakeWhop(), FakeNinja()
    return cfg, eng


def run(eng):
    return asyncio.run(eng.reconcile(1))


def snap(cfg, eng):
    return asyncio.run(lifecycle.snapshot(cfg, eng, 1))


def outbox(cfg):
    with connect(cfg) as db:
        return [dict(r) for r in db.execute("SELECT status FROM message_outbox WHERE kind='activation'")]


def test_before_activation_snapshot_flags_missing_licenses(rig):
    cfg, eng = rig
    s = snap(cfg, eng)
    assert s['whop']['entitled'] and s['write_gate']['allowed']
    assert s['overall'] == 'mismatch'
    assert all(p['detail'] == 'entitled, but no NinjaTrader license exists' for p in s['products'])


def test_full_lifecycle_matrix(rig):
    cfg, eng = rig

    # 1. Purchase + activation: three licenses, one success email queued.
    out = run(eng)
    assert out['writes'] == 3 and len(eng.nt.writes) == 3
    assert snap(cfg, eng)['overall'] == 'consistent'
    assert outbox(cfg) == [{'status': 'pending'}]

    # 2. Duplicate webhook / repeated activation: no new licenses, no second email.
    assert run(eng)['writes'] == 0 and len(eng.nt.writes) == 3
    assert len(outbox(cfg)) == 1

    # 3. Renewal: paid-through moves forward, licenses extended to match.
    eng.whop.days = 60
    assert snap(cfg, eng)['overall'] == 'mismatch'      # snapshot notices before reconcile
    assert run(eng)['writes'] == 3
    assert snap(cfg, eng)['overall'] == 'consistent'

    # 4. Cancel at period end: still paid up, access kept, nothing written.
    eng.whop.status = 'canceling'
    assert run(eng)['writes'] == 0
    s = snap(cfg, eng)
    assert s['whop']['entitled'] and s['whop']['cancel_at_period_end'] and s['overall'] == 'consistent'

    # 5. Expiry: all three licenses end now.
    eng.whop.status = 'expired'
    s = snap(cfg, eng)
    assert s['overall'] == 'mismatch'
    assert all(p['detail'] == 'NOT entitled, but the NinjaTrader license is still active' for p in s['products'])
    assert run(eng)['writes'] == 3
    s = snap(cfg, eng)
    assert s['overall'] == 'consistent' and not s['whop']['entitled']
    assert all(p['detail'].startswith('no active license (expired') for p in s['products'])

    # 6. Restore the same membership (e.g. payment recovered): licenses come back.
    eng.whop.status, eng.whop.days = 'active', 30
    assert run(eng)['writes'] == 3
    assert snap(cfg, eng)['overall'] == 'consistent'
    with connect(cfg) as db:
        assert db.execute('SELECT COUNT(*) FROM licenses').fetchone()[0] == 3   # reused, never duplicated


def test_whop_outage_never_revokes(rig):
    cfg, eng = rig
    run(eng)
    eng.whop.down = True
    with pytest.raises(IntegrationError):
        run(eng)
    assert all(r['expirationDateUTC'] > datetime.now(timezone.utc).isoformat()
               for rows in eng.nt.rows.values() for r in rows)
    s = snap(cfg, eng)
    assert 'error' in s['whop'] and s['overall'] == 'unknown'


def test_partial_ninjatrader_failure_sends_no_success_email(rig):
    cfg, eng = rig
    eng.nt.fail_on = {next(iter(INDICATORS))}
    with pytest.raises(IntegrationError, match='License sync incomplete'):
        run(eng)
    assert outbox(cfg) == []
    s = snap(cfg, eng)
    assert s['overall'] == 'mismatch'
    assert [p['status'] for p in s['products']].count('ok') == len(INDICATORS) - 1
    eng.nt.fail_on = set()          # retry succeeds, then the email is queued
    run(eng)
    assert snap(cfg, eng)['overall'] == 'consistent' and outbox(cfg) == [{'status': 'pending'}]


def test_members_off_the_allowlist_are_never_written(rig):
    cfg, eng = rig
    cfg.allowed_test_email = 'someone-else@example.com'
    out = run(eng)
    assert out.get('mode') == 'observe_only' and eng.nt.writes == []
    assert snap(cfg, eng)['write_gate'] == {'allowed': False, 'reason': 'membership/email pair is not on the write allowlist'}


def test_staged_rollout_allowlist_requires_exact_pair(rig):
    cfg, eng = rig
    cfg.allowed_test_email = cfg.allowed_test_membership = ''
    cfg.license_write_allowlist = f'mem_other:{EMAIL}, {MEM}:wrong@example.com'
    assert run(eng).get('mode') == 'observe_only' and eng.nt.writes == []
    cfg.license_write_allowlist = f'mem_other:x@example.com, {MEM}:{EMAIL.upper()}'
    assert run(eng)['writes'] == 3


def test_writes_switch_off_means_observe_only(rig):
    cfg, eng = rig
    cfg.license_writes = False
    assert run(eng).get('mode') == 'observe_only' and eng.nt.writes == []
    assert snap(cfg, eng)['write_gate']['reason'].startswith('LICENSE_WRITES_ENABLED is false')


def test_lifetime_license_is_flagged(rig):
    cfg, eng = rig
    for pid in INDICATORS:
        eng.nt.rows[pid] = [{'id': 1, 'email': EMAIL, 'expirationDateUTC': None}]
    assert all('lifetime' in p['detail'] for p in snap(cfg, eng)['products'])


def test_snapshot_route_requires_admin(rig, monkeypatch):
    from fastapi.testclient import TestClient
    import app as web
    cfg, eng = rig
    monkeypatch.setattr(web, 'cfg', cfg)
    monkeypatch.setattr(web, 'engine', eng)
    cfg.admin_password = 'pw-for-tests'
    with TestClient(web.app) as client:
        assert client.get('/admin/lifecycle/1').status_code == 401
        r = client.get('/admin/lifecycle/1', auth=('admin', 'pw-for-tests'))
        assert r.status_code == 200 and r.json()['customer']['membership_id'] == MEM
        assert client.get('/admin/lifecycle/999', auth=('admin', 'pw-for-tests')).status_code == 404
    assert eng.nt.writes == []      # the route itself never writes
