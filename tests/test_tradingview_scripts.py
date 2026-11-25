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


PLANNER = TV / 'atr-position-size-planner.pine'
EPS = 1e-9

# Verified CME contract specifications: value per point, tick size, paired contract.
SPECS = {
    'ES': (50.0, 0.25, 'MES'), 'MES': (5.0, 0.25, 'ES'),
    'NQ': (20.0, 0.25, 'MNQ'), 'MNQ': (2.0, 0.25, 'NQ'),
    'YM': (5.0, 1.0, 'MYM'), 'MYM': (0.5, 1.0, 'YM'),
    'RTY': (50.0, 0.1, 'M2K'), 'M2K': (5.0, 0.1, 'RTY'),
    'CL': (1000.0, 0.01, 'MCL'), 'MCL': (100.0, 0.01, 'CL'),
    'GC': (100.0, 0.1, 'MGC'), 'MGC': (10.0, 0.1, 'GC'),
    'SI': (5000.0, 0.005, 'SIL'), 'SIL': (1000.0, 0.005, 'SI'),
    '6E': (125000.0, 0.00005, 'M6E'), 'M6E': (12500.0, 0.0001, '6E'),
    'BTC': (5.0, 5.0, 'MBT'), 'MBT': (0.1, 5.0, 'BTC'),
}
MICROS = {'MES', 'MNQ', 'MYM', 'M2K', 'MCL', 'MGC', 'SIL', 'M6E', 'MBT'}


# ---- Python reference of the Pine formulas (kept line-for-line equivalent) ----

def ticks_for(raw, tk):
    return math.ceil(raw / tk - EPS) if tk and tk > 0 and raw > 0 else 0


def size_for(budget, per):
    return math.floor(budget / per + EPS) if per and per > 0 and budget > 0 else 0


def budget_for(mode='Fixed $', risk=250.0, acct=50000.0, pct=0.5, dd_left=2500.0, streak=10,
               buffer_pct=10.0, daily_left=0.0):
    buffer = 1 - buffer_pct / 100
    base = {'% of account': acct * pct / 100, 'Prop firm': dd_left * buffer / streak}.get(mode, risk)
    if daily_left > 0:
        cap = daily_left * (buffer if mode == 'Prop firm' else 1) / 2
        return min(base, cap)
    return base


def plan(budget, atr, mult, root, cost_std=0.0, cost_micro=0.0, pv=None, tick=None):
    """Main size for the chart symbol (pv/tick from the symbol, as in Pine)."""
    pv = pv if pv is not None else SPECS[root][0]
    tick = tick if tick is not None else SPECS[root][1]
    cost = cost_micro if root in MICROS else cost_std
    ticks = ticks_for(atr * mult, tick)
    per = ticks * tick * pv + cost
    n = size_for(budget, per)
    return {'ticks': ticks, 'stop': ticks * tick, 'per': per, 'n': n, 'risk': n * per,
            'left': budget - n * per, 'used': n * per / budget * 100 if budget > 0 else None}


def pair(budget, atr, mult, root, cost_std=0.0, cost_micro=0.0):
    """Standard-versus-micro rows, each with its own tick size and value per point."""
    if root not in SPECS:
        return None
    partner = SPECS[root][2]
    std, micro = (partner, root) if root in MICROS else (root, partner)
    out = {}
    for r in (std, micro):
        pv, tk, _ = SPECS[r]
        c = cost_micro if r in MICROS else cost_std
        t = ticks_for(atr * mult, tk)
        per = t * tk * pv + c
        n = size_for(budget, per)
        out[r] = (n, n * per, budget - n * per, t)
    return out


# ---- The script itself ----

