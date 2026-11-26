"""Active $0 promotional memberships that Whop reports without period dates.

Regression for the live test membership mem_T1AdJRcFkJNNSk: status active, the
approved monthly plan, a 100%-off promo, and current_period_start,
current_period_end and expires_at all null. It was rejected as
"status_or_paid_period_not_eligible", so the member could not sign in.
"""
import asyncio
import datetime as dt
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest

from clients import membership_entitlement, rolling_period_end
from config import BUSINESS_ID, INDICATORS, PRODUCT_ID, Config
from engine import Engine
from member_lookup import resolve_member
from store import connect

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 24, 18, 0, tzinfo=UTC)

# The live record, as returned by Whop's membership API (fields the app reads).
LIVE = {
    'id': 'mem_T1AdJRcFkJNNSk', 'member_id': 'mber_xgSgwGypmHaKP', 'user_id': 'user_bN8EFSrzs4Lqz',
    'account': {'id': 'biz_a1txPozoELC3Yc'}, 'status': 'active',
    'product_id': 'prod_Nr8ggb93WCyC1', 'product': {'id': 'prod_Nr8ggb93WCyC1', 'title': 'StartUpTrading'},
    'variant_id': 'plan_qSXeS0xoDapGU', 'promo_code_id': 'promo_GjHPSAMb8GM8', 'billing_period_days': 30,
    'initial_price': {'currency': 'usd', 'amount': '0.00'}, 'renewal_price': {'currency': 'usd', 'amount': '0.00'},
    'current_period_start': None, 'current_period_end': None, 'expires_at': None,
    'cancel_at_period_end': False, 'canceled_at': None,
}


def live(**changes):
    m = {**LIVE, **changes}
    return {k: v for k, v in m.items() if v is not _DROP}


_DROP = object()


# --- The live membership is now eligible ---------------------------------------

def test_live_promo_membership_is_eligible():
    ent = membership_entitlement(live(), now=NOW)
    assert ent and ent['membership_id'] == 'mem_T1AdJRcFkJNNSk'
    assert ent['plan_id'] == 'plan_qSXeS0xoDapGU' and ent['user_id'] == 'user_bN8EFSrzs4Lqz'
    assert ent['period_source'] == 'rolling_active'
    end = dt.datetime.fromisoformat(ent['paid_through'].replace('Z', '+00:00'))
    # Bounded: never more than one 30-day period (plus the 2-day runway) ahead.
    assert NOW + dt.timedelta(days=2) <= end <= NOW + dt.timedelta(days=32)


def test_rolling_period_is_stable_then_advances_once_per_period():
    created = '2026-11-24T16:05:00Z'
    m = live(created_at=created)
    first = membership_entitlement(m, now=NOW)['paid_through']
    # Reconciling again later in the same period gives the same date, so no license rewrite.
    for hours in (1, 24, 24 * 10, 24 * 27):
        assert membership_entitlement(m, now=NOW + dt.timedelta(hours=hours))['paid_through'] == first
    assert first == '2026-12-24T16:05:00Z'
    # Inside the last 2 days of the period it already points at the next boundary...
    later = membership_entitlement(m, now=dt.datetime(2026, 12, 23, 0, 0, tzinfo=UTC))['paid_through']
    assert later == '2027-01-23T16:05:00Z'
    # ...and stays there after the boundary passes.
    assert membership_entitlement(m, now=dt.datetime(2026, 12, 25, tzinfo=UTC))['paid_through'] == later


def test_real_period_dates_still_win_over_the_rolling_period():
    end = (NOW + dt.timedelta(days=9)).isoformat().replace('+00:00', 'Z')
    ent = membership_entitlement(live(current_period_end=end), now=NOW)
    assert ent['paid_through'] == end and ent['period_source'] == 'whop_period'


# --- Identity checks are unchanged ---------------------------------------------

@pytest.mark.parametrize('changes', [
    {'account': {'id': 'biz_someone_else'}},
    {'account': _DROP},
    {'product_id': 'prod_other', 'product': {'id': 'prod_other'}},
    {'variant_id': 'plan_not_approved'},
    {'variant_id': _DROP},
    {'variant_id': 'plan_qSXeS0xoDapGU', 'plan': {'id': 'plan_B84PWlvXemyfX'}},  # conflicting plan
], ids=['other-business', 'no-business', 'other-product', 'unapproved-plan', 'no-plan', 'plan-conflict'])
def test_identity_failures_stay_ineligible(changes):
    assert membership_entitlement(live(**changes), now=NOW) is None


# --- Missing dates are not a blanket approval ------------------------------------

@pytest.mark.parametrize('changes', [
    {'status': 'trialing'}, {'status': 'canceling'}, {'status': 'past_due'}, {'status': 'expired'},
    {'status': 'canceled'}, {'status': 'completed'}, {'status': 'unresolved'}, {'status': 'drafted'},
    {'status': _DROP},
    {'cancel_at_period_end': True},
    {'canceled_at': '2026-11-24T17:00:00Z'},
    {'billing_period_days': _DROP}, {'billing_period_days': None}, {'billing_period_days': 0},
    {'billing_period_days': 365},             # annual period on the monthly plan
    {'billing_period_days': 3650}, {'billing_period_days': '30'}, {'billing_period_days': True},
    {'expires_at': '2026-11-01T00:00:00Z'},   # a past expiry always wins
    {'current_period_end': '2026-11-20T00:00:00Z'},  # a past period end always wins
    {'current_period_end': 'not-a-date'},     # unparseable dates fail closed
    {'current_period_start': '2026-11-24T00:00:00Z'},  # partial period data: no guessing
    {'created_at': 'not-a-date'},
], ids=lambda c: '-'.join(f'{k}={"missing" if v is _DROP else v}' for k, v in c.items()))
def test_unsafe_shapes_stay_ineligible(changes):
    assert membership_entitlement(live(**changes), now=NOW) is None


