"""The YouTube production kit: packages, idea list, assets, the Risk Card, and the Lesson desk."""
import csv
import datetime as dt
import json
import shutil
import struct
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from marketing import compliance
from youtube import lesson_desk
from youtube.lesson_desk import BeatStep, LessonPackage, ShortScript

ROOT = Path(__file__).resolve().parents[1]
YT = ROOT / 'youtube'


# ---- packages and idea list ------------------------------------------------

def test_every_production_file_passes_the_phrase_rules():
    files = sorted((YT / 'production').rglob('*.md'))
    assert len(files) >= 7
    for f in files:
        assert compliance.check_text(f.read_text()) == [], f


def test_each_numbered_package_is_complete():
    for d in sorted((YT / 'production').glob('0[0-9][1-9]-*')):
        text = (d / 'package.md').read_text()
        for section in ('## 1. Brief', '## 2. Beat sheet', '## 3. Full script', '## 4. Publish sheet',
                        '## 5. Shorts', '## 6. Gate checklist'):
            assert section in text, (d.name, section)
        assert 'utm_campaign=' in text and compliance.RISK_LINE.split('.')[0] in text
        assert 'youtube/assets/out/thumb-' in text
        thumb = text.split('`youtube/assets/out/')[1].split('`')[0]
        assert (YT / 'assets' / 'out' / thumb).is_file(), thumb


def test_idea_list_is_ranked_and_packaged_ones_exist():
    with (YT / 'ideas.csv').open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 100 and [int(r['rank']) for r in rows] == list(range(1, 101))
    scores = [int(r['score']) for r in rows]
    assert scores == sorted(scores, reverse=True)
    packaged = [r for r in rows if r['status'] == 'packaged']
    assert len(packaged) == 4
    for r in packaged:
        assert (YT / 'production' / r['package'] / 'package.md').is_file()
    for r in rows:
        assert compliance.check_text(r['title']) == [], r['title']


# ---- assets ----------------------------------------------------------------

def png_size(path):
    with open(path, 'rb') as f:
        head = f.read(24)
    assert head[:8] == b'\x89PNG\r\n\x1a\n'
    return struct.unpack('>II', head[16:24])


def test_rendered_assets_have_youtube_sizes():
    jobs = json.loads((YT / 'assets' / 'renders.json').read_text())
    for job in jobs:
        assert png_size(YT / 'assets' / 'out' / job['out']) == (job['w'], job['h']), job['out']
    sizes = {j['out']: (j['w'], j['h']) for j in jobs}
    assert sizes['banner.png'] == (2560, 1440)
    assert all(v == (1280, 720) for k, v in sizes.items() if k.startswith('thumb-'))


