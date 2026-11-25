"""Production licensing controls: LICENSE_ALL_MEMBERS, emergency stop, circuit breaker.

See PRODUCTION_LICENSING.md for the operating procedures these tests pin down.
"""
import asyncio
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import attention
import controls
import lifecycle
import test_phase3_rehearsal as R
from clients import IntegrationError
from config import INDICATORS, Config
from engine import Engine
from store import connect

PW = 'a-long-admin-password-for-tests'
BASE = 'https://activate.example.com'


def make(tmp_path, n=1, **overrides):
    """n verified members, none on the allowlist unless overridden."""
    kw = dict(db=str(tmp_path / 'p.db'), database_url='', require_database_url=False, license_writes=True,
              allowed_test_email='', allowed_test_membership='', nt_username='u', nt_password='p', nt_cid='c',
              nt_sec='s', admin_password=PW, public_base_url=BASE)
    kw.update(overrides)
    cfg = Config(**kw)
    with connect(cfg) as db:
        for i in range(1, n + 1):
            db.execute('INSERT INTO customers(membership_id,whop_user_id,buyer_email,buyer_email_verified,nt_email,verified,status,updated_at) '
                       'VALUES(?,?,?,?,?,?,?,?)', (f'mem_{i}', R.USER, f'b{i}@example.com', 1, f'nt{i}@example.com', 1, 'pending', int(time.time())))
    eng = Engine(cfg)
    eng.whop, eng.nt = Whop(), R.FakeNinja()
    return cfg, eng


class Whop(R.FakeWhop):
    async def membership(self, mid):
        m = await super().membership(mid)
        m['id'] = mid
        return m


def reconcile(eng, cid=1):
    return asyncio.run(eng.reconcile(cid))


# --- Scope ---------------------------------------------------------------------------

def test_all_members_is_off_by_default():
    assert Config().license_all_members is False
    assert controls.mode(Config(license_writes=False)) == 'off'


def test_without_all_members_only_the_allowlist_is_written(tmp_path):
    cfg, eng = make(tmp_path, n=2, allowed_test_membership='mem_1', allowed_test_email='nt1@example.com')
    assert reconcile(eng, 1)['writes'] == len(INDICATORS)
    out = reconcile(eng, 2)
    assert out['writes'] == 0 and out['mode'] == 'observe_only'
    assert controls.mode(cfg) == 'allowlist'


def test_all_members_licenses_every_verified_eligible_member(tmp_path):
    cfg, eng = make(tmp_path, n=3, license_all_members=True)
    for cid in (1, 2, 3):
        assert reconcile(eng, cid)['writes'] == len(INDICATORS)
    assert controls.mode(cfg) == 'all_members'
    snap = asyncio.run(lifecycle.snapshot(cfg, eng, 2))
    assert snap['write_gate'] == {'allowed': True, 'reason': 'LICENSE_ALL_MEMBERS is on'}


def test_all_members_still_requires_a_verified_ninjatrader_email(tmp_path):
    cfg, eng = make(tmp_path, n=1, license_all_members=True)
    with connect(cfg) as db:
        db.execute('UPDATE customers SET verified=0')
    assert reconcile(eng)['writes'] == 0 and eng.nt.writes == []


def test_emergency_stop_overrides_all_members(tmp_path):
    cfg, eng = make(tmp_path, n=1, license_all_members=True, license_writes=False)
    out = reconcile(eng)
    assert out['writes'] == 0 and out['mode'] == 'observe_only' and eng.nt.writes == []
    assert controls.mode(cfg) == 'off'
    snap = asyncio.run(lifecycle.snapshot(cfg, eng, 1))
    assert snap['write_gate']['allowed'] is False and 'emergency stop' in snap['write_gate']['reason']


def test_emergency_stop_also_stops_revocations(tmp_path):
    cfg, eng = make(tmp_path, n=1, license_all_members=True)
    reconcile(eng)
    cfg.license_writes = False
    eng.whop.status = 'expired'
    reconcile(eng)
    now = datetime.now(timezone.utc).isoformat()
    assert all(r['expirationDateUTC'] > now for rs in eng.nt.rows.values() for r in rs)   # not revoked yet
    cfg.license_writes = True
    out = reconcile(eng)                                                                 # catches up on resume
    assert {p['action'] for p in out['products']} == {'expired'}


# --- Circuit breaker -------------------------------------------------------------------

def test_too_many_grants_trips_the_breaker_and_pauses_everything(tmp_path):
    cfg, eng = make(tmp_path, n=3, license_all_members=True, breaker_max_grants_per_hour=len(INDICATORS) + 1)
    assert reconcile(eng, 1)['writes'] == len(INDICATORS)
    with pytest.raises(IntegrationError):
        reconcile(eng, 2)                         # the second member's second grant hits the limit
    with connect(cfg) as db:
        state = controls.breaker(db)
        assert state and 'granted' in state['reason']
        assert any(i['key'] == 'breaker:tripped' and i['severity'] == 'high' for i in attention.find_issues(db, cfg))
    writes = len(eng.nt.writes)
    out = reconcile(eng, 3)
    assert out['mode'] == 'paused' and out['writes'] == 0 and len(eng.nt.writes) == writes


