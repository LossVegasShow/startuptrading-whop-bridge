"""Structured outputs exchanged between the marketing agents."""
from typing import List, Literal

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
