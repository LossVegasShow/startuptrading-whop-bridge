"""Weekly run: research -> metrics -> plan -> write -> compliance -> approval queue.

Nothing is posted anywhere. The output is a review queue (queue.md for
people, queue.json for tools) that a person approves before anything goes
live.
"""
import datetime as dt
import json
from pathlib import Path

from . import agents, compliance, desks

READY = 'ready_for_review'
NEEDS_CHANGES = 'needs_changes'
FAILED = 'failed'


def _pack_fields(pack):
    fields = {'youtube_title': pack.youtube_title, 'youtube_description': pack.youtube_description,
              'shorts_script': pack.shorts_script, 'email_subject': pack.email_subject,
              'email_body': pack.email_body}
    for i, post in enumerate(pack.x_posts, 1):
        fields[f'x_post_{i}'] = post
    return fields


def _add_risk_lines(pack):
    pack.youtube_description = compliance.with_risk_line(pack.youtube_description)
    pack.email_body = compliance.with_risk_line(pack.email_body)
    pack.shorts_script = compliance.with_risk_line(pack.shorts_script, short=True)
    pack.x_posts = [compliance.with_risk_line(p, short=True) for p in pack.x_posts]
    return pack


def produce(client, brief):
    """Write one brief, review it, and return a queue item dict."""
    item = {'brief': brief.model_dump(), 'status': FAILED, 'issues': [], 'rule_hits': {}, 'pack': None}
    try:
        draft = agents.write_pack(client, brief)
        hits = compliance.check_pack(_pack_fields(draft))
        review = agents.review_pack(client, draft, hits)
    except agents.AgentError as e:
        item['issues'] = [f'Agent error: {e}']
        return item
    pack = _add_risk_lines(review.revised)
    remaining = compliance.check_pack(_pack_fields(pack))
    item.update(pack=pack.model_dump(), issues=review.issues, rule_hits=remaining,
                status=READY if review.approved and not remaining else NEEDS_CHANGES)
    return item


def read_metrics(metrics_dir):
    """Concatenate CSV/TXT exports (Whop, GHL, YouTube Studio) into one text block."""
    d = Path(metrics_dir) if metrics_dir else None
    if not d or not d.is_dir():
        return ''
    parts = []
    for f in sorted(d.iterdir()):
        if f.suffix.lower() in ('.csv', '.txt', '.md') and f.is_file() and not f.name.upper().startswith('README'):
            parts.append(f'--- {f.name} ---\n' + f.read_text(encoding='utf-8', errors='replace')[:20000])
    return '\n\n'.join(parts)


def run(client, out_root, metrics_dir=None, today=None, max_briefs=5, outreach=0, contacted_path=None,
        transcripts_dir=None):
    """One weekly run. outreach = how many prospects to find (0 skips the outreach desk)."""
    today = today or dt.date.today()
    out = Path(out_root) / today.isoformat()
    out.mkdir(parents=True, exist_ok=True)

    report = agents.research(client)
    metrics_text = read_metrics(metrics_dir)
    kpis = agents.analyze(client, metrics_text) if metrics_text else None
    plan = agents.plan_week(client, report, kpis)
    items = [produce(client, b) for b in plan.briefs[:max_briefs]]

    outreach_items = _desk(lambda: desks.run_outreach(client, outreach, contacted_path)) if outreach else []
    clip_items = _desk(lambda: desks.run_clips(client, transcripts_dir)) if transcripts_dir else []

    date = today.isoformat()
    result = {'date': date, 'theme': plan.theme, 'rationale': plan.rationale,
              'research': report.model_dump(), 'kpis': kpis.model_dump() if kpis else None, 'items': items,
              'outreach': outreach_items, 'clips': clip_items}
    (out / 'queue.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    (out / 'queue.md').write_text(render_markdown(result), encoding='utf-8')
    if outreach_items:
        (out / 'outreach.md').write_text(desks.render_outreach(outreach_items, date), encoding='utf-8')
    if clip_items:
        (out / 'clips.md').write_text(desks.render_clips(clip_items, date), encoding='utf-8')
    return out, result


def _desk(fn):
    """A failing side desk shouldn't sink the content queue."""
    try:
        return fn()
    except agents.AgentError as e:
        return [{'status': FAILED, 'error': str(e)}]


def render_markdown(r):
    ready = sum(i['status'] == READY for i in r['items'])
    lines = [f"# Marketing queue: week of {r['date']}", '',
             f"**Theme:** {r['theme']}", '', r['rationale'], '',
             f"{ready} of {len(r['items'])} pieces are ready for your review. "
             'Nothing has been posted. Approve, edit or reject each one before publishing.', '']
    if r.get('kpis'):
        k = r['kpis']
        lines += ['## Metrics', '', k['summary'], '']
        lines += [f'- Win: {w}' for w in k['wins']] + [f'- Concern: {c}' for c in k['concerns']]
        lines += [f'- Next week: {x}' for x in k['recommendations']] + ['']
    extra = []
    if r.get('outreach'):
        extra.append(f"{sum(i.get('status') == READY for i in r['outreach'])} outreach pitches in `outreach.md`")
    if r.get('clips'):
        extra.append(f"{sum(i.get('status') == READY for i in r['clips'])} clips in `clips.md`")
    if extra:
        lines += ['Also this week: ' + '; '.join(extra) + '.', '']
    lines += ['## Record this week', '',
              'What Jack needs to capture on stream so the team can cut these pieces:', '']
    lines += [f"- [ ] **{i['brief']['title']}**: {i['brief']['record_this']}" for i in r['items']] + ['']
    for n, i in enumerate(r['items'], 1):
        b = i['brief']
        lines += [f"## {n}. {b['title']}", '',
                  f"Status: **{i['status']}** · pillar: {b['pillar']} · CTA: {b['call_to_action']}", '']
        if i['issues']:
            lines += ['Compliance notes:', ''] + [f'- {x}' for x in i['issues']] + ['']
        for field, hits in (i['rule_hits'] or {}).items():
            lines += [f"- ⚠ {field}: \"{h['match']}\" ({h['why']})" for h in hits]
        p = i['pack']
        if p:
            lines += ['### YouTube', '', f"**{p['youtube_title']}**", '', p['youtube_description'], '',
                      '### Short (script)', '', p['shorts_script'], '', '### X posts', '']
            lines += [f'{k}. {x}' for k, x in enumerate(p['x_posts'], 1)]
            lines += ['', '### Email', '', f"**Subject:** {p['email_subject']}", '', p['email_body'], '']
    lines += ['## Research', '']
    lines += [f"- {f['summary']}" + (f" ([source]({f['source_url']}))" if f['source_url'] else '')
              for f in r['research']['competitor_moves']]
    lines += [f'- Traders are asking: {q}' for q in r['research']['audience_questions']]
    return '\n'.join(lines) + '\n'
