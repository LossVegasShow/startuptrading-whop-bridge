"""The AI video engine: episode checks, chart math, captions. No rendering, no network."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'video'))
import build  # noqa: E402

EPISODES = sorted((ROOT / 'video' / 'episodes').glob('*.json'))
SCENE_TYPES = {'hook', 'steps', 'formula', 'contracts', 'chart', 'riskcard', 'statement', 'recap', 'endcard', 'chapter'}


@pytest.mark.parametrize('path', EPISODES, ids=lambda p: p.stem)
def test_episode_passes_phrase_rules_and_is_well_formed(path):
    ep = json.loads(path.read_text())
    assert build.check_episode(ep) == {}
    assert ep['id'] == path.stem and ep['voice_id'] and ep['disclaimer']
    for s in ep['scenes']:
        assert s['type'] in SCENE_TYPES, s['type']
        assert s.get('say') or s.get('min'), 'every scene needs narration or a minimum length'
    # The last 20 seconds hold the end card for YouTube's end-screen elements.
    assert ep['scenes'][-1]['type'] == 'endcard' and ep['scenes'][-1].get('min', 0) >= 20


@pytest.mark.parametrize('path', EPISODES, ids=lambda p: p.stem)
def test_on_screen_math_is_right(path):
    """Formula and contract scenes must agree with the narration's rounding-down rule."""
    ep = json.loads(path.read_text())
    for s in ep['scenes']:
        if s['type'] == 'formula':
            per = s['stop'] * s['ppt']
            n = int(s['risk'] // per)
            assert n * per <= s['risk']
            if 'say' in s and n == 0:
                assert 'zero' in s['say'].lower()
        if s['type'] == 'contracts':
            for c in s['cards']:
                assert int(s['risk'] // (s['stop'] * c['ppt'])) * s['stop'] * c['ppt'] <= s['risk']


def test_banned_phrase_in_narration_is_caught():
    ep = {'scenes': [{'type': 'statement', 'text': 'ok', 'say': 'This setup is very profitable.'}]}
    assert 0 in build.check_episode(ep)


def test_atr_is_wilder_and_synthetic_bars_are_deterministic_and_on_tick():
    bars = [[10, 12, 9, 11], [11, 13, 10, 12], [12, 12.5, 8, 9]]
    a = build.atr(bars, n=2)
    # True ranges 3, 3, 4.5 (high-low beats the gaps); Wilder: (3 * (2 - 1) + 4.5) / 2 = 3.75
    assert a == [3, 3.0, 3.75]
    b1 = build.synthetic_bars(2, 70, 5125, 2.4)
    assert b1 == build.synthetic_bars(2, 70, 5125, 2.4)
    assert all(abs(v * 4 - round(v * 4)) < 1e-9 for bar in b1 for v in bar)
    assert all(bar[1] >= max(bar[0], bar[3]) and bar[2] <= min(bar[0], bar[3]) for bar in b1)


def test_episode_001_chart_matches_the_narration():
    ep = json.loads((ROOT / 'video' / 'episodes' / '001-how-many-contracts.json').read_text())
    chart = build.prepare_chart(dict(ep['scenes'][7]), ROOT / 'video' / 'episodes')
    assert 3.9 < chart['atr'][-1] < 4.1          # "reading about four points"
    assert abs((chart['entryAt'] - chart['stopAt']) - 6) < 0.1  # "a six-point stop"
    assert chart['source'] == 'Illustration, not live market data'


def test_captions_are_ordered_and_cover_the_narration():
    srt = build.captions([(0.15, 4.0, 'First sentence here. Second one.'), (5.0, 2.0, 'Third.'), (7.5, 0, '')])
    blocks = [b for b in srt.strip().split('\n\n')]
    assert len(blocks) == 3
    assert blocks[0].startswith('1\n00:00:00,150 --> ') and blocks[2].endswith('Third.')
    assert build.srt_time(3723.5) == '01:02:03,500'


def test_long_caption_lines_are_split():
    parts = build.split_chunk('word ' * 40)
    assert len(parts) > 1 and all(len(p) <= 84 for p in parts)
