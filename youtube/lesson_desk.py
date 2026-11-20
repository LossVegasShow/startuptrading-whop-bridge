"""The Lesson desk: drafts Lesson packages from youtube/ideas.csv.

Standalone: it reuses the marketing team's brand brief, model settings and
phrase rules by importing them, and changes nothing in marketing/.

    python -m youtube.lesson_desk --count 2            # needs ANTHROPIC_API_KEY

Each draft has the same sections as the hand-built packages in
youtube/production/. A person reviews it, copies it to youtube/production/
and marks the idea "packaged" in the CSV. Nothing is published.
"""
import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Literal

from pydantic import BaseModel, Field

from marketing import agents, compliance

ROOT = Path(__file__).resolve().parent


class BeatStep(BaseModel):
    name: str
    point: str = Field(description='The key point, one sentence.')
    number_to_say: str = Field(description='The concrete number or example said on camera, or "none".')
    chart_to_show: str = Field(description='What is on screen during this step.')


class ShortScript(BaseModel):
    hook: str = Field(description='The first line, said in the first second. Under 40 characters.')
    script: str = Field(description='30 to 60 seconds of speech.')


class LessonPackage(BaseModel):
    titles: List[str] = Field(description='Exactly 3 genuinely different title options, under 70 characters each.')
    thumbnail_words: str = Field(description='2 or 3 words for the thumbnail that add to the title, not repeat it.')
    thumbnail_concept: str = Field(description="Jack's expression plus one chart element.")
    hook: str = Field(description='The first line, word for word, showing the problem and the promise.')
    roadmap: str = Field(description='One sentence naming the three steps.')
    structure: Literal['Problem-Solve', 'Story', 'Breakdown', 'Showdown']
    steps: List[BeatStep]
    twist: str = Field(description='Where the obvious answer is wrong.')
    recap: List[str] = Field(description='Three short recap lines.')
    description_first_lines: str = Field(description='Two sentences with the search phrase, for the top of the description.')
    chapters: List[str] = Field(description='5 to 7 chapters as "m:ss Name", starting at 0:00.')
    pinned_comment: str
    shorts: List[ShortScript] = Field(description='Two Shorts cut from this Lesson.')
    jack_facts_needed: List[str] = Field(
        description='Every fact only Jack can supply (a real chart, a date, his own rule or story), as brackets to fill.')


LESSON_WRITER = """Role: YouTube Producer for the channel "Jack Gleason | StartUpTrading".
Turn one idea from the ranked idea list into a complete Lesson package for an 8 to 12 minute video, in Jack's
voice. Rules from the channel's production system:
- Package first: three genuinely different titles (search phrase first where it fits, one number or market,
  no hype words); thumbnail words that add to the title.
- The hook shows the problem and the promise in the first 15 seconds. No intro, no asking for subscribes.
- Use one structure: Problem-Solve, Story, Breakdown or Showdown, with a twist beat where the obvious answer
  is wrong.
- Use real, checkable numbers for any sizing example (ES $50/pt, MES $5/pt, NQ $20/pt, MNQ $2/pt, E-nano S&P
  $0.50/pt; contracts = risk / (stop points x $ per point), always rounded down).
- Never invent Jack's trades, dates, results or personal rules: put them in jack_facts_needed as brackets.
- Results are only ever in ticks. Never profit, income, win-rate or guarantee language.
- One call to action: the free calculator, then the next video."""


def write_lesson(client, idea):
    prompt = 'Idea from the ranked list:\n' + json.dumps(idea, indent=1)
    return agents._ask(client, LESSON_WRITER, prompt, LessonPackage, effort='high')


READY = 'ready_for_review'
NEEDS_CHANGES = 'needs_changes'
# Formats the desk packages; streams and weekly series are produced live instead.
LESSON_FORMATS = {'Lesson', 'Story', 'Tutorial', 'News day', 'Opinion', 'Comparison', 'Manifesto'}


def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')[:60]


