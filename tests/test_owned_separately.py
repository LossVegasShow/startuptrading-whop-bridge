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