def test_contract_table_in_the_script_matches_the_verified_specs():
    src = PLANNER.read_text()
    grab = lambda name: re.search(rf'var \w+\[\] {name} = array\.from\((.*?)\)\n', src, re.S).group(1)
    roots = re.findall(r'"([^"]+)"', grab('ROOTS'))
    pvs = [float(x) for x in re.findall(r'[\d.]+', grab('PVS'))]
    ticks = [float(x) for x in re.findall(r'[\d.]+', grab('TICKS'))]
    pairs = re.findall(r'"([^"]+)"', grab('PAIRS'))
    micros = set(re.findall(r'"([^"]+)"', grab('MICROS')))
    assert len(roots) == len(pvs) == len(ticks) == len(pairs) == len(SPECS)
    assert {r: (pv, tk, p) for r, pv, tk, p in zip(roots, pvs, ticks, pairs)} == SPECS
    assert micros == MICROS


def test_core_rules_and_defaults_are_unchanged():
    src = PLANNER.read_text()
    for token in ('tk > 0 and raw > 0 ? math.ceil(raw / tk - EPS) : 0',
                  'per > 0 and budget > 0 ? math.floor(budget / per + EPS) : 0',
                  'EPS          = 1e-9',
                  'riskMode  = input.string("Fixed $"', 'riskUsd   = input.float(250.0',
                  'atrLen    = input.int(14', 'stopMult  = input.float(1.5',
                  'closedBar = input.bool(false', 'pvInput   = input.float(0.0',
                  'costStd   = input.float(0.0', 'costMicro = input.float(0.0',
                  'dailyLeft = input.float(0.0'):
        assert token in src, token


def test_closed_bar_htf_atr_has_no_lookahead():
    src = PLANNER.read_text()
    # Closed bar: value shifted one bar AND lookahead on (the documented non-repainting form).
    # Live: no shift and lookahead off. Never lookahead_on with an unshifted value.
    assert 'atrPair(closedBar ? 1 : 0)' in src
    assert 'lookahead = closedBar ? barmerge.lookahead_on : barmerge.lookahead_off' in src
    assert src.count('request.security(') == 1
    assert 'tfTooLow = timeframe.in_seconds(tfUse) < timeframe.in_seconds(timeframe.period)' in src


def test_dashboard_wording():
    src = PLANNER.read_text()
    assert 'Actual risk' not in src and '"Estimated stop risk"' in src
    assert 'hypothetical' in src and '"MAX POSITION"' in src
    assert src.count('"PLAN ') >= 5                       # every chart level says PLAN
    assert "Planning aid. Check your firm's own rules." in src
    assert 'planning levels only: no orders are placed' in src


# ---- Validated calculations ----

def test_validated_es_mes_nq_mnq():
    es = plan(500, 4.0, 1.5, 'ES')
    assert (es['ticks'], es['stop'], es['per'], es['n'], es['risk'], es['left']) == (24, 6.0, 300.0, 1, 300.0, 200.0)
    assert es['used'] == 60.0
    assert plan(500, 4.0, 1.5, 'MES')['n'] == 16 and plan(500, 4.0, 1.5, 'MES')['risk'] == 480.0
    nq = plan(500, 20.0, 1.5, 'NQ')
    assert (nq['stop'], nq['per'], nq['n'], nq['risk'], nq['left']) == (30.0, 600.0, 0, 0.0, 500.0)
    mnq = plan(500, 20.0, 1.5, 'MNQ')
    assert (mnq['per'], mnq['n'], mnq['risk'], mnq['left']) == (60.0, 8, 480.0, 20.0)


