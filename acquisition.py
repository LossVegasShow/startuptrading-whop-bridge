"""Acquisition attribution and revenue, server side (acquisition.py).

Three verified joins, no personal data in any report:

1. Visitor -> membership: the activation app receives the browser's anonymous
   attribution (sales-site tracking.js sutHandoff, on links from /welcome and
   /setup), keeps it in a short-lived cookie through Whop sign-in, and stores it
   ONCE per Whop membership (customer_attribution). Later sign-ins never overwrite it.
2. Membership -> revenue: Whop's signed payment webhooks (payment.*) are the source
   of truth. Only non-personal fields are kept (payments). Refunds have no webhook,
   so recent paid payments are re-read from the Whop API (refresh_payments).
3. Membership -> activation: the existing customers / licenses tables.

Reports exclude internal QA memberships and emails (MARKETING_EXCLUDE_MEMBERSHIPS,
MARKETING_EXCLUDE_EMAILS) and never count $0 payments as revenue. Anything we
can't measure is reported as unavailable, never estimated silently.
See growth/MARKETING_ANALYTICS.md.
"""
import datetime as dt
import json
import re
import time
from urllib.parse import quote

import httpx

from config import INDICATORS, PRODUCT_ID, COMMUNITY_PRODUCT_ID, BUSINESS_ID

# The acquisition channel taxonomy. Same keys as sales-site/src/tracking.js sutChannel.
CHANNELS = {
    'google_organic': 'Google organic search', 'google_paid': 'Google paid advertising',
    'tradingview': 'TradingView', 'youtube': 'YouTube', 'instagram': 'Instagram', 'facebook': 'Facebook',
    'tiktok': 'TikTok', 'discord': 'Discord', 'reddit': 'Reddit', 'x_twitter': 'X / Twitter',
    'ai_referral': 'ChatGPT & AI assistants', 'affiliate': 'Affiliate referrals', 'email': 'Email campaigns',
    'direct': 'Direct', 'other_referral': 'Other referrals', 'unknown': 'Unknown',
}
PAID_CHANNELS = {'google_paid'}
PAID_MEDIUMS = {'cpc', 'ppc', 'paid', 'paidsearch', 'paid_search', 'paidsocial', 'paid_social', 'display', 'cpm', 'cpv', 'ads'}

# Hand-off keys (sut_<key>) -> customer_attribution columns.
HANDOFF = {'vid': 'visitor_id', 'fs': 'first_source', 'fm': 'first_medium', 'fc': 'first_campaign',
           'fx': 'first_content', 'fch': 'first_channel', 'fl': 'first_landing', 'ft': 'first_at',
           'ls': 'last_source', 'lm': 'last_medium', 'lc': 'last_campaign', 'lx': 'last_content',
           'lch': 'last_channel', 'aff': 'affiliate', 'gcid': 'ga_client_id'}
# Columns of customer_attribution (ga_client_id lives in ga_clients).
ATTR_COLS = [c for c in HANDOFF.values() if c != 'ga_client_id']
GA_CLIENT = re.compile(r'\d{4,12}\.\d{6,12}')
_SAFE = re.compile(r'^[A-Za-z0-9 _.,:/()+\-%]{1,120}$')

ATTR_COOKIE = 'sut_attr'


def parse_handoff(params):
    """Validated attribution from the activation link's sut_* query parameters."""
    out = {}
    for key, col in HANDOFF.items():
        v = str(params.get('sut_' + key) or '').strip()
        if not v or not _SAFE.match(v) or '@' in v:
            continue
        if col == 'visitor_id' and not re.fullmatch(r'[a-f0-9]{16,32}', v):
            continue
        if col == 'ga_client_id' and not GA_CLIENT.fullmatch(v):
            continue
        if col.endswith('_channel') and v not in CHANNELS:
            continue
        if col == 'first_at':
            if not v.isdigit():
                continue
            v = int(v) // 1000 if len(v) > 10 else int(v)
        out[col] = v
    return out


def cookie_value(data):
    return quote(json.dumps(data, separators=(',', ':')))


