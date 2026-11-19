"""Read-only lifecycle snapshot for one customer, used during the Phase 3 live test.

For each step of the test (buy, activate, renew, cancel, expire, restore) an
operator opens /admin/lifecycle/{customer_id} and sees, side by side:

  * what Whop says (membership status, paid-through date, entitlement),
  * what our database recorded (customer row, license rows, emails, audit),
  * what NinjaTrader actually has (licenses for the linked email),

plus a per-indicator verdict: does NinjaTrader match what Whop entitles?

Nothing here writes anywhere. It only calls the Whop membership GET and the
NinjaTrader license-list GET; the create/update methods are never used.
"""
import datetime as dt

from clients import IntegrationError, membership_entitlement, membership_plan_id, parse_utc
from config import INDICATORS
from store import connect, customer

# NinjaTrader expiry may differ from Whop's paid-through by a few seconds of rounding.
TOLERANCE_SECONDS = 60


def write_gate(cfg, c):
    """Explain whether the engine is allowed to write licenses for this customer."""
    if not cfg.license_writes:
        return {'allowed': False, 'reason': 'LICENSE_WRITES_ENABLED is false (observe-only)'}
    if not c.get('verified') or not c.get('nt_email'):
        return {'allowed': False, 'reason': 'NinjaTrader email not verified yet'}
    pairs = cfg.write_allowlist()
    key = (c['membership_id'], c['nt_email'].casefold())
    if key in pairs:
        return {'allowed': True, 'reason': 'membership and NinjaTrader email are on the write allowlist'}
    return {'allowed': False, 'reason': 'membership/email pair is not on the write allowlist'}


def expected_state(entitlement):
    if entitlement:
        return {'licensed': True, 'until': entitlement['paid_through']}
    return {'licensed': False, 'until': None}


def verdict(expected, remote_rows, now=None):
    """Compare NinjaTrader's rows for one product with what Whop entitles."""
    now = now or dt.datetime.now(dt.timezone.utc)
    if remote_rows is None:
        return {'status': 'unknown', 'detail': 'NinjaTrader licenses could not be read'}
    if len(remote_rows) > 1:
        return {'status': 'mismatch', 'detail': f'{len(remote_rows)} licenses for this email (expected at most 1)'}
    row = remote_rows[0] if remote_rows else None
    exp = parse_utc(row.get('expirationDateUTC')) if row else None
    active = bool(row) and (exp is None or exp > now)
    if expected['licensed']:
        if not row:
            return {'status': 'mismatch', 'detail': 'entitled, but no NinjaTrader license exists'}
        if exp is None:
            return {'status': 'mismatch', 'detail': 'license has no expiry (lifetime); bridge cannot enforce it'}
        want = parse_utc(expected['until'])
        if not active:
            return {'status': 'mismatch', 'detail': 'entitled, but the NinjaTrader license is expired'}
        if want and abs((exp - want).total_seconds()) > TOLERANCE_SECONDS:
            return {'status': 'mismatch', 'detail': f'license expires {row.get("expirationDateUTC")}, '
                                                    f'Whop paid-through is {expected["until"]}'}
        return {'status': 'ok', 'detail': f'active until {row.get("expirationDateUTC")}'}
    if active:
        return {'status': 'mismatch', 'detail': 'NOT entitled, but the NinjaTrader license is still active'}
    return {'status': 'ok', 'detail': 'no active license' + (f' (expired {row.get("expirationDateUTC")})' if row else '')}


async def snapshot(cfg, engine, cid):
    with connect(cfg) as db:
        c = customer(db, cid)
        if not c:
            raise IntegrationError('Customer not found')
        db_licenses = [dict(r) for r in db.execute(
            'SELECT product_id,license_id,expiration,state,updated_at FROM licenses WHERE customer_id=? ORDER BY product_id', (cid,))]
        outbox = [dict(r) for r in db.execute(
            'SELECT kind,status,attempts,last_error,updated_at FROM message_outbox WHERE customer_id=?', (cid,))]
        recent = [dict(r) for r in db.execute(
            'SELECT at,action,details FROM audit WHERE customer_id=? ORDER BY id DESC LIMIT 20', (cid,))]

    out = {
        'customer': {k: c.get(k) for k in ('id', 'membership_id', 'whop_user_id', 'status', 'plan_id', 'paid_through',
                                           'buyer_email_verified', 'verified', 'nt_email', 'onboarding_path')},
        'write_gate': write_gate(cfg, c),
        'database': {'licenses': db_licenses, 'emails': outbox, 'recent_audit': recent},
    }

    # Whop: the source of truth for entitlement.
    entitlement = None
    try:
        m = await engine.whop.membership(c['membership_id'])
        entitlement = membership_entitlement(m)
        out['whop'] = {'status': (m or {}).get('status'), 'plan_id': membership_plan_id(m) if m else None,
                       'current_period_end': (m or {}).get('current_period_end'),
                       'cancel_at_period_end': (m or {}).get('cancel_at_period_end'),
                       'user_id_matches': (m or {}).get('user_id') == c.get('whop_user_id'),
                       'entitled': bool(entitlement),
                       'paid_through': entitlement['paid_through'] if entitlement else None}
    except Exception as exc:  # report, never raise: the snapshot must still render
        out['whop'] = {'error': str(exc)[:200]}
    expected = expected_state(entitlement) if 'error' not in out['whop'] else None

    # NinjaTrader: what is actually licensed to the linked email.
    remote = {}
    nt_ready = all([cfg.nt_username, cfg.nt_password, cfg.nt_cid, cfg.nt_sec])
    if c.get('nt_email') and nt_ready:
        for pid in INDICATORS:
            try:
                rows = await engine.nt.licenses(pid)
                remote[pid] = [{'id': r.get('id'), 'expirationDateUTC': r.get('expirationDateUTC')}
                               for r in rows if str(r.get('email', '')).casefold() == c['nt_email'].casefold()]
            except Exception as exc:
                remote[pid] = None
                out.setdefault('ninjatrader_errors', {})[pid] = str(exc)[:200]
    out['ninjatrader'] = {
        'readable': bool(c.get('nt_email') and nt_ready),
        'reason': None if (c.get('nt_email') and nt_ready) else
                  ('NinjaTrader email not linked yet' if not c.get('nt_email') else 'NinjaTrader credentials not configured'),
        'licenses': {str(pid): remote.get(pid) for pid in INDICATORS},
    }

    products = []
    owned = {int(r['product_id']) for r in db_licenses if r['state'] == 'owned_separately'}
    for pid, name in INDICATORS.items():
        if pid in owned and out['ninjatrader']['readable'] and remote.get(pid):
            row = remote[pid][0]
            products.append({'product_id': pid, 'name': name, 'status': 'ok',
                             'detail': f'owned separately (one-time purchase), not managed by the membership; '
                                       f'expires {row.get("expirationDateUTC") or "never"}'})
            continue
        if expected is None:
            v = {'status': 'unknown', 'detail': 'Whop membership could not be read'}
        elif not out['ninjatrader']['readable']:
            v = {'status': 'unknown', 'detail': out['ninjatrader']['reason']}
        else:
            v = verdict(expected, remote.get(pid))
        products.append({'product_id': pid, 'name': name, **v})
    out['products'] = products
    statuses = {p['status'] for p in products}
    out['overall'] = 'consistent' if statuses == {'ok'} else ('mismatch' if 'mismatch' in statuses else 'unknown')
    out['expected'] = expected
    return out
