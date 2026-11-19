"""Moving the activation app to activate.startuptrading.com without breaking anything."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient

import app as web

NEW = 'https://activate.startuptrading.com'
OLD_HOST = 'startuptrading-whop-bridge.onrender.com'


def client_for(monkeypatch, tmp_path, *, base=NEW, redirect=True):
    monkeypatch.setattr(web.cfg, 'public_base_url', base)
    monkeypatch.setattr(web.cfg, 'canonical_redirect', redirect)
    monkeypatch.setattr(web.cfg, 'database_url', '')
    monkeypatch.setattr(web.cfg, 'require_database_url', False)
    monkeypatch.setattr(web.cfg, 'db', str(tmp_path / 'c.sqlite'))
    return TestClient(web.app)


def test_old_host_pages_redirect_to_new_domain(monkeypatch, tmp_path):
    with client_for(monkeypatch, tmp_path) as c:
        r = c.get('/onboarding?error=bad_code', headers={'host': OLD_HOST}, follow_redirects=False)
    assert r.status_code == 302
    assert r.headers['location'] == NEW + '/onboarding?error=bad_code'


def test_new_host_is_served_normally(monkeypatch, tmp_path):
    with client_for(monkeypatch, tmp_path) as c:
        r = c.get('/', headers={'host': 'activate.startuptrading.com'}, follow_redirects=False)
    assert r.status_code == 200


def test_webhooks_health_and_oauth_callback_never_redirect(monkeypatch, tmp_path):
    with client_for(monkeypatch, tmp_path) as c:
        h = c.get('/health', headers={'host': OLD_HOST}, follow_redirects=False)
        assert h.status_code == 200 and h.json()['public_host'] == 'activate.startuptrading.com'
        w = c.post('/webhooks/whop', json={}, headers={'host': OLD_HOST}, follow_redirects=False)
        assert w.status_code != 302
        cb = c.get('/oauth/callback', headers={'host': OLD_HOST}, follow_redirects=False)
        assert cb.status_code != 302


def test_form_posts_are_not_redirected(monkeypatch, tmp_path):
    # A redirected POST would drop the form body; only GET/HEAD move hosts.
    with client_for(monkeypatch, tmp_path) as c:
        r = c.post('/onboarding/refresh', data={'csrf_token': 'x'}, headers={'host': OLD_HOST},
                   follow_redirects=False)
    assert r.status_code != 302


def test_off_by_default_and_requires_https(monkeypatch, tmp_path):
    assert web.Config().canonical_redirect is False
    with client_for(monkeypatch, tmp_path, redirect=False) as c:
        assert c.get('/', headers={'host': OLD_HOST}, follow_redirects=False).status_code == 200
    with client_for(monkeypatch, tmp_path, base='http://activate.startuptrading.com') as c:
        assert c.get('/', headers={'host': OLD_HOST}, follow_redirects=False).status_code == 200
