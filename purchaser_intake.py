'''Record eligible Whop buyers before they open the activation page.

Webhook is only a trigger. Identity, plan, entitlement and buyer contact are obtained
from a fresh authenticated Whop API lookup. No NinjaTrader license is created here.
'''
import time
from clients import IntegrationError, membership_entitlement, membership_plan_id
from config import BUSINESS_ID, PRODUCT_ID, PLANS
from store import connect, request_crm_sync, audit


def member_email(record):
    '''Extract an email only from a trusted API response, not a signed event payload.''' 
    if not isinstance(record,dict):return ''
    user=record.get('user')
    if not isinstance(user,dict):user={}
    for value in (record.get('email'),record.get('buyer_email'),user.get('email')):
        if isinstance(value,str):
            value=value.strip().lower()
            if '@' in value and len(value)<=200 and '.' in value.rsplit('@',1)[-1]:
                return value
    return ''


async def member_api_email(whop, m):
    '''The buyer's Whop email from the Members API, bound to a verified membership.

    Returns '' when the membership has no member ID, the client can't look
    members up, or Whop has no email for the member (callers then fall back or
    retry). Raises IntegrationError on API errors and on ANY identity mismatch:
    the member must be the membership's own member, in the StartUpTrading
    business, for the membership's own Whop user. The member's own `status`
    (e.g. 'joined') says nothing about the subscription and is ignored;
    eligibility comes only from the membership. This is the Whop account email,
    never the NinjaTrader email, which is verified separately.
    '''
    member_id=m.get('member_id') if isinstance(m,dict) else None
    lookup=getattr(whop,'member',None)
    if not isinstance(member_id,str) or not member_id.startswith('mber_') or lookup is None:
        return ''
    rec=await lookup(member_id)
    if not isinstance(rec,dict):
        raise IntegrationError('Unexpected Whop member response')
    account=rec.get('account') if isinstance(rec.get('account'),dict) else {}
    user=rec.get('user') if isinstance(rec.get('user'),dict) else {}
    if rec.get('id')!=member_id:
        raise IntegrationError('Whop member identity mismatch: member ID')
    if (rec.get('account_id') or account.get('id'))!=BUSINESS_ID:
        raise IntegrationError('Whop member identity mismatch: business')
    if not user.get('id') or user.get('id')!=m.get('user_id'):
        raise IntegrationError('Whop member identity mismatch: user')
    value=rec.get('email')
    if not isinstance(value,str):
        return ''
    value=value.strip().lower()
    if '@' not in value or len(value)>200 or '.' not in value.rsplit('@',1)[-1]:
        return ''
    return value


def is_target_membership(m):
    if not isinstance(m,dict):return False
    acct=m.get('account') or {}
    prod=m.get('product') or {}
    if not isinstance(acct,dict):acct={}
    if not isinstance(prod,dict):prod={}
    return ((m.get('account_id') or acct.get('id'))==BUSINESS_ID and
            (m.get('product_id') or prod.get('id'))==PRODUCT_ID and
            membership_plan_id(m) in PLANS)


async def import_membership(cfg,whop, membership_id, *, verified_membership=None):
    '''Upsert buyer record after validating membership with Whop.

    Ineligible subscriptions are only imported when a prior record exists;
    a canceled membership never gets an activation record created by itself.
    '''
    if not isinstance(membership_id,str) or not membership_id.startswith('mem_'):
        return {'state':'unmappable'}
    # The admin intake route passes an authenticated Whop membership-list record.
    # Reuse it rather than making a second, potentially incompatible detail call.
    # Normal webhook intake still independently retrieves membership data.
    if verified_membership is not None:
        m=verified_membership
    else:
        m=await whop.membership(membership_id)
        if not membership_plan_id(m):
            m=await whop.resolve_membership(m)
    if not isinstance(m,dict) or m.get('id')!=membership_id:
        raise IntegrationError('Whop membership lookup ID mismatch')
    if not is_target_membership(m):
        return {'state':'ignored_other_product'}
    userid=m.get('user_id')
    if not isinstance(userid,str) or not userid.startswith('user_'):
        raise IntegrationError('Whop membership user ID missing; retry')
    ent=membership_entitlement(m)
    with connect(cfg) as db:
        row=db.execute('SELECT * FROM customers WHERE membership_id=?',(membership_id,)).fetchone()
    if not ent and not row:
        return {'state':'ignored_ineligible'}
    email=member_email(m)
    if not email and not row:
        # The membership record carries no contact fields; Whop exposes the
        # customer's email on the Members API. Identity-bound, never guessed
        # from the webhook payload.
        email=await member_api_email(whop,m)
    if not email and not row:
        # Legacy fallback: some API versions return email on the user record.
        info=await whop.user(userid)
        email=member_email(info)
    if not email and not row:
        raise IntegrationError('Whop buyer email unavailable; retry; no placeholder customer created')
    now=int(time.time())
    with connect(cfg) as db:
        # Recheck inside transaction to handle OAuth sign-in concurrent with webhook.
        row=db.execute('SELECT * FROM customers WHERE membership_id=?',(membership_id,)).fetchone()
        if row:
            if row['whop_user_id'] and row['whop_user_id']!=userid:
                raise IntegrationError('Whop membership owner changed; manual review needed')
            if email and row['buyer_email']!=email:
                # Do not silently override a customer's independently verified email.
                audit(db,row['id'],'buyer_email_change_review','Whop account email changed')
            cid=row['id']
            db.execute('UPDATE customers SET whop_user_id=?,plan_id=?,paid_through=?,updated_at=? WHERE id=?',
                       (userid,membership_plan_id(m),ent['paid_through'] if ent else None,now,cid))
            action='updated'
        else:
            cur=db.execute('''INSERT INTO customers(membership_id,whop_user_id,buyer_email,
                buyer_email_verified,plan_id,paid_through,status,updated_at)
                VALUES(?,?,?,?,?,?,?,?)''',
                (membership_id,userid,email,0,ent['plan_id'],ent['paid_through'],'invited',now))
            cid=cur.lastrowid
            action='created'
            audit(db,cid,'buyer_captured_from_whop','Pending account linking; no license issued')
        request_crm_sync(db,cid)
    return {'state':action,'customer_id':cid}


async def handle_queued_event(cfg,whop,engine,event):
    '''Handle a durable signed event; errors propagate for scheduled retry.''' 
    mid=event.get('object_id') or ''
    if not mid.startswith('mem_'):
        # Payment IDs are not membership IDs; never mistake them for a buyer.
        return 'needs_mapping'
    result=await import_membership(cfg,whop,mid)
    if result['state'] in ('ignored_other_product','ignored_ineligible','unmappable'):
        return result['state']
    # Existing verified customers reconcile their licenses; new buyers remain
    # unverified and cannot be provisioned by just receiving a webhook.
    await engine.reconcile(result['customer_id'])
    return 'processed'