def read_cookie(raw):
    if not raw or len(raw) > 2048:
        return {}
    try:
        from urllib.parse import unquote
        data = json.loads(unquote(raw))
    except (ValueError, TypeError):
        return {}
    return parse_handoff({'sut_' + k: data.get(col) for k, col in HANDOFF.items()}) if isinstance(data, dict) else {}


def record_attribution(db, membership_id, customer_id, data, method='activation_link', now=None):
    """Store a membership's acquisition data once. Never overwrites: the first
    attribution captured for a membership is its original acquisition."""
    if not data or not str(membership_id).startswith('mem_'):
        return False
    cols = [c for c in ATTR_COLS if c in data]
    if not cols:
        return False
    vals = [data[c] for c in cols]
    sql = (f"INSERT INTO customer_attribution(membership_id,customer_id,{','.join(cols)},method,captured_at) "
           f"VALUES(?,?,{','.join('?' * len(cols))},?,?) ON CONFLICT(membership_id) DO NOTHING")
    cur = db.execute(sql, (membership_id, customer_id, *vals, method, now or int(time.time())))
    return cur.rowcount == 1


def ga_client_from_cookie(raw):
    """GA4's client id from the _ga cookie (shared across *.startuptrading.com)."""
    m = re.fullmatch(r'GA\d\.\d\.(\d{4,12}\.\d{6,12})', str(raw or '').strip())
    return m.group(1) if m else ''


def record_ga_client(db, membership_id, client_id, source, now=None):
    """The GA4 client id for a membership, kept once (the buyer's browser at activation)."""
    if not client_id or not GA_CLIENT.fullmatch(client_id) or not str(membership_id).startswith('mem_'):
        return False
    cur = db.execute('INSERT INTO ga_clients(membership_id,client_id,source,captured_at) VALUES(?,?,?,?) '
                     'ON CONFLICT(membership_id) DO NOTHING', (membership_id, client_id, source[:30], now or int(time.time())))
    return cur.rowcount == 1


# --- Free community (Discord) ---------------------------------------------------------

def is_community_membership(m):
    """A verified Whop membership of the free StartUpTrading Community product."""
    if not isinstance(m, dict):
        return False
    prod = m.get('product') if isinstance(m.get('product'), dict) else {}
    acct = m.get('account') if isinstance(m.get('account'), dict) else {}
    account = m.get('account_id') or acct.get('id')
    return (m.get('product_id') or prod.get('id')) == COMMUNITY_PRODUCT_ID and (not account or account == BUSINESS_ID)


def record_community_member(db, m, now=None):
    """Upsert a community membership (no personal data: ids, status, join date)."""
    if not is_community_membership(m) or not str(m.get('id', '')).startswith('mem_'):
        return False
    user = m.get('user_id') or ((m.get('user') or {}).get('id') if isinstance(m.get('user'), dict) else None)
    db.execute("""INSERT INTO community_members(membership_id,whop_user_id,status,joined_at,updated_at) VALUES(?,?,?,?,?)
        ON CONFLICT(membership_id) DO UPDATE SET status=excluded.status, updated_at=excluded.updated_at""",
               (m['id'], user if str(user or '').startswith('user_') else None, str(m.get('status') or '')[:30],
                m.get('created_at'), now or int(time.time())))
    return True


def community_report(db, start=None, end=None):
    """Free community joins and upgrades to the paid membership (verified, from Whop)."""
    rows = [dict(r) for r in db.execute('SELECT * FROM community_members')]
    paid_users = {r['whop_user_id']: r for r in db.execute(
        "SELECT whop_user_id, membership_id, status FROM customers WHERE whop_user_id IS NOT NULL AND status<>'transferred'")}
    revenue = {}
    for p in db.execute("SELECT membership_id, usd_total, total, refunded_amount FROM payments WHERE status='paid' AND total>0"):
        revenue[p['membership_id']] = revenue.get(p['membership_id'], 0) + \
            (p['usd_total'] if p['usd_total'] is not None else p['total'] or 0) - (p['refunded_amount'] or 0)

    def in_range(r):
        t = _ts(r['joined_at']) or r['updated_at']
        return (start is None or t >= start) and (end is None or t < end)
    joined = [r for r in rows if in_range(r)]
    upgraded = [r for r in joined if r['whop_user_id'] in paid_users]
    up_rev = sum(revenue.get(paid_users[r['whop_user_id']]['membership_id'], 0) for r in upgraded)
    return {'joined': len(joined), 'active': sum(1 for r in joined if r['status'] in ('active', 'completed', 'trialing')),
            'upgraded': len(upgraded), 'upgrade_rate': round(100 * len(upgraded) / len(joined), 1) if joined else None,
            'upgraded_revenue': round(up_rev, 2)}


