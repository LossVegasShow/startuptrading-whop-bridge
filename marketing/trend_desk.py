"""The trend desk: real-time trend-jacking for the awareness offensive.

    python -m marketing.trend_desk                 # one radar run (needs ANTHROPIC_API_KEY)
    python -m marketing.trend_desk --dry-run       # feeds + calendar only, no AI, no key needed
    python -m marketing.trend_desk --calendar 45   # print the next 45 days of moments with ready lines

Each run:
  feeds (Google Trends, Reddit, Wikipedia) -> merge -> topic safety filter -> drop already-seen
  -> shortlist -> one AI call (verify with web search, rank, write) -> phrase rules -> alert + queue

Nothing is posted automatically. The alert goes to a phone-friendly Discord or Slack channel
(TREND_ALERT_WEBHOOK) so one person can approve and post within minutes. See
growth/TREND_JACKING_PLAYBOOK.md for the approval rules.

The AI is only called when there is something new, and at most --max-ai-runs times a day, so a
radar that runs every 30 minutes stays cheap on quiet days.
"""
import argparse
import datetime as dt
import json
import os
import sys
import urllib.request
from pathlib import Path

from . import agents, compliance, moments, trend_sources

READY = 'ready_for_review'
NEEDS_CHANGES = 'needs_changes'
SKIPPED = 'skipped'
SEEN_HOURS = 72
X_LIMIT = 280

try:
    from zoneinfo import ZoneInfo
    ET_TZ = ZoneInfo('America/New_York')
except Exception:  # no tz database (some Windows installs): fall back to UTC labels
    ET_TZ = dt.timezone.utc


# ---- state -------------------------------------------------------------------

def load_state(path):
    p = Path(path) if path else None
    if p and p.is_file():
        try:
            s = json.loads(p.read_text(encoding='utf-8'))
            return {'seen': s.get('seen', {}), 'moments': s.get('moments', {}), 'ai_runs': s.get('ai_runs', {})}
        except (ValueError, OSError):
            pass
    return {'seen': {}, 'moments': {}, 'ai_runs': {}}


def save_state(path, state, now):
    cutoff = now - dt.timedelta(hours=SEEN_HOURS)
    state['seen'] = {k: v for k, v in state['seen'].items() if dt.datetime.fromisoformat(v) >= cutoff}
    today = now.date().isoformat()
    state['ai_runs'] = {d: n for d, n in state['ai_runs'].items() if d >= (now.date() - dt.timedelta(days=7)).isoformat()}
    state['moments'] = {k: v for k, v in state['moments'].items() if k.rsplit(':', 1)[-1] >= today}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(state, indent=1, sort_keys=True), encoding='utf-8')


# ---- compliance on a pick -------------------------------------------------------

def check_pick(pick):
    """Add risk lines, run the phrase rules and the topic filter on the copy. Returns a queue item."""
    item = {'pick': pick.model_dump(), 'rule_hits': {}, 'status': SKIPPED}
    if pick.speed == 'skip' or not pick.posts:
        return item
    p = pick.posts
    p.x_post = compliance.with_risk_line(p.x_post, short=True)
    p.threads_caption = compliance.with_risk_line(p.threads_caption, short=True)
    p.short_script = compliance.with_risk_line(p.short_script, short=True)
    fields = {'x_post': p.x_post, 'threads_caption': p.threads_caption, 'short_hook': p.short_hook,
              'short_script': p.short_script, 'reply_line': p.reply_line}
    hits = compliance.check_pack(fields)
    for name, text in fields.items():
        if compliance.BLOCKED_TOPICS.search(text):
            hits.setdefault(name, []).append({'rule': 'sensitive_topic', 'match': 'sensitive word',
                                              'why': 'Never joke about tragedy, violence or illness.'})
    if len(p.x_post) > X_LIMIT:
        hits.setdefault('x_post', []).append({'rule': 'length', 'match': f'{len(p.x_post)} chars',
                                              'why': f'Over {X_LIMIT} characters with the risk line.'})
    item.update(pick=pick.model_dump(), rule_hits=hits, status=READY if not hits else NEEDS_CHANGES)
    return item


