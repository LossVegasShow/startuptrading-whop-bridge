"""Buyer email from Whop's Members API, bound to the verified membership.

Live issue: purchase webhooks failed with "Whop buyer email unavailable"
because neither the membership record nor the user profile carries an email.
Whop returns it as the top-level `email` of GET /api/v1/members/{mber_...}.
"""
import asyncio
import copy
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
import pytest

from clients import IntegrationError, WhopClient
from config import Config
from purchaser_intake import import_membership, member_api_email
from store import connect

# Actual live records (membership from the earlier eligibility fix, member as returned by Whop).
MEMBERSHIP = {
    'id': 'mem_T1AdJRcFkJNNSk', 'member_id': 'mber_xgSgwGypmHaKP', 'user_id': 'user_bN8EFSrzs4Lqz',
    'account': {'id': 'biz_a1txPozoELC3Yc'}, 'status': 'active',
    'product_id': 'prod_Nr8ggb93WCyC1', 'product': {'id': 'prod_Nr8ggb93WCyC1', 'title': 'StartUpTrading'},
    'variant_id': 'plan_qSXeS0xoDapGU', 'promo_code_id': 'promo_GjHPSAMb8GM8', 'billing_period_days': 30,
    'initial_price': {'currency': 'usd', 'amount': '0.00'}, 'renewal_price': {'currency': 'usd', 'amount': '0.00'},
    'current_period_start': None, 'current_period_end': None, 'expires_at': None,
    'cancel_at_period_end': False, 'canceled_at': None,
    'created_at': '2026-11-24T16:44:59.217Z', 'updated_at': '2026-11-24T16:44:59.619Z',
}
MEMBER = {
    'id': 'mber_xgSgwGypmHaKP', 'account_id': 'biz_a1txPozoELC3Yc', 'buyer_account_id': None,
    'access_level': 'customer', 'status': 'joined', 'display_name': 'phonysolvent77', 'name': None,
    'email': 'bitbanditbrand@gmail.com',
    'user': {'id': 'user_bN8EFSrzs4Lqz', 'username': 'phonysolvent77', 'name': None},
}


class Whop:
    def __init__(self, membership=None, member=None, user=None, member_error=None):
        self.m = copy.deepcopy(membership or MEMBERSHIP)
        self.rec = copy.deepcopy(member if member is not None else MEMBER)
        self.u = user if user is not None else {'id': self.m['user_id'], 'username': 'phonysolvent77'}
        self.member_error = member_error
        self.member_calls, self.user_calls = [], 0

    async def membership(self, mid): return copy.deepcopy(self.m)

    async def member(self, mid):
        self.member_calls.append(mid)
        if self.member_error:
            raise self.member_error
        return copy.deepcopy(self.rec)

    async def user(self, uid):
        self.user_calls += 1
        return self.u


@pytest.fixture
def cfg(tmp_path):
    return Config(database_url='', require_database_url=False, db=str(tmp_path / 'm.sqlite'))


def customers(cfg):
    with connect(cfg) as db:
        return [dict(r) for r in db.execute('SELECT * FROM customers')]


# --- The live response -----------------------------------------------------------

def test_live_member_email_is_used_for_the_live_membership():
    whop = Whop()
    assert asyncio.run(member_api_email(whop, MEMBERSHIP)) == 'bitbanditbrand@gmail.com'
    assert whop.member_calls == ['mber_xgSgwGypmHaKP']


def test_purchase_webhook_creates_the_buyer_record_with_the_whop_email(cfg):
    whop = Whop()
    out = asyncio.run(import_membership(cfg, whop, 'mem_T1AdJRcFkJNNSk'))
    assert out['state'] == 'created'
    [c] = customers(cfg)
    assert c['buyer_email'] == 'bitbanditbrand@gmail.com'
    assert c['whop_user_id'] == 'user_bN8EFSrzs4Lqz' and c['membership_id'] == 'mem_T1AdJRcFkJNNSk'
    # The Whop email is not a NinjaTrader link and not a verification of anything.
    assert c['nt_email'] is None and c['verified'] == 0 and c['buyer_email_verified'] == 0
    assert whop.user_calls == 0
    with connect(cfg) as db:
        assert db.execute('SELECT COUNT(*) FROM licenses').fetchone()[0] == 0


def test_member_joined_status_does_not_make_an_ineligible_membership_eligible(cfg):
    whop = Whop(membership={**MEMBERSHIP, 'status': 'expired'})
    assert asyncio.run(import_membership(cfg, whop, 'mem_T1AdJRcFkJNNSk'))['state'] == 'ignored_ineligible'
    assert customers(cfg) == [] and whop.member_calls == []


def test_existing_record_keeps_its_ninjatrader_email_separate(cfg):
    asyncio.run(import_membership(cfg, Whop(), 'mem_T1AdJRcFkJNNSk'))
    with connect(cfg) as db:
        db.execute("UPDATE customers SET nt_email='different-ninja@example.com', verified=1")
    whop = Whop(member={**MEMBER, 'email': 'new-whop-address@example.com'})
    assert asyncio.run(import_membership(cfg, whop, 'mem_T1AdJRcFkJNNSk'))['state'] == 'updated'
    [c] = customers(cfg)
    assert c['buyer_email'] == 'bitbanditbrand@gmail.com' and c['nt_email'] == 'different-ninja@example.com'
    assert whop.member_calls == []          # not needed once the record exists


