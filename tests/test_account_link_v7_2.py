import time
from fastapi.testclient import TestClient
import app as web
from store import connect

def setup(tmp_path):
 web.cfg.database_url=''
 web.cfg.require_database_url=False
 web.cfg.db=str(tmp_path/'link.sqlite')
 web.cfg.admin_password='test-secret-for-codes'
 with connect(web.cfg) as db:
  db.execute('INSERT INTO customers(membership_id,whop_user_id,buyer_email,buyer_email_verified,nt_email,verified,status,updated_at) VALUES(?,?,?,?,?,?,?,?)',('mem_link','user_link','buyer@example.com',1,'ninja@example.com',1,'eligible',int(time.time())))
  db.execute('INSERT INTO sessions(token_hash,customer_id,expires_at) VALUES(?,?,?)',(web.hash_token('t'*40),1,int(time.time())+3600))
 return {'sut_session':'t'*40},web.csrf('t'*40)

def test_verified_member_sees_linked_account_not_password(tmp_path):
 cookies,token=setup(tmp_path)
 with TestClient(web.app) as client:
  r=client.get('/onboarding',cookies=cookies)
  assert r.status_code==200 and 'ninja@example.com' in r.text
  assert 'Whop identity confirmed' in r.text
  assert 'password' in r.text.lower()
  assert 'Send membership code' not in r.text

def test_verified_account_cannot_relink_from_direct_post(tmp_path):
 cookies,token=setup(tmp_path)
 with TestClient(web.app) as client:
  r=client.post('/onboarding/nt-code',data={'csrf_token':token,'nt_email':'hijack@example.com','path':'existing'},cookies=cookies,follow_redirects=False)
  assert r.status_code==409
 with connect(web.cfg) as db:
  row=db.execute('SELECT nt_email,verified FROM customers WHERE id=1').fetchone()
  assert row['nt_email']=='ninja@example.com' and row['verified']==1

def test_existing_licenses_prevent_relink_even_if_verified_flag_cleared(tmp_path):
 cookies,token=setup(tmp_path)
 with connect(web.cfg) as db:
  db.execute('UPDATE customers SET verified=0 WHERE id=1')
  db.execute('INSERT INTO licenses(customer_id,product_id,license_id,state,updated_at) VALUES(?,?,?,?,?)',(1,2067,500,'created',int(time.time())))
 with TestClient(web.app) as client:
  r=client.post('/onboarding/nt-code',data={'csrf_token':token,'nt_email':'other@example.com','path':'new'},cookies=cookies)
  assert r.status_code==409

def test_unique_verified_email_in_db(tmp_path):
 import sqlite3
 cookies,token=setup(tmp_path)
 with connect(web.cfg) as db:
  db.execute('INSERT INTO customers(membership_id,buyer_email,nt_email,verified,updated_at) VALUES(?,?,?,?,?)',('mem_b','other@example.com','ninja@example.com',0,int(time.time())))
 try:
  with connect(web.cfg) as db:db.execute('UPDATE customers SET verified=1 WHERE membership_id=?',('mem_b',))
  assert False,'duplicate verified email should be blocked'
 except sqlite3.IntegrityError:pass

def test_legacy_sqlite_migration_preserves_customer(tmp_path):
 import sqlite3
 from store import SCHEMA
 path=tmp_path/'legacy.sqlite'
 old=SCHEMA.replace('buyer_email TEXT NOT NULL, buyer_email_verified INTEGER NOT NULL DEFAULT 0, nt_email TEXT,','buyer_email TEXT NOT NULL, nt_email TEXT,').replace('CREATE UNIQUE INDEX IF NOT EXISTS idx_verified_nt_email ON customers(lower(nt_email)) WHERE verified=1 AND nt_email IS NOT NULL;','')
 with sqlite3.connect(path) as conn:
  conn.executescript(old)
  conn.execute('INSERT INTO customers(membership_id,buyer_email,updated_at) VALUES(?,?,?)',('mem_old','old@example.com',int(time.time())))
 web.cfg.db=str(path)
 with connect(web.cfg) as db:
  row=db.execute('SELECT membership_id,buyer_email_verified FROM customers WHERE membership_id=?',('mem_old',)).fetchone()
  assert row['buyer_email_verified']==0
 with connect(web.cfg) as db:
  assert db.execute('SELECT COUNT(*) FROM customers').fetchone()[0]==1


def test_whop_linked_ninja_email_otp_end_to_end_no_license_writes(tmp_path,monkeypatch):
 import asyncio
 from store import customer
 cookies,token=setup(tmp_path)
 web.cfg.license_writes=False
 with connect(web.cfg) as db:
  db.execute('UPDATE customers SET nt_email=NULL,verified=0 WHERE id=1')
 emails=[]
 monkeypatch.setattr(web,'deliver_code',lambda address,code:emails.append((address,code)))
 with TestClient(web.app) as client:
  r=client.post('/onboarding/nt-code',data={'csrf_token':token,'nt_email':'new@example.com','path':'existing'},cookies=cookies,follow_redirects=False)
  assert r.status_code==303
  assert len(emails)==1 and emails[0][0]=='new@example.com'
  async def fake_reconcile(cid):return {'status':'observe_only','writes':0}
  monkeypatch.setattr(web.engine,'reconcile',fake_reconcile)
  r=client.post('/onboarding/nt-verify',data={'csrf_token':token,'code':emails[0][1]},cookies=cookies,follow_redirects=False)
  assert r.status_code==303
 with connect(web.cfg) as db:
  row=customer(db,1)
  assert row['nt_email']=='new@example.com' and row['verified']==1
  assert db.execute('SELECT COUNT(*) FROM licenses').fetchone()[0]==0
