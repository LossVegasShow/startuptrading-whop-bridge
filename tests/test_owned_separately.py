"""Members who already bought an indicator outright (one-time purchase)."""
import asyncio
import time
from datetime import datetime, timedelta, timezone

import pytest

import lifecycle
import test_phase3_rehearsal as R
from config import INDICATORS, Config
from engine import Engine
from store import connect

ATR = 2067          # sold one-time on startuptrading.com/atr-checkout


@pytest.fixture
def rig(tmp_path):
    cfg = Config(db=str(tmp_path / 'o.db'), database_url='', require_database_url=False,
                 license_writes=True, allowed_test_email=R.EMAIL, allowed_test_membership=R.MEM,
                 nt_username='u', nt_password='p', nt_cid='c', nt_sec='s')
    with connect(cfg) as db:
        db.execute('INSERT INTO customers(membership_id,whop_user_id,buyer_email,buyer_email_verified,nt_email,verified,status,updated_at) '
                   'VALUES(?,?,?,?,?,?,?,?)', (R.MEM, R.USER, 'b@example.com', 1, R.EMAIL, 1, 'pending', int(time.time())))
    eng = Engine(cfg)
    eng.whop, eng.nt = R.FakeWhop(), R.FakeNinja()
    return cfg, eng


def owns(eng, pid, expiry):
    eng.nt.rows[pid].append({'id': 555, 'email': R.EMAIL, 'expirationDateUTC': expiry})


def rows(cfg, sql):
    with connect(cfg) as db:
        return [dict(r) for r in db.execute(sql)]


@pytest.mark.parametrize('expiry', [None, '2099-01-01T00:00:00Z'])   # lifetime, or longer than the membership
def test_owned_indicator_counts_and_is_never_touched(rig, expiry):
    cfg, eng = rig
    owns(eng, ATR, expiry)
    out = asyncio.run(eng.reconcile(1))
    assert out['writes'] == len(INDICATORS) - 1                      # only the other two were created
    assert ('create', ATR) not in eng.nt.writes and ('update', ATR) not in eng.nt.writes
    assert eng.nt.rows[ATR] == [{'id': 555, 'email': R.EMAIL, 'expirationDateUTC': expiry}]
    lic = {r['product_id']: r for r in rows(cfg, 'SELECT * FROM licenses')}
    assert lic[ATR]['state'] == 'owned_separately' and lic[ATR]['license_id'] is None
    assert rows(cfg, "SELECT status FROM message_outbox WHERE kind='activation'") == [{'status': 'pending'}]
    snap = asyncio.run(lifecycle.snapshot(cfg, eng, 1))
    assert snap['overall'] == 'consistent'
    assert 'owned separately' in next(p for p in snap['products'] if p['product_id'] == ATR)['detail']


def test_membership_ending_never_revokes_an_owned_indicator(rig):
    cfg, eng = rig
    owns(eng, ATR, None)
    asyncio.run(eng.reconcile(1))
    eng.whop.status = 'expired'
    asyncio.run(eng.reconcile(1))
    assert eng.nt.rows[ATR][0]['expirationDateUTC'] is None              # still lifetime
    others = [r for pid, rs in eng.nt.rows.items() if pid != ATR for r in rs]
    assert others and all(r['expirationDateUTC'] < datetime.now(timezone.utc).isoformat() for r in others)


def test_separate_license_ending_before_membership_needs_review(rig):
    cfg, eng = rig
    owns(eng, ATR, (datetime.now(timezone.utc) + timedelta(days=2)).replace(microsecond=0).isoformat())
    with pytest.raises(Exception, match='License sync incomplete for products 2067'):
        asyncio.run(eng.reconcile(1))
    detail = rows(cfg, "SELECT details FROM audit WHERE action='sync_error'")
    assert detail and 'expires before the membership; manual review required' in detail[0]['details']
    assert rows(cfg, "SELECT * FROM message_outbox WHERE kind='activation'") == []
    assert ('update', ATR) not in eng.nt.writes and ('create', ATR) not in eng.nt.writes


def test_refunded_one_time_purchase_falls_back_to_membership_license(rig):
    cfg, eng = rig
    owns(eng, ATR, None)
    asyncio.run(eng.reconcile(1))
    eng.nt.rows[ATR] = []                                                # one-time license removed
    asyncio.run(eng.reconcile(1))
    assert ('create', ATR) in eng.nt.writes
    lic = {r['product_id']: r for r in rows(cfg, 'SELECT * FROM licenses')}
    assert lic[ATR]['state'] == 'created' and lic[ATR]['license_id'] is not None