# --- Identity binding --------------------------------------------------------------

@pytest.mark.parametrize('change', [
    {'id': 'mber_someone_else'},
    {'account_id': 'biz_other_business'},
    {'account_id': None},
    {'user': {'id': 'user_someone_else', 'username': 'x'}},
    {'user': None},
    {'user': {'username': 'phonysolvent77'}},
], ids=['member-id', 'business', 'no-business', 'user', 'no-user', 'no-user-id'])
def test_mismatched_member_identity_never_creates_a_record(cfg, change):
    whop = Whop(member={**MEMBER, **change})
    with pytest.raises(IntegrationError, match='identity mismatch'):
        asyncio.run(import_membership(cfg, whop, 'mem_T1AdJRcFkJNNSk'))
    assert customers(cfg) == [] and whop.user_calls == 0


def test_nested_account_object_is_accepted():
    rec = {**MEMBER, 'account_id': None, 'account': {'id': 'biz_a1txPozoELC3Yc'}}
    assert asyncio.run(member_api_email(Whop(member=rec), MEMBERSHIP)) == 'bitbanditbrand@gmail.com'


# --- Missing emails and API errors ------------------------------------------------

@pytest.mark.parametrize('email', [None, '', 'not-an-email', 'a@b', 123])
def test_missing_or_invalid_member_email_falls_back_then_fails_closed(cfg, email):
    whop = Whop(member={**MEMBER, 'email': email})
    with pytest.raises(IntegrationError, match='buyer email unavailable'):
        asyncio.run(import_membership(cfg, whop, 'mem_T1AdJRcFkJNNSk'))
    assert whop.user_calls == 1 and customers(cfg) == []


def test_legacy_user_email_still_works_when_members_api_has_none(cfg):
    whop = Whop(member={**MEMBER, 'email': None}, user={'email': 'Legacy@Example.org'})
    assert asyncio.run(import_membership(cfg, whop, 'mem_T1AdJRcFkJNNSk'))['state'] == 'created'
    assert customers(cfg)[0]['buyer_email'] == 'legacy@example.org'


def test_members_api_error_propagates_for_retry(cfg):
    whop = Whop(member_error=IntegrationError('Whop member lookup HTTP 503'))
    with pytest.raises(IntegrationError, match='HTTP 503'):
        asyncio.run(import_membership(cfg, whop, 'mem_T1AdJRcFkJNNSk'))
    assert customers(cfg) == []


def test_membership_without_member_id_skips_the_members_api():
    m = {k: v for k, v in MEMBERSHIP.items() if k != 'member_id'}
    whop = Whop()
    assert asyncio.run(member_api_email(whop, m)) == '' and whop.member_calls == []


def test_email_in_the_membership_record_still_wins(cfg):
    whop = Whop(membership={**MEMBERSHIP, 'user': {'id': 'user_bN8EFSrzs4Lqz', 'email': 'on-record@example.com'}})
    asyncio.run(import_membership(cfg, whop, 'mem_T1AdJRcFkJNNSk'))
    assert customers(cfg)[0]['buyer_email'] == 'on-record@example.com' and whop.member_calls == []


# --- HTTP client -----------------------------------------------------------------------

def run_client(handler, member_id='mber_xgSgwGypmHaKP'):
    real = httpx.AsyncClient
    factory = lambda **kw: real(transport=httpx.MockTransport(handler), **kw)
    with patch('clients.httpx.AsyncClient', side_effect=factory):
        return asyncio.run(WhopClient(Config(whop_api_key='test-key')).member(member_id))


def test_client_calls_the_members_endpoint_with_auth_and_version():
    def handler(req):
        assert req.url.path == '/api/v1/members/mber_xgSgwGypmHaKP'
        assert req.headers['authorization'] == 'Bearer test-key' and req.headers.get('api-version-date')
        return httpx.Response(200, json=MEMBER)
    assert run_client(handler)['email'] == 'bitbanditbrand@gmail.com'


def test_client_unwraps_a_data_envelope():
    assert run_client(lambda req: httpx.Response(200, json={'data': MEMBER}))['id'] == MEMBER['id']


@pytest.mark.parametrize('status', [401, 403, 404, 500])
def test_client_http_errors_raise(status):
    with pytest.raises(IntegrationError, match=str(status)):
        run_client(lambda req: httpx.Response(status, json={}))


@pytest.mark.parametrize('bad', ['mem_T1AdJRcFkJNNSk', 'user_x', '', None, 'mber_' + 'x' * 200])
def test_client_rejects_non_member_ids(bad):
    with pytest.raises(IntegrationError, match='Invalid Whop member ID'):
        run_client(lambda req: httpx.Response(200, json=MEMBER), member_id=bad)
