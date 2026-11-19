"""Entitlement reconciliation; production writes intentionally unsupported in this release.
Safe writes can be enabled for a single explicitly allowlisted test email + membership.
"""
import datetime as dt, time
from config import Config, INDICATORS
from clients import membership_entitlement, WhopClient, NinjaClient, IntegrationError, parse_utc
from store import connect, audit, customer

class Engine:
    def __init__(self,cfg):
        self.cfg=cfg; self.whop=WhopClient(cfg); self.nt=NinjaClient(cfg)
    def allowed(self,c):
        return bool(self.cfg.license_writes and self.cfg.allowed_test_email and
                    self.cfg.allowed_test_membership and c.get('nt_email','').lower()==self.cfg.allowed_test_email
                    and c['membership_id']==self.cfg.allowed_test_membership)
    async def reconcile(self,cid):
        with connect(self.cfg) as db:
            c=customer(db,cid)
        if not c: raise IntegrationError('Customer not found')
        membership=await self.whop.membership(c['membership_id'])
        ent=membership_entitlement(membership)
        if (membership.get('user_id') and c['whop_user_id'] and membership['user_id']!=c['whop_user_id']):
            raise IntegrationError('Whop account identity changed: manual review required')
        if ent:
            state='eligible'
        else:
            state='ineligible'
        with connect(self.cfg) as db:
            db.execute('UPDATE customers SET status=?,plan_id=?,paid_through=?,updated_at=? WHERE id=?',
                       (state,ent['plan_id'] if ent else None,ent['paid_through'] if ent else None,int(time.time()),cid))
            audit(db,cid,'membership_reconciled',state)
        if not c['verified'] or not c['nt_email']:
            return {'status':'awaiting_verification' if ent else 'ineligible','writes':0}
        if not self.allowed(c):
            return {'status':state,'writes':0,'mode':'observe_only'}
        # Only one explicitly allowlisted test membership is writable.
        changes=[]
        for product_id in INDICATORS:
            try:
                existing=await self.nt.licenses(product_id)
                matches=[r for r in existing if str(r.get('email','')).casefold()==c['nt_email'].casefold()]
                if len(matches)>1: raise IntegrationError('Duplicate licenses require manual review')
                current=matches[0] if matches else None
                if ent:
                    desired=ent['paid_through']
                    if current:
                        old=parse_utc(current.get('expirationDateUTC'))
                        # None = lifetime or unknown; do not silently modify lifetime licenses.
                        if old is None: raise IntegrationError('Existing lifetime/unknown license: manual review')
                        if abs((old-parse_utc(desired)).total_seconds())>60:
                            await self.nt.update(product_id,current['id'],c['nt_email'],desired)
                        license_id=current['id']; action='synced'
                    else:
                        license_id=await self.nt.create(product_id,c['nt_email'],desired);action='created'
                else:
                    if not current: continue
                    if not current.get('expirationDateUTC'):
                        raise IntegrationError('Lifetime/unknown license: manual review before expiration')
                    old=parse_utc(current['expirationDateUTC'])
                    if old and old>dt.datetime.now(dt.timezone.utc):
                        desired=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(minutes=2)).isoformat().replace('+00:00','Z')
                        await self.nt.update(product_id,current['id'],c['nt_email'],desired)
                    else: desired=current['expirationDateUTC']
                    license_id=current['id']; action='expired'
                with connect(self.cfg) as db:
                    db.execute('INSERT INTO licenses(customer_id,product_id,license_id,expiration,state,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(customer_id,product_id) DO UPDATE SET license_id=excluded.license_id,expiration=excluded.expiration,state=excluded.state,updated_at=excluded.updated_at',
                               (cid,product_id,license_id,desired,action,int(time.time())))
                    audit(db,cid,'ninjatrader_'+action,f'{product_id}/{license_id}')
                changes.append({'product_id':product_id,'action':action})
            except Exception as exc:
                with connect(self.cfg) as db:
                    audit(db,cid,'sync_error',f'{product_id}: {str(exc)[:130]}')
                changes.append({'product_id':product_id,'action':'error'})
        return {'status':state,'writes':sum(x['action'] in ('synced','created','expired') for x in changes), 'products':changes}
