"""Offline tests for the real-time trend desk. No API key or network needed."""
import datetime as dt
import json
from types import SimpleNamespace

import pytest

from marketing import compliance, moments, trend_desk, trend_sources
from marketing.models import MomentTake, TrendPick, TrendPost, TrendRadar

NOW = dt.datetime(2026, 11, 27, 15, 0, tzinfo=dt.timezone.utc)  # Black Friday, 10:00 ET

GOOGLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:ht="https://trends.google.com/trending/rss" version="2.0"><channel>
<item><title>black friday deals</title><ht:approx_traffic>2M+</ht:approx_traffic>
  <ht:news_item><ht:news_item_title>Shoppers line up early</ht:news_item_title>
  <ht:news_item_url>https://news.test/bf</ht:news_item_url></ht:news_item></item>
<item><title>giant pumpkin record</title><ht:approx_traffic>200K+</ht:approx_traffic></item>
<item><title>hurricane warning florida</title><ht:approx_traffic>500K+</ht:approx_traffic></item>
</channel></rss>"""

REDDIT = json.dumps({'data': {'children': [
    {'data': {'title': 'Black Friday deals', 'subreddit': 'popular', 'permalink': '/r/x/1', 'ups': 50000}},
    {'data': {'title': 'Pinned rules', 'stickied': True, 'permalink': '/r/x/2', 'ups': 1}},
    {'data': {'title': 'NSFW thing', 'over_18': True, 'permalink': '/r/x/3', 'ups': 9}},
]}})

WIKI = json.dumps({'mostread': {'articles': [
    {'title': 'Main_Page', 'titles': {'normalized': 'Main Page'}, 'views': 9},
    {'title': 'Giant_pumpkin', 'titles': {'normalized': 'Giant pumpkin'}, 'views': 120000,
     'extract': 'A large pumpkin.'},
]}})


def fetch(url):
    if 'trends.google' in url:
        return GOOGLE_RSS
    if 'reddit' in url:
        if 'wallstreetbets' in url:
            raise OSError('blocked')
        return REDDIT
    return WIKI


def post(**over):
    p = dict(x_post='Black Friday is just FOMO with a parking problem.',
             threads_caption='Black Friday energy, trader edition.', short_hook='Doorbusters vs your stop',
             short_script='Jack holds up a receipt: smaller size today.', visual='Jack on camera',
             reply_line='The real doorbuster is a defined stop.')
    p.update(over)
    return TrendPost(**p)


def pick(trend='black friday deals', speed='post_now', posts=None, **over):
    d = dict(trend=trend, what_happened='Shoppers lined up.', source_url='https://news.test/bf',
             why_viral='Everyone shops today.', bridge='FOMO', speed=speed, found_by_search=False,
             safety_note='Safe, light.', posts=posts if posts is not None else (None if speed == 'skip' else post()))
    d.update(over)
    return TrendPick(**d)


class Fake:
    def __init__(self, radar=None, refuse=False):
        self.calls = []
        self.radar = radar or TrendRadar(picks=[pick(), pick('war update', speed='skip')], moment_takes=[
            MomentTake(moment_id='black_friday', x_post='Half-day session, whole-day feelings.',
                       short_hook='Half-day', short_script='Size down today.')])
        self.refuse = refuse
        self.messages = SimpleNamespace(parse=self._parse)

    def _parse(self, **kw):
        self.calls.append(kw)
        if self.refuse:
            return SimpleNamespace(stop_reason='refusal', parsed_output=None, content=[])
        return SimpleNamespace(stop_reason='end_turn', parsed_output=self.radar, content=[])


# ---- moments calendar -------------------------------------------------------

def test_known_dates():
    assert moments.thanksgiving(2026) == dt.date(2026, 11, 26)
    occ = {(o.moment.id, o.date) for o in moments.occurrences(2026)}
    assert ('black_friday', dt.date(2026, 11, 27)) in occ
    assert ('cyber_monday', dt.date(2026, 11, 30)) in occ
    assert ('fomc', dt.date(2026, 12, 9)) in occ
    assert ('quad_witching', dt.date(2026, 12, 18)) in occ
    assert ('memorial_day', dt.date(2026, 5, 25)) in occ
    assert ('friday_13', dt.date(2026, 11, 13)) in occ
    assert ('super_bowl', dt.date(2027, 2, 14)) in {(o.moment.id, o.date) for o in moments.occurrences(2027)}


def test_upcoming_uses_lead_windows():
    ids = [o.moment.id for o in moments.upcoming(dt.date(2026, 11, 27))]
    assert ids[0] == 'black_friday' and 'cyber_monday' in ids
    assert 'christmas' not in ids  # 28 days out, outside its window
    assert any(o.moment.id == 'christmas' for o in moments.upcoming(dt.date(2026, 11, 27), days=30))


@pytest.mark.parametrize('mid', sorted(moments.MOMENTS))
def test_every_seed_line_passes_the_rules(mid):
    for line in moments.MOMENTS[mid].seeds:
        assert compliance.check_text(line) == [], line
        assert compliance.topic_safety(line) != 'blocked', line
        assert len(compliance.with_risk_line(line, short=True)) <= trend_desk.X_LIMIT, line


def test_respectful_days_have_no_jokes():
    for m in moments.MOMENTS.values():
        if m.kind == 'respectful':
            assert all('closed' in s for s in m.seeds)


# ---- sources and filters ----------------------------------------------------

def test_parsers_and_merge():
    sigs, errors = trend_sources.collect(NOW, fetch=fetch)
    assert errors == ['reddit/wallstreetbets: OSError: blocked']
    titles = [s.title for s in sigs]
    assert 'Pinned rules' not in titles and 'NSFW thing' not in titles and 'Main Page' not in titles
    g = trend_sources.parse_google_trends(GOOGLE_RSS)
    assert g[0].traffic == 2_000_000 and g[0].url == 'https://news.test/bf'
    merged = {s.key: s for s in trend_sources.merge(sigs)}
    assert set(merged['black friday deals'].sources) >= {'google_trends', 'reddit/popular'}


def test_shortlist_drops_tragedy_and_seen_and_ranks_multi_source_first():
    sigs, _ = trend_sources.collect(NOW, fetch=fetch)
    keep, dropped = trend_sources.shortlist(sigs, seen={'giant pumpkin record'})
    keys = [k.key for k in keep]
    assert 'hurricane warning florida' not in keys and dropped['blocked'] == 1
    assert 'giant pumpkin record' not in keys and dropped['seen'] == 1
    assert keys[0] == 'black friday deals'


@pytest.mark.parametrize('text,expected', [
    ('Market crash fears', 'ok'), ('Plane crash in Ohio', 'blocked'), ('Singer dies at 80', 'blocked'),
    ('New tariffs announced', 'caution'), ('Giant pumpkin record', 'ok'), ('Election night', 'caution'),
])
def test_topic_safety(text, expected):
    assert compliance.topic_safety(text) == expected


# ---- the run ----------------------------------------------------------------

def test_run_writes_queue_and_state(tmp_path):
    c = Fake()
    state = tmp_path / 'state.json'
    out, r = trend_desk.run(c, tmp_path / 'out', state, now=NOW, fetch=fetch)
    assert r['ai'] == 'ok' and len(c.calls) == 1
    prompt = c.calls[0]['messages'][0]['content']
    assert 'black friday deals' in prompt and 'hurricane' not in prompt.lower()
    assert any(t['type'] == 'web_search_20260209' for t in c.calls[0]['tools'])
    ready = [i for i in r['items'] if i['status'] == trend_desk.READY]
    assert len(ready) == 1 and compliance.has_risk_line(ready[0]['pick']['posts']['x_post'])
    assert [i['status'] for i in r['items']].count(trend_desk.SKIPPED) == 1
    md = out.read_text()
    assert 'POST NOW' in md and 'Black Friday: 2026-11-27 (today)' in md and 'Skipped' in md
    assert (tmp_path / 'out' / 'latest.md').read_text() == md
    s = json.loads(state.read_text())
    assert 'black friday deals' in s['seen'] and s['ai_runs'] == {'2026-11-27': 1}
    assert 'black_friday:2026-11-27' in s['moments']

    # Second run, same feeds: nothing new and the moment is written, so no AI call.
    _, r2 = trend_desk.run(c, tmp_path / 'out', state, now=NOW + dt.timedelta(minutes=30), fetch=fetch)
    assert r2['ai'] == 'not_needed' and len(c.calls) == 1


def test_rule_hits_hold_a_post(tmp_path):
    bad = TrendRadar(picks=[pick(posts=post(x_post='This setup is so profitable, guaranteed.'))], moment_takes=[])
    _, r = trend_desk.run(Fake(bad), tmp_path / 'o', tmp_path / 's.json', now=NOW, fetch=fetch)
    item = r['items'][0]
    assert item['status'] == trend_desk.NEEDS_CHANGES
    assert {h['rule'] for h in item['rule_hits']['x_post']} >= {'profit_claim', 'guarantee'}
    long = TrendRadar(picks=[pick(posts=post(x_post='x' * 250))], moment_takes=[])
    _, r = trend_desk.run(Fake(long), tmp_path / 'o2', tmp_path / 's2.json', now=NOW, fetch=fetch)
    assert 'length' in {h['rule'] for h in r['items'][0]['rule_hits']['x_post']}


def test_daily_cap_and_failures(tmp_path):
    state = tmp_path / 's.json'
    state.write_text(json.dumps({'ai_runs': {'2026-11-27': 3}}))
    c = Fake()
    _, r = trend_desk.run(c, tmp_path / 'o', state, now=NOW, fetch=fetch, max_ai_runs=3)
    assert r['ai'].startswith('daily_cap') and not c.calls and r['moments']

    _, r = trend_desk.run(Fake(refuse=True), tmp_path / 'o', tmp_path / 's2.json', now=NOW, fetch=fetch)
    assert r['ai'].startswith('failed') and r['candidates']


def test_all_feeds_down_still_searches(tmp_path):
    def down(url):
        raise OSError('no network')
    state = tmp_path / 's.json'
    state.write_text(json.dumps({'moments': {'black_friday:2026-11-27': 'x', 'cyber_monday:2026-11-30': 'x'}}))
    c = Fake()
    _, r = trend_desk.run(c, tmp_path / 'o', state, now=NOW, fetch=down)
    assert len(r['feed_errors']) == 5 and r['ai'] == 'ok'
    assert 'web search' in c.calls[0]['messages'][0]['content']


def test_dry_run_needs_no_client_and_keeps_state(tmp_path):
    state = tmp_path / 's.json'
    _, r = trend_desk.run(None, tmp_path / 'o', state, now=NOW, fetch=fetch, dry_run=True)
    assert r['ai'] == 'dry_run' and r['candidates'] and not state.exists()


def test_alert_text_and_webhook_shapes():
    r = {'time': '2026-11-27T10:00-05:00', 'items': [trend_desk.check_pick(pick())],
         'moments': [{'name': 'Black Friday', 'days_away': 0, 'fresh': True, 'seeds': ['Line one']}]}
    text = trend_desk.alert_text(r)
    assert 'POST NOW' in text and 'Today is Black Friday' in text and len(text) <= 1900
    assert trend_desk.alert_text({'time': r['time'], 'items': [], 'moments': []}) == ''

    sent = []

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def opener(req, timeout):
        sent.append(json.loads(req.data))
        return Resp()
    assert trend_desk.send_alert('https://hooks.slack.com/x', 'hi', opener=opener)
    assert trend_desk.send_alert('https://discord.com/api/webhooks/x', 'hi', opener=opener)
    assert sent == [{'text': 'hi'}, {'content': 'hi'}]
    assert not trend_desk.send_alert('', 'hi', opener=opener)


def test_calendar_cli(capsys):
    assert trend_desk.main(['--calendar', '5']) == 0
    assert 'Moments calendar' in capsys.readouterr().out


def test_cli_without_key(monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    assert trend_desk.main(['--out', '/nonexistent-never-written']) == 2