def check_take(take):
    take.x_post = compliance.with_risk_line(take.x_post, short=True)
    take.short_script = compliance.with_risk_line(take.short_script, short=True)
    hits = compliance.check_pack({'x_post': take.x_post, 'short_hook': take.short_hook,
                                  'short_script': take.short_script})
    return {**take.model_dump(), 'rule_hits': hits, 'status': READY if not hits else NEEDS_CHANGES}


# ---- the run -------------------------------------------------------------------

def due_moments(today, state):
    """Moments in their lead window; `fresh` is True the first time each one is seen."""
    out = []
    for o in moments.upcoming(today):
        key = f'{o.moment.id}:{o.date.isoformat()}'
        out.append({'id': o.moment.id, 'name': o.moment.name, 'kind': o.moment.kind, 'date': o.date.isoformat(),
                    'days_away': o.days_away, 'angle': o.moment.angle, 'seeds': list(o.moment.seeds),
                    'verify': o.moment.verify, 'notes': o.moment.notes, 'extra': o.extra,
                    'key': key, 'fresh': key not in state['moments']})
    return out


def run(client, out_root, state_path, now=None, limit=15, max_ai_runs=16, fetch=trend_sources._get,
        dry_run=False):
    now = now or dt.datetime.now(dt.timezone.utc)
    local = now.astimezone(ET_TZ)
    state = load_state(state_path)

    signals, errors = trend_sources.collect(now, fetch=fetch)
    candidates, dropped = trend_sources.shortlist(signals, seen=state['seen'], limit=limit)
    due = due_moments(local.date(), state)
    # Respectful days never get AI jokes; their seed notice is enough.
    fresh = [m for m in due if m['fresh'] and m['kind'] != 'respectful']
    runs_today = state['ai_runs'].get(local.date().isoformat(), 0)
    all_feeds_failed = not signals and bool(errors)

    result = {'time': local.isoformat(timespec='minutes'), 'feed_errors': errors, 'signals': len(signals),
              'dropped': dropped, 'candidates': [c.to_dict() for c in candidates], 'moments': due,
              'items': [], 'moment_takes': [], 'ai': 'not_needed'}

    if dry_run:
        result['ai'] = 'dry_run'
    elif not (candidates or fresh or all_feeds_failed):
        result['ai'] = 'not_needed'
    elif runs_today >= max_ai_runs:
        result['ai'] = f'daily_cap_reached ({max_ai_runs})'
    else:
        payload = [{'title': c.title, 'detail': c.detail, 'sources': c.sources, 'traffic': c.traffic,
                    'safety': c.safety} for c in candidates]
        moment_payload = [{k: m[k] for k in ('id', 'name', 'kind', 'date', 'angle', 'seeds')} for m in fresh]
        try:
            radar = agents.trend_jockey(client, local.strftime('%A %Y-%m-%d %H:%M ET'), payload,
                                        moment_payload, errors)
            result['items'] = [check_pick(p) for p in radar.picks]
            result['moment_takes'] = [check_take(t) for t in radar.moment_takes]
            result['ai'] = 'ok'
            for m in fresh:
                state['moments'][m['key']] = now.isoformat()
        except agents.AgentError as e:
            result['ai'] = f'failed: {e}'
        except Exception as e:  # API/network errors: keep the feed and calendar output
            result['ai'] = f'failed: {type(e).__name__}: {str(e)[:160]}'
        state['ai_runs'][local.date().isoformat()] = runs_today + 1
        # Mark what the AI saw as seen even on failure, so a bad topic doesn't burn every run.
        for c in candidates:
            state['seen'][c.key] = now.isoformat()
        for i in result['items']:
            state['seen'][trend_sources.normalize(i['pick']['trend'])] = now.isoformat()

    if not dry_run:
        for m in due:  # remembrance days get their notice once, never an AI take
            if m['kind'] == 'respectful':
                state['moments'].setdefault(m['key'], now.isoformat())
    out = write_outputs(out_root, result, local)
    if not dry_run:
        save_state(state_path, state, now)
    return out, result