# --- Payments ------------------------------------------------------------------------

def _money(v):
    if isinstance(v, dict):
        v = v.get('amount')
    try:
        return round(float(v), 2) if v not in (None, '') else None
    except (TypeError, ValueError):
        return None


def payment_row(p):
    """The non-personal fields of a Whop payment. Never the buyer's email, name,
    phone, address, IP, user agent, card or license details."""
    if not isinstance(p, dict) or not str(p.get('id', '')).startswith('pay_'):
        return None
    ref = p.get('membership_id') or ((p.get('membership') or {}).get('id') if isinstance(p.get('membership'), dict) else None)
    return {'id': p['id'], 'membership_id': ref if str(ref or '').startswith('mem_') else None,
            'product_id': p.get('product_id'), 'plan_id': p.get('variant_id') or p.get('plan_id'),
            'status': p.get('status'), 'substatus': p.get('substatus'), 'billing_reason': p.get('billing_reason'),
            'currency': p.get('currency'), 'total': _money(p.get('total')), 'usd_total': _money(p.get('usd_total')),
            'refunded_amount': _money(p.get('refunded_amount')) or 0.0, 'promo_code_id': p.get('promo_code_id'),
            'checkout_origin': (p.get('checkout_origin') or '')[:120] or None,
            'checkout_surface': p.get('checkout_surface'), 'checkout_configuration_id': p.get('checkout_configuration_id'),
            'paid_at': p.get('paid_at'), 'refunded_at': p.get('refunded_at'), 'created_at': p.get('created_at'),
            'updated_at': p.get('updated_at') or p.get('created_at') or ''}


PAYMENT_COLS = ('membership_id', 'product_id', 'plan_id', 'status', 'substatus', 'billing_reason', 'currency', 'total',
                'usd_total', 'refunded_amount', 'promo_code_id', 'checkout_origin', 'checkout_surface',
                'checkout_configuration_id', 'paid_at', 'refunded_at', 'created_at', 'updated_at')


def record_payment(db, payment, source, now=None):
    """Upsert one payment. Idempotent (webhook retries) and order-safe: an older
    copy (by updated_at) never replaces a newer one."""
    row = payment_row(payment)
    if not row:
        return False
    now = now or int(time.time())
    have = db.execute('SELECT updated_at FROM payments WHERE id=?', (row['id'],)).fetchone()
    if have and (have['updated_at'] or '') > (row['updated_at'] or ''):
        return False
    if have:
        db.execute(f"UPDATE payments SET {','.join(c + '=?' for c in PAYMENT_COLS)},last_source=?,received_at=? WHERE id=?",
                   (*[row[c] for c in PAYMENT_COLS], source[:60], now, row['id']))
    else:
        db.execute(f"INSERT INTO payments(id,{','.join(PAYMENT_COLS)},last_source,received_at) "
                   f"VALUES(?,{','.join('?' * len(PAYMENT_COLS))},?,?)",
                   (row['id'], *[row[c] for c in PAYMENT_COLS], source[:60], now))
    return True