def test_pair_comparison_uses_each_contracts_own_specs():
    p = pair(500, 4.0, 1.5, 'ES')
    assert p == {'ES': (1, 300.0, 200.0, 24), 'MES': (16, 480.0, 20.0, 24)}
    assert pair(500, 4.0, 1.5, 'MES') == p                   # same result from the micro chart
    p = pair(500, 20.0, 1.5, 'NQ')
    assert p['NQ'][0] == 0 and p['MNQ'][:3] == (8, 480.0, 20.0)
    # Euro FX: different tick sizes, so the same raw stop rounds differently.
    p = pair(500, 0.00082, 1.5, '6E')                           # raw stop 0.00123
    assert p['6E'][3] == 25 and p['M6E'][3] == 13
    assert math.isclose(25 * 0.00005 * 125000, 156.25) and math.isclose(13 * 0.0001 * 12500, 16.25)
    assert p['6E'][0] == 3 and p['M6E'][0] == 30
    # YM: whole-point ticks.
    assert pair(500, 25.0, 1.5, 'YM')['YM'][3] == 38             # 37.5 rounds up to 38 points


def test_unsupported_symbol_has_no_pair():
    assert pair(500, 4.0, 1.5, 'ZB') is None
    zb = plan(500, 0.2, 1.5, 'ZB', pv=1000.0, tick=1 / 32)       # main size still works
    assert zb['ticks'] == 10 and zb['n'] == 1


# ---- Tick boundaries and floating point ----

def test_exact_tick_boundary_is_not_pushed_up():
    assert ticks_for(6.0, 0.25) == 24
    assert ticks_for(4.000000000001 * 1.5, 0.25) == 24          # float noise above the boundary
    assert ticks_for((0.1 + 0.2) * 10, 0.1) == 30               # 3.0000000000000004
    assert ticks_for(6.01, 0.25) == 25                           # a real overshoot still rounds up
    assert ticks_for(0.0, 0.25) == 0 and ticks_for(-1.0, 0.25) == 0


def test_contract_floor_is_not_pulled_down_by_float_noise():
    assert size_for(0.3 * 1000, 100) == 3                        # 299.99999999999994 / 100
    assert size_for(600, 300) == 2
    assert size_for(599.99, 300) == 1                            # a real shortfall still rounds down
    assert size_for(500, 0) == 0 and size_for(0, 300) == 0


# ---- Risk modes ----

def test_percent_and_prop_firm_budgets():
    assert budget_for('% of account', acct=50000, pct=0.5) == 250.0
    assert math.isclose(budget_for('Prop firm', dd_left=2000, streak=10, buffer_pct=10), 180.0)
    assert math.isclose(budget_for('Prop firm', dd_left=2000, buffer_pct=10, daily_left=300), 135.0)
    assert budget_for('Fixed $', risk=250, daily_left=300) == 150.0     # cap = half of daily left
    assert budget_for('Fixed $', risk=100, daily_left=300) == 100.0     # cap only lowers
    assert budget_for('Prop firm', dd_left=0) == 0.0                    # nothing left: size 0
    assert plan(budget_for('Prop firm', dd_left=0), 4.0, 1.5, 'ES')['n'] == 0


# ---- Costs and invalid data ----

def test_costs_reduce_size_never_raise_risk():
    es = plan(500, 4.0, 1.5, 'ES', cost_std=4.5)
    assert es['per'] == 304.5 and es['n'] == 1 and es['risk'] <= 500
    mes = plan(500, 4.0, 1.5, 'MES', cost_std=4.5, cost_micro=1.2)
    assert math.isclose(mes['per'], 31.2) and mes['n'] == 16 and mes['risk'] <= 500
    p = pair(500, 4.0, 1.5, 'ES', cost_std=4.5, cost_micro=1.2)
    assert p['ES'][0] == 1 and p['MES'][0] == 16


def test_invalid_data_gives_zero_not_errors():
    assert plan(500, 0.0, 1.5, 'ES')['n'] == 0
    assert plan(500, 4.0, 1.5, 'ES', pv=0.0)['n'] == 0
    src = PLANNER.read_text()
    assert 'dataOk = not na(atr) and atr > 0 and not na(pointValue) and pointValue > 0 and tick > 0' in src
    assert '"Waiting for ATR data"' in src and '"Set the value per point"' in src
    assert 'syminfo.currency == "USD" ? "$" : syminfo.currency' in src     # non-USD symbols labelled
