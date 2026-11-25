"""Activation reminders need explicit operator approval, separate from licensing.

Turning on LICENSE_ALL_MEMBERS must never email the backlog of unactivated
members by itself. An operator reviews the list at /admin/reminders, ticks the
recipients and types the exact count.
"""
import asyncio
import time

import pytest
from fastapi.testclient import TestClient

import lifecycle_emails
from config import Config
from store import connect

NOW = int(time.time())
PW = 'a-long-admin-password-for-tests'
BASE = 'https://activate.example.com'


class Outbox:
    def __init__(self): self.sent = []

    async def __call__(self, body, headers):
        self.sent.append(body)
        return 'msg_1'


@pytest.fixture
def cfg(tmp_path):
    return Config(db=str(tmp_path / 'r.sqlite'), database_url='', require_database_url=False, public_base_url=BASE,
                  resend_api_key='re_test', resend_from='a@b.co', admin_password=PW, license_writes=True)


def add(cfg, mid):
    with connect(cfg) as db:
        db.execute('INSERT INTO customers(membership_id,whop_user_id,buyer_email,buyer_email_verified,status,paid_through,updated_at) '
                   'VALUES(?,?,?,?,?,?,?)', (mid, 'user_' + mid, mid + '@buyer.example', 1, 'eligible', '2026-12-24T00:00:00Z', NOW))
        cid = db.execute('SELECT id FROM customers WHERE membership_id=?', (mid,)).fetchone()['id']
        lifecycle_emails.schedule_reminders(db, now=NOW - 4 * 86400)      # both reminders already due
    return cid


def send(cfg, cid, kind='activation_reminder_1', post=None):
    return asyncio.run(lifecycle_emails.send(cfg, cid, kind, post=post or Outbox()))


def test_all_members_alone_does_not_send_reminders(cfg):
    cfg.license_all_members = True
    cid = add(cfg, 'mem_a')
    post = Outbox()
    assert send(cfg, cid, post=post) == 'held' and post.sent == []
    with connect(cfg) as db:
        assert db.execute("SELECT status FROM message_outbox WHERE customer_id=? AND kind='activation_reminder_1'",
                          (cid,)).fetchone()['status'] == 'pending'


def test_approved_reminder_sends_only_for_the_approved_member(cfg):
    cfg.license_all_members = True
    a, b = add(cfg, 'mem_a'), add(cfg, 'mem_b')
    with connect(cfg) as db:
        assert lifecycle_emails.approve(db, cfg, {(a, 'activation_reminder_1')}, 'batch1') == 1
    post = Outbox()
    assert send(cfg, a, post=post) == 'sent' and post.sent[0]['to'] == ['mem_a@buyer.example']
    assert send(cfg, b) == 'held'
    assert send(cfg, a, 'activation_reminder_2') == 'held'                # approval is per reminder


def test_approval_without_open_licensing_still_holds(cfg):
    cid = add(cfg, 'mem_a')                                                # allowlist mode, not allowlisted
    with connect(cfg) as db:
        lifecycle_emails.approve(db, cfg, {(cid, 'activation_reminder_1')}, 'b')
    assert send(cfg, cid) == 'held'
    cfg.license_all_members = True
    assert send(cfg, cid) == 'sent'


def test_emergency_stop_holds_even_approved_reminders(cfg):
    cfg.license_all_members = True
    cid = add(cfg, 'mem_a')
    with connect(cfg) as db:
        lifecycle_emails.approve(db, cfg, {(cid, 'activation_reminder_1')}, 'b')
    cfg.license_writes = False
    assert send(cfg, cid) == 'held'


def test_held_list_and_approval_ignore_reminders_that_no_longer_apply(cfg):
    cfg.license_all_members = True
    a, b = add(cfg, 'mem_a'), add(cfg, 'mem_b')
    with connect(cfg) as db:
        db.execute("UPDATE customers SET verified=1, nt_email='n@nt.example' WHERE id=?", (b,))   # b activated
        held = lifecycle_emails.held_reminders(db, cfg)
        assert {h['customer_id'] for h in held} == {a}
        assert all(h['licensing_open'] and not h['approved'] for h in held)
        assert lifecycle_emails.approve(db, cfg, {(b, 'activation_reminder_1'), (a, 'activation_reminder_1')}, 'x') == 1
        assert db.execute("SELECT details FROM audit WHERE action='reminders_released'").fetchone()['details'] == 'batch x: 1 reminder(s)'


def test_auto_setting_sends_without_approval(cfg):
    cfg.license_all_members = True
    cfg.activation_reminders_auto = True
    assert send(cfg, add(cfg, 'mem_a')) == 'sent'


def test_auto_is_off_by_default():
    assert Config().activation_reminders_auto is False


# --- Approval page -------------------------------------------------------------------

@pytest.fixture
def web(cfg, monkeypatch):
    import app
    monkeypatch.setattr(app, 'cfg', cfg)
    with TestClient(app.app, base_url=BASE) as c:
        yield c


def release(c, items, confirm):
    return c.post('/admin/reminders/release', data={'item': items, 'confirm': confirm},
                  auth=('admin', PW), headers={'origin': BASE})


def test_page_lists_recipients_and_requires_the_exact_count(web, cfg):
    cfg.license_all_members = True
    a, b = add(cfg, 'mem_a'), add(cfg, 'mem_b')
    html = web.get('/admin/reminders', auth=('admin', PW)).text
    assert 'mem_a@buyer.example' in html and 'mem_b@buyer.example' in html and 'Waiting for approval' in html
    items = [f'{a}:activation_reminder_1', f'{b}:activation_reminder_1']
    assert release(web, items, 'SEND 1').status_code == 400
    assert release(web, items, 'yes').status_code == 400
    with connect(cfg) as db:
        assert db.execute('SELECT COUNT(*) AS n FROM reminder_approvals').fetchone()['n'] == 0
    assert release(web, items, 'SEND 2').status_code == 200
    with connect(cfg) as db:
        assert db.execute('SELECT COUNT(*) AS n FROM reminder_approvals').fetchone()['n'] == 2
    assert 'Approved' in web.get('/admin/reminders', auth=('admin', PW)).text


def test_release_needs_admin_and_same_origin(web, cfg):
    cid = add(cfg, 'mem_a')
    item = [f'{cid}:activation_reminder_1']
    assert web.post('/admin/reminders/release', data={'item': item, 'confirm': 'SEND 1'},
                    headers={'origin': BASE}).status_code == 401
    assert web.post('/admin/reminders/release', data={'item': item, 'confirm': 'SEND 1'}, auth=('admin', PW),
                    headers={'origin': 'https://evil.example'}).status_code == 403


def test_release_rejects_unknown_kinds_and_empty_selection(web, cfg):
    cid = add(cfg, 'mem_a')
    assert release(web, [f'{cid}:access_ended'], 'SEND 1').status_code == 400
    assert release(web, [], 'SEND 0').status_code == 400
