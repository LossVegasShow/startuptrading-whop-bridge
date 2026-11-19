import sqlite3, time
from pathlib import Path
from contextlib import contextmanager
from config import Config

SCHEMA = '''
CREATE TABLE IF NOT EXISTS customers (
  id INTEGER PRIMARY KEY, membership_id TEXT NOT NULL UNIQUE, whop_user_id TEXT,
  buyer_email TEXT NOT NULL, nt_email TEXT, verified INTEGER NOT NULL DEFAULT 0,
  onboarding_path TEXT, status TEXT NOT NULL DEFAULT 'invited', plan_id TEXT,
  paid_through TEXT, updated_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS invites (
  token_hash TEXT PRIMARY KEY, customer_id INTEGER NOT NULL, expires_at INTEGER NOT NULL,
  used_at INTEGER, FOREIGN KEY(customer_id) REFERENCES customers(id));
CREATE TABLE IF NOT EXISTS oauth_states (
  state_hash TEXT PRIMARY KEY, verifier TEXT NOT NULL, nonce TEXT NOT NULL, expires_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY, customer_id INTEGER NOT NULL, expires_at INTEGER NOT NULL,
  FOREIGN KEY(customer_id) REFERENCES customers(id));
CREATE TABLE IF NOT EXISTS codes (
  customer_id INTEGER NOT NULL, purpose TEXT NOT NULL, code_hash TEXT NOT NULL,
  target_email TEXT NOT NULL, expires_at INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
  requested_at INTEGER NOT NULL, PRIMARY KEY(customer_id,purpose));
CREATE TABLE IF NOT EXISTS licenses (
  customer_id INTEGER NOT NULL, product_id INTEGER NOT NULL, license_id INTEGER,
  expiration TEXT, state TEXT NOT NULL, updated_at INTEGER NOT NULL,
  PRIMARY KEY(customer_id,product_id));
CREATE TABLE IF NOT EXISTS webhook_events (
  webhook_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, object_id TEXT, received_at INTEGER NOT NULL,
  state TEXT NOT NULL DEFAULT 'queued', last_error TEXT);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY, at INTEGER NOT NULL, customer_id INTEGER,
  action TEXT NOT NULL, details TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_customer_email ON customers(nt_email);
CREATE INDEX IF NOT EXISTS idx_event_state ON webhook_events(state);
'''

@contextmanager
def connect(cfg:Config):
    path=Path(cfg.db); path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(str(path),timeout=20)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA busy_timeout=10000'); db.execute('PRAGMA foreign_keys=ON'); db.execute('PRAGMA journal_mode=WAL')
    db.executescript(SCHEMA)
    try:
        yield db
        db.commit()
    finally: db.close()

def audit(db,cid,action,detail=''):
    db.execute('INSERT INTO audit(at,customer_id,action,details) VALUES(?,?,?,?)',
               (int(time.time()),cid,action,str(detail)[:400]))

def customer(db,cid):
    r=db.execute('SELECT * FROM customers WHERE id=?',(cid,)).fetchone()
    return dict(r) if r else None
