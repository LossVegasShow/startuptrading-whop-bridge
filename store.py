import sqlite3, time, os, re
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
CREATE TABLE IF NOT EXISTS admin_test_oauth_states (
  state_hash TEXT PRIMARY KEY, verifier TEXT NOT NULL, nonce TEXT NOT NULL, expires_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS admin_test_sessions (
  token_hash TEXT PRIMARY KEY, whop_user_id TEXT NOT NULL, verified_email TEXT, expires_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS admin_email_tests (
  whop_user_id TEXT PRIMARY KEY, code_hash TEXT,
  expires_at INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
  requested_at INTEGER NOT NULL, verified_at INTEGER);
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
CREATE TABLE IF NOT EXISTS sync_leases (
  customer_id INTEGER PRIMARY KEY, owner TEXT NOT NULL, expires_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS webhook_events (
  webhook_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, object_id TEXT, received_at INTEGER NOT NULL,
  state TEXT NOT NULL DEFAULT 'queued', last_error TEXT);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY, at INTEGER NOT NULL, customer_id INTEGER,
  action TEXT NOT NULL, details TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_customer_email ON customers(nt_email);
CREATE INDEX IF NOT EXISTS idx_event_state ON webhook_events(state);
'''

# Persistent PostgreSQL is required for hosted customer storage. SQLite remains
# useful for local development/tests but must not be used for real hosted signups.
POSTGRES_SCHEMA = SCHEMA.replace('id INTEGER PRIMARY KEY,', 'id BIGSERIAL PRIMARY KEY,')

class PostgresResult:
    def __init__(self, rows, rowcount, lastrowid=None):
        self._rows=rows
        self.rowcount=rowcount
        self.lastrowid=lastrowid
    def fetchone(self):
        return self._rows[0] if self._rows else None
    def fetchall(self):
        return self._rows
    def __iter__(self):
        return iter(self._rows)


def postgres_sql(sql):
    # Existing v4 queries use SQLite '?' parameters. Translate only trusted
    # application-owned SQL, never arbitrary user-supplied query strings.
    if sql.startswith('INSERT OR REPLACE INTO codes'):
        sql=sql.replace('INSERT OR REPLACE INTO codes','INSERT INTO codes',1)
        sql += (' ON CONFLICT (customer_id,purpose) DO UPDATE SET '
                'code_hash=EXCLUDED.code_hash,target_email=EXCLUDED.target_email,'
                'expires_at=EXCLUDED.expires_at,attempts=0,requested_at=EXCLUDED.requested_at')
    if sql.startswith('INSERT OR IGNORE INTO webhook_events'):
        sql=sql.replace('INSERT OR IGNORE INTO webhook_events','INSERT INTO webhook_events',1)
        sql+=' ON CONFLICT (webhook_id) DO NOTHING'
    return sql.replace('?', '%s')

class PostgresConnection:
    def __init__(self, conn):
        self.conn=conn
    def execute(self,sql,params=()):
        translated=postgres_sql(sql)
        insert_id=bool(re.search(r'^INSERT INTO (customers|audit)\b',translated,re.I)) and 'RETURNING' not in translated.upper()
        if insert_id:translated+=' RETURNING id'
        with self.conn.cursor() as cursor:
            cursor.execute(translated,tuple(params))
            rows=cursor.fetchall() if cursor.description else []
            inserted=rows[0]['id'] if insert_id and rows else None
            return PostgresResult(rows,cursor.rowcount,inserted)

@contextmanager
def connect(cfg:Config):
    url=getattr(cfg,'database_url','')
    if url:
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(url, row_factory=dict_row, connect_timeout=10) as raw:
            with raw.cursor() as cursor:
                for statement in POSTGRES_SCHEMA.split(';'):
                    if statement.strip():cursor.execute(statement)
            yield PostgresConnection(raw)
        return
    # A public Render free web service loses its local SQLite DB on restart.
    # Explicitly fail closed rather than pretend customer verification persists.
    if getattr(cfg,'require_database_url',False):
        raise RuntimeError('DATABASE_URL required for hosted operation; SQLite is ephemeral')
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
