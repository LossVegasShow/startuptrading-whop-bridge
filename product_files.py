"""Private hosting for the proprietary product files (NinjaTrader exports).

The files are NEVER in GitHub (the repository is public). An admin uploads them
once at /admin/products; they're stored in the app's database, and only accepted
when the name and SHA-256 match products.json. /downloads/<file> serves them only
to a signed-in member with an active paid membership; anyone else is sent through
Whop sign-in first. The free community product never grants access.
"""
import hashlib
import re
import time

from config import PRODUCTS

MAX_BYTES = 50 * 1024 * 1024
NEXT_COOKIE = 'sut_next'


def registered(filename):
    return next((p for p in PRODUCTS.values() if p['file'] == filename), None)


def safe_next(value):
    """Only a download path may be the post-sign-in destination (no open redirect)."""
    m = re.fullmatch(r'/downloads/([A-Za-z0-9_.-]{1,120})', str(value or ''))
    return value if m and registered(m.group(1)) else ''


def store(db, filename, content, now=None):
    """Save an uploaded product file. Returns (ok, message)."""
    p = registered(filename)
    if not p:
        return False, f'{filename} is not a product file in products.json'
    if not content or len(content) > MAX_BYTES:
        return False, 'Empty or too large'
    digest = hashlib.sha256(content).hexdigest()
    if digest != p['sha256']:
        return False, f'{filename}: SHA-256 {digest[:12]}… does not match products.json ({p["sha256"][:12]}…). Upload the exact released file, or update products.json first.'
    if not content.startswith(b'PK'):
        return False, 'Not a .zip file'
    db.execute("""INSERT INTO product_files(file,sha256,size,content,uploaded_at) VALUES(?,?,?,?,?)
        ON CONFLICT(file) DO UPDATE SET sha256=excluded.sha256, size=excluded.size, content=excluded.content,
        uploaded_at=excluded.uploaded_at""", (filename, digest, len(content), content, now or int(time.time())))
    return True, f'{filename} stored ({len(content):,} bytes, SHA-256 verified)'


def status(db):
    have = {r['file']: dict(r) for r in db.execute('SELECT file, sha256, size, uploaded_at FROM product_files')}
    out = []
    for p in PRODUCTS.values():
        h = have.get(p['file'])
        out.append({'name': p['name'], 'file': p['file'], 'expected': p['sha256'], 'uploaded': bool(h),
                    'ok': bool(h) and h['sha256'] == p['sha256'], 'size': h['size'] if h else None,
                    'uploaded_at': h['uploaded_at'] if h else None})
    return out


def fetch(db, filename):
    row = db.execute('SELECT content, sha256 FROM product_files WHERE file=?', (filename,)).fetchone()
    p = registered(filename)
    if not row or not p or row['sha256'] != p['sha256']:
        return None
    return bytes(row['content'])
