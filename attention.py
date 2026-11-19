"""What needs an operator's attention, from the database alone (no Whop or
NinjaTrader calls, so it's cheap enough to run on every worker cycle).

Each issue has a stable `key` so alerts can be sent once and re-sent daily
while the problem persists. Issues carry IDs only, never customer emails, so
they're safe to post into a team chat.
"""
import time

from config import INDICATORS

ACTIVE_LICENSE_STATES = ('created', 'renewed', 'unchanged')
SUCCESS_AUDIT = ('ninjatrader_created', 'ninjatrader_renewed', 'ninjatrader_unchanged',
                 'ninjatrader_expired', 'ninjatrader_already_expired', 'ninjatrader_absent')
FAILURE_AUDIT = ('sync_error', 'reconcile_retry_needed')

HIGH, MEDIUM, LOW = 'high', 'medium', 'low'
ORDER = {HIGH: 0, MEDIUM: 1, LOW: 2}


def _issue(key, severity, title, detail, customer_id=None):
    return {'key': key, 'severity': severity, 'title': title, 'detail': detail,
            'customer_id': customer_id,
            'link': f'/admin/lifecycle/{customer_id}' if customer_id else '/admin'}


def find_issues(db, cfg, now=None):
    now = now or int(time.time())
    issues = []

    # 1. Paid members whose access should have ended but whose licenses still look active.
    for r in db.execute("""SELECT c.id, c.membership_id, COUNT(*) AS n FROM customers c
            JOIN licenses l ON l.customer_id=c.id
            WHERE c.status='ineligible' AND l.state IN ('created','renewed','unchanged')
            GROUP BY c.id, c.membership_id"""):
        issues.append(_issue(f'revoke:{r["id"]}', HIGH, 'Access ended but licenses not revoked',
                             f'{r["membership_id"]}: {r["n"]} license(s) still recorded as active', r['id']))

    # 2. License syncs whose latest outcome was a failure (last 7 days).
    for r in db.execute("""SELECT a.customer_id, a.action, a.details, a.at, c.membership_id FROM audit a
            JOIN customers c ON c.id=a.customer_id
            WHERE a.id IN (SELECT MAX(id) FROM audit WHERE customer_id IS NOT NULL AND action IN
                           ('sync_error','reconcile_retry_needed','ninjatrader_created','ninjatrader_renewed',
                            'ninjatrader_unchanged','ninjatrader_expired','ninjatrader_already_expired',
                            'ninjatrader_absent') GROUP BY customer_id)
              AND a.action IN ('sync_error','reconcile_retry_needed') AND a.at>?""", (now - 7 * 86400,)):
        issues.append(_issue(f'sync:{r["customer_id"]}', HIGH, 'License sync failing',
                             f'{r["membership_id"]}: {r["details"][:140]}', r['customer_id']))

    # 3. Verified, paying members on the write allowlist without all licenses after 30 minutes.
    allow = cfg.write_allowlist() if cfg.license_writes else set()
    for r in db.execute("""SELECT id, membership_id, nt_email, updated_at FROM customers
            WHERE status='eligible' AND verified=1 AND updated_at<?""", (now - 1800,)):
        if (r['membership_id'], (r['nt_email'] or '').casefold()) not in allow:
            continue
        have = db.execute("SELECT COUNT(*) AS n FROM licenses WHERE customer_id=? AND state IN ('created','renewed','unchanged')",
                          (r['id'],)).fetchone()['n']
        if have < len(INDICATORS):
            issues.append(_issue(f'licensing:{r["id"]}', HIGH, 'Paying member missing licenses',
                                 f'{r["membership_id"]}: {have}/{len(INDICATORS)} indicators active', r['id']))

    # 4. Webhook events that failed or couldn't be matched to a membership.
    for r in db.execute("""SELECT webhook_id, event_type, state, last_error FROM webhook_events
            WHERE state IN ('retry','needs_mapping') ORDER BY received_at DESC LIMIT 50"""):
        issues.append(_issue(f'webhook:{r["webhook_id"]}', MEDIUM,
                             'Whop event needs mapping' if r['state'] == 'needs_mapping' else 'Whop event failing',
                             f'{r["event_type"]}' + (f': {r["last_error"][:120]}' if r['last_error'] else '')))

    # 5. Events stuck in the queue: the background worker may not be running.
    stuck = db.execute("SELECT COUNT(*) AS n FROM webhook_events WHERE state='queued' AND received_at<?",
                       (now - 1800,)).fetchone()['n']
    if stuck:
        issues.append(_issue('worker:stalled', HIGH, 'Background worker may be stopped',
                             f'{stuck} Whop event(s) queued for over 30 minutes. Check RUN_RECONCILER=true and Render logs.'))

    # 6. Emails that keep failing.
    for r in db.execute("""SELECT o.customer_id, o.kind, o.attempts, o.last_error, c.membership_id FROM message_outbox o
            JOIN customers c ON c.id=o.customer_id WHERE o.status='retry' AND o.attempts>=3"""):
        issues.append(_issue(f'email:{r["customer_id"]}:{r["kind"]}', MEDIUM, 'Email failing',
                             f'{r["membership_id"]} {r["kind"]}: {r["attempts"]} attempts'
                             + (f', {r["last_error"][:100]}' if r['last_error'] else ''), r['customer_id']))

    # 7. CRM sync that keeps failing.
    for r in db.execute("""SELECT s.customer_id, s.attempts, s.last_error, c.membership_id FROM crm_sync s
            JOIN customers c ON c.id=s.customer_id WHERE s.status='retry' AND s.attempts>=3"""):
        issues.append(_issue(f'crm:{r["customer_id"]}', LOW, 'CRM sync failing',
                             f'{r["membership_id"]}: {r["attempts"]} attempts', r['customer_id']))

    # 8. Paying members who haven't activated after 3 days (one summary line, not per person).
    n = db.execute("""SELECT COUNT(*) AS n FROM customers c WHERE c.status='eligible' AND c.verified=0
            AND EXISTS (SELECT 1 FROM message_outbox o WHERE o.customer_id=c.id AND o.kind='activation_reminder_2'
                        AND o.status='sent')""").fetchone()['n']
    if n:
        issues.append(_issue('unactivated', LOW, 'Paid but not activated',
                             f'{n} member(s) still not activated after both reminder emails. Consider a personal message.'))

    issues.sort(key=lambda i: ORDER[i['severity']])
    return issues
