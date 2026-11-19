"""Customer-facing UX: friendly errors, onboarding steps, emails, CSP-safe templates."""
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient

import app as web
import email_templates
from store import connect

HTML = {'accept': 'text/html,application/xhtml+xml,*/*;q=0.8'}
ROOT = Path(__file__).resolve().parents[1]


def setup(tmp_path, **cols):
    web.cfg.database_url = ''
    web.cfg.require_database_url = False
    web.cfg.db = str(tmp_path / 'ux.sqlite')
    web.cfg.admin_password = 'test-secret-for-codes'
    row = {'membership_id': 'mem_ux', 'whop_user_id': 'user_ux', 'buyer_email': 'buyer@example.com',
           'buyer_email_verified': 1, 'nt_email': None, 'verified': 0, 'status': 'buyer_verified',
           'updated_at': int(time.time())}
    row.update(cols)
    with connect(web.cfg) as db:
        db.execute(f"INSERT INTO customers({','.join(row)}) VALUES({','.join('?' * len(row))})", tuple(row.values()))
        db.execute('INSERT INTO sessions(token_hash,customer_id,expires_at) VALUES(?,?,?)',
                   (web.hash_token('u' * 40), 1, int(time.time()) + 3600))
    return {'sut_session': 'u' * 40}, web.csrf('u' * 40)


def test_browser_without_session_gets_friendly_page_not_json(tmp_path):
    setup(tmp_path)
    with TestClient(web.app) as client:
        r = client.get('/onboarding', headers=HTML)
    assert r.status_code == 403
    assert r.headers['content-type'].startswith('text/html')
    assert 'Your activation session ended' in r.text and '/oauth/login' in r.text
    assert '"detail"' not in r.text


def test_api_clients_keep_json_errors(tmp_path):
    setup(tmp_path)
    with TestClient(web.app) as client:
        r = client.get('/onboarding')
        assert r.status_code == 403 and r.json()['detail'] == 'Use your private activation invitation'
        # Webhooks and admin stay JSON even for a browser Accept header.
        w = client.post('/webhooks/whop', json={}, headers=HTML)
        assert w.headers['content-type'].startswith('application/json')
        a = client.get('/admin', headers=HTML)
        assert a.status_code in (401, 503)
        if a.status_code == 401:
            assert 'WWW-Authenticate' in a.headers


def test_wrong_code_returns_to_onboarding_with_banner(tmp_path, monkeypatch):
    cookies, token = setup(tmp_path, nt_email='ninja@example.com')
    monkeypatch.setattr(web, 'deliver_code', lambda *a: None)
    with TestClient(web.app, cookies=cookies) as client:
        client.post('/onboarding/nt-code', data={'csrf_token': token, 'nt_email': 'ninja@example.com', 'path': 'existing'},
                    headers=HTML, follow_redirects=False)
        r = client.post('/onboarding/nt-verify', data={'csrf_token': token, 'code': '000000'},
                        headers=HTML, follow_redirects=False)
        assert r.status_code == 303 and r.headers['location'] == '/onboarding?error=bad_code'
        page = client.get(r.headers['location'], headers=HTML)
    assert 'That code didn&#39;t work' in page.text and 'role="alert"' in page.text


def test_missing_form_field_redirects_instead_of_422_json(tmp_path):
    cookies, token = setup(tmp_path)
    with TestClient(web.app, cookies=cookies) as client:
        r = client.post('/onboarding/nt-code', data={'csrf_token': token}, headers=HTML, follow_redirects=False)
    assert r.status_code == 303 and r.headers['location'] == '/onboarding?error=bad_input'


def test_unknown_error_query_is_ignored(tmp_path):
    cookies, _ = setup(tmp_path)
    with TestClient(web.app, cookies=cookies) as client:
        r = client.get('/onboarding?error=<script>', headers=HTML)
    assert r.status_code == 200 and '<script>' not in r.text


def test_unknown_page_is_friendly_404():
    with TestClient(web.app) as client:
        r = client.get('/does-not-exist', headers=HTML)
    assert r.status_code == 404 and 'This page doesn&#39;t exist' in r.text


def test_onboarding_steps(tmp_path):
    base = {'buyer_email_verified': 1, 'verified': 0, 'nt_email': None, 'status': 'eligible'}
    v = web.onboarding_view({**base, 'buyer_email_verified': 0}, [])
    assert v['step'] == 1 and v['stepper'][0][1] == 'current'
    v = web.onboarding_view(base, [])
    assert v['step'] == 2 and [s for _, s in v['stepper']] == ['done', 'current', '']
    v = web.onboarding_view({**base, 'nt_email': 'a@b.co'}, [])
    assert v['step'] == 3 and v['visual_step'] == 2
    v = web.onboarding_view({**base, 'nt_email': 'a@b.co', 'verified': 1}, [])
    assert v['step'] == 4 and not v['all_active'] and v['indicators'][0]['label'] == 'Activating'
    lic = [{'product_id': pid, 'state': 'created'} for pid in web.INDICATORS]
    v = web.onboarding_view({**base, 'nt_email': 'a@b.co', 'verified': 1}, lic)
    assert v['all_active'] and [s for _, s in v['stepper']] == ['done', 'done', 'done']
    lic[0]['state'] = 'error'
    v = web.onboarding_view({**base, 'nt_email': 'a@b.co', 'verified': 1}, lic)
    assert not v['all_active'] and v['indicators'][0]['label'] == 'Needs attention'


def test_each_step_renders(tmp_path):
    for i, cols in enumerate([{'buyer_email_verified': 0}, {}, {'nt_email': 'n@example.com'},
                              {'nt_email': 'n@example.com', 'verified': 1, 'status': 'eligible'},
                              {'nt_email': 'n@example.com', 'verified': 1, 'status': 'ineligible'}]):
        d = tmp_path / str(i); d.mkdir()
        cookies, _ = setup(d, **cols)
        with TestClient(web.app, cookies=cookies) as client:
            r = client.get('/onboarding', headers=HTML)
        assert r.status_code == 200, r.text
    assert "Your membership isn't active" in r.text


def test_landing_lists_all_three_indicators():
    with TestClient(web.app) as client:
        r = client.get('/', headers=HTML)
    assert r.status_code == 200 and '/oauth/login' in r.text
    for name in web.INDICATORS.values():
        assert name.replace('&', '&amp;') in r.text


def test_customer_templates_have_no_inline_styles_or_scripts():
    # The Content-Security-Policy blocks inline styles and scripts.
    for name in ('_base.html', 'index.html', 'onboarding.html', 'error.html'):
        text = (ROOT / 'templates' / name).read_text()
        assert not re.search(r'\sstyle="', text), name
        assert '<script' not in text, name


def test_emails_escape_user_content():
    html = email_templates.activation_email('<b>x</b>@example.com', ['A & B'], 'https://guide.example/x', '', 'help@example.com')
    assert '<b>x</b>' not in html and '&lt;b&gt;' in html and 'A &amp; B' in html
    code = email_templates.code_email('123456')
    assert '123456' in code and '10 minutes' in code
