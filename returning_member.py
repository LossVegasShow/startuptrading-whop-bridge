"""Returning members: move a NinjaTrader link from an ended membership to a new one.

When a membership ends and the same person buys again, Whop issues a new
membership ID, so the bridge creates a new customer record. That record can't
claim the NinjaTrader email, and the engine won't adopt the existing licenses,
because both still belong to the old record.

A transfer is allowed only when ALL of these hold:
  1. the old and new records belong to the same Whop user (non-empty user IDs,
     the new one proven by Whop OAuth);
  2. Whop confirms, live, that the old membership is no longer entitled (a
     paying membership never loses its licenses);
  3. the new customer has just verified the NinjaTrader inbox with a code;
  4. no license sync for the old record is running.

The email link and license rows then move together in one database
transaction, with an audit entry on both records. The engine afterwards
extends the same NinjaTrader licenses to the new paid-through date.
"""
import secrets
import time

from clients import IntegrationError, membership_entitlement
from store import audit, request_crm_sync


class StillActiveElsewhere(Exception):
    """The old membership is still entitled; licenses must not move."""


class TransferBusy(Exception):
    """A license sync for the old record is running; try again shortly."""


def holder_of(db, email, exclude_id):
    """The other verified customer currently linked to this NinjaTrader email, if any."""
    row = db.execute('SELECT * FROM customers WHERE lower(nt_email)=lower(?) AND id!=? AND verified=1',
                     (email, exclude_id)).fetchone()
    return dict(row) if row else None


def same_whop_user(holder, c):
    a, b = (holder or {}).get('whop_user_id') or '', (c or {}).get('whop_user_id') or ''
    return bool(a) and a.startswith('user_') and a == b


async def confirm_holder_ended(engine, holder):
    """Fresh Whop check that the old membership is no longer entitled. Fails closed."""
    m = await engine.whop.membership(holder['membership_id'])
    if not isinstance(m, dict) or m.get('id') != holder['membership_id']:
        raise IntegrationError('Old membership could not be confirmed with Whop')
    if m.get('user_id') != holder['whop_user_id']:
        raise IntegrationError('Old membership owner changed; manual review required')
    if not m.get('status'):
        raise IntegrationError('Incomplete Whop membership response; retry later')
    if membership_entitlement(m):
        raise StillActiveElsewhere(holder['membership_id'])


def transfer(db, holder_id, new_id, email):
    """Move the NinjaTrader link and license rows from holder_id to new_id. Call inside one transaction."""
    holder = db.execute('SELECT * FROM customers WHERE id=?', (holder_id,)).fetchone()
    new = db.execute('SELECT * FROM customers WHERE id=?', (new_id,)).fetchone()
    if not holder or not new:
        raise IntegrationError('Customer record missing during transfer')
    holder, new = dict(holder), dict(new)
    if not (holder['verified'] and (holder['nt_email'] or '').lower() == email.lower()):
        raise IntegrationError('NinjaTrader link changed during transfer; retry')
    if not same_whop_user(holder, new):
        raise IntegrationError('Whop user mismatch during transfer')
    if db.execute('SELECT 1 FROM licenses WHERE customer_id=? LIMIT 1', (new_id,)).fetchone():
        raise IntegrationError('New membership already has license rows; manual review required')
    now = int(time.time())
    moved = db.execute('SELECT COUNT(*) AS n FROM licenses WHERE customer_id=?', (holder_id,)).fetchone()['n']
    # Unlink the old record first: the unique index allows one verified holder per email.
    db.execute("UPDATE customers SET verified=0,status='transferred',updated_at=? WHERE id=?", (now, holder_id))
    db.execute('UPDATE licenses SET customer_id=?,updated_at=? WHERE customer_id=?', (new_id, now, holder_id))
    db.execute("UPDATE customers SET verified=1,status='pending',updated_at=? WHERE id=?", (now, new_id))
    audit(db, holder_id, 'ninjatrader_link_transferred_out',
          f'to customer {new_id} ({new["membership_id"]}); {moved} license rows')
    audit(db, new_id, 'ninjatrader_link_transferred_in',
          f'from customer {holder_id} ({holder["membership_id"]}); {moved} license rows; same Whop user')
    request_crm_sync(db, holder_id)
    request_crm_sync(db, new_id)
    return moved


class HolderLease:
    """Hold the engine's per-customer sync lease on the old record during the transfer."""

    def __init__(self, engine, holder_id):
        self.engine, self.holder_id, self.owner = engine, holder_id, secrets.token_hex(18)

    def __enter__(self):
        if not self.engine.acquire(self.holder_id, self.owner):
            raise TransferBusy(self.holder_id)
        return self

    def __exit__(self, *exc):
        self.engine.release(self.holder_id, self.owner)
        return False
