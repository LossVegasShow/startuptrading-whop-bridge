"""The marketing team: one function per role, each a Claude API call.

Every agent shares the same brand brief as a cached system block, then gets
its own role instructions. Outputs are validated Pydantic objects, so one
stage hands the next exactly the shape it expects.

`client` is an `anthropic.Anthropic()` instance (or a test double with the
same `messages.parse` method). Nothing here publishes anything.
"""
import json
from pathlib import Path

from .models import (ClipList, ContentBrief, ContentPack, KPIReport, PitchList, ProspectList, ResearchReport,
                     ReviewResult, WeeklyPlan)

MODEL = 'claude-opus-5-5'
MAX_TOKENS = 16000
BRIEF_PATH = Path(__file__).with_name('brand_brief.md')
WEB_SEARCH = {'type': 'web_search_20260209', 'name': 'web_search', 'max_uses': 8}


class AgentError(RuntimeError):
    """An agent returned no usable output (refusal, truncation, or bad shape)."""


def brand_brief():
    return BRIEF_PATH.read_text(encoding='utf-8')


def _system(role):
    # Brand brief first and cached: every call in a run shares this prefix.
    return [
        {'type': 'text', 'text': 'You are part of the in-house marketing team for StartUpTrading.\n\n' + brand_brief(),
         'cache_control': {'type': 'ephemeral'}},
        {'type': 'text', 'text': role},
    ]


def _ask(client, role, prompt, output_format, effort='medium', tools=None, max_turns=4):
    messages = [{'role': 'user', 'content': prompt}]
    kwargs = dict(model=MODEL, max_tokens=MAX_TOKENS, system=_system(role),
                  output_config={'effort': effort}, output_format=output_format)
    if tools:
        kwargs['tools'] = tools
    for _ in range(max_turns):
        resp = client.messages.parse(messages=messages, **kwargs)
        if resp.stop_reason == 'pause_turn':
            # Server tool (web search) paused a long turn: resend to let it continue.
            messages = [messages[0], {'role': 'assistant', 'content': resp.content}]
            continue
        if resp.stop_reason == 'refusal':
            raise AgentError('the model declined this request')
        if resp.stop_reason == 'max_tokens':
            raise AgentError('output was cut off at max_tokens')
        if resp.parsed_output is None:
            raise AgentError('no structured output returned')
        return resp.parsed_output
    raise AgentError('web search did not finish within the turn limit')


RESEARCHER = """Role: Market Researcher.
Search the web for what happened in the last 7 days that matters to a NinjaTrader futures day trader:
new or updated NinjaTrader indicators and add-ons (ATR sizing, trade managers, trend scanners), trade-room
offers and prices, NinjaTrader Live and NinjaTrader Ecosystem news, and questions traders are asking on
forums, Reddit and YouTube. Report facts with their source URL. Do not invent prices or numbers; if you
could not find something, leave it out."""

STRATEGIST = """Role: Content Strategist.
Turn the research and metrics into one weekly theme and 5 content briefs. Each brief must be something Jack
can capture during his normal live morning session, so that one stream feeds a week of posts. Spread briefs
across the four pillars. Most calls to action should be the free indicator; at most two should be "join"."""

WRITER = """Role: Copywriter.
Write the full content pack for one brief, as Jack, in the brand voice. YouTube copy should help search
(name the market and the setup). The Shorts script needs a hook in the first 2 seconds. Calls to action
link to https://startuptrading.com/indicators (free indicator) or https://startuptrading.com/join.
Follow every hard rule in the brand brief. End the email and the YouTube description with the risk line."""

COMPLIANCE = """Role: Compliance Reviewer for futures marketing (CFTC, NFA Rule 2-29, FTC Endorsement Guides).
Review the content pack strictly against the hard rules in the brand brief. Flag anything that claims or
implies profits, income, win rates or guaranteed outcomes; unprovable superlatives; hypothetical or backtested
results; pressure tactics; trade calls; testimonials about money; and facts not in the brand brief. Return a
revised pack that fixes every issue while keeping the useful teaching. Set approved=false if you could not
fix something without changing the piece's meaning."""