# --- Already-expired licenses the bridge didn't create (old trial, lapsed test) ---
# Live case: the test NinjaTrader account had 2067/2071/2205 licenses that expired
# 2026-11-19, so activation stopped with "Pre-existing license expires before the
# membership; manual review required".

EXPIRED = '2026-11-19T01:32:39.000Z'


def expired_everywhere(eng):
    for i, pid in enumerate(INDICATORS):
        eng.nt.rows[pid].append({'id': 82900 + i, 'email': R.EMAIL.upper(), 'expirationDateUTC': EXPIRED})


def test_expired_foreign_licenses_are_adopted_and_extended_not_duplicated(rig):
    cfg, eng = rig
    expired_everywhere(eng)
    out = asyncio.run(eng.reconcile(1))
    assert ('create', ATR) not in eng.nt.writes and not any(w[0] == 'create' for w in eng.nt.writes)
    assert out['writes'] == len(INDICATORS)
    paid = rows(cfg, 'SELECT paid_through FROM customers')[0]['paid_through']
    for i, pid in enumerate(INDICATORS):
        assert len(eng.nt.rows[pid]) == 1 and eng.nt.rows[pid][0]['expirationDateUTC'] == paid
    lic = {r['product_id']: r for r in rows(cfg, 'SELECT * FROM licenses')}
    assert all(lic[pid]['license_id'] == 82900 + i for i, pid in enumerate(INDICATORS))
    assert len(rows(cfg, "SELECT * FROM audit WHERE action='ninjatrader_adopted_expired'")) == len(INDICATORS)
    assert rows(cfg, "SELECT status FROM message_outbox WHERE kind='activation'") == [{'status': 'pending'}]
    assert asyncio.run(lifecycle.snapshot(cfg, eng, 1))['overall'] == 'consistent'
    # Repeat reconciles change nothing and send nothing new.
    writes = len(eng.nt.writes)
    assert asyncio.run(eng.reconcile(1))['writes'] == 0 and len(eng.nt.writes) == writes
    assert len(rows(cfg, "SELECT * FROM message_outbox WHERE kind='activation'")) == 1


def test_adopted_licenses_are_expired_again_when_the_membership_ends(rig):
    cfg, eng = rig
    expired_everywhere(eng)
    asyncio.run(eng.reconcile(1))
    eng.whop.status = 'expired'
    out = asyncio.run(eng.reconcile(1))
    assert {p['action'] for p in out['products']} == {'expired'}
    now = datetime.now(timezone.utc)
    for pid in INDICATORS:
        end = datetime.fromisoformat(eng.nt.rows[pid][0]['expirationDateUTC'].replace('Z', '+00:00'))
        assert end <= now


def test_expired_foreign_license_is_left_alone_when_not_entitled(rig):
    cfg, eng = rig
    expired_everywhere(eng)
    eng.whop.status = 'expired'
    asyncio.run(eng.reconcile(1))
    assert eng.nt.writes == []
    assert all(r['expirationDateUTC'] == EXPIRED for rs in eng.nt.rows.values() for r in rs)


def test_expired_foreign_license_is_not_adopted_without_write_permission(tmp_path):
    cfg = Config(db=str(tmp_path / 'g.db'), database_url='', require_database_url=False,
                 license_writes=False, allowed_test_email=R.EMAIL, allowed_test_membership=R.MEM,
                 nt_username='u', nt_password='p', nt_cid='c', nt_sec='s')
    with connect(cfg) as db:
        db.execute('INSERT INTO customers(membership_id,whop_user_id,buyer_email,buyer_email_verified,nt_email,verified,status,updated_at) '
                   'VALUES(?,?,?,?,?,?,?,?)', (R.MEM, R.USER, 'b@example.com', 1, R.EMAIL, 1, 'pending', int(time.time())))
    eng = Engine(cfg)
    eng.whop, eng.nt = R.FakeWhop(), R.FakeNinja()
    expired_everywhere(eng)
    assert asyncio.run(eng.reconcile(1))['writes'] == 0 and eng.nt.writes == []


def test_two_licenses_for_the_same_email_still_need_review(rig):
    cfg, eng = rig
    eng.nt.rows[ATR] += [{'id': 1, 'email': R.EMAIL, 'expirationDateUTC': EXPIRED},
                         {'id': 2, 'email': R.EMAIL, 'expirationDateUTC': EXPIRED}]
    with pytest.raises(Exception, match='2067'):
        asyncio.run(eng.reconcile(1))
    assert ('update', ATR) not in eng.nt.writes and ('create', ATR) not in eng.nt.writes
