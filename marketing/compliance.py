"""Deterministic compliance checks for marketing copy.

The AI compliance reviewer catches nuance; these rules catch the phrases that
must never ship, whatever the model decides. A piece with any hit is held back
as "needs_changes" and never marked ready for review.
"""
import re

RISK_LINE = ('Futures trading involves substantial risk of loss and is not suitable for '
             'every investor. Education only, not financial advice.')
# For X posts and Shorts captions, where space is tight.
SHORT_RISK_LINE = 'Futures trading involves substantial risk of loss. Education only, not financial advice.'
SPANISH_RISK_LINE = ('El trading de futuros implica un riesgo sustancial de pérdida. '
                     'Solo educativo, no es asesoramiento financiero.')

# (rule id, pattern, why). Patterns are case-insensitive.
BANNED = [
    ('profit_claim', r'\bprofit(?:s|able|ability)?\b(?!\s+targets?\b)',
     'Profit language implies results. "Profit target" is fine.'),
    ('income_claim', r'\b(?:income|paycheck|financial freedom|quit your (?:job|9.?to.?5)|replace your (?:job|salary))\b',
     'Income claims are banned.'),
    ('money_made', r'\b(?:made|make|making|earn(?:ed|ing|s)?|bank(?:ed)?|pull(?:ed)?)\s+(?:(?:me|us|you|him|them|my|our)\s+)?'
     r'(?:over\s+|about\s+|nearly\s+)?\$\s?\d',
     'Statements about money made are banned.'),
    ('pnl', r'\b(?:p\s?&\s?l|pnl|account balance|green day|red day)\b',
     'No P&L or account balances.'),
    ('win_rate', r'\b(?:win(?:ning)?\s*(?:rate|percentage|%)|\d{2,3}\s?%\s*(?:accura\w*|win\w*|success\w*))',
     'No win rates or accuracy figures.'),
    ('guarantee', r'\b(?:guarantee[ds]?|risk[- ]free|no[- ]risk|can\'?t lose|never lose|sure thing|get rich)\b',
     'No guarantees or "no risk" claims.'),
    ('superlative', r'\b(?:best (?:trader|traders|in the world|on the planet)|one of the best|nowhere else|'
                    r'only (?:tool|indicator|one) (?:like|of its kind)|#1 trader|world[- ]class trader)\b',
     'Unprovable superlatives are banned.'),
    ('hypothetical', r'\b(?:backtest(?:ed|ing|s)?|hypothetical|simulated (?:results|returns|performance))\b',
     'No backtests or hypothetical results in marketing.'),
    ('urgency', r'\b(?:only \d+ (?:spots|seats|places) left|last chance|act now|expires (?:tonight|today)|hurry)\b',
     'No pressure tactics.'),
    ('trade_call', r'\b(?:buy|sell|short|long) (?:now|here) at\b',
     'Trade calls cross into advice. Keep it educational.'),
    # Spanish captions (clip desk)
    ('es_profit', r'\b(?:ganancias?|rentables?|rentabilidad|ingresos|garantizad[oa]s?|sin riesgo|hazte rico)\b',
     'Spanish: no profit, income or guarantee language.'),
]
_COMPILED = [(rid, re.compile(p, re.IGNORECASE), why) for rid, p, why in BANNED]

# Phrases that would trip a rule but say the opposite of a claim. Only these exact
# shapes are allowed: the brand line "show your risk, not your profits".
ALLOWED = re.compile(r'\brisk,?\s+not\s+(?:my\s+|your\s+|the\s+)?profits\b', re.IGNORECASE)


def check_text(text):
    """Return a list of {rule, match, why} hits for one piece of text."""
    hits = []
    text = ALLOWED.sub('risk', text or '')
    for rid, rx, why in _COMPILED:
        for m in rx.finditer(text):
            hits.append({'rule': rid, 'match': m.group(0), 'why': why})
    return hits


def has_risk_line(text):
    t = (text or '').lower()
    return 'substantial risk' in t or 'risk of loss' in t or 'riesgo sustancial' in t


def with_risk_line(text, short=False, spanish=False):
    """Append the risk line if the text doesn't already carry one."""
    if has_risk_line(text):
        return text
    line = SPANISH_RISK_LINE if spanish else (SHORT_RISK_LINE if short else RISK_LINE)
    return (text or '').rstrip() + '\n\n' + line


def check_pack(fields):
    """Check a dict of {field name: text}. Returns {field: [hits]} for fields with hits."""
    return {name: hits for name, text in fields.items() if (hits := check_text(text))}
