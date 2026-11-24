"""Admin buttons (Reconcile, Invite, Process events) work from a real browser.

Live bug: the app sent `Referrer-Policy: no-referrer`, so Chrome sent
`Origin: null` on the admin forms' POSTs and require_admin rejected every one
with 403 "Invalid administration request origin". The policy is now
`same-origin`: same-site form posts carry the real Origin, other sites get no
referrer at all, and the origin check itself is unchanged.
"""
import pytest
from fastapi.testclient import TestClient

import app as web

PW = 'a-long-admin-password-for-tests'
BASE = 'https://activate.startuptrading.com'


@pytest.fixture
def client(tmp_path, monkeypatch):
    for k, v in dict(database_url='', require_database_url=False, db=str(tmp_path / 'o.sqlite'),
                     admin_password=PW, public_base_url=BASE, canonical_redirect=False).items():
        if hasattr(web.cfg, k):
            monkeypatch.setattr(web.cfg, k, v)
    with TestClient(web.app, base_url=BASE) as c:
        yield c


def post(c, origin=None, referer=None):
    headers = {}
    if origin is not None:
        headers['origin'] = origin
    if referer is not None:
        headers['referer'] = referer
    return c.post('/admin/handle-events', auth=('admin', PW), headers=headers)


def test_referrer_policy_lets_same_origin_forms_send_their_origin(client):
    policy = client.get('/health').headers['referrer-policy']
    # 'no-referrer' makes browsers send Origin: null on POST, which breaks every admin form.
    assert policy == 'same-origin'


def test_admin_post_from_the_app_itself_is_accepted(client):
    assert post(client, origin=BASE).status_code != 403
    assert post(client, referer=BASE + '/admin').status_code != 403


@pytest.mark.parametrize('origin', ['null', 'https://evil.example', 'http://activate.startuptrading.com', ''])
def test_admin_post_from_anywhere_else_is_still_rejected(client, origin):
    r = post(client, origin=origin)
    assert r.status_code == 403 and 'origin' in r.text.lower()
