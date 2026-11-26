"""Private hosting of the product files: stored in the app's database (never in
GitHub), uploaded by an admin, downloaded only by members with an active paid
membership."""
import hashlib
import io
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

import product_files
import store
from security import hash_token
from store import connect
from test_marketing import cfg_for, PW, BASE


def fake_zip(tag):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('Info.xml', tag)
    return buf.getvalue()


@pytest.fixture
def registry(monkeypatch):
    """Two fake products (the real files are never in the repository)."""
    files = {'A_2026.zip': fake_zip('a'), 'B_2026.zip': fake_zip('b')}
    reg = {1: {'name': 'Tool A', 'file': 'A_2026.zip', 'sha256': hashlib.sha256(files['A_2026.zip']).hexdigest()},
           2: {'name': 'Tool B', 'file': 'B_2026.zip', 'sha256': hashlib.sha256(files['B_2026.zip']).hexdigest()}}
    monkeypatch.setattr(product_files, 'PRODUCTS', reg)
    return files


def test_store_accepts_only_registered_verified_zips(tmp_path, registry):
    cfg = cfg_for(tmp_path)
    with connect(cfg) as db:
        assert product_files.store(db, 'evil.zip', registry['A_2026.zip'])[0] is False
        assert product_files.store(db, 'A_2026.zip', registry['B_2026.zip'])[0] is False      # wrong content
        assert product_files.store(db, 'A_2026.zip', b'')[0] is False
        ok, msg = product_files.store(db, 'A_2026.zip', registry['A_2026.zip'])
        assert ok and 'verified' in msg
        st = {s['file']: s for s in product_files.status(db)}
        assert st['A_2026.zip']['ok'] and not st['B_2026.zip']['uploaded']
        assert product_files.fetch(db, 'A_2026.zip') == registry['A_2026.zip']
        assert product_files.fetch(db, 'B_2026.zip') is None


def test_safe_next_never_redirects_elsewhere(registry):
    assert product_files.safe_next('/downloads/A_2026.zip') == '/downloads/A_2026.zip'
    for bad in ('https://evil.example/x', '//evil.example', '/downloads/nope.zip', '/admin', '/downloads/../app.py', None):
        assert product_files.safe_next(bad) == ''


def session_for(cfg, status):
    token = 'tok_' + 'x' * 40
    with connect(cfg) as db:
        db.execute("INSERT INTO customers(id,membership_id,whop_user_id,buyer_email,verified,status,updated_at) "
                   "VALUES(1,'mem_d','user_d','b@example.com',1,?,1)", (status,))
        db.execute('INSERT INTO sessions(token_hash,customer_id,expires_at) VALUES(?,?,?)',
                   (hash_token(token), 1, int(time.time()) + 3600))
    return token


@pytest.fixture
def client(tmp_path, monkeypatch, registry):
    import app
    cfg = cfg_for(tmp_path, whop_client_id='c', whop_client_secret='s')
    monkeypatch.setattr(app, 'cfg', cfg)
    with TestClient(app.app, base_url=BASE, follow_redirects=False) as c:
        yield c, cfg


def test_download_requires_sign_in_then_returns_there(client):
    c, cfg = client
    assert c.get('/downloads/nope.zip').status_code == 404
    r = c.get('/downloads/A_2026.zip')
    assert r.status_code == 303 and r.headers['location'] == '/oauth/login'
    assert r.cookies.get(product_files.NEXT_COOKIE).strip('"') == '/downloads/A_2026.zip'
    assert 'httponly' in r.headers['set-cookie'].lower()


def test_download_only_for_active_paid_members(client, registry):
    c, cfg = client
    token = session_for(cfg, 'ineligible')
    c.cookies.set('sut_session', token)
    assert c.get('/downloads/A_2026.zip').status_code == 403            # lapsed / not paid
    with connect(cfg) as db:
        db.execute("UPDATE customers SET status='eligible'")
    assert c.get('/downloads/A_2026.zip').status_code == 503            # not uploaded yet
    with connect(cfg) as db:
        product_files.store(db, 'A_2026.zip', registry['A_2026.zip'])
    r = c.get('/downloads/A_2026.zip')
    assert r.status_code == 200 and r.content == registry['A_2026.zip']
    assert r.headers['content-type'] == 'application/zip' and 'attachment; filename="A_2026.zip"' in r.headers['content-disposition']
    assert 'no-store' in r.headers['cache-control']
    with connect(cfg) as db:
        assert db.execute("SELECT details FROM audit WHERE action='product_download'").fetchone()['details'] == 'A_2026.zip'


def test_admin_upload_page(client, registry):
    c, cfg = client
    assert c.get('/admin/products').status_code == 401
    assert 'Not uploaded' in c.get('/admin/products', auth=('admin', PW)).text
    r = c.post('/admin/products', auth=('admin', PW), headers={'origin': BASE},
               files={'file1': ('A_2026.zip', registry['A_2026.zip'], 'application/zip'),
                      'file2': ('B_2026.zip', b'PK-wrong', 'application/zip')})
    assert r.status_code == 200 and 'OK: A_2026.zip stored' in r.text and 'Refused: B_2026.zip' in r.text
    # Cross-site posts are refused.
    assert c.post('/admin/products', auth=('admin', PW), headers={'origin': 'https://evil.example'},
                  files={'file1': ('A_2026.zip', registry['A_2026.zip'])}).status_code == 403


def test_postgres_stores_files_as_bytea():
    assert 'content BYTEA NOT NULL' in store.POSTGRES_SCHEMA and 'content BLOB NOT NULL' in store.SCHEMA


def test_hero_image_is_served_and_cached(client):
    c, cfg = client
    r = c.get('/static/brand/jack-hero.webp')
    assert r.status_code == 200 and r.headers['content-type'] == 'image/webp'
    assert r.headers['cache-control'] == 'public, max-age=86400'
    assert c.get('/static/site.css').headers['cache-control'] == 'no-store'
