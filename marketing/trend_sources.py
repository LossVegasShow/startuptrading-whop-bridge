"""Live trend signals: what the internet is talking about right now.

Each source is a free, public feed. A source that fails (blocked, rate limited, changed shape) is
reported and skipped; the run continues with the rest. Everything here is plain stdlib so the
radar can run every 30 minutes without extra dependencies.

The AI step (agents.trend_jockey) adds web search on top, which catches what's viral on X, TikTok
and Instagram, where there's no free feed.
"""
import datetime as dt
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from typing import List, Optional

from . import compliance

USER_AGENT = 'StartUpTrading-trend-radar/1.0 (marketing research; contact via website)'
TIMEOUT = 15

GOOGLE_TRENDS_RSS = 'https://trends.google.com/trending/rss?geo=US'
REDDIT_HOT = 'https://www.reddit.com/r/{sub}/hot.json?limit=25&raw_json=1'
REDDIT_SUBS = ('popular', 'wallstreetbets', 'FuturesTrading')
WIKI_MOST_READ = 'https://api.wikimedia.org/feed/v1/wikipedia/en/featured/{y}/{m:02d}/{d:02d}'

# Words that make a trend easier to bridge to trading. They lift a trend's pre-score;
# they never decide on their own (the AI judges the bridge).
TRADER_ADJACENT = re.compile(
    r'\b(?:fed|fomc|powell|rates?|inflation|cpi|jobs|unemployment|recession|stocks?|market|dow|nasdaq|s&p|'
    r'nvidia|apple|tesla|microsoft|amazon|meta|google|openai|ai|bitcoin|crypto|gold|oil|dollar|yen|'
    r'earnings|ipo|crash|rally|bubble|billion|trillion|bank|price|prices|sale|deal|black friday|cyber monday|'
    r'super bowl|bet|betting|odds|lottery|powerball|jackpot|record)\b', re.IGNORECASE)


@dataclass
class Signal:
    title: str
    source: str
    detail: str = ''
    url: str = ''
    traffic: int = 0
    sources: List[str] = field(default_factory=list)
    safety: str = 'ok'
    score: float = 0.0

    @property
    def key(self):
        return normalize(self.title)

    def to_dict(self):
        return {k: v for k, v in asdict(self).items()}


def normalize(title):
    return re.sub(r'[^a-z0-9]+', ' ', (title or '').lower()).strip()


