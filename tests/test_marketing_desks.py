"""Offline tests for the outreach and clip desks. No API key or network needed."""
import datetime as dt
from types import SimpleNamespace

from marketing import agents, compliance, desks, pipeline
from marketing.models import (Clip, ClipList, ContentPack, Pitch, PitchList, Prospect, ProspectList,
                              ResearchReport, ReviewResult, WeeklyPlan, ContentBrief)


def prospect(name, kind='podcast'):
    return Prospect(name=name, kind=kind, url=f'https://{name.lower().replace(" ", "")}.test',
                    audience='Futures day traders', why_fit='Covers risk management',
                    contact_route='Guest form on their site')


def pitch(name, body='Jack can walk your listeners through ATR sizing.'):
    return Pitch(prospect_name=name, subject='Guest idea: sizing a news day', body=body,
                 follow_up='Just bumping this. Happy to send a clip.')


def clip(**over):
    c = dict(source_file='mon.txt', start='00:12:03', end='00:12:48', hook='Why my stop got wider today',
             caption_en='ATR expanded, so the stop widened and the size dropped.',
             caption_es='El ATR se expandió, así que el stop se amplió y el tamaño bajó.',
             pillar='process', why='A visible tool moment')
    c.update(over)
    return Clip(**c)


class Fake:
    def __init__(self, prospects=(), pitches=None, clips=None, refuse=()):
        self.calls = []
        self.prospects = list(prospects)
        self.pitches = pitches
        self.clips = clips or [clip()]
        self.refuse = set(refuse)
        self.messages = SimpleNamespace(parse=self._parse)

    def _parse(self, **kw):
        self.calls.append(kw)
        fmt = kw['output_format']
        if fmt in self.refuse:
            return SimpleNamespace(stop_reason='refusal', parsed_output=None, content=[])
        out = {
            ProspectList: lambda: ProspectList(prospects=self.prospects),
            PitchList: lambda: PitchList(pitches=self.pitches if self.pitches is not None
                                         else [pitch(p.name) for p in self.prospects]),
            ClipList: lambda: ClipList(clips=self.clips),
            ResearchReport: lambda: ResearchReport(competitor_moves=[], audience_questions=['q'],
                                                   trending_topics=[], content_ideas=[]),
            WeeklyPlan: lambda: WeeklyPlan(theme='T', rationale='R', briefs=[ContentBrief(
                id='b1', title='B1', pillar='live', angle='a', record_this='r', channels=['x'],
                call_to_action='free_indicator')]),
            ContentPack: lambda: ContentPack(brief_id='b1', youtube_title='t', youtube_description='d',
                                             shorts_script='s', x_posts=['x'], email_subject='e', email_body='b'),
            ReviewResult: lambda: ReviewResult(approved=True, issues=[], revised=ContentPack(
                brief_id='b1', youtube_title='t', youtube_description='d', shorts_script='s', x_posts=['x'],
                email_subject='e', email_body='b')),
        }[fmt]()
        return SimpleNamespace(stop_reason='end_turn', parsed_output=out, content=[])


# ---- outreach --------------------------------------------------------------

def test_outreach_skips_contacted_and_drafts_pitches(tmp_path):
    contacted = tmp_path / 'contacted.txt'
    contacted.write_text('# sent already\nOld Pod  # emailed 11/1\n\n')
    c = Fake(prospects=[prospect('Old Pod'), prospect('Futures Talk'), prospect('Apex Desk', 'prop_firm')])
    items = desks.run_outreach(c, 10, contacted)
    assert [i['prospect']['name'] for i in items] == ['Futures Talk', 'Apex Desk']
    assert all(i['status'] == desks.READY for i in items)
    finder = c.calls[0]
    assert finder['tools'][0]['type'] == 'web_search_20260209'
    assert 'Old Pod' in finder['messages'][0]['content']


def test_pitch_with_banned_phrase_or_missing_is_held():
    c = Fake(prospects=[prospect('A'), prospect('B')],
             pitches=[pitch('A', body='Our members find it so profitable.')])
    items = {i['prospect']['name']: i for i in desks.run_outreach(c)}
    assert items['A']['status'] == desks.NEEDS_CHANGES and 'body' in items['A']['rule_hits']
    assert items['B']['status'] == desks.NEEDS_CHANGES and items['B']['pitch'] is None


