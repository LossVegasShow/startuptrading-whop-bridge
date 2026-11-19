from types import SimpleNamespace
import store
import app as service
from fastapi import HTTPException


def test_sqlite_to_postgres_insert_codes():
    query=store.postgres_sql('INSERT OR REPLACE INTO codes(customer_id,purpose,code_hash,target_email,expires_at,attempts,requested_at) VALUES(?,?,?,?,?,0,?)')
    assert 'ON CONFLICT (customer_id,purpose)' in query
    assert '%s' in query and '?' not in query


def test_sqlite_to_postgres_event_dedupe():
    query=store.postgres_sql('INSERT OR IGNORE INTO webhook_events(webhook_id,event_type,object_id,received_at,state) VALUES(?,?,?,?,?)')
    assert 'ON CONFLICT (webhook_id) DO NOTHING' in query


def test_postgres_schema_identity_columns():
    assert 'id BIGSERIAL PRIMARY KEY' in store.POSTGRES_SCHEMA
    assert 'token_hash TEXT PRIMARY KEY' in store.POSTGRES_SCHEMA


def test_resend_https_success(monkeypatch):
    service.cfg.resend_api_key='re_test'
    service.cfg.resend_from='StartUpTrading <verify@example.com>'
    captured={}
    class Response:status_code=200
    class FakeClient:
        def __init__(self,timeout):pass
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def post(self,url,json,headers):
            captured.update(url=url,payload=json,headers=headers)
            return Response()
    monkeypatch.setattr(service.httpx,'Client',FakeClient)
    service.deliver_code('member@example.com','123456')
    assert captured['url']=='https://api.resend.com/emails'
    assert captured['payload']['to']==['member@example.com']
    assert '123456' in captured['payload']['text']
    service.cfg.resend_api_key=''


def test_resend_rejects_failed_delivery(monkeypatch):
    service.cfg.resend_api_key='re_test'
    service.cfg.resend_from='verify@example.com'
    class Response:status_code=403
    class FakeClient:
        def __init__(self,timeout):pass
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def post(self,*args,**kwargs):return Response()
    monkeypatch.setattr(service.httpx,'Client',FakeClient)
    try:
        service.deliver_code('member@example.com','123456')
        assert False,'Expected error'
    except HTTPException as exc:
        assert exc.status_code==503
    finally:
        service.cfg.resend_api_key=''
