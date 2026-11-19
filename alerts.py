"""Post "needs attention" issues to a Discord or Slack channel.

Set ALERT_WEBHOOK_URL to a Discord webhook (discord.com/api/webhooks/...) or a
Slack incoming webhook (hooks.slack.com/...). Each issue is posted when first
seen and again once a day while it persists; resolved issues are forgotten, so
they alert again if they come back. Messages carry IDs only, never emails.
"""
import time
from urllib.parse import urlsplit

import httpx

REMIND_AFTER = 24 * 3600
MAX_LINES = 10
ICON = {'high': '🔴', 'medium': '🟠', 'low': '🟡'}


def due(db, issues, now):
    """Issues to announce now; also forgets keys that are no longer present."""
    current = {i['key'] for i in issues}
    seen = {r['key']: dict(r) for r in db.execute('SELECT key,first_seen,last_sent FROM alert_log')}
    for key in set(seen) - current:
        db.execute('DELETE FROM alert_log WHERE key=?', (key,))
    return [i for i in issues if i['key'] not in seen or now - seen[i['key']]['last_sent'] >= REMIND_AFTER]


def mark_sent(db, issues, now):
    for i in issues:
        db.execute('INSERT INTO alert_log(key,first_seen,last_sent) VALUES(?,?,?) '
                   'ON CONFLICT(key) DO UPDATE SET last_sent=excluded.last_sent', (i['key'], now, now))


def message(issues, base_url, total):
    lines = [f'**StartUpTrading: {total} item(s) need attention**' if total else '']
    for i in issues[:MAX_LINES]:
        lines.append(f'{ICON.get(i["severity"], "•")} {i["title"]}: {i["detail"]}')
    if len(issues) > MAX_LINES:
        lines.append(f'…and {len(issues) - MAX_LINES} more.')
    lines.append(f'{base_url}/admin/attention')
    return '\n'.join(l for l in lines if l)


def payload(url, text):
    host = (urlsplit(url).hostname or '').lower()
    if host.endswith('discord.com') or host.endswith('discordapp.com'):
        return {'content': text[:1900]}
    return {'text': text}


def valid_url(url):
    parts = urlsplit(url or '')
    return parts.scheme == 'https' and bool(parts.hostname) and not parts.username


async def notify(cfg, db_factory, issues, now=None, post=None):
    """Send one digest of new/overdue issues. Never raises: alerts must not break the worker."""
    if not valid_url(cfg.alert_webhook_url):
        return 'not_configured'
    now = now or int(time.time())
    with db_factory() as db:
        todo = due(db, issues, now)
    if not todo:
        return 'nothing_new'
    text = message(todo, cfg.public_base_url, len(issues))
    try:
        if post:
            ok = await post(cfg.alert_webhook_url, payload(cfg.alert_webhook_url, text))
        else:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(cfg.alert_webhook_url, json=payload(cfg.alert_webhook_url, text))
            ok = r.status_code < 300
    except Exception:
        ok = False
    if not ok:
        return 'failed'
    with db_factory() as db:
        mark_sent(db, todo, now)
    return 'sent'