async def refresh_payments(cfg, connect, limit=25, days=120, stale_hours=12):
    """Re-read recent paid payments from Whop so refunds and disputes show up
    (Whop has no refund webhook). Best effort: any failure is left for next time."""
    if not cfg.whop_api_key:
        return 0
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).isoformat()
    stale = int(time.time()) - stale_hours * 3600
    with connect(cfg) as db:
        ids = [r['id'] for r in db.execute(
            "SELECT id FROM payments WHERE status='paid' AND created_at>? AND received_at<? ORDER BY received_at LIMIT ?",
            (cutoff, stale, limit))]
    done = 0
    async with httpx.AsyncClient(timeout=18) as client:
        for pid in ids:
            try:
                r = await client.get(f'https://api.whop.com/api/v1/payments/{pid}', headers={
                    'Authorization': f'Bearer {cfg.whop_api_key}', 'Api-Version-Date': cfg.whop_api_version})
            except httpx.HTTPError:
                break
            if r.status_code != 200:
                continue
            data = r.json()
            with connect(cfg) as db:
                record_payment(db, data.get('data', data) if isinstance(data, dict) else {}, 'api_refresh')
                db.execute('UPDATE payments SET received_at=? WHERE id=?', (int(time.time()), pid))
            done += 1
    return done


# --- Reporting -----------------------------------------------------------------------

def _csv(v):
    return {x.strip().lower() for x in str(v or '').split(',') if x.strip()}


def _ts(iso):
    try:
        return int(dt.datetime.fromisoformat(str(iso).replace('Z', '+00:00')).timestamp())
    except (TypeError, ValueError):
        return None


def is_paid_traffic(channel, medium):
    return channel in PAID_CHANNELS or str(medium or '').lower() in PAID_MEDIUMS