def _get(url, opener=None):
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': '*/*'})
    with (opener or urllib.request.urlopen)(req, timeout=TIMEOUT) as r:
        return r.read().decode('utf-8', errors='replace')


def _traffic(text):
    """'200K+' -> 200000, '2M+' -> 2000000."""
    m = re.match(r'\s*([\d.,]+)\s*([KkMm]?)', text or '')
    if not m:
        return 0
    n = float(m.group(1).replace(',', ''))
    return int(n * {'k': 1e3, 'm': 1e6}.get(m.group(2).lower(), 1))


def _local(tag):
    return tag.rsplit('}', 1)[-1]


def _child(el, name):
    """First child with this local name, whatever its namespace (Google has changed it before)."""
    return next((c for c in el if _local(c.tag) == name), None)


def _text(el, name):
    c = _child(el, name) if el is not None else None
    return (c.text or '').strip() if c is not None and c.text else ''


def parse_google_trends(xml_text):
    root = ET.fromstring(xml_text)
    out = []
    for item in root.iter('item'):
        title = _text(item, 'title')
        if not title:
            continue
        news = _child(item, 'news_item')
        out.append(Signal(title=title, source='google_trends', detail=_text(news, 'news_item_title'),
                          url=_text(news, 'news_item_url'), traffic=_traffic(_text(item, 'approx_traffic'))))
    return out


def parse_reddit(json_text, sub):
    data = json.loads(json_text)
    out = []
    for child in data.get('data', {}).get('children', []):
        p = child.get('data', {})
        if p.get('stickied') or p.get('over_18'):
            continue
        out.append(Signal(title=(p.get('title') or '').strip(), source=f'reddit/{sub}',
                          detail=f"r/{p.get('subreddit', sub)}", url='https://www.reddit.com' + p.get('permalink', ''),
                          traffic=int(p.get('ups') or 0)))
    return [s for s in out if s.title]


def parse_wikipedia(json_text, limit=25):
    data = json.loads(json_text)
    skip = ('Main_Page', 'Special:', 'Wikipedia:', 'Portal:', 'File:')
    out = []
    for a in data.get('mostread', {}).get('articles', [])[:limit]:
        title = (a.get('titles') or {}).get('normalized') or a.get('title', '')
        if not title or a.get('title', '').startswith(skip):
            continue
        out.append(Signal(title=title, source='wikipedia', detail=(a.get('extract') or '')[:200],
                          url=((a.get('content_urls') or {}).get('desktop') or {}).get('page', ''),
                          traffic=int(a.get('views') or 0)))
    return out


def collect(now: Optional[dt.datetime] = None, fetch=_get):
    """Fetch every source. Returns (signals, errors). `fetch(url)` is swappable for tests."""
    now = now or dt.datetime.now(dt.timezone.utc)
    signals, errors = [], []
    jobs = [('google_trends', GOOGLE_TRENDS_RSS, parse_google_trends)]
    jobs += [(f'reddit/{s}', REDDIT_HOT.format(sub=s), lambda t, s=s: parse_reddit(t, s)) for s in REDDIT_SUBS]
    y = (now - dt.timedelta(days=1)).date()  # the most-read list is published for the previous day
    jobs.append(('wikipedia', WIKI_MOST_READ.format(y=y.year, m=y.month, d=y.day), parse_wikipedia))
    for name, url, parse in jobs:
        try:
            signals += parse(fetch(url))
        except Exception as e:  # one broken feed must not stop the radar
            errors.append(f'{name}: {type(e).__name__}: {str(e)[:120]}')
    return signals, errors


def merge(signals):
    """Merge the same topic seen in several feeds. Being in more than one feed is the best virality tell."""
    by_key = {}
    for s in signals:
        k = s.key
        if not k:
            continue
        if k in by_key:
            m = by_key[k]
            m.traffic = max(m.traffic, s.traffic)
            m.detail = m.detail or s.detail
            m.url = m.url or s.url
            if s.source not in m.sources:
                m.sources.append(s.source)
        else:
            s.sources = [s.source]
            by_key[k] = s
    return list(by_key.values())


def score(s: Signal):
    """A rough pre-score so the AI only sees the strongest candidates."""
    base = {'google_trends': 3.0, 'reddit/popular': 2.0, 'wikipedia': 1.5,
            'reddit/wallstreetbets': 2.5, 'reddit/FuturesTrading': 2.0}
    pts = max(base.get(src, 1.0) for src in s.sources) + 2.0 * (len(s.sources) - 1)
    if s.traffic:
        pts += min(3.0, len(str(s.traffic)) / 2)  # roughly log10 of traffic, capped
    if TRADER_ADJACENT.search(f'{s.title} {s.detail}'):
        pts += 2.0
    if s.safety == 'caution':
        pts -= 1.0
    return round(pts, 2)


def shortlist(signals, seen=(), limit=15):
    """Merge, drop unsafe and already-seen topics, score, and keep the top `limit`.

    Returns (candidates, dropped) where dropped counts why topics were removed."""
    dropped = {'blocked': 0, 'seen': 0}
    keep = []
    for s in merge(signals):
        s.safety = compliance.topic_safety(f'{s.title} {s.detail}')
        if s.safety == 'blocked':
            dropped['blocked'] += 1
            continue
        if s.key in seen:
            dropped['seen'] += 1
            continue
        s.score = score(s)
        keep.append(s)
    keep.sort(key=lambda s: (-s.score, -s.traffic))
    return keep[:limit], dropped
