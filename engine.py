"""Whop-authoritative, ownership-safe, retryable NinjaTrader license reconciliation.
Writes only for members in scope (controls.in_scope): the allowlist, or every verified member with LICENSE_ALL_MEMBERS.
"""
import datetime as dt
import secrets
import time
from config import INDICATORS, RETIRED_INDICATORS
from clients import membership_entitlement, membership_plan_id, WhopClient, NinjaClient, IntegrationError, parse_utc
from store import connect, audit, customer, request_crm_sync, queue_activation_email
import lifecycle_emails
import controls

class Engine:
    def __init__(self,cfg):
        self.cfg=cfg; self.whop=WhopClient(cfg); self.nt=NinjaClient(cfg)

    def allowed(self,c):
        # Writes need the global switch, a verified NinjaTrader email, AND either
        # LICENSE_ALL_MEMBERS or an exact membership + email pair on the allowlist.
        # The circuit breaker is checked separately, immediately before each write.
        return controls.in_scope(self.cfg,c)

    async def _write(self,kind,cid,pid,call):
        """Every NinjaTrader write goes through here: breaker check, then the call, then the log."""
        controls.guard(self.cfg,kind)
        try:
            result=await call()
        except Exception:
            controls.record(self.cfg,controls.FAILURE,cid,pid)
            raise
        controls.record(self.cfg,kind,cid,pid)
        return result

    def acquire(self,cid,owner):
        now=int(time.time())
        with connect(self.cfg) as db:
            # Conditional upsert is atomic in SQLite and PostgreSQL.
            result=db.execute("""INSERT INTO sync_leases(customer_id,owner,expires_at) VALUES(?,?,?)
                ON CONFLICT(customer_id) DO UPDATE SET owner=excluded.owner,expires_at=excluded.expires_at
                WHERE sync_leases.expires_at<?""",(cid,owner,now+600,now))
            return result.rowcount==1

    def release(self,cid,owner):
        with connect(self.cfg) as db:
            db.execute('DELETE FROM sync_leases WHERE customer_id=? AND owner=?',(cid,owner))

    async def reconcile(self,cid):
        owner=secrets.token_hex(18)
        if not self.acquire(cid,owner):
            raise IntegrationError('Customer sync already in progress; retry later')
        try:
            return await self._reconcile(cid)
        finally:
            self.release(cid,owner)

    async def _reconcile(self,cid):
        with connect(self.cfg) as db:
            c=customer(db,cid)
            if not c: raise IntegrationError('Customer not found')
            owned={int(r['product_id']):dict(r) for r in db.execute(
                'SELECT * FROM licenses WHERE customer_id=?',(cid,)).fetchall()}
        membership=await self.whop.membership(c['membership_id'])
        if not isinstance(membership,dict) or membership.get('id')!=c['membership_id']:
            raise IntegrationError('Membership identity could not be confirmed')
        # Mandatory ID binding even for revoked members, not just when eligible.
        api_user=membership.get('user_id')
        if not api_user or api_user!=c['whop_user_id']:
            raise IntegrationError('Whop user identity unavailable or changed; manual review')
        # Incomplete API objects must not revoke access; retry when Whop responds fully.
        if not (membership.get('status') and (membership.get('product_id') or (membership.get('product') or {}).get('id')) and membership_plan_id(membership) and (membership.get('account_id') or (membership.get('account') or {}).get('id'))):
            raise IntegrationError('Incomplete Whop membership response; retry without license changes')
        entitlement=membership_entitlement(membership)
        state='eligible' if entitlement else 'ineligible'
        with connect(self.cfg) as db:
            db.execute('UPDATE customers SET status=?,plan_id=?,paid_through=?,updated_at=? WHERE id=?',
                       (state,entitlement['plan_id'] if entitlement else None,
                        entitlement['paid_through'] if entitlement else None,int(time.time()),cid))
            audit(db,cid,'membership_reconciled',state)
            request_crm_sync(db,cid)
            cancelling=membership.get('status')=='canceling' or membership.get('cancel_at_period_end') is True
            lifecycle_emails.on_reconcile(db,c,bool(entitlement),cancelling)
        if not c.get('verified') or not c.get('nt_email'):
            return {'status':'awaiting_verification' if entitlement else 'ineligible','writes':0}
        if not self.allowed(c):
            return {'status':state,'writes':0,'mode':'observe_only'}
        with connect(self.cfg) as db:
            paused=controls.breaker(db)
        if paused:
            # Nothing is written, granted OR revoked, until an operator resumes writes.
            return {'status':state,'writes':0,'mode':'paused','reason':paused.get('reason')}
        if not all([self.cfg.nt_username,self.cfg.nt_password,self.cfg.nt_cid,self.cfg.nt_sec]):
            raise IntegrationError('NinjaTrader vendor credentials not configured')
        changes=[]; failures=[]
        for pid in INDICATORS:
            record=owned.get(pid)
            try:
                # Reading licenses is mandatory before every write, to guard against duplicates
                # and discover manual tampering. Never touch unrelated pre-existing licenses.
                remote=await self.nt.licenses(pid)
                matches=[r for r in remote if str(r.get('email','')).casefold()==c['nt_email'].casefold()]
                if len(matches)>1:raise IntegrationError('Duplicate licenses: manual review required')
                matched=matches[0] if matches else None
                adopted=False
                if record and record.get('license_id') is not None:
                    if not matched or int(matched['id'])!=int(record['license_id']):
                        raise IntegrationError('Owned license missing or changed; manual review required')
                    selected=matched
                else:
                    expired_before=parse_utc(matched.get('expirationDateUTC')) if matched else None
                    if matched and entitlement and expired_before is not None and expired_before<=dt.datetime.now(dt.timezone.utc):
                        # A license the bridge didn't create that has ALREADY EXPIRED (an old
                        # trial, a lapsed earlier test). It grants nothing today, so extending
                        # it to the paid-through date takes no access away from anyone, and
                        # reuses it instead of creating a duplicate. From here on the bridge
                        # owns it, so it is expired again when the membership ends.
                        with connect(self.cfg) as db:
                            audit(db,cid,'ninjatrader_adopted_expired',f'{pid}/{matched.get("id")} expired {matched.get("expirationDateUTC")}')
                        selected=matched
                        adopted=True
                    elif matched:
                        # A license the bridge didn't create, e.g. a one-time purchase on
                        # startuptrading.com. Never modify or revoke it. If it's lifetime or
                        # lasts at least as long as the membership, the member already has
                        # this indicator: record it as owned separately and move on.
                        old=parse_utc(matched.get('expirationDateUTC'))
                        covers=old is None or not entitlement or old>=parse_utc(entitlement['paid_through'])
                        if not covers:
                            raise IntegrationError('Pre-existing license expires before the membership; manual review required')
                        with connect(self.cfg) as db:
                            db.execute("""INSERT INTO licenses(customer_id,product_id,license_id,expiration,state,updated_at)
                                VALUES(?,?,NULL,?,'owned_separately',?) ON CONFLICT(customer_id,product_id)
                                DO UPDATE SET license_id=NULL,expiration=excluded.expiration,state='owned_separately',
                                updated_at=excluded.updated_at""",(cid,pid,matched.get('expirationDateUTC'),int(time.time())))
                            audit(db,cid,'ninjatrader_owned_separately',f'{pid}/{matched.get("id")}')
                        changes.append({'product_id':pid,'action':'owned_separately'})
                        continue
                    else:
                        selected=None
                if entitlement:
                    desired=entitlement['paid_through']
                    if selected:
                        old=parse_utc(selected.get('expirationDateUTC'))
                        if old is None: raise IntegrationError('Missing/lifetime expiration: manual review')
                        new=parse_utc(desired)
                        if abs((old-new).total_seconds())>60:
                            await self._write(controls.GRANT if adopted else controls.RENEW,cid,pid,
                                              lambda:self.nt.update(pid,selected['id'],c['nt_email'],desired))
                            action='renewed'
                        else:action='unchanged'
                        lid=int(selected['id'])
                    else:
                        # On timeout, the next attempt detects the untracked remote license and
                        # REFUSES creation rather than risking duplicate issuance.
                        lid=await self._write(controls.GRANT,cid,pid,lambda:self.nt.create(pid,c['nt_email'],desired))
                        action='created'
                else:
                    if not selected:
                        action='absent';changes.append({'product_id':pid,'action':action});continue
                    old=parse_utc(selected.get('expirationDateUTC'))
                    if old is None:raise IntegrationError('Missing/lifetime expiration: manual review')
                    now=dt.datetime.now(dt.timezone.utc)
                    if old>now:
                        desired=(now-dt.timedelta(minutes=2)).isoformat().replace('+00:00','Z')
                        await self._write(controls.REVOKE,cid,pid,lambda:self.nt.update(pid,selected['id'],c['nt_email'],desired))
                        action='expired'
                    else:
                        desired=selected['expirationDateUTC'];action='already_expired'
                    lid=int(selected['id'])
                with connect(self.cfg) as db:
                    db.execute("""INSERT INTO licenses(customer_id,product_id,license_id,expiration,state,updated_at)
                        VALUES(?,?,?,?,?,?) ON CONFLICT(customer_id,product_id)
                        DO UPDATE SET license_id=excluded.license_id,expiration=excluded.expiration,
                        state=excluded.state,updated_at=excluded.updated_at""",
                        (cid,pid,lid,desired,action,int(time.time())))
                    audit(db,cid,'ninjatrader_'+action,f'{pid}/{lid}')
                changes.append({'product_id':pid,'action':action})
            except Exception as exc:
                # Failing one indicator must not prevent independent attempts for other indicators.
                with connect(self.cfg) as db:
                    audit(db,cid,'sync_error',f'{pid}: {str(exc)[:170]}')
                changes.append({'product_id':pid,'action':'error'})
                failures.append(pid)
        for pid in RETIRED_INDICATORS:
            record=owned.get(pid)
            # Only licenses the bridge itself issued; owned-separately rows have no license_id.
            if not record or record.get('license_id') is None or record.get('state')=='retired':
                continue
            try:
                remote=await self.nt.licenses(pid)
                matched=[r for r in remote if int(r.get('id') or 0)==int(record['license_id'])]
                if not matched or str(matched[0].get('email','')).casefold()!=c['nt_email'].casefold():
                    raise IntegrationError('Retired product license missing or changed; manual review required')
                old=parse_utc(matched[0].get('expirationDateUTC'))
                if old is None:raise IntegrationError('Missing/lifetime expiration: manual review')
                now=dt.datetime.now(dt.timezone.utc)
                desired=matched[0]['expirationDateUTC']
                if old>now:
                    desired=(now-dt.timedelta(minutes=2)).isoformat().replace('+00:00','Z')
                    await self._write(controls.REVOKE,cid,pid,lambda:self.nt.update(pid,matched[0]['id'],c['nt_email'],desired))
                with connect(self.cfg) as db:
                    db.execute("UPDATE licenses SET expiration=?,state='retired',updated_at=? WHERE customer_id=? AND product_id=?",
                               (desired,int(time.time()),cid,pid))
                    audit(db,cid,'ninjatrader_retired',f'{pid}/{record["license_id"]} ({RETIRED_INDICATORS[pid]} is no longer in the membership)')
                changes.append({'product_id':pid,'action':'retired'})
            except Exception as exc:
                with connect(self.cfg) as db:
                    audit(db,cid,'sync_error',f'{pid}: {str(exc)[:170]}')
                changes.append({'product_id':pid,'action':'error'})
                failures.append(pid)
        result={'status':state,'writes':sum(x['action'] in ('created','renewed','expired','retired') for x in changes),
                'products':changes,'partial_failure':bool(failures)}
        if not failures and entitlement:
            with connect(self.cfg) as db:
                queue_activation_email(db,cid)
                request_crm_sync(db,cid)
        elif not failures:
            with connect(self.cfg) as db:request_crm_sync(db,cid)
        if failures:
            raise IntegrationError('License sync incomplete for products '+','.join(map(str,failures))+'; scheduled retry required')
        return result
