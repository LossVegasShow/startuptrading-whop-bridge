"""Security hardening: admin brute force, code caps, invite scanners, headers, cleanup."""
import time

import pytest
from fastapi.testclient import TestClient

import app as web
from security import LoginThrottle, admin_throttle
from store import connect

PW = 'a-long-admin-password-for-tests'


@pytest.fixture
def client(tmp_path, monkeypatch):
    for k, v in dict(database_url='', require_database_url=False, db=str(tmp_path / 's.sqlite'),
                     admin_password=PW, public_base_url='http://127.0.0.1:8000',
                     whop_webhook_secret='whsec-test').items():
        monkeypatch.setattr(web.cfg, k, v)
    with TestClient(web.app) as c:
        yield c


def admin(c, password, ip='203.0.113.5'):
    return c.get('/admin', auth=('admin', password), headers={'x-forwarded-for': f'198.51.100.1, {ip}'})


# --- Admin login brute force ---------------------------------------------------

def test_admin_locks_out_a_client_after_ten_failures(client):
    for _ in range(10):
        assert admin(client, 'wrong').status_code == 401
    locked = admin(client, PW)
    assert locked.status_code == 429 and locked.headers['retry-after'] == '900'
    assert admin(client, PW, ip='203.0.113.99').status_code == 200   # other clients unaffected


def test_forged_forwarded_for_prefix_does_not_dodge_the_lock(client):
    for i in range(10):
        client.get('/admin', auth=('admin', 'x'), headers={'x-forwarded-for': f'10.0.0.{i}, 203.0.113.5'})
    assert admin(client, PW).status_code == 429


def test_global_limit_stops_ip_rotation():
    t = LoginThrottle(per_client=10, global_limit=50, window=900)
    for i in range(50):
        t.failure(f'198.51.100.{i}', now=1000)
    assert t.blocked('192.0.2.1', now=1001)
    assert not t.blocked('192.0.2.1', now=1000 + 901)          # window expires


def test_success_clears_that_clients_failures(client):
    for _ in range(9):
        admin(client, 'wrong')
    assert admin(client, PW).status_code == 200
    assert admin(client, 'wrong').status_code == 401              # counter restarted, not locked


def test_non_ascii_password_attempt_is_a_clean_401(client):
    # hmac.compare_digest on non-ASCII str raises TypeError (was a 500).
    assert admin(client, 'pässwörd').status_code == 401


# --- One-time code daily cap --------------------------------------------------------

def make_member(cfg):
    now = int(time.time())
    with connect(cfg) as db:
        db.execute("INSERT INTO customers(membership_id,whop_user_id,buyer_email,buyer_email_verified,verified,status,updated_at) "
                   "VALUES('mem_cap','user_cap','b@example.com',1,0,'buyer_verified',?)", (now,))
        cid = db.execute("SELECT id FROM customers WHERE membership_id='mem_cap'").fetchone()['id']
        db.execute('INSERT INTO sessions(token_hash,customer_id,expires_at) VALUES(?,?,?)', (web.hash_token('c' * 40), cid, now + 3600))
    return cid


def test_code_requests_are_capped_per_day(client, monkeypatch):
    cid = make_member(web.cfg)
    monkeypatch.setattr(web, 'deliver_code', lambda *a: None)
    now = int(time.time())
    with connect(web.cfg) as db:      # ten earlier requests today (beyond the 60-second cooldown)
        for i in range(10):
            db.execute("INSERT INTO audit(at,customer_id,action,details) VALUES(?,?,'code_requested','nt')", (now - 3600 - i, cid))
    data = {'csrf_token': web.csrf('c' * 40), 'nt_email': 'n@example.com', 'path': 'existing'}
    client.cookies.set('sut_session', 'c' * 40)
    r = client.post('/onboarding/nt-code', data=data, follow_redirects=False)
    assert r.status_code == 429
    page = client.post('/onboarding/nt-code', data=data, headers={'accept': 'text/html'}, follow_redirects=False)
    assert page.headers['location'] == '/onboarding?error=code_cap'
    with connect(web.cfg) as db:      # yesterday's requests don't count
        db.execute("UPDATE audit SET at=? WHERE action='code_requested'", (now - 90000,))
    assert client.post('/onboarding/nt-code', data=data, follow_redirects=False).status_code == 303


# --- Invite links survive email scanners -----------------------------------------------

def test_opening_an_invite_does_not_use_it_up(client):
    cid = make_member(web.cfg)
    with connect(web.cfg) as db:
        db.execute('INSERT INTO invites(token_hash,customer_id,expires_at) VALUES(?,?,?)',
                   (web.hash_token('invite-token-123'), cid, int(time.time()) + 3600))
    for _ in range(3):                                   # scanner + preview + human
        r = client.get('/activate/invite-token-123', headers={'accept': 'text/html'})
        assert r.status_code == 200 and 'Continue to activation' in r.text
        assert 'sut_session' not in r.cookies
    with connect(web.cfg) as db:
        assert db.execute('SELECT used_at FROM invites').fetchone()['used_at'] is None
    r = client.post('/activate/invite-token-123', follow_redirects=False)
    assert r.status_code == 303 and r.headers['location'] == '/onboarding' and 'sut_session' in r.cookies
    assert client.post('/activate/invite-token-123', follow_redirects=False).status_code == 404   # single use
    assert client.get('/activate/not-a-real-token').status_code == 404


# --- Headers, webhook size, cleanup -------------------------------------------------------------

def test_hsts_only_on_https(client, monkeypatch):
    assert 'strict-transport-security' not in client.get('/health').headers
    monkeypatch.setattr(web.cfg, 'public_base_url', 'https://activate.startuptrading.com')
    h = client.get('/health').headers
    assert h['strict-transport-security'] == 'max-age=31536000' and 'camera=()' in h['permissions-policy']


def test_oversized_webhook_rejected_by_declared_length(client):
    r = client.post('/webhooks/whop', content=b'{}', headers={'content-length': str(300 * 1024)})
    assert r.status_code == 413


def test_expired_signin_state_and_sessions_are_purged(client):
    cid = make_member(web.cfg)
    now = int(time.time())
    with connect(web.cfg) as db:
        db.execute("INSERT INTO oauth_states(state_hash,verifier,nonce,expires_at) VALUES('old','v','n',?)", (now - 10,))
        db.execute("INSERT INTO oauth_states(state_hash,verifier,nonce,expires_at) VALUES('new','v','n',?)", (now + 600,))
        db.execute("INSERT INTO sessions(token_hash,customer_id,expires_at) VALUES('gone',?,?)", (cid, now - 10))
        web.purge_expired(db)
        assert [r['state_hash'] for r in db.execute('SELECT state_hash FROM oauth_states')] == ['new']
        assert db.execute("SELECT COUNT(*) AS n FROM sessions WHERE token_hash='gone'").fetchone()['n'] == 0
