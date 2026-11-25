"""Production licensing controls: who may receive writes, and the circuit breaker.

Three layers, checked before every NinjaTrader write:

1. Emergency stop: LICENSE_WRITES_ENABLED=false stops every write (grants,
   renewals AND revocations) immediately.
2. Scope: LICENSE_ALL_MEMBERS=true licenses every verified member with an
   eligible membership. Off (the default), only the exact membership +
   NinjaTrader email pairs on the allowlist (ALLOWED_TEST_* and
   LICENSE_WRITE_ALLOWLIST) are written.
3. Circuit breaker: if the app grants or revokes unusually many licenses in an
   hour, or NinjaTrader keeps failing, it trips. A tripped breaker pauses ALL
   writes, including revocations, raises a HIGH alert, and stays tripped (it is
   stored in the database, so a restart doesn't clear it) until an operator
   resumes writes from /admin.

While writes are stopped or paused, nothing is lost: every sync is state-based,
so the next reconcile after resuming applies whatever Whop says then. Licenses
always carry an expiry (the paid-through date), so NinjaTrader still switches a
member off at the end of their paid period even if a revocation was paused.
See PRODUCTION_LICENSING.md.
"""
import json
import time

from clients import IntegrationError
from store import connect, audit

BREAKER_KEY = 'circuit_breaker'
# Kinds recorded in license_write_log.
GRANT, RENEW, REVOKE, FAILURE = 'grant', 'renew', 'revoke', 'failure'


class BreakerOpen(IntegrationError):
    """Raised instead of writing when the circuit breaker is (or just became) tripped."""


def mode(cfg):
    if not cfg.license_writes:
        return 'off'
    return 'all_members' if cfg.license_all_members else 'allowlist'


MODE_LABEL = {'off': 'Writes off (observe only)', 'allowlist': 'Allowlist only', 'all_members': 'All members'}


def in_scope(cfg, c):
    """Whether this customer may receive license writes, ignoring the breaker."""
    if not (cfg.license_writes and c and c.get('verified') and c.get('nt_email')):
        return False
    if cfg.license_all_members:
        return True
    return (c['membership_id'], c['nt_email'].casefold()) in cfg.write_allowlist()


def breaker(db):
    """The tripped state as a dict, or None when writes may proceed."""
    row = db.execute('SELECT value FROM control_state WHERE key=?', (BREAKER_KEY,)).fetchone()
    if not row:
        return None
    try:
        state = json.loads(row['value'])
    except (TypeError, ValueError):
        state = {'reason': 'unreadable breaker state', 'tripped_at': 0}
    return state if state.get('tripped') else None


def trip(db, reason, now=None):
    now = now or int(time.time())
    if breaker(db):
        return
    value = json.dumps({'tripped': True, 'reason': reason, 'tripped_at': now})
    db.execute("""INSERT INTO control_state(key,value,updated_at) VALUES(?,?,?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""", (BREAKER_KEY, value, now))
    audit(db, None, 'circuit_breaker_tripped', reason[:200])


def reset(db, now=None):
    """Resume writes. Counts restart from now, so the same burst doesn't re-trip at once."""
    now = now or int(time.time())
    state = breaker(db)
    value = json.dumps({'tripped': False, 'reset_at': now})
    db.execute("""INSERT INTO control_state(key,value,updated_at) VALUES(?,?,?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""", (BREAKER_KEY, value, now))
    audit(db, None, 'circuit_breaker_reset', (state or {}).get('reason', 'not tripped')[:200])
    return state


def _reset_at(db):
    row = db.execute('SELECT value FROM control_state WHERE key=?', (BREAKER_KEY,)).fetchone()
    try:
        return int(json.loads(row['value']).get('reset_at', 0)) if row else 0
    except (TypeError, ValueError):
        return 0


def count(db, kind, window, now=None):
    now = now or int(time.time())
    since = max(now - window, _reset_at(db))
    return db.execute('SELECT COUNT(*) AS n FROM license_write_log WHERE kind=? AND at>?', (kind, since)).fetchone()['n']


def limits(cfg):
    return {GRANT: (cfg.breaker_max_grants_per_hour, 3600, 'licenses granted in the last hour'),
            REVOKE: (cfg.breaker_max_revocations_per_hour, 3600, 'licenses revoked in the last hour'),
            FAILURE: (cfg.breaker_max_failures_per_15min, 900, 'NinjaTrader write failures in the last 15 minutes')}


def guard(cfg, kind, now=None):
    """Call immediately before a NinjaTrader write of this kind. Raises BreakerOpen
    if writes are paused, or trips the breaker if this write would exceed a limit."""
    # Raise only AFTER the transaction commits: raising inside it would roll the trip back.
    reason = None
    with connect(cfg) as db:
        state = breaker(db)
        if state:
            reason = state.get('reason', '')
        elif kind in limits(cfg):
            limit, window, label = limits(cfg)[kind]
            if count(db, kind, window, now) >= limit:
                reason = f'{limit} {label} (limit BREAKER_MAX_{"GRANTS_PER_HOUR" if kind == GRANT else "REVOCATIONS_PER_HOUR"})'
                trip(db, reason, now)
    if reason is not None:
        raise BreakerOpen('License writes paused by the circuit breaker: ' + reason)


def record(cfg, kind, cid=None, pid=None, now=None):
    now = now or int(time.time())
    with connect(cfg) as db:
        db.execute('INSERT INTO license_write_log(at,kind,customer_id,product_id) VALUES(?,?,?,?)', (now, kind, cid, pid))
        if kind == FAILURE:
            limit, window, label = limits(cfg)[FAILURE]
            if count(db, FAILURE, window, now) >= limit:
                trip(db, f'{limit} {label} (limit BREAKER_MAX_FAILURES_PER_15MIN)', now)
        # Keep the log small: nothing older than a day is ever counted.
        db.execute('DELETE FROM license_write_log WHERE at<?', (now - 86400,))


def status(cfg, db, now=None):
    """Everything the dashboard, snapshot and /health need to show."""
    state = breaker(db)
    out = {'mode': mode(cfg), 'mode_label': MODE_LABEL[mode(cfg)],
           'breaker': 'tripped' if state else 'ok', 'breaker_reason': (state or {}).get('reason'),
           'breaker_tripped_at': (state or {}).get('tripped_at')}
    for kind, (limit, window, label) in limits(cfg).items():
        out[kind] = {'count': count(db, kind, window, now), 'limit': limit, 'window_minutes': window // 60}
    return out
