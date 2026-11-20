"""The Lesson desk: turns the next ideas on youtube/ideas.csv into Lesson packages.

Each package has the same sections as the hand-built ones in youtube/production/
(brief, beat sheet, publish sheet, Shorts, gate checklist). A person reviews it,
then copies it to youtube/production/ and marks the idea "packaged" in the CSV.
Nothing is published.
"""
import csv
import re
from pathlib import Path

from . import agents, compliance

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
            pkg = agents.write_lesson(client, idea)
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
