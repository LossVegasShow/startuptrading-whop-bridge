"""The outreach desk and the clip desk.

Outreach: finds podcasts, prop firms, communities, newsletters and journalists,
then drafts a personal pitch for each. A person sends them from their own email.

Clips: reads stream transcripts dropped in marketing/transcripts/ and picks
the best short-form moments, captioned in English and Spanish.

Both only produce drafts. Phrase-rule hits hold an item as needs_changes.
"""
from pathlib import Path

from . import agents, compliance

READY = 'ready_for_review'
NEEDS_CHANGES = 'needs_changes'
TRANSCRIPT_TYPES = ('.txt', '.srt', '.vtt')
MAX_TRANSCRIPT_CHARS = 120_000


def read_contacted(path):
    """One prospect name per line; '#' starts a comment."""
    p = Path(path) if path else None
    if not p or not p.is_file():
        return []
    names = [line.split('#', 1)[0].strip() for line in p.read_text(encoding='utf-8').splitlines()]
    return [n for n in names if n]


def run_outreach(client, count=10, contacted_path=None):
    contacted = read_contacted(contacted_path)
    skip = {c.lower() for c in contacted}
    prospects = agents.find_prospects(client, count, contacted)
    prospects.prospects = [p for p in prospects.prospects if p.name.lower() not in skip]
    if not prospects.prospects:
        return []
    pitches = {p.prospect_name.lower(): p for p in agents.write_pitches(client, prospects).pitches}
    items = []
    for pr in prospects.prospects:
        pitch = pitches.get(pr.name.lower())
        hits = compliance.check_pack({'subject': pitch.subject, 'body': pitch.body,
                                      'follow_up': pitch.follow_up}) if pitch else {}
        items.append({'prospect': pr.model_dump(), 'pitch': pitch.model_dump() if pitch else None,
                      'rule_hits': hits,
                      'status': READY if pitch and not hits else NEEDS_CHANGES})
    return items


def read_transcripts(folder):
    d = Path(folder) if folder else None
    if not d or not d.is_dir():
        return []
    return [(f.name, f.read_text(encoding='utf-8', errors='replace')[:MAX_TRANSCRIPT_CHARS])
            for f in sorted(d.iterdir())
            if f.is_file() and f.suffix.lower() in TRANSCRIPT_TYPES and not f.name.upper().startswith('README')]


def run_clips(client, folder, max_clips=6):
    items = []
    for name, text in read_transcripts(folder):
        try:
            clips = agents.find_clips(client, name, text, max_clips).clips
        except agents.AgentError as e:
            items.append({'source_file': name, 'status': 'failed', 'error': str(e)})
            continue
        for c in clips:
            c.caption_en = compliance.with_risk_line(c.caption_en, short=True)
            c.caption_es = compliance.with_risk_line(c.caption_es, spanish=True)
            hits = compliance.check_pack({'hook': c.hook, 'caption_en': c.caption_en, 'caption_es': c.caption_es})
            items.append({**c.model_dump(), 'rule_hits': hits, 'status': READY if not hits else NEEDS_CHANGES})
    return items


def render_outreach(items, date):
    ready = sum(i.get('status') == READY for i in items)
    lines = [f'# Outreach: week of {date}', '',
             f'{ready} of {len(items)} pitches are ready. Nothing has been sent. Send each one from your own '
             'email or the contact route listed, then add the name to `marketing/outreach/contacted.txt` '
             'so it is skipped next week.', '']
    for n, i in enumerate(items, 1):
        if 'error' in i:
            lines += [f"- ⚠ The outreach desk failed this week: {i['error']}", '']
            continue
        p, pitch = i['prospect'], i['pitch']
        lines += [f"## {n}. {p['name']} ({p['kind']})", '',
                  f"Status: **{i['status']}** · [{p['url']}]({p['url']})", '',
                  f"- Audience: {p['audience']}", f"- Why Jack fits: {p['why_fit']}",
                  f"- Contact: {p['contact_route']}", '']
        for field, hits in (i['rule_hits'] or {}).items():
            lines += [f"- ⚠ {field}: \"{h['match']}\" ({h['why']})" for h in hits]
        if pitch:
            lines += [f"**Subject:** {pitch['subject']}", '', pitch['body'], '',
                      f"*Follow-up after 7 days:* {pitch['follow_up']}", '']
        else:
            lines += ['_No pitch was written for this prospect._', '']
    return '\n'.join(lines) + '\n'


def render_clips(items, date):
    ok = [i for i in items if i['status'] != 'failed']
    lines = [f'# Clips: week of {date}', '',
             f'{sum(i["status"] == READY for i in ok)} of {len(ok)} clips are ready to cut. '
             'Cut each one from the stream recording at the timestamps below.', '']
    for i in items:
        if i['status'] == 'failed':
            lines += [f"- ⚠ {i['source_file']}: {i['error']}", '']
            continue
        lines += [f"## {i['hook']}", '',
                  f"`{i['source_file']}` {i['start']} → {i['end']} · {i['pillar']} · **{i['status']}**", '',
                  f"Why: {i['why']}", '']
        for field, hits in (i['rule_hits'] or {}).items():
            lines += [f"- ⚠ {field}: \"{h['match']}\" ({h['why']})" for h in hits]
        lines += ['**English caption**', '', i['caption_en'], '', '**Spanish caption**', '', i['caption_es'], '']
    return '\n'.join(lines) + '\n'