def test_no_new_prospects_skips_pitch_writer():
    c = Fake(prospects=[])
    assert desks.run_outreach(c) == []
    assert [k['output_format'] for k in c.calls] == [ProspectList]


def test_outreach_markdown_says_nothing_was_sent():
    md = desks.render_outreach(desks.run_outreach(Fake(prospects=[prospect('Futures Talk')])), '2026-11-23')
    assert 'Nothing has been sent' in md and 'contacted.txt' in md and 'Guest form' in md


# ---- clips -----------------------------------------------------------------

def test_clips_read_only_transcripts_and_add_risk_lines(tmp_path):
    (tmp_path / 'mon.txt').write_text('00:12:03 Jack: ATR expanded today...')
    (tmp_path / 'tue.vtt').write_text('WEBVTT')
    (tmp_path / 'README.txt').write_text('instructions')
    (tmp_path / 'notes.pdf').write_bytes(b'%PDF')
    c = Fake()
    items = desks.run_clips(c, tmp_path)
    files = [k['messages'][0]['content'].split('\n')[0] for k in c.calls]
    assert files == ['Transcript file: mon.txt', 'Transcript file: tue.vtt']
    assert len(items) == 2 and all(i['status'] == desks.READY for i in items)
    assert items[0]['caption_en'].endswith(compliance.SHORT_RISK_LINE)
    assert items[0]['caption_es'].endswith(compliance.SPANISH_RISK_LINE)


def test_spanish_profit_language_is_held(tmp_path):
    (tmp_path / 'mon.txt').write_text('...')
    c = Fake(clips=[clip(caption_es='Así consigo ganancias todos los días.')])
    item = desks.run_clips(c, tmp_path)[0]
    assert item['status'] == desks.NEEDS_CHANGES and 'caption_es' in item['rule_hits']


def test_one_bad_transcript_does_not_stop_the_rest(tmp_path):
    (tmp_path / 'a.txt').write_text('...')
    c = Fake(refuse={ClipList})
    items = desks.run_clips(c, tmp_path)
    assert items[0]['status'] == 'failed'
    assert '⚠ a.txt: the model declined this request' in desks.render_clips(items, 'd')


def test_missing_transcript_folder_is_fine(tmp_path):
    assert desks.run_clips(Fake(), tmp_path / 'nope') == []


# ---- compliance additions --------------------------------------------------

def test_brand_tagline_allowed_but_profit_claims_still_caught():
    assert compliance.check_text('I show you my risk, not my profits.') == []
    assert compliance.check_text('Show your risk, not your profits') == []
    assert compliance.check_text('My profits this week were great')
    assert compliance.check_text('not my profits, but yours will grow')  # no "risk," before it


# ---- weekly run with all desks ---------------------------------------------

def test_weekly_run_writes_desk_files(tmp_path):
    t = tmp_path / 'transcripts'
    t.mkdir()
    (t / 'mon.txt').write_text('...')
    c = Fake(prospects=[prospect('Futures Talk')])
    out, result = pipeline.run(c, tmp_path / 'out', today=dt.date(2026, 11, 23), max_briefs=1,
                               outreach=5, contacted_path=tmp_path / 'none.txt', transcripts_dir=t)
    assert (out / 'outreach.md').exists() and (out / 'clips.md').exists()
    assert len(result['outreach']) == 1 and len(result['clips']) == 1
    assert '1 outreach pitches in `outreach.md`' in (out / 'queue.md').read_text()


def test_failing_outreach_desk_keeps_content_queue(tmp_path):
    c = Fake(prospects=[prospect('X')], refuse={ProspectList})
    _, result = pipeline.run(c, tmp_path, today=dt.date(2026, 11, 23), max_briefs=1, outreach=5)
    assert result['items'][0]['status'] == pipeline.READY
    assert result['outreach'][0]['status'] == pipeline.FAILED
    assert 'outreach desk failed' in desks.render_outreach(result['outreach'], 'd')


def test_metrics_readme_is_not_treated_as_metrics(tmp_path):
    (tmp_path / 'README.txt').write_text('Drop exports here')
    assert pipeline.read_metrics(tmp_path) == ''