ANALYST = """Role: Marketing Analyst.
Read this week's metrics exports and compare them with the targets: free-indicator leads 150/week,
lead-to-member conversion 3-5%, activation within 24h 85%, monthly churn under 10%, annual-plan share 20%.
Say what moved and why, plainly, with the numbers. Recommend concrete changes for next week. If a number
is missing, say so rather than guessing."""


def research(client):
    return _ask(client, RESEARCHER, 'Research this week. Report findings with sources.',
                ResearchReport, effort='medium', tools=[WEB_SEARCH])


def plan_week(client, report, kpis=None):
    prompt = ('Research this week:\n' + report.model_dump_json(indent=1) +
              ('\n\nMetrics this week:\n' + kpis.model_dump_json(indent=1) if kpis else
               '\n\nNo metrics this week.'))
    return _ask(client, STRATEGIST, prompt, WeeklyPlan, effort='high')


def write_pack(client, brief: ContentBrief):
    return _ask(client, WRITER, 'Brief:\n' + brief.model_dump_json(indent=1), ContentPack, effort='medium')


def review_pack(client, pack: ContentPack, rule_hits=None):
    prompt = 'Content pack to review:\n' + pack.model_dump_json(indent=1)
    if rule_hits:
        prompt += ('\n\nThe automatic phrase checker also flagged these, and they must be removed:\n' +
                   json.dumps(rule_hits, indent=1))
    return _ask(client, COMPLIANCE, prompt, ReviewResult, effort='high')


def analyze(client, metrics_text):
    return _ask(client, ANALYST, 'Metrics exports:\n' + metrics_text, KPIReport, effort='medium')


PROSPECTOR = """Role: Outreach Researcher.
Use web search to find real outlets and communities where Jack would be a welcome guest or partner: futures and
day-trading podcasts that take guests, prop-trading firms with education or affiliate programs, trading
Discord communities with public contact routes, trading newsletters, YouTube channels that do interviews or
collaborations, journalists who cover retail trading and volatility, and trading events. Prefer active ones
(posted in the last 3 months). Only list what you actually found, with the page URL. Copy contact routes only
as published; never guess an email address. Skip anyone on the already-contacted list."""

PITCH_WRITER = """Role: Outreach Writer.
Write a short, personal first pitch for each prospect, from the StartUpTrading team on Jack's behalf. Lead with
what's in it for their audience: a guest segment ("Show your risk, not your profits"; how ATR sizing keeps a
news day and a quiet day at the same dollar risk; surviving prop-firm drawdown rules), the free position-size
calculator and prop-firm risk planner, the free ATR indicator, or a co-hosted live sizing clinic. Mention one
specific thing about them from the research. Credentials only as listed in the brand brief. Never mention
results, income or performance. No flattery padding, no pressure."""

CLIPPER = """Role: Clip Editor.
Read this live-stream transcript and pick the strongest 30 to 60 second moments for Shorts, Reels and TikTok:
a clear teaching point, a tool doing something visible (a size or stop being set, the scanner ranking markets),
a quotable line about risk or process, or a relatable story. Skip anything about profits, P&L, account size or
calls to buy or sell. For each, give exact start and end timestamps from the transcript, a hook for the first
2 seconds, an English caption and a natural Latin American Spanish caption."""


def find_prospects(client, count=10, contacted=()):
    prompt = f'Find {count} new outreach prospects this week, spread across the kinds.'
    if contacted:
        prompt += '\n\nAlready contacted (skip these):\n' + '\n'.join(f'- {c}' for c in contacted)
    return _ask(client, PROSPECTOR, prompt, ProspectList, effort='medium', tools=[WEB_SEARCH])


def write_pitches(client, prospects: ProspectList):
    return _ask(client, PITCH_WRITER, 'Prospects:\n' + prospects.model_dump_json(indent=1), PitchList,
                effort='medium')


def find_clips(client, name, transcript, max_clips=6):
    prompt = (f'Transcript file: {name}\nPick up to {max_clips} clips.\n\n'
              '<transcript>\n' + transcript + '\n</transcript>')
    return _ask(client, CLIPPER, prompt, ClipList, effort='medium')