def test_too_many_revocations_trips_the_breaker(tmp_path):
    cfg, eng = make(tmp_path, n=2, license_all_members=True, breaker_max_revocations_per_hour=len(INDICATORS))
    reconcile(eng, 1); reconcile(eng, 2)
    eng.whop.status = 'expired'                   # e.g. a bad Whop response marking everyone ended
    assert {p['action'] for p in reconcile(eng, 1)['products']} == {'expired'}
    with pytest.raises(IntegrationError):
        reconcile(eng, 2)
    with connect(cfg) as db:
        assert 'revoked' in controls.breaker(db)['reason']
    now = datetime.now(timezone.utc).isoformat()
    member2 = [r for rs in eng.nt.rows.values() for r in rs if r['email'] == 'nt2@example.com']
    assert member2 and all(r['expirationDateUTC'] > now for r in member2)   # second member kept access


def test_repeated_ninjatrader_failures_trip_the_breaker(tmp_path):
    cfg, eng = make(tmp_path, n=1, license_all_members=True, breaker_max_failures_per_15min=2)
    eng.nt.fail_on = set(INDICATORS)
    with pytest.raises(IntegrationError):
        reconcile(eng)
    with connect(cfg) as db:
        assert 'failures' in controls.breaker(db)['reason']
    eng.nt.fail_on = set()
    assert reconcile(eng)['mode'] == 'paused'


def test_breaker_survives_a_restart_and_resumes_only_when_reset(tmp_path):
    cfg, eng = make(tmp_path, n=1, license_all_members=True)
    with connect(cfg) as db:
        controls.trip(db, 'manual test')
    eng2 = Engine(cfg)                             # a fresh process reads the same database
    eng2.whop, eng2.nt = eng.whop, eng.nt
    assert reconcile(eng2)['mode'] == 'paused'
    with connect(cfg) as db:
        assert controls.reset(db)['reason'] == 'manual test'
        assert controls.breaker(db) is None
        actions = [r['action'] for r in db.execute('SELECT action FROM audit WHERE customer_id IS NULL ORDER BY id')]
        assert actions == ['circuit_breaker_tripped', 'circuit_breaker_reset']
    assert reconcile(eng2)['writes'] == len(INDICATORS)


def test_reset_restarts_the_counts(tmp_path):
    cfg, eng = make(tmp_path, n=2, license_all_members=True, breaker_max_grants_per_hour=len(INDICATORS))
    reconcile(eng, 1)
    with pytest.raises(IntegrationError):
        reconcile(eng, 2)
    with connect(cfg) as db:
        controls.reset(db)
        assert controls.count(db, controls.GRANT, 3600) == 0
    assert reconcile(eng, 2)['writes'] == len(INDICATORS)


def test_status_reports_counts_and_limits(tmp_path):
    cfg, eng = make(tmp_path, n=1, license_all_members=True)
    reconcile(eng)
    with connect(cfg) as db:
        st = controls.status(cfg, db)
    assert st['mode'] == 'all_members' and st['breaker'] == 'ok'
    assert st['grant']['count'] == len(INDICATORS) and st['grant']['limit'] == cfg.breaker_max_grants_per_hour
    assert st['revoke']['count'] == 0 and st['failure']['count'] == 0


# --- Admin, health ---------------------------------------------------------------------

@pytest.fixture
def web(tmp_path, monkeypatch):
    import app
    cfg, eng = make(tmp_path, n=0)
    monkeypatch.setattr(app, 'cfg', cfg)
    with TestClient(app.app, base_url=BASE) as c:
        yield c, cfg


def test_dashboard_shows_mode_and_breaker(web):
    c, cfg = web
    html = c.get('/admin', auth=('admin', PW)).text
    assert 'Licensing controls' in html and 'Allowlist only' in html and 'Circuit breaker: <b>OK</b>' in html
    with connect(cfg) as db:
        controls.trip(db, '61 licenses granted in the last hour')
    html = c.get('/admin', auth=('admin', PW)).text
    assert 'Circuit breaker tripped' in html and '61 licenses granted' in html and 'WRITES PAUSED' in html


def test_resume_requires_typing_resume(web):
    c, cfg = web
    with connect(cfg) as db:
        controls.trip(db, 'test')
    post = lambda word: c.post('/admin/breaker/reset', data={'confirm': word}, auth=('admin', PW), headers={'origin': BASE})
    assert post('yes').status_code == 400
    with connect(cfg) as db:
        assert controls.breaker(db)
    assert post('RESUME').status_code == 200
    with connect(cfg) as db:
        assert controls.breaker(db) is None


def test_resume_needs_admin_and_same_origin(web):
    c, cfg = web
    assert c.post('/admin/breaker/reset', data={'confirm': 'RESUME'}, headers={'origin': BASE}).status_code == 401
    assert c.post('/admin/breaker/reset', data={'confirm': 'RESUME'}, auth=('admin', PW),
                  headers={'origin': 'https://evil.example'}).status_code == 403


def test_health_reports_mode_and_breaker(web):
    c, cfg = web
    body = c.get('/health').json()
    assert body['mode'] == 'allowlist_only' and body['circuit_breaker'] == 'ok'
    cfg.license_all_members = True
    assert c.get('/health').json()['mode'] == 'all_members'
    cfg.license_writes = False
    assert c.get('/health').json()['mode'] == 'observe_only'