def report(cfg, db, start=None, end=None, basis='first', channel='', campaign='', landing='', affiliate='',
           traffic='', now=None):
    """Verified subscription, activation and revenue metrics by acquisition.
    Dates filter on when a subscriber was first seen (subscribers) and when money
    moved (revenue)."""
    now = now or int(time.time())
    excl_mem, excl_email = _csv(cfg.marketing_exclude_memberships), _csv(cfg.marketing_exclude_emails)
    customers = [dict(r) for r in db.execute('SELECT id,membership_id,buyer_email,nt_email,verified,status FROM customers')]
    first_seen = {r['customer_id']: r['t'] for r in db.execute(
        'SELECT customer_id, MIN(at) AS t FROM audit WHERE customer_id IS NOT NULL GROUP BY customer_id')}
    attribution = {r['membership_id']: dict(r) for r in db.execute('SELECT * FROM customer_attribution')}
    licensed = {}
    for r in db.execute("SELECT customer_id, product_id, license_id, state FROM licenses"):
        if int(r['product_id']) in INDICATORS and (r['license_id'] or r['state'] == 'owned_separately') \
                and r['state'] not in ('expired', 'already_expired', 'absent'):
            licensed.setdefault(r['customer_id'], set()).add(int(r['product_id']))
    # Only the paid membership's payments ever count (the free community is a separate product).
    payments = [dict(r) for r in db.execute('SELECT * FROM payments') if r['product_id'] in (None, '', PRODUCT_ID)]

    excluded = set()
    for c in customers:
        if c['membership_id'].lower() in excl_mem or (c['buyer_email'] or '').lower() in excl_email \
                or (c['nt_email'] or '').lower() in excl_email:
            excluded.add(c['membership_id'])
    excluded |= {m for m in excl_mem if m.startswith('mem_')}

    def dims(mem):
        a = attribution.get(mem) or {}
        ch = a.get(f'{basis}_channel') or (a.get('first_channel') if basis == 'last' else None) or 'unknown'
        med = a.get(f'{basis}_medium') or a.get('first_medium')
        return {'channel': ch if ch in CHANNELS else 'unknown', 'campaign': a.get(f'{basis}_campaign') or a.get('first_campaign') or '',
                'landing': a.get('first_landing') or '', 'affiliate': a.get('affiliate') or '',
                'paid': is_paid_traffic(ch, med), 'captured': bool(a)}

    def keep(d):
        return ((not channel or d['channel'] == channel) and (not campaign or d['campaign'] == campaign)
                and (not landing or d['landing'] == landing) and (not affiliate or d['affiliate'] == affiliate)
                and (not traffic or (traffic == 'paid') == d['paid']))

    def in_range(t):
        return t is not None and (start is None or t >= start) and (end is None or t < end)

    pay_by_mem = {}
    for p in payments:
        if p['membership_id']:
            pay_by_mem.setdefault(p['membership_id'], []).append(p)

    rows, lands = {}, {}
    totals = {'subscribers': 0, 'paying': 0, 'promo_only': 0, 'activated': 0, 'linked': 0, 'churned': 0,
              'revenue': 0.0, 'refunds': 0.0, 'initial_revenue': 0.0, 'renewal_revenue': 0.0,
              'failed_payments': 0, 'refunded_payments': 0, 'attribution_captured': 0, 'excluded': len(excluded),
              'mrr': 0.0}
    for c in customers:
        mem = c['membership_id']
        if mem in excluded or c['status'] == 'transferred':
            continue
        d = dims(mem)
        if not keep(d):
            continue
        r = rows.setdefault(d['channel'], {'channel': d['channel'], 'label': CHANNELS[d['channel']], 'subscribers': 0,
                                           'paying': 0, 'activated': 0, 'revenue': 0.0, 'refunds': 0.0, 'churned': 0})
        lp = lands.setdefault(d['landing'] or '(not captured)', {'landing': d['landing'] or '(not captured)', 'subscribers': 0,
                                                                  'paying': 0, 'activated': 0, 'revenue': 0.0, 'refunds': 0.0})
        pays = pay_by_mem.get(mem, [])
        paid = [p for p in pays if p['status'] == 'paid' and (p['total'] or 0) > 0]
        rev = sum((p['usd_total'] if p['usd_total'] is not None else p['total'] or 0) for p in paid if in_range(_ts(p['paid_at'] or p['created_at'])))
        ref = sum(p['refunded_amount'] or 0 for p in paid if in_range(_ts(p['refunded_at'] or p['paid_at'])))
        r['revenue'] += rev; r['refunds'] += ref
        lp['revenue'] += rev; lp['refunds'] += ref
        totals['revenue'] += rev; totals['refunds'] += ref
        # A membership's first paid payment is its initial purchase; every later one is a renewal.
        # (Independent of Whop's billing_reason wording.)
        for n, p in enumerate(sorted(paid, key=lambda p: p['paid_at'] or p['created_at'] or '')):
            if in_range(_ts(p['paid_at'] or p['created_at'])):
                totals['renewal_revenue' if n else 'initial_revenue'] += (p['usd_total'] if p['usd_total'] is not None else p['total'] or 0)
        totals['failed_payments'] += sum(1 for p in pays if p['status'] in ('failed', 'uncollectible') and in_range(_ts(p['created_at'])))
        totals['refunded_payments'] += sum(1 for p in paid if (p['refunded_amount'] or 0) > 0)
        if not in_range(first_seen.get(c['id'])):
            continue
        r['subscribers'] += 1; totals['subscribers'] += 1; lp['subscribers'] += 1
        totals['attribution_captured'] += d['captured']
        if paid:
            r['paying'] += 1; totals['paying'] += 1; lp['paying'] += 1
            if c['status'] == 'eligible':
                # Estimate: the latest payment net of refunds, annual plans spread over 12 months.
                last = max(paid, key=lambda p: p['paid_at'] or p['created_at'] or '')
                amount = (last['usd_total'] if last['usd_total'] is not None else last['total'] or 0) - (last['refunded_amount'] or 0)
                if amount > 0:
                    totals['mrr'] += amount / 12 if 'B84PWlvXemyfX' in str(last['plan_id']) else amount
        elif pays or c['status'] == 'eligible':
            totals['promo_only'] += 1
        if c['verified']:
            totals['linked'] += 1
        if licensed.get(c['id']) == set(INDICATORS):
            r['activated'] += 1; totals['activated'] += 1; lp['activated'] += 1
        if c['status'] == 'ineligible':
            r['churned'] += 1; totals['churned'] += 1

    for r in lands.values():
        r['net_revenue'] = round(r['revenue'] - r['refunds'], 2)
    for r in rows.values():
        r['net_revenue'] = round(r['revenue'] - r['refunds'], 2)
        r['ltv'] = round(r['net_revenue'] / r['paying'], 2) if r['paying'] else None
        r['activation_rate'] = round(100 * r['activated'] / r['subscribers'], 1) if r['subscribers'] else None
    t = totals
    t['net_revenue'] = round(t['revenue'] - t['refunds'], 2)
    t['mrr'] = round(t['mrr'], 2)
    t['ltv'] = round(t['net_revenue'] / t['paying'], 2) if t['paying'] else None
    t['activation_rate'] = round(100 * t['activated'] / t['subscribers'], 1) if t['subscribers'] else None
    t['churn_rate'] = round(100 * t['churned'] / t['subscribers'], 1) if t['subscribers'] else None
    t['attribution_rate'] = round(100 * t['attribution_captured'] / t['subscribers'], 1) if t['subscribers'] else None
    order = list(CHANNELS)
    return {'totals': t, 'landing_rows': sorted(lands.values(), key=lambda r: -r['net_revenue']), 'channels': sorted(rows.values(), key=lambda r: (-r['net_revenue'], order.index(r['channel']))),
            'campaigns': sorted({a.get('first_campaign') for a in attribution.values() if a.get('first_campaign')} |
                                {a.get('last_campaign') for a in attribution.values() if a.get('last_campaign')}),
            'landings': sorted({a.get('first_landing') for a in attribution.values() if a.get('first_landing')}),
            'affiliates': sorted({a.get('affiliate') for a in attribution.values() if a.get('affiliate')})}


