"""Member lifecycle emails, sent through the existing message_outbox.

  activation_reminder_1  24 h after a paying member is first seen without activating
  activation_reminder_2  72 h after, if still not activated
  access_ending          they cancelled but still have paid time left
  access_ended           an activated member's membership ended

The outbox gives each (customer, kind) at most one email, with retries and a
Resend idempotency key. Every email is re-checked against the customer's
current state right before sending, and dropped ("cancelled") if it no longer
applies, so nobody is reminded after activating or told their access ended
after they've rejoined.

Sent to the Whop purchase email (these are about the membership).
"""
import datetime as dt
import time

import httpx

import email_templates
from store import connect, customer

REMINDER_DELAYS = {'activation_reminder_1': 24 * 3600, 'activation_reminder_2': 72 * 3600}
KINDS = tuple(REMINDER_DELAYS) + ('access_ending', 'access_ended')


def _queue(db, cid, kind, email, due_at, now):
    db.execute("""INSERT INTO message_outbox(customer_id,kind,target_email,next_attempt_at,updated_at)
        VALUES(?,?,?,?,?) ON CONFLICT(customer_id,kind) DO NOTHING""", (cid, kind, email, due_at, now))


def _cancel(db, cid, kinds, now):
    for kind in kinds:
        db.execute("""UPDATE message_outbox SET status='cancelled',updated_at=?
            WHERE customer_id=? AND kind=? AND status IN ('pending','retry')""", (now, cid, kind))


def schedule_reminders(db, now=None):
    """Queue the two activation reminders for paying members who haven't activated."""
    now = now or int(time.time())
    rows = db.execute("""SELECT id,buyer_email FROM customers
        WHERE status='eligible' AND verified=0 AND buyer_email IS NOT NULL AND buyer_email<>''""").fetchall()
    for r in rows:
        for kind, delay in REMINDER_DELAYS.items():
            _queue(db, r['id'], kind, r['buyer_email'], now + delay, now)
    return len(rows)


def on_reconcile(db, before, entitled, cancelling, now=None):
    """Called by the engine after each Whop check, with the customer row as it was before."""
    now = now or int(time.time())
    cid, email = before['id'], before['buyer_email']
    if before.get('verified'):
        _cancel(db, cid, REMINDER_DELAYS, now)
    if entitled:
        _cancel(db, cid, ('access_ended',), now)
        if cancelling and before.get('verified'):
            _queue(db, cid, 'access_ending', email, now, now)
        elif not cancelling:
            _cancel(db, cid, ('access_ending',), now)
    else:
        _cancel(db, cid, ('access_ending',) + tuple(REMINDER_DELAYS), now)
        if before.get('status') == 'eligible' and before.get('verified'):
            _queue(db, cid, 'access_ended', email, now, now)


def still_applies(kind, c):
    if not c or c.get('status') == 'transferred':
        return False
    if kind in REMINDER_DELAYS:
        return c['status'] == 'eligible' and not c['verified']
    if kind == 'access_ending':
        return c['status'] == 'eligible' and bool(c['verified'])
    if kind == 'access_ended':
        return c['status'] == 'ineligible'
    return False


def _date(iso):
    try:
        d = dt.datetime.fromisoformat(str(iso).replace('Z', '+00:00'))
        return f'{d:%B} {d.day}, {d.year}'
    except (ValueError, TypeError):
        return 'the end of your billing period'


def render(kind, c, cfg):
    activate = cfg.public_base_url + '/'
    rejoin = cfg.checkout_url or activate
    support = cfg.support_email
    if kind == 'activation_reminder_1':
        return ('Your StartUpTrading indicators are waiting',
                email_templates.reminder_email(first=True, activation_url=activate, support_email=support))
    if kind == 'activation_reminder_2':
        return ('Need a hand activating your indicators?',
                email_templates.reminder_email(first=False, activation_url=activate, support_email=support))
    if kind == 'access_ending':
        when = _date(c.get('paid_through'))
        return (f'Your StartUpTrading access ends on {when}',
                email_templates.ending_email(when, cfg.whop_hub_url, support))
    if kind == 'access_ended':
        return ('Your StartUpTrading indicators have been switched off',
                email_templates.ended_email(rejoin, support))
    raise ValueError(kind)


def enabled(cfg):
    return bool(cfg.resend_api_key and cfg.resend_from)


def licensing_open_for(cfg, c):
    """Whether this member's licenses could actually be issued right now.

    Activation reminders tell a paying member to go and activate. While license
    writes are off, or limited to a test allowlist, a member outside it would
    activate and receive nothing, so their reminders are held (left pending,
    not cancelled) until licensing is open to their membership.
    """
    if not cfg.license_writes or not c:
        return False
    return c.get('membership_id') in {m for m, _ in cfg.write_allowlist()}


async def send(cfg, cid, kind, post=None):
    """Send one lifecycle email if it's due and still applies. Returns a status word."""
    if not enabled(cfg):
        return 'not_configured'
    now = int(time.time())
    with connect(cfg) as db:
        row = db.execute("SELECT * FROM message_outbox WHERE customer_id=? AND kind=?", (cid, kind)).fetchone()
        c = customer(db, cid)
        if not row or row['status'] not in ('pending', 'retry') or row['next_attempt_at'] > now:
            return 'not_due'
        row = dict(row)
        if kind in REMINDER_DELAYS and still_applies(kind, c) and not licensing_open_for(cfg, c):
            return 'held'
        if not still_applies(kind, c):
            _cancel(db, cid, (kind,), now)
            return 'cancelled'
        claimed = db.execute("""UPDATE message_outbox SET status='sending',updated_at=?
            WHERE customer_id=? AND kind=? AND status IN ('pending','retry')""", (now, cid, kind))
        if claimed.rowcount != 1:
            return 'not_due'
    subject, (text, html) = render(kind, c, cfg)
    body = {'from': cfg.resend_from, 'to': [row['target_email']], 'subject': subject, 'text': text, 'html': html}
    headers = {'Authorization': 'Bearer ' + cfg.resend_api_key, 'Idempotency-Key': f'sut-{kind}-{cid}-v1'}
    try:
        if post:
            message_id = await post(body, headers)
        else:
            async with httpx.AsyncClient(timeout=18) as client:
                resp = await client.post('https://api.resend.com/emails', headers=headers, json=body)
            if resp.status_code not in (200, 201, 202):
                raise RuntimeError(f'Resend HTTP {resp.status_code}')
            message_id = resp.json().get('id')
        if not message_id:
            raise RuntimeError('Resend response missing message ID')
        with connect(cfg) as db:
            db.execute("""UPDATE message_outbox SET status='sent',provider_message_id=?,last_error=NULL,updated_at=?
                WHERE customer_id=? AND kind=?""", (message_id, int(time.time()), cid, kind))
        return 'sent'
    except Exception as exc:
        with connect(cfg) as db:
            db.execute("""UPDATE message_outbox SET status='retry',attempts=attempts+1,next_attempt_at=?,
                last_error=?,updated_at=? WHERE customer_id=? AND kind=?""",
                       (int(time.time()) + min(3600, 60 * 2 ** min(row['attempts'], 6)), str(exc)[:180],
                        int(time.time()), cid, kind))
        return 'retry'