def test_annual_plan_needs_a_365_day_period():
    annual = live(variant_id='plan_B84PWlvXemyfX', billing_period_days=365)
    ent = membership_entitlement(annual, now=NOW)
    assert ent and ent['plan_id'] == 'plan_B84PWlvXemyfX'
    assert membership_entitlement(live(variant_id='plan_B84PWlvXemyfX', billing_period_days=30), now=NOW) is None


def test_rolling_period_end_ignores_records_with_any_timestamp():
    assert rolling_period_end(live(expires_at='2027-01-01T00:00:00Z'), NOW) is None
    assert rolling_period_end(live(), NOW) is not None


# --- The admin diagnostic now reports "eligible" ---------------------------------

def test_member_lookup_reports_eligible_for_the_live_record(monkeypatch):
    class Response:
        status_code = 200

        def __init__(self, body): self.body = body

        def json(self): return self.body

    class Client:
        def __init__(self, **kwargs): pass

        async def __aenter__(self): return self

        async def __aexit__(self, *args): pass

        async def get(self, url, **kwargs):
            return Response({'data': [live()], 'page_info': {'has_next_page': False}})

    monkeypatch.setattr('member_lookup.httpx.AsyncClient', Client)
    cfg = SimpleNamespace(whop_api_key='fake', whop_api_version='2026-11-17')
    result = asyncio.run(resolve_member(cfg, 'mber_xgSgwGypmHaKP', 'user_bN8EFSrzs4Lqz'))
    assert len(result) == 1
    r = result[0]
    assert r['membership_id'] == 'mem_T1AdJRcFkJNNSk'
    assert r['eligible_now'] is True and r['eligibility_reason'] == 'eligible'
    assert r['user_matches_expected'] is True


# --- Licensing stays gated and idempotent ----------------------------------------

EMAIL = 'tester@example.com'


class FakeWhop:
    def __init__(self): self.record = live(created_at='2026-11-24T16:05:00Z')

    async def membership(self, mid): return dict(self.record)


class FakeNinja:
    def __init__(self):
        self.rows = {pid: [] for pid in INDICATORS}
        self.writes = []

    async def licenses(self, pid): return [dict(r) for r in self.rows[pid]]

    async def create(self, pid, email, end):
        lid = 70000 + pid
        self.rows[pid].append({'id': lid, 'email': email, 'expirationDateUTC': end})
        self.writes.append(('create', pid))
        return lid

    async def update(self, pid, lid, email, end):
        next(r for r in self.rows[pid] if r['id'] == lid)['expirationDateUTC'] = end
        self.writes.append(('update', pid, end))
        return lid


def rig(tmp_path, writes=True, allowed=LIVE['id']):
    cfg = Config(db=str(tmp_path / 'promo.db'), database_url='', require_database_url=False,
                 license_writes=writes, allowed_test_email=EMAIL, allowed_test_membership=allowed,
                 nt_username='u', nt_password='p', nt_cid='c', nt_sec='s')
    with connect(cfg) as db:
        db.execute('INSERT INTO customers(membership_id,whop_user_id,buyer_email,buyer_email_verified,nt_email,verified,status,updated_at) '
                   'VALUES(?,?,?,?,?,?,?,?)', (LIVE['id'], LIVE['user_id'], 'buyer@example.com', 1, EMAIL, 1, 'pending', int(time.time())))
    eng = Engine(cfg)
    eng.whop, eng.nt = FakeWhop(), FakeNinja()
    return cfg, eng


def activation_emails(cfg):
    with connect(cfg) as db:
        return db.execute("SELECT COUNT(*) FROM message_outbox WHERE kind='activation'").fetchone()[0]


def test_promo_member_is_licensed_once_and_repeat_reconciles_change_nothing(tmp_path):
    cfg, eng = rig(tmp_path)
    first = asyncio.run(eng.reconcile(1))
    assert first['status'] == 'eligible' and first['writes'] == len(INDICATORS)
    assert sorted(w[1] for w in eng.nt.writes) == sorted(INDICATORS)
    assert activation_emails(cfg) == 1
    for _ in range(2):
        again = asyncio.run(eng.reconcile(1))
        assert again['writes'] == 0 and {p['action'] for p in again['products']} == {'unchanged'}
    assert len(eng.nt.writes) == len(INDICATORS) and activation_emails(cfg) == 1


def test_promo_member_is_revoked_when_whop_ends_it(tmp_path):
    cfg, eng = rig(tmp_path)
    asyncio.run(eng.reconcile(1))
    eng.whop.record['status'] = 'expired'
    out = asyncio.run(eng.reconcile(1))
    assert out['status'] == 'ineligible'
    assert {p['action'] for p in out['products']} == {'expired'}
    now = dt.datetime.now(UTC)
    for pid in INDICATORS:
        end = dt.datetime.fromisoformat(eng.nt.rows[pid][0]['expirationDateUTC'].replace('Z', '+00:00'))
        assert end <= now


@pytest.mark.parametrize('writes,allowed', [(False, LIVE['id']), (True, 'mem_someone_else')],
                         ids=['writes-disabled', 'not-allowlisted'])
def test_write_gate_still_applies(tmp_path, writes, allowed):
    cfg, eng = rig(tmp_path, writes=writes, allowed=allowed)
    out = asyncio.run(eng.reconcile(1))
    assert out['status'] == 'eligible'
    assert out['writes'] == 0 and out.get('mode') == 'observe_only'
    assert eng.nt.writes == [] and activation_emails(cfg) == 0
