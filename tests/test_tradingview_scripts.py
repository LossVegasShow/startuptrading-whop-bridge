"""Guards for the TradingView scripts in growth/tradingview/.

TradingView's publishing rules forbid links, websites, social handles, contact
details and company names in a script's title, code, chart output and
description; the profile Signature is the only place for a link. These tests
fail if any of that slips into a script or its description, and pin the core
sizing math and its defaults."""
import math
import re
from pathlib import Path

import pytest

TV = Path(__file__).resolve().parents[1] / 'growth' / 'tradingview'
SCRIPTS = sorted(TV.glob('*.pine'))
FORBIDDEN = re.compile(r'https?://|www\.|\.com\b|\.io\b|startup\s*trading|discord|youtube|whop|telegram|t\.me|'
                       r'instagram|twitter|\bx\.com|(?<!//)@[a-z0-9_]|\bqr\b|e-?mail me|dm me|link in bio', re.I)


def code_without_license(text):
    # The standard MPL header line is TradingView's own convention for open-source scripts.
    return '\n'.join(l for l in text.splitlines() if 'mozilla.org/MPL/2.0' not in l)


@pytest.mark.parametrize('path', SCRIPTS, ids=lambda p: p.name)
def test_scripts_are_plain_ascii_with_short_lines(path):
    # Non-ASCII characters and very long lines get mangled when copied out of
    # previews into TradingView's editor (a truncated line broke the first paste).
    text = path.read_text()
    bad = [(n, l) for n, l in enumerate(text.splitlines(), 1) if not l.isascii() or len(l) > 95]
    assert bad == []


@pytest.mark.parametrize('path', SCRIPTS, ids=lambda p: p.name)
def test_scripts_contain_no_promotion(path):
    hits = FORBIDDEN.findall(code_without_license(path.read_text()))
    assert hits == [], hits


@pytest.mark.parametrize('path', SCRIPTS, ids=lambda p: p.name)
def test_scripts_use_the_shared_design_system(path):
    src = path.read_text()
    assert src.startswith('// This Pine Script code is subject to the terms of the Mozilla Public License 2.0')
    assert '//@version=6' in src
    for token in ('C_HEADER     = color.new(#fa7b39, 0)', 'C_PANEL      = color.new(#0b0e13, 4)',
                  'MOTTO        = "Risk first | stop second | size last"', 'text_font_family = font.family_monospace'):
        assert token in src, (path.name, token)


def test_description_is_clean_and_signature_is_tracked():
    text = (TV / 'atr-position-size-planner.description.txt').read_text()
    public, signature = text.split('\nSIGNATURE', 1)
    body = public.split('DESCRIPTION', 1)[1]
    body = body.split('\n', 1)[1]          # drop the internal instruction line
    assert FORBIDDEN.findall(body) == []
    assert 'utm_source=tradingview' in signature and 'utm_medium=signature' in signature


def test_core_math_and_defaults_are_unchanged():
    src = (TV / 'atr-position-size-planner.pine').read_text()
    assert 'stopPts     = math.ceil(atr * stopMult / tick) * tick' in src
    assert 'contracts   = perContract > 0 ? math.floor(riskBudget / perContract) : 0' in src
    assert 'perContract = stopPts * pointValue + commRt' in src
    for default in ('riskMode  = input.string("Fixed $"', 'riskUsd   = input.float(250.0', 'atrLen    = input.int(14',
                    'stopMult  = input.float(1.5', 'commRt    = input.float(0.0', 'closedBar = input.bool(false',
                    'pvInput   = input.float(0.0'):
        assert default in src, default


def size(risk, atr, mult, tick, pv, costs=0.0):
    """Python reference of the script's rule, used to check the published examples."""
    stop = math.ceil(atr * mult / tick) * tick
    per = stop * pv + costs
    n = math.floor(risk / per) if per > 0 else 0
    return stop, per, n, n * per


def test_reference_examples_match_the_companion_page():
    assert size(500, 4.0, 1.5, 0.25, 50) == (6.0, 300.0, 1, 300.0)          # ES
    assert size(500, 20.0, 1.5, 0.25, 20)[2] == 0                           # NQ: skip or go micro
    assert size(500, 20.0, 1.5, 0.25, 2) == (30.0, 60.0, 8, 480.0)          # MNQ
    assert size(250, 4.1, 1.5, 0.25, 50)[0] == 6.25                         # stop rounds UP to a tick
    stop, per, n, actual = size(500, 4.0, 1.5, 0.25, 50, costs=5.0)         # costs shrink the size, never raise risk
    assert per == 305.0 and actual <= 500
