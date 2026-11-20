"""Offline tests for the marketing team. No API key or network needed."""
import datetime as dt
import json
from types import SimpleNamespace

import pytest

from marketing import agents, compliance, pipeline
from marketing.models import (ContentBrief, ContentPack, Finding, KPIReport, ResearchReport, ReviewResult,
                              WeeklyPlan)

RISK = compliance.RISK_LINE


def _pack(brief_id='atr-stop', **over):
    p = dict(brief_id=brief_id, youtube_title='ES open: placing an ATR stop on a trend day',
             youtube_description='How I size the trade from ATR before the open.',
             shorts_script='Watch the stop move with volatility.',
             x_posts=['ES trend read before the open: up, strength 3 of 5.'],
             email_subject='How I set every stop', email_body='Here is the ATR math I use.')
    p.update(over)
    return ContentPack(**p)


def _brief(i, cta='free_indicator'):
    return ContentBrief(id=f'b{i}', title=f'Brief {i}', pillar='process', angle='ATR sizing',
                        record_this='Narrate the stop on the ES open', channels=['youtube', 'x'],
                        call_to_action=cta)


class FakeClient:
    """Stands in for anthropic.Anthropic(): returns canned objects by output type."""

    def __init__(self, review=None, pause_first=False, refuse=None):
        self.calls = []
        self.review = review
        self.pause_first = pause_first
        self.refuse = refuse or set()
        self.messages = SimpleNamespace(parse=self._parse)

    def _parse(self, **kw):
        self.calls.append(kw)
        fmt = kw['output_format']
        if fmt is ResearchReport and self.pause_first and len(kw['messages']) == 1:
            return SimpleNamespace(stop_reason='pause_turn', parsed_output=None, content=['partial'])
        if fmt in self.refuse:
            return SimpleNamespace(stop_reason='refusal', parsed_output=None, content=[])
        out = {
            ResearchReport: lambda: ResearchReport(
                competitor_moves=[Finding(summary='A vendor cut its ATR tool price.', source_url='https://x.test/a')],
                audience_questions=['How do I size MES with ATR?'], trending_topics=['CPI'],
                content_ideas=['ATR on CPI day']),
            KPIReport: lambda: KPIReport(summary='Leads up 10%.', wins=['Shorts'], concerns=['Churn'],
                                         recommendations=['More Shorts']),
            WeeklyPlan: lambda: WeeklyPlan(theme='Volatility week', rationale='CPI is Wednesday.',
                                           briefs=[_brief(i) for i in range(1, 8)]),
            ContentPack: lambda: _pack(json.loads(kw['messages'][0]['content'].split('\n', 1)[1])['id']),
            ReviewResult: lambda: self.review(kw) if self.review else ReviewResult(
                approved=True, issues=[], revised=_pack(
                    json.loads(kw['messages'][0]['content'].split('\n', 1)[1].split('\n\nThe automatic')[0])
                    ['brief_id'])),
        }[fmt]()
        return SimpleNamespace(stop_reason='end_turn', parsed_output=out, content=[])


# ---- compliance rules ------------------------------------------------------

@pytest.mark.parametrize('text,rule', [
    ('This setup is so profitable', 'profit_claim'),
    ('I made $2,400 this morning', 'money_made'),
    ('This made me $500 today', 'money_made'),
    ('Replace your salary with trading', 'income_claim'),
    ('85% win rate on this setup', 'win_rate'),
    ('A risk-free way to trade', 'guarantee'),
    ('Jack is one of the best traders alive', 'superlative'),
    ('A tool offered nowhere else', 'superlative'),
    ('Backtested over 10 years', 'hypothetical'),
    ('Only 3 spots left!', 'urgency'),
    ('Buy now at 5120', 'trade_call'),
    ('Look at that P&L', 'pnl'),
])
def test_banned_phrases_are_caught(text, rule):
    assert rule in {h['rule'] for h in compliance.check_text(text)}


@pytest.mark.parametrize('text', [
    'The indicator places your stop and profit target from ATR.',
    'Membership is $99/month, cancel anytime.',
    'Here is my read on the ES open. ' + RISK,
    'Size every trade so the risk stays the same.',
])
def test_normal_trading_copy_passes(text):
    assert compliance.check_text(text) == []


def test_risk_line_added_once():
    once = compliance.with_risk_line('Hello')
    assert once.endswith(RISK)
    assert compliance.with_risk_line(once) == once
    assert compliance.with_risk_line('Hi', short=True).endswith(compliance.SHORT_RISK_LINE)
    assert compliance.check_text(RISK + compliance.SHORT_RISK_LINE) == []


def test_brand_brief_itself_is_clean_except_the_rules_section():
    brief = agents.brand_brief()
    facts = brief.split('## Hard rules')[0]
    assert compliance.check_text(facts) == []


# ---- agents ----------------------------------------------------------------

