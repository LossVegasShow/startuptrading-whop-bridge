"""Check that every live page runs the current analytics scripts.

    python growth/gtm/check_live.py            # checks https://startuptrading.com
    python growth/gtm/check_live.py --base URL

GoHighLevel puts each page's embed in the page body (runs first) and injects the
site-wide header code afterwards. If a page's embed is older than the header, the
older script claims the once-per-page sut_attribution event and GTM gets its
(old-shaped) payload. This compares every copy of tracking.js on each page with the
repository's sales-site/src/tracking.js and exits non-zero on any stale copy.
"""
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGES = ['/', '/join', '/free-tools', '/futures-position-size-calculator',
         '/tradingview/atr-position-size-planner', '/welcome', '/setup']


def core_hash(js):
    if '/*track-core*/' not in js:
        return None
    core = js.split('/*track-core*/')[1].split('/*end-track-core*/')[0]
    return hashlib.sha256(core.encode()).hexdigest()[:12]


def analyze(html, repo_tracking):
    """[(where, 'current'|'stale', hash)] for every tracking.js copy in a GoHighLevel page."""
    want = core_hash(repo_tracking)
    out = []
    for s in re.findall(r'<script(?![^>]*application/json)[^>]*>(.*?)</script>', html, re.S):
        h = core_hash(s)
        if h:
            out.append(('page body' + (' (header code)' if 'SUT_GTM_ID' in s else ' (embed)'), 'current' if h == want else 'stale', h))
    m = re.search(r'id="__NUXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if m:
        try:
            data = json.loads(m.group(1))
        except ValueError:
            data = []
        for x in data:
            if isinstance(x, str):
                h = core_hash(x)
                if h:
                    out.append(('injected' + (' (header code)' if 'SUT_GTM_ID' in x else ' (embed)'), 'current' if h == want else 'stale', h))
    return out


def main(base='https://startuptrading.com'):
    repo = (ROOT / 'sales-site' / 'src' / 'tracking.js').read_text()
    bad = 0
    for p in PAGES:
        req = urllib.request.Request(base + p, headers={'User-Agent': 'sut-check-live'})
        html = urllib.request.urlopen(req, timeout=30).read().decode('utf-8', 'replace')
        copies = analyze(html, repo)
        stale = [c for c in copies if c[1] == 'stale']
        bad += len(stale)
        status = 'OK' if copies and not stale else ('NO TRACKING' if not copies else 'STALE: re-paste this page\'s embed')
        print(f'{p:42} {status:40} ' + ', '.join(f'{w}={s}' for w, s, _ in copies))
    return 1 if bad else 0


if __name__ == '__main__':
    base = sys.argv[sys.argv.index('--base') + 1] if '--base' in sys.argv else 'https://startuptrading.com'
    sys.exit(main(base))