def test_risk_card_logic(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('node not installed')
    html = (YT / 'assets' / 'risk-card.html').read_text()
    core = html.split('/*risk-card-core*/')[1].split('/*end-risk-card-core*/')[0]
    script = tmp_path / 'rc.js'
    script.write_text(core + '''
console.log(JSON.stringify([
  riskCardModel({m: 'es', stop: '24', qty: '1', risk: '300'}),
  riskCardModel({m: 'ES', stop: '24', qty: '2', state: 'result', res: '-24', risk: '300'}),
  riskCardModel({m: 'NQ', stop: '40', qty: '1', state: 'result', res: '60'}),
  riskCardModel({m: '<script>', stop: 'x'})
]));''')
    plan, loss, win, bad = json.loads(subprocess.run([node, str(script)], capture_output=True, text=True,
                                                     check=True).stdout)
    assert plan['title'] == 'RISK CARD · ES' and plan['stop'] == '24 ticks (6.00 pts)'
    assert plan['risk'] == '$300' and plan['showRisk'] and not plan['showResult']
    # Results: ticks only, never dollars.
    assert loss['res'] == '−24 ticks' and loss['resNote'] == 'stopped as planned' and not loss['showRisk']
    assert win['res'] == '+60 ticks' and win['resClass'] == 'pos'
    assert '$' not in loss['res'] + win['res']
    assert bad['title'] == 'RISK CARD · SCRIPT' and bad['stop'] == '—'


# ---- the Lesson desk ---------------------------------------------------------

def lesson_pkg(**over):
    p = dict(titles=['How Many MES Contracts for a $50K Evaluation?', 'Sizing a $50K Evaluation', 'The $250 Rule'],
             thumbnail_words='SIZE FIRST', thumbnail_concept='Jack focused; the planner on screen',
             hook='Your evaluation is $50,000. Your real account is $2,500.', roadmap='Three steps: ...',
             structure='Problem-Solve',
             steps=[BeatStep(name='Drawdown', point='Size from the drawdown.', number_to_say='$2,500 / 10 = $250',
                             chart_to_show='planner')],
             twist='A bigger account makes it worse.', recap=['a', 'b', 'c'],
             description_first_lines='How many MES contracts for a $50K evaluation? Here is the math.',
             chapters=['0:00 Hook', '1:00 Step 1'], pinned_comment='What is your drawdown?',
             shorts=[ShortScript(hook='$2,500, not $50,000.', script='...')],
             jack_facts_needed=['[Jack: his firm experience]'])
    p.update(over)
    return LessonPackage(**p)


class Fake:
    def __init__(self, pkg=None, refuse=False):
        self.calls, self.pkg, self.refuse = [], pkg or lesson_pkg(), refuse
        self.messages = SimpleNamespace(parse=self._parse)

    def _parse(self, **kw):
        self.calls.append(kw)
        assert kw['output_format'] is LessonPackage
        if self.refuse:
            return SimpleNamespace(stop_reason='refusal', parsed_output=None, content=[])
        return SimpleNamespace(stop_reason='end_turn', parsed_output=self.pkg, content=[])


def test_next_ideas_skip_packaged_and_live_formats():
    ideas = lesson_desk.next_ideas(YT / 'ideas.csv', 3)
    assert [int(i['rank']) for i in ideas] == [4, 5, 6]
    assert all(i['status'] == 'idea' and i['format'] in lesson_desk.LESSON_FORMATS for i in ideas)
    assert lesson_desk.next_ideas(YT / 'missing.csv', 3) == [] and lesson_desk.next_ideas(YT / 'ideas.csv', 0) == []


def test_lesson_desk_drafts_and_checks(tmp_path):
    c = Fake()
    items = lesson_desk.run_lessons(c, YT / 'ideas.csv', 2)
    assert [i['status'] for i in items] == [lesson_desk.READY] * 2
    assert c.calls[0]['output_config']['effort'] == 'high'
    assert '"rank": "4"' in c.calls[0]['messages'][0]['content']
    md = lesson_desk.render_package(items[0])
    assert 'utm_campaign=' in md and compliance.RISK_LINE in md and '[Jack: his firm experience]' in md


def test_lesson_with_banned_phrase_is_held():
    items = lesson_desk.run_lessons(Fake(lesson_pkg(hook='This setup is so profitable')), YT / 'ideas.csv', 1)
    assert items[0]['status'] == lesson_desk.NEEDS_CHANGES and 'hook' in items[0]['rule_hits']
    assert '⚠ hook' in lesson_desk.render_package(items[0])


def test_run_writes_drafts_and_uses_the_shared_brand_brief(tmp_path):
    c = Fake()
    out, items = lesson_desk.run(c, YT / 'ideas.csv', tmp_path, count=2, today=dt.date(2026, 11, 23))
    files = sorted(p.name for p in out.iterdir())
    assert out == tmp_path / '2026-11-23'
    assert files[0] == 'index.md' and len(files) == 3
    kw = c.calls[0]
    assert kw['model'] == 'claude-opus-5-5' and 'StartUpTrading brand brief' in kw['system'][0]['text']
    assert kw['system'][0]['cache_control'] == {'type': 'ephemeral'}


def test_cli_without_key_exits_2(monkeypatch, capsys):
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    assert lesson_desk.main([]) == 2
    assert 'ANTHROPIC_API_KEY' in capsys.readouterr().err


def test_failed_lesson_is_reported():
    items = lesson_desk.run_lessons(Fake(refuse=True), YT / 'ideas.csv', 1)
    assert items[0]['status'] == 'failed'
    assert '⚠ rank 4' in lesson_desk.render_index(items, 'd')