def test_every_call_uses_model_effort_and_cached_brief():
    c = FakeClient()
    pipeline.run(c, '/tmp/unused-out-dir-sut', today=dt.date(2026, 11, 23), max_briefs=1)
    assert c.calls
    for kw in c.calls:
        assert kw['model'] == 'claude-opus-5-5'
        assert kw['output_config']['effort'] in ('medium', 'high')
        assert kw['system'][0]['cache_control'] == {'type': 'ephemeral'}
        assert 'StartUpTrading brand brief' in kw['system'][0]['text']
        assert 'thinking' not in kw and 'budget_tokens' not in json.dumps(kw, default=str)
    research_call = c.calls[0]
    assert research_call['tools'][0]['type'] == 'web_search_20260209'


def test_research_resumes_after_pause_turn():
    c = FakeClient(pause_first=True)
    report = agents.research(c)
    assert report.audience_questions
    assert len(c.calls) == 2
    second = c.calls[1]['messages']
    assert [m['role'] for m in second] == ['user', 'assistant']
    assert second[1]['content'] == ['partial']


def test_refusal_raises_agent_error():
    with pytest.raises(agents.AgentError):
        agents.research(FakeClient(refuse={ResearchReport}))


# ---- pipeline --------------------------------------------------------------

def test_run_writes_queue_and_adds_risk_lines(tmp_path):
    out, result = pipeline.run(FakeClient(), tmp_path, today=dt.date(2026, 11, 23), max_briefs=5)
    assert out == tmp_path / '2026-11-23'
    assert len(result['items']) == 5  # capped even though the plan had 7
    for item in result['items']:
        assert item['status'] == pipeline.READY
        p = item['pack']
        assert compliance.has_risk_line(p['youtube_description'])
        assert compliance.has_risk_line(p['email_body'])
        assert all(compliance.has_risk_line(x) for x in p['x_posts'])
    md = (out / 'queue.md').read_text()
    assert 'Nothing has been posted' in md
    assert '5 of 5 pieces are ready' in md
    assert '- [ ] **Brief 1**: Narrate the stop on the ES open' in md
    assert json.loads((out / 'queue.json').read_text())['theme'] == 'Volatility week'


def test_phrase_hits_are_sent_to_reviewer_and_block_if_not_fixed(tmp_path):
    seen = {}

    def bad_review(kw):
        seen['prompt'] = kw['messages'][0]['content']
        # Reviewer "approves" but leaves a banned phrase in: the code must still hold it back.
        return ReviewResult(approved=True, issues=['tightened'],
                            revised=_pack(email_body='This made me $500 today.'))

    c = FakeClient(review=bad_review)
    c_write = c._parse

    def parse(**kw):
        r = c_write(**kw)
        if kw['output_format'] is ContentPack:
            r.parsed_output = _pack(youtube_title='The most profitable setup')
        return r
    c.messages = SimpleNamespace(parse=parse)

    item = pipeline.produce(c, _brief(1))
    assert 'profit_claim' in seen['prompt']
    assert item['status'] == pipeline.NEEDS_CHANGES
    assert 'email_body' in item['rule_hits']


def test_reviewer_rejection_is_needs_changes():
    c = FakeClient(review=lambda kw: ReviewResult(approved=False, issues=['claims results'], revised=_pack()))
    assert pipeline.produce(c, _brief(1))['status'] == pipeline.NEEDS_CHANGES


def test_writer_failure_marks_item_failed_and_run_continues(tmp_path):
    c = FakeClient(refuse={ContentPack})
    _, result = pipeline.run(c, tmp_path, today=dt.date(2026, 11, 23), max_briefs=2)
    assert [i['status'] for i in result['items']] == [pipeline.FAILED, pipeline.FAILED]
    assert 'Agent error' in result['items'][0]['issues'][0]


def test_metrics_folder_feeds_analyst(tmp_path):
    m = tmp_path / 'metrics'
    m.mkdir()
    (m / 'week.csv').write_text('metric,value\nleads,120\n')
    (m / 'ignore.bin').write_bytes(b'\x00')
    c = FakeClient()
    _, result = pipeline.run(c, tmp_path / 'out', metrics_dir=m, today=dt.date(2026, 11, 23), max_briefs=1)
    assert result['kpis']['summary'] == 'Leads up 10%.'
    analyst = [k for k in c.calls if k['output_format'] is KPIReport][0]
    assert 'leads,120' in analyst['messages'][0]['content'] and 'ignore.bin' not in analyst['messages'][0]['content']


def test_no_metrics_skips_analyst(tmp_path):
    c = FakeClient()
    _, result = pipeline.run(c, tmp_path, metrics_dir=tmp_path / 'missing', max_briefs=1)
    assert result['kpis'] is None
    assert not [k for k in c.calls if k['output_format'] is KPIReport]


def test_cli_without_key_exits_2(monkeypatch, capsys):
    from marketing.__main__ import main
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    assert main([]) == 2
    assert 'ANTHROPIC_API_KEY' in capsys.readouterr().err