def write_outputs(out_root, result, local):
    day = Path(out_root) / local.date().isoformat()
    day.mkdir(parents=True, exist_ok=True)
    stamp = local.strftime('%H%M')
    md = render_markdown(result)
    (day / f'trends-{stamp}.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    (day / f'trends-{stamp}.md').write_text(md, encoding='utf-8')
    (Path(out_root) / 'latest.md').write_text(md, encoding='utf-8')
    return day / f'trends-{stamp}.md'


# ---- rendering -----------------------------------------------------------------

SPEED_LABEL = {'post_now': '🔴 POST NOW (within 60 min)', 'post_today': '🟠 Post today', 'watch': '🟡 Watch',
               'skip': '⚪ Skip'}


def _hits(lines, rule_hits):
    for field, hits in (rule_hits or {}).items():
        lines += [f"- ⚠ {field}: \"{h['match']}\" ({h['why']})" for h in hits]


def render_markdown(r):
    live = [i for i in r['items'] if i['status'] != SKIPPED]
    lines = [f"# Trend desk: {r['time']}", '',
             f"{len(live)} trend posts and {len(r['moment_takes'])} moment takes drafted. Nothing has been posted. "
             'Approve, tweak and post, following the playbook (growth/TREND_JACKING_PLAYBOOK.md).', '',
             f"Feeds: {r['signals']} signals, {r['dropped']['blocked']} dropped as sensitive, "
             f"{r['dropped']['seen']} already seen, {len(r['candidates'])} shortlisted. AI: {r['ai']}.", '']
    if r['feed_errors']:
        lines += ['Feeds that failed: ' + '; '.join(r['feed_errors']), '']
    order = {'post_now': 0, 'post_today': 1, 'watch': 2, 'skip': 3}
    for n, i in enumerate(sorted(live, key=lambda i: order[i['pick']['speed']]), 1):
        p, posts = i['pick'], i['pick']['posts']
        lines += [f"## {n}. {p['trend']}", '', f"**{SPEED_LABEL[p['speed']]}** · status: **{i['status']}**"
                  + (' · found by search' if p['found_by_search'] else ''), '',
                  f"- What happened: {p['what_happened']}" + (f" ([source]({p['source_url']}))" if p['source_url'] else ''),
                  f"- Why it's viral: {p['why_viral']}", f"- Trader bridge: {p['bridge']}",
                  f"- Safety: {p['safety_note']}", '']
        _hits(lines, i['rule_hits'])
        lines += ['**X / Threads**', '', posts['x_post'], '', '**Instagram / TikTok caption**', '',
                  posts['threads_caption'], '', f"**Short:** hook \"{posts['short_hook']}\"", '',
                  posts['short_script'], '', f"**Visual:** {posts['visual']}", '',
                  f"**Reply to drop under big posts:** {posts['reply_line']}", '']
    if r['moment_takes']:
        lines += ['## Fresh takes on upcoming moments', '']
        for t in r['moment_takes']:
            lines += [f"### {t['moment_id']} · {t['status']}", '']
            _hits(lines, t['rule_hits'])
            lines += [t['x_post'], '', f"Short hook: \"{t['short_hook']}\"", '', t['short_script'], '']
    if r['moments']:
        lines += render_moments(r['moments'])
    skipped = [i['pick'] for i in r['items'] if i['status'] == SKIPPED]
    if skipped:
        lines += ['## Skipped', ''] + [f"- {p['trend']}: {p['safety_note']}" for p in skipped] + ['']
    return '\n'.join(lines) + '\n'


def render_moments(due):
    lines = ['## On the calendar (ready-to-post lines)', '']
    for m in due:
        when = 'today' if m['days_away'] == 0 else f"in {m['days_away']} day{'s' * (m['days_away'] != 1)}"
        lines += [f"### {m['name']}: {m['date']} ({when})", '', f"Angle: {m['angle']}"
                  + (f" · {m['notes']}" if m['notes'] else '')
                  + (' · **verify the date/time before posting**' if m['verify'] else ''), '']
        lines += [f'- {compliance.with_risk_line(s, short=True)}'.replace('\n\n', ' ') for s in m['seeds']] + ['']
    return lines


def render_calendar(today, days):
    due = [{'name': o.moment.name, 'date': o.date.isoformat(), 'days_away': o.days_away, 'angle': o.moment.angle,
            'notes': o.moment.notes, 'verify': o.moment.verify, 'seeds': o.moment.seeds}
           for o in moments.upcoming(today, days)]
    return '\n'.join([f'# Moments calendar: {today.isoformat()} + {days} days', ''] + render_moments(due)) + '\n'


# ---- alert -----------------------------------------------------------------------

def alert_text(result, limit=1900):
    """Short, phone-friendly. Only post_now and post_today items that passed the rules."""
    hot = [i for i in result['items'] if i['status'] == READY and i['pick']['speed'] in ('post_now', 'post_today')]
    today = [m for m in result['moments'] if m['days_away'] == 0 and m['fresh']]
    if not hot and not today:
        return ''
    parts = [f"Trend desk {result['time'][11:16]} ET: {len(hot)} ready"]
    for i in hot:
        p = i['pick']
        parts.append(f"\n{SPEED_LABEL[p['speed']]}: {p['trend']}\n{p['posts']['x_post']}")
    for m in today:
        parts.append(f"\nToday is {m['name']}. Ready line:\n{m['seeds'][0]}")
    parts.append('\nFull queue: the latest trend-radar run in GitHub Actions.')
    text = '\n'.join(parts)
    return text if len(text) <= limit else text[:limit - 1] + '…'


def send_alert(url, text, opener=urllib.request.urlopen):
    if not url or not text:
        return False
    key = 'text' if 'hooks.slack.com' in url else 'content'
    req = urllib.request.Request(url, data=json.dumps({key: text}).encode(), method='POST',
                                 headers={'Content-Type': 'application/json',
                                          'User-Agent': trend_sources.USER_AGENT})
    try:
        with opener(req, timeout=15):
            return True
    except Exception as e:
        print(f'Alert webhook failed: {type(e).__name__}', file=sys.stderr)
        return False


# ---- CLI -------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m marketing.trend_desk', description='Run the real-time trend desk.')
    ap.add_argument('--out', default='marketing/out/trends')
    ap.add_argument('--state', default='marketing/out/trend_state.json', help='Seen-topics memory between runs.')
    ap.add_argument('--limit', type=int, default=15, help='Candidates the AI sees per run.')
    ap.add_argument('--max-ai-runs', type=int, default=16, help='Cap on AI calls per day (ET).')
    ap.add_argument('--dry-run', action='store_true', help='Feeds and calendar only. No AI, no state change.')
    ap.add_argument('--calendar', type=int, metavar='DAYS', help='Print the moments calendar and exit.')
    args = ap.parse_args(argv)

    if args.calendar is not None:
        print(render_calendar(dt.datetime.now(ET_TZ).date(), args.calendar))
        return 0
    client = None
    if not args.dry_run:
        if not os.environ.get('ANTHROPIC_API_KEY'):
            print('ANTHROPIC_API_KEY is not set (see marketing/README.md). Use --dry-run to test the feeds.',
                  file=sys.stderr)
            return 2
        import anthropic  # imported here so the tests don't need the SDK installed
        client = anthropic.Anthropic(max_retries=3)
    out, result = run(client, args.out, args.state, limit=args.limit, max_ai_runs=args.max_ai_runs,
                      dry_run=args.dry_run)
    sent = send_alert(os.environ.get('TREND_ALERT_WEBHOOK', ''), alert_text(result))
    ready = sum(i['status'] == READY for i in result['items'])
    print(f"Wrote {out}: {ready} ready, {len(result['candidates'])} candidates, AI {result['ai']}, "
          f"alert {'sent' if sent else 'not sent'}.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