# --- GA4 Measurement Protocol: verified server events --------------------------------
# Purchases, refunds and activation milestones are sent from here, never from the
# browser, so a page reload or a shared /welcome link can't create a conversion.
# Each event is sent once (ga_events_sent), without personal data, and never for
# QA memberships. A buyer whose GA4 client id never reached us is still counted,
# after 72 hours, under a stable anonymous id (GA4 then reports it as unattributed).

MP_URL = 'https://www.google-analytics.com/mp/collect'


def _excluded_memberships(cfg, customers):
    excl_mem, excl_email = _csv(cfg.marketing_exclude_memberships), _csv(cfg.marketing_exclude_emails)
    out = {m for m in excl_mem if m.startswith('mem_')}
    for c in customers:
        if c['membership_id'].lower() in excl_mem or (c['buyer_email'] or '').lower() in excl_email \
                or (c['nt_email'] or '').lower() in excl_email:
            out.add(c['membership_id'])
    return out


def _anon_client(mem):
    import hashlib
    h = int(hashlib.sha256(('sut:' + mem).encode()).hexdigest()[:15], 16)
    return f'{h % 10**10}.{1700000000 + h % 10**8}'


def pending_ga_events(cfg, db, now=None):
    """[(event_key, client_id, event, timestamp)] not yet sent."""
    now = now or int(time.time())
    from config import PLANS
    sent = {r['event_key'] for r in db.execute('SELECT event_key FROM ga_events_sent')}
    customers = [dict(r) for r in db.execute('SELECT id,membership_id,buyer_email,nt_email,verified,status FROM customers')]
    excluded = _excluded_memberships(cfg, customers)
    clients = {r['membership_id']: r['client_id'] for r in db.execute('SELECT membership_id,client_id FROM ga_clients')}
    channel = {r['membership_id']: r['first_channel'] for r in db.execute('SELECT membership_id,first_channel FROM customer_attribution')}
    out = []

    def client_for(mem, since):
        if mem in clients:
            return clients[mem]
        return _anon_client(mem) if since and now - since > 72 * 3600 else None

    by_mem = {}
    for p in db.execute("SELECT * FROM payments WHERE status='paid' AND total>0 AND membership_id IS NOT NULL"):
        if p['product_id'] not in (None, '', PRODUCT_ID):
            continue
        by_mem.setdefault(p['membership_id'], []).append(dict(p))
    for mem, pays in by_mem.items():
        if mem in excluded:
            continue
        for n, p in enumerate(sorted(pays, key=lambda p: p['paid_at'] or p['created_at'] or '')):
            paid_ts = _ts(p['paid_at'] or p['created_at'])
            client = client_for(mem, paid_ts or p['received_at'])
            if not client:
                continue
            value = p['usd_total'] if p['usd_total'] is not None else p['total']
            currency = 'USD' if p['usd_total'] is not None else str(p['currency'] or 'usd').upper()
            ts = paid_ts if paid_ts and now - paid_ts < 71 * 3600 else None
            key = 'purchase:' + p['id']
            if key not in sent:
                out.append((key, client, {'name': 'purchase', 'params': {
                    'transaction_id': p['id'], 'value': value, 'currency': currency, 'affiliation': 'whop',
                    'coupon': p['promo_code_id'] or '', 'purchase_type': 'renewal' if n else 'initial',
                    'acquisition_channel': channel.get(mem) or 'unknown', 'engagement_time_msec': 1,
                    'items': [{'item_id': p['plan_id'] or 'membership', 'item_name': PLANS.get(p['plan_id'], 'StartUpTrading membership'),
                               'price': value, 'quantity': 1}]}}, ts))
            refunded = p['refunded_amount'] or 0
            key = f'refund:{p["id"]}:{refunded:.2f}'
            if refunded > 0 and key not in sent:
                out.append((key, client, {'name': 'refund', 'params': {
                    'transaction_id': p['id'], 'value': refunded, 'currency': currency, 'engagement_time_msec': 1}}, None))
    licensed = {}
    for r in db.execute('SELECT customer_id, product_id, license_id, state FROM licenses'):
        if int(r['product_id']) in INDICATORS and (r['license_id'] or r['state'] == 'owned_separately') \
                and r['state'] not in ('expired', 'already_expired', 'absent'):
            licensed.setdefault(r['customer_id'], set()).add(int(r['product_id']))
    for c in customers:
        mem = c['membership_id']
        if mem in excluded or c['status'] == 'transferred' or mem not in clients:
            continue
        base = {'acquisition_channel': channel.get(mem) or 'unknown', 'engagement_time_msec': 1}
        if c['verified'] and 'linked:' + mem not in sent:
            out.append(('linked:' + mem, clients[mem], {'name': 'ninjatrader_linked', 'params': dict(base)}, None))
        if licensed.get(c['id']) == set(INDICATORS) and 'activated:' + mem not in sent:
            out.append(('activated:' + mem, clients[mem], {'name': 'activation_complete', 'params': dict(base)}, None))
        if c['status'] == 'ineligible' and c['verified'] and 'cancel:' + mem not in sent:
            out.append(('cancel:' + mem, clients[mem], {'name': 'subscription_cancel', 'params': dict(base)}, None))
    return out


async def ga_sync(cfg, connect, now=None, post=None, limit=50):
    """Send pending verified events to GA4. Needs GA4_MEASUREMENT_ID + GA4_API_SECRET."""
    if not (cfg.ga4_measurement_id and cfg.ga4_api_secret):
        return 0
    with connect(cfg) as db:
        events = pending_ga_events(cfg, db, now)[:limit]
    if not events:
        return 0
    url = f'{MP_URL}?measurement_id={quote(cfg.ga4_measurement_id)}&api_secret={quote(cfg.ga4_api_secret)}'
    sent = 0
    async with httpx.AsyncClient(timeout=10) as client:
        for key, client_id, event, ts in events:
            body = {'client_id': client_id, 'non_personalized_ads': True, 'events': [event]}
            if ts:
                body['timestamp_micros'] = int(ts) * 1_000_000
            try:
                r = await (post(url, body) if post else client.post(url, json=body))
            except httpx.HTTPError:
                break
            if 200 <= r.status_code < 300:
                with connect(cfg) as db:
                    db.execute('INSERT INTO ga_events_sent(event_key,sent_at) VALUES(?,?) ON CONFLICT(event_key) DO NOTHING',
                               (key, int(time.time())))
                sent += 1
    return sent