def next_ideas(ideas_path, count):
    p = Path(ideas_path) if ideas_path else None
    if not p or not p.is_file() or count <= 0:
        return []
    with p.open(newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    rows = [r for r in rows if r.get('status', 'idea') == 'idea' and r.get('format') in LESSON_FORMATS]
    rows.sort(key=lambda r: int(r['rank']))
    return rows[:count]


def _fields(pkg):
    fields = {'hook': pkg.hook, 'roadmap': pkg.roadmap, 'twist': pkg.twist,
              'description': pkg.description_first_lines, 'pinned_comment': pkg.pinned_comment,
              'thumbnail_words': pkg.thumbnail_words}
    for i, t in enumerate(pkg.titles, 1):
        fields[f'title_{i}'] = t
    for i, s in enumerate(pkg.steps, 1):
        fields[f'step_{i}'] = f'{s.point} {s.number_to_say}'
    for i, s in enumerate(pkg.shorts, 1):
        fields[f'short_{i}'] = f'{s.hook} {s.script}'
    return fields


def run_lessons(client, ideas_path, count=2):
    items = []
    for idea in next_ideas(ideas_path, count):
        try:
            pkg = write_lesson(client, idea)
        except agents.AgentError as e:
            items.append({'idea': idea, 'status': 'failed', 'error': str(e)})
            continue
        hits = compliance.check_pack(_fields(pkg))
        items.append({'idea': idea, 'package': pkg.model_dump(), 'rule_hits': hits,
                      'status': READY if not hits else NEEDS_CHANGES})
    return items


def render_package(item):
    idea, p = item['idea'], item['package']
    utm = f"utm_source=youtube&utm_medium=description&utm_campaign={slugify(idea['title'])}"
    steps = '\n'.join(f"STEP {i} · {s['name']}: {s['point']} | say: {s['number_to_say']} | show: {s['chart_to_show']}"
                      for i, s in enumerate(p['steps'], 1))
    hits = ''.join(f"\n- ⚠ {f}: \"{h['match']}\" ({h['why']})" for f, hs in (item['rule_hits'] or {}).items() for h in hs)
    shorts = '\n'.join(f"{i}. **\"{s['hook']}\"** {s['script']}\n   Caption ends: *{compliance.SHORT_RISK_LINE}*"
                       for i, s in enumerate(p['shorts'], 1))
    return f"""# Draft · rank {idea['rank']} · {p['titles'][0]}

Status: **{item['status']}** (drafted by the Lesson desk; review before moving to youtube/production/){hits}

## 1. Brief

- **Target search:** {idea['search_target']}  ·  autocomplete confirmed: [ ]
- **Category:** {idea['category']} · **Structure:** {p['structure']}
- **The twist:** {p['twist']}
- **Thumbnail:** words "{p['thumbnail_words']}" · {p['thumbnail_concept']}
- **Facts only Jack can supply:**
{chr(10).join('    - [ ] ' + f for f in p['jack_facts_needed']) or '    - none'}

## 2. Beat sheet

```text
HOOK (word for word): "{p['hook']}"
ROADMAP: "{p['roadmap']}"
{steps}
TWIST: {p['twist']}
SUBSCRIBE MOMENT: right after the first payoff, tied to it.
RECAP: {' / '.join(p['recap'])}
```

## 3. Publish sheet

**Titles to test:**

1. {p['titles'][0]}
{chr(10).join(f'{i}. {t}' for i, t in enumerate(p['titles'][1:], 2))}

**Description:**

```text
{p['description_first_lines']}

Free position-size calculator: https://startuptrading.com/futures-position-size-calculator?{utm}
Free ATR indicator for NinjaTrader: https://startuptrading.com/indicators?{utm}

Live ES & NQ every weekday, 9:00 ET.

Chapters
{chr(10).join(p['chapters'])}

Instagram: @trader

{compliance.RISK_LINE}
```

**Pinned comment:** {p['pinned_comment']}

## 4. Shorts

{shorts}
"""


def render_index(items, date):
    lines = [f'# Lesson desk: week of {date}', '']
    for i in items:
        if i['status'] == 'failed':
            lines.append(f"- ⚠ rank {i['idea']['rank']} {i['idea']['title']}: {i['error']}")
        else:
            lines.append(f"- rank {i['idea']['rank']} · **{i['status']}** · {i['package']['titles'][0]}")
    return '\n'.join(lines) + '\n'


def run(client, ideas_path, out_root, count=2, today=None):
    """Draft `count` packages and write them to out_root/<date>/. Returns (folder, items)."""
    today = today or dt.date.today()
    out = Path(out_root) / today.isoformat()
    out.mkdir(parents=True, exist_ok=True)
    items = run_lessons(client, ideas_path, count)
    (out / 'index.md').write_text(render_index(items, today.isoformat()), encoding='utf-8')
    for item in items:
        if item.get('package'):
            name = f"rank-{int(item['idea']['rank']):03d}-{slugify(item['idea']['title'])}.md"
            (out / name).write_text(render_package(item), encoding='utf-8')
    return out, items


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m youtube.lesson_desk', description='Draft Lesson packages.')
    ap.add_argument('--count', type=int, default=2, help='How many packages to draft.')
    ap.add_argument('--ideas', default=str(ROOT / 'ideas.csv'), help='The ranked idea list.')
    ap.add_argument('--out', default=str(ROOT / 'drafts'), help='Where to write the drafts.')
    args = ap.parse_args(argv)
    if not os.environ.get('ANTHROPIC_API_KEY'):
        print('ANTHROPIC_API_KEY is not set. See marketing/README.md for adding the secret.', file=sys.stderr)
        return 2
    import anthropic  # only needed for real runs
    client = anthropic.Anthropic(max_retries=4)
    try:
        out, items = run(client, args.ideas, args.out, args.count)
    except anthropic.APIError as e:
        print(f'Anthropic API error: {e}', file=sys.stderr)
        return 1
    ready = sum(i['status'] == READY for i in items)
    print(f'Wrote {out}/index.md: {ready} of {len(items)} packages ready for review.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
