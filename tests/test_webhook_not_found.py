"""Whop webhooks for memberships Whop then reports as not found (HTTP 404): retried
for a day, then closed if the membership was never a customer; a known customer's
membership keeps alerting. Alerts name the membership ID."""
import asyncio
import time
from unittest.mock import patch

import httpx
import pytest

import attention
from clients import IntegrationError, NotFoundError, WhopClient
from config import Config
from purchaser_intake import NOT_FOUND_GRACE, failed_event_state
from store import connect
from test_marketing import cfg_for


def lookup(status):
    real = httpx.AsyncClient
    factory = lambda **kw: real(transport=httpx.MockTransport(lambda req: httpx.Response(status, json={})), **kw)
    with patch('clients.httpx.AsyncClient', side_effect=factory):
        return asyncio.run(WhopClient(Config(whop_api_key='k')).membership('mem_gone'))


def test_404_is_a_distinct_not_found_error():
    with pytest.raises(NotFoundError, match='HTTP 404'):
        lookup(404)
    with pytest.raises(IntegrationError) as e:
        lookup(500)
    assert not isinstance(e.value, NotFoundError)


def event(received_at, mid='mem_gone'):
    return {'webhook_id': 'msg_1', 'event_type': 'membership.activated', 'object_id': mid, 'received_at': received_at}


def test_unknown_membership_is_retried_for_a_day_then_closed(tmp_path):
    cfg = cfg_for(tmp_path)
    now = time.time()
    assert failed_event_state(cfg, event(now - 3600), NotFoundError('x'), now) == 'retry'
    assert failed_event_state(cfg, event(now - NOT_FOUND_GRACE), NotFoundError('x'), now) == 'not_found'
    # Other failures are always retried.
    assert failed_event_state(cfg, event(now - 9 * NOT_FOUND_GRACE), IntegrationError('HTTP 500'), now) == 'retry'
    with connect(cfg) as db:
        assert db.execute("SELECT details FROM audit WHERE action='webhook_not_found'").fetchone()['details'].startswith(
            'membership.activated mem_gone')


def test_known_customer_membership_keeps_alerting(tmp_path):
    cfg = cfg_for(tmp_path)
    with connect(cfg) as db:
        db.execute("INSERT INTO customers(id,membership_id,whop_user_id,buyer_email,verified,status,updated_at) "
                   "VALUES(1,'mem_gone','user_a','b@example.com',1,'eligible',1)")
    now = time.time()
    assert failed_event_state(cfg, event(now - 9 * NOT_FOUND_GRACE), NotFoundError('x'), now) == 'retry'


def test_attention_names_the_membership_and_drops_closed_events(tmp_path):
    cfg = cfg_for(tmp_path)
    with connect(cfg) as db:
        db.execute("INSERT INTO webhook_events(webhook_id,event_type,object_id,received_at,state,last_error) "
                   "VALUES('msg_1','membership.activated','mem_abc',1,'retry','Whop membership lookup HTTP 404')")
        db.execute("INSERT INTO webhook_events(webhook_id,event_type,object_id,received_at,state,last_error) "
                   "VALUES('msg_2','membership.deactivated','mem_old',1,'not_found','Whop membership lookup HTTP 404')")
        details = [i['detail'] for i in attention.find_issues(db, cfg) if i['title'] == 'Whop event failing']
    assert details == ['membership.activated mem_abc: Whop membership lookup HTTP 404']
