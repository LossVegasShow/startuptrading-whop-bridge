"""Structured outputs exchanged between the marketing agents."""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Pillar = Literal['process', 'live', 'bundle', 'easy_start']
Channel = Literal['youtube', 'shorts', 'x', 'email', 'community']


class Finding(BaseModel):
    summary: str = Field(description='One or two sentences, factual.')
    source_url: str = Field(description='The page this came from. Empty if none.')


class ResearchReport(BaseModel):
    competitor_moves: List[Finding] = Field(
        description='New releases, prices, promotions or content from NinjaTrader indicator vendors and trade rooms.')
    audience_questions: List[str] = Field(
        description='Questions futures traders are asking this week about sizing, stops, trend reading or NinjaTrader.')
    trending_topics: List[str] = Field(description='Market events or themes traders will care about this week.')
    content_ideas: List[str] = Field(description='Specific video or post ideas Jack could make from this.')


class ContentBrief(BaseModel):
    id: str = Field(description='Short slug, e.g. "atr-stop-trend-day".')
    title: str
    pillar: Pillar
    angle: str = Field(description='The one idea this piece teaches.')
    record_this: str = Field(
        description='What Jack needs to show or say on stream for this piece, e.g. "During the ES open, narrate how '
                    'ATR Order Automation sets the stop".')
    channels: List[Channel]
    call_to_action: Literal['free_indicator', 'join']


class WeeklyPlan(BaseModel):
    theme: str = Field(description='The week in one line.')
    rationale: str = Field(description='Why this theme, based on the research and the metrics.')
    briefs: List[ContentBrief]


class ContentPack(BaseModel):
    brief_id: str
    youtube_title: str = Field(description='Under 70 characters, names the market or setup.')
    youtube_description: str
    shorts_script: str = Field(description='30 to 60 seconds, with a hook in the first 2 seconds.')
    x_posts: List[str] = Field(description='Two or three posts, each under 260 characters.')
    email_subject: str
    email_body: str


class ReviewResult(BaseModel):
    approved: bool = Field(description='True only if the revised pack breaks none of the hard rules.')
    issues: List[str] = Field(description='Each problem found in the original, and how it was fixed.')
    revised: ContentPack


class KPIReport(BaseModel):
    summary: str
    wins: List[str]
    concerns: List[str]
    recommendations: List[str] = Field(description='Concrete changes for next week, most important first.')


# ---- Outreach desk ---------------------------------------------------------

ProspectKind = Literal['podcast', 'prop_firm', 'discord', 'newsletter', 'youtube', 'journalist', 'event']


class Prospect(BaseModel):
    name: str
    kind: ProspectKind
    url: str = Field(description='The page where you found them.')
    audience: str = Field(description='Who they reach, as described on their own pages. No invented numbers.')
    why_fit: str = Field(description='Why Jack is a good fit for them, specifically.')
    contact_route: str = Field(
        description='How to reach them, only as published on their site (guest form URL, contact page, '
                    'listed email). Write "not published" if you did not find one. Never guess an email.')


class ProspectList(BaseModel):
    prospects: List[Prospect]


class Pitch(BaseModel):
    prospect_name: str
    subject: str
    body: str = Field(description='Under 150 words, personal, offers something specific.')
    follow_up: str = Field(description='A two-sentence follow-up to send after 7 days with no reply.')


class PitchList(BaseModel):
    pitches: List[Pitch]


# ---- Clip desk -------------------------------------------------------------

class Clip(BaseModel):
    source_file: str
    start: str = Field(description='Timestamp where the clip starts, as written in the transcript.')
    end: str
    hook: str = Field(description='On-screen text for the first 2 seconds, under 60 characters.')
    caption_en: str
    caption_es: str = Field(description='The same caption in natural Latin American Spanish.')
    pillar: Pillar
    why: str = Field(description='Why this moment will hold attention.')


class ClipList(BaseModel):
    clips: List[Clip]


# ---- Trend desk (real-time) ------------------------------------------------

SpeedTier = Literal['post_now', 'post_today', 'watch', 'skip']


class TrendPost(BaseModel):
    x_post: str = Field(description='Under 190 characters (the risk line is added after). Names the trend in the '
                                    'first five words. Funny to anyone; a trading twist only if it makes the joke better.')
    threads_caption: str = Field(description='Instagram/Threads/TikTok caption, under 300 characters, same joke.')
    short_hook: str = Field(description='On-screen text for the first 2 seconds of a vertical video, under 60 chars.')
    short_script: str = Field(description='A 10 to 20 second piece Jack can film on his phone in one take.')
    visual: str = Field(description='What the image or video shows. Prefer Jack reacting on camera or an original '
                                    'chart graphic. Never a company logo or someone else\'s footage.')
    reply_line: str = Field(description='A one-line reply to drop under the biggest posts about this trend.')


class TrendPick(BaseModel):
    trend: str = Field(description='The trend as people are searching it.')
    what_happened: str = Field(description='One or two factual sentences, verified by search.')
    source_url: str = Field(description='A credible page confirming what happened. Empty only for speed=skip.')
    why_viral: str = Field(description='Why it is spreading and how long it will likely stay hot.')
    bridge: str = Field(description='The trading twist, if one truly improves the joke. Empty for pure humor.')
    speed: SpeedTier = Field(description='post_now: peaking, safe, strong joke, post within 60 minutes. '
                                         'post_today: rising, good joke. watch: may get big. '
                                         'skip: unsafe or not funny enough.')
    found_by_search: bool = Field(description='True if this came from your own search, not the candidate list.')
    safety_note: str = Field(description='Any sensitivity, and why it is safe (or why skipped).')
    posts: Optional[TrendPost] = Field(default=None, description='Null when speed is skip.')


class MomentTake(BaseModel):
    moment_id: str
    x_post: str = Field(description='Under 190 characters. Better than the seed lines and different from them.')
    short_hook: str
    short_script: str = Field(description='10 to 20 seconds, one take.')


class TrendRadar(BaseModel):
    picks: List[TrendPick] = Field(description='Most urgent first.')
    moment_takes: List[MomentTake]
