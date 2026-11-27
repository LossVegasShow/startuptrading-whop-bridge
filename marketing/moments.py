"""The known-moments calendar: dates everyone online will talk about, with ready-to-post lines.

The trend desk reads this every run. A moment enters the queue `lead_days` before its date so
the post can be scheduled ahead, and the AI writes fresh variants on the day. The seed lines below
were written by hand and pass the phrase rules in `compliance.py` (see tests/test_trend_desk.py).

Kinds:
- fun:        jokes welcome.
- market:     a market event (FOMC, jobs, expiry). Wit plus one useful risk point.
- respectful: a day of remembrance. Markets-closed notice only; never a joke.

Dates marked `verify` come from a rule or a third-party calendar. Check the official source
(named in `notes`) before scheduling the post.
"""
import datetime as dt
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

MON, TUE, WED, THU, FRI, SAT, SUN = range(7)


@dataclass(frozen=True)
class Moment:
    id: str
    name: str
    kind: str                     # fun | market | respectful
    angle: str                    # the bridge from the moment to trading
    seeds: Tuple[str, ...]        # ready-to-post lines (risk line is added on output)
    lead_days: int = 3
    verify: bool = False
    notes: str = ''


@dataclass
class Occurrence:
    moment: Moment
    date: dt.date
    days_away: int = 0
    extra: dict = field(default_factory=dict)


def nth_weekday(year, month, weekday, n):
    """n-th weekday of a month (n=1 first). n=-1 is the last one."""
    if n > 0:
        d = dt.date(year, month, 1)
        d += dt.timedelta(days=(weekday - d.weekday()) % 7)
        return d + dt.timedelta(weeks=n - 1)
    nxt = dt.date(year + (month == 12), month % 12 + 1, 1)
    d = nxt - dt.timedelta(days=1)
    return d - dt.timedelta(days=(d.weekday() - weekday) % 7)


def thanksgiving(year):
    return nth_weekday(year, 11, THU, 4)


# FOMC decision days (the second day of each meeting; statement 2:00 pm ET, press conference 2:30).
# Source: federalreserve.gov/monetarypolicy/fomccalendars.htm, revised 2027 schedule of 2026-11-12.
# The October 2027 meeting is strategy-only (no policy decision), so it is not listed.
FOMC_DECISIONS = [dt.date(2026, 12, 9),
                  dt.date(2027, 1, 27), dt.date(2027, 3, 17), dt.date(2027, 4, 28), dt.date(2027, 6, 9),
                  dt.date(2027, 7, 28), dt.date(2027, 9, 15), dt.date(2027, 11, 17)]
SUPER_BOWLS = {2027: dt.date(2027, 2, 14), 2028: dt.date(2028, 2, 13)}


M = Moment
MOMENTS = {m.id: m for m in [
    # ---- Holidays and culture ------------------------------------------------
    M('new_years_eve', "New Year's Eve", 'fun', 'Resolutions vs a written trading plan.', (
        "New Year's resolutions last about two weeks. Trading plans written at 11:58 pm on Dec 31 don't do "
        "better. Write yours on a boring Tuesday.",
        "2027 resolution: stop adding to losers. Same as my 2026 resolution. Self-awareness is step one.",
        "Countdown tonight: 10, 9, 8... The only countdown I respect in a trade is the one to my stop.",
    )),
    M('new_years_day', "New Year's Day", 'fun', 'Fresh start, same risk rules. Markets closed.', (
        "New year, new me. Same max loss per trade, though. Some things don't need a reboot.",
        "Markets are closed today. Perfect day to do the one thing nobody does: read last year's trade journal.",
    ), lead_days=1),
    M('valentines', "Valentine's Day", 'fun', "Don't fall in love with a position.", (
        "Valentine's Day reminder: don't marry your position. It was never going to commit to you either.",
        "If you have to text a trade \"please come back,\" it's time to let it go. That's what the stop is for.",
        "Roses are red, my size was too big. I moved my stop once, and that was the gig.",
    )),
    M('super_bowl', 'Super Bowl Sunday', 'fun', 'Football has timeouts and a two-minute warning. Markets do not.', (
        "The Super Bowl has a two-minute warning. NQ does not.",
        "Every team walks out with a playbook and a defense. Show me your plan for when the first play goes wrong.",
        "Super Bowl on Valentine's Day. Somebody's about to learn about risk management the hard way, "
        "and it isn't the quarterback.",
    ), lead_days=4, verify=True, notes='Date from the NFL schedule; 2027 falls on Valentine\'s Day.'),
    M('pi_day', 'Pi Day (3/14)', 'fun', 'Irrational numbers vs irrational sizing.', (
        "Pi Day: the only irrational number a trader should be comfortable with. Your position size isn't one of them.",
    ), lead_days=2),
    M('st_patricks', "St. Patrick's Day", 'fun', 'Luck is not a risk plan.', (
        "Luck of the Irish is a lovely tradition and a terrible risk plan. Define the stop before the entry.",
        "Four-leaf clovers are rare. So are traders who actually respect their max daily loss. Be rare.",
    )),
    M('april_fools', "April Fools' Day", 'fun', 'The jokes traders tell themselves.', (
        "Best April Fools' joke in trading: \"I'll just hold it until it comes back.\"",
        "April Fools' prank idea: tell your trading buddy you followed your plan all week. They'll never believe it.",
    )),
    M('tax_day', 'US Tax Day', 'fun', 'Record keeping is part of the process.', (
        "Tax day: the one day a year traders wish they'd taken fewer trades.",
        "My accountant asked why the spreadsheet has 4,000 rows. Overtrading has a paperwork department.",
    ), notes='Light touch only. No tax advice: point to a tax professional.'),
    M('may_fourth', 'May the 4th', 'fun', 'Patience and discipline, film-quote style.', (
        "Do or do not. There is no \"just one more trade.\"",
        "Fear leads to oversizing. Oversizing leads to revenge trading. Revenge trading leads to suffering.",
    ), lead_days=2),
    M('memorial_day', 'Memorial Day', 'respectful', 'Markets closed. Remembrance, no jokes.', (
        "US markets are closed today for Memorial Day. We're stepping away from the charts to remember those who "
        "gave their lives in service.",
    ), lead_days=2, notes='Check CME holiday hours. No humor, no promotion.'),
    M('juneteenth', 'Juneteenth', 'respectful', 'Markets closed. Observance, no jokes.', (
        "US markets are closed today in observance of Juneteenth.",
    ), lead_days=2, notes='Check CME holiday hours. No humor, no promotion.'),
    M('july_fourth', 'Independence Day', 'fun', 'Independence from bad habits.', (
        "Happy Fourth. Declare independence from revenge trading. Life, liberty and the pursuit of a defined stop.",
        "Fireworks are best enjoyed from a distance. So are thin pre-holiday sessions.",
    ), notes='Check CME early-close hours for July 3.'),
    M('halloween', 'Halloween', 'fun', 'The scariest things in trading.', (
        "Scariest costume this year: a 10-contract NQ position on CPI morning with no stop.",
        "Things that go bump in the night: overnight gaps on a position you swore you'd close before the bell.",
        "Trick or treat? Neither. Trade your plan.",
    )),
    M('thanksgiving', 'Thanksgiving', 'fun', 'Gratitude for the trades not taken. Markets closed.', (
        "Grateful for stop losses, half-days, and every trade I didn't take this year.",
        "Thanksgiving tip: you can go back for seconds at dinner. Don't go back for seconds on a losing trade.",
    ), lead_days=2, notes='CME equity futures halt early on Thanksgiving Day; check the holiday calendar.'),
    M('black_friday', 'Black Friday', 'fun', 'Shoppers buy at a discount; traders panic at one. Half-day session.', (
        "Black Friday: people line up at 5 am to buy things 40% off, then panic when the market is 5% off.",
        "Black Friday is just FOMO with a parking problem.",
        "Doorbusters at 6 am. Futures close early at 12:15 pm CT. Half-day session, full-size emotions. Size down.",
        "Thin holiday volume is a store with one cashier and 400 people in line. Things get weird fast. "
        "Smaller size, wider patience.",
        "The checkout screen says \"You saved $212.\" Nobody ever gets that pop-up for the trade they didn't take. "
        "So here it is: you did.",
        "Things that should never be a doorbuster: your position size.",
    ), lead_days=4, notes='CME equity index futures close early at 12:15 pm CT; confirm on cmegroup.com/trading-hours.'),
    M('cyber_monday', 'Cyber Monday', 'fun', 'Urgency is a sales tactic. In trading it is a warning sign.', (
        "Cyber Monday rule: if a deal needs a countdown timer to convince you, it isn't a deal. Same goes for a setup.",
        "\"Add to cart\" has the same energy as \"add to a losing position.\" Both feel great for about four seconds.",
        "Cyber Monday is the only day \"limited time only\" is honest. In trading, there's always another setup tomorrow.",
    )),
    M('christmas_eve', 'Christmas Eve', 'fun', 'Holiday sessions and the Santa rally myth.', (
        "The Santa Claus rally is real in the same way Santa is: a lovely tradition and a terrible risk plan.",
        "Santa checks his list twice. Check your stop once, then leave it alone.",
    ), notes='Check CME early-close hours.'),
    M('christmas', 'Christmas Day', 'fun', 'Markets closed. Light gratitude.', (
        "All I want for Christmas is a stop loss I actually respect.",
        "Markets are closed. The best trade today is the one with your family. Merry Christmas from StartUpTrading.",
    ), lead_days=2),

    # ---- Market moments ------------------------------------------------------
    M('fomc', 'FOMC decision', 'market', 'Event risk: spreads widen, ranges jump, size comes down.', (
        "FOMC at 2:00. The market spends six hours pretending it doesn't care, then six seconds proving it does.",
        "Fed day plan: small size before 2:00, no size at 2:00, and a fresh read after the press conference.",
        "My heart rate at 1:59 pm on Fed day: elevated. My position size: not.",
    ), lead_days=2, verify=True, notes='Statement 2:00 pm ET, press conference 2:30. Dates are tentative: '
                                        'federalreserve.gov/monetarypolicy/fomccalendars.htm'),
    M('jobs_report', 'Jobs report (NFP)', 'market', '8:30 am ET release; the first minutes are noise.', (
        "Jobs report at 8:30. The only job I have at 8:29 is not having a position.",
        "NFP morning: the first five minutes are the market reading the headline. The next hour is it reading the "
        "details. Wait for the second one.",
    ), lead_days=1, verify=True, notes='Usually the first Friday; confirm on bls.gov/schedule/news_release/empsit.htm.'),
    M('quad_witching', 'Quad witching (quarterly expiry)', 'market', 'Expiry-day volume and odd moves.', (
        "Quad witching: it isn't Halloween, but the candles still get scary.",
        "Expiry Friday. Lots of volume, very little of it about the trade you're looking at. Size down.",
    ), lead_days=2, verify=True, notes='Third Friday of Mar/Jun/Sep/Dec. Confirm on cmegroup.com.'),
    M('es_roll', 'Index futures roll', 'market', 'Check the contract month on your chart.', (
        "Roll week. Your chart didn't break, the contract changed. Check the month before you check your sanity.",
        "PSA: if volume on your ES chart suddenly looks like a ghost town, you might be trading last quarter's contract.",
    ), lead_days=2, verify=True, notes='Usually the second Thursday of the expiry month (8 days before expiry). '
                                       'Confirm on cmegroup.com.'),
    M('dst_change', 'US clocks change', 'market', 'Session times shift; Europe changes on a different week.', (
        "Clocks changed. Your alarm is wrong, your chart's session times may be wrong, and for a couple of weeks "
        "London is on a different hour too. Check before the open.",
        "Daylight saving: the one day a year everyone gets an extra hour of screen time they didn't ask for.",
    ), lead_days=2, notes='US: second Sunday of March, first Sunday of November.'),
    M('friday_13', 'Friday the 13th', 'fun', 'Superstition vs process.', (
        "Friday the 13th. Traders who are superstitious about the date, but not about trading without a stop.",
        "Unlucky day? Luck has nothing to do with it. Defined risk does.",
    ), lead_days=2),
]}


def occurrences(year):
    """All moment dates in one calendar year."""
    out = []

    def add(mid, d, **extra):
        if d and d.year == year:
            out.append(Occurrence(MOMENTS[mid], d, extra=extra))

    fixed = {'new_years_day': (1, 1), 'valentines': (2, 14), 'pi_day': (3, 14), 'st_patricks': (3, 17),
             'april_fools': (4, 1), 'tax_day': (4, 15), 'may_fourth': (5, 4), 'juneteenth': (6, 19),
             'july_fourth': (7, 4), 'halloween': (10, 31), 'christmas_eve': (12, 24), 'christmas': (12, 25),
             'new_years_eve': (12, 31)}
    for mid, (mo, day) in fixed.items():
        add(mid, dt.date(year, mo, day))
    tg = thanksgiving(year)
    add('thanksgiving', tg)
    add('black_friday', tg + dt.timedelta(days=1))
    add('cyber_monday', tg + dt.timedelta(days=4))
    add('memorial_day', nth_weekday(year, 5, MON, -1))
    add('dst_change', nth_weekday(year, 3, SUN, 2), direction='forward')
    add('dst_change', nth_weekday(year, 11, SUN, 1), direction='back')
    add('super_bowl', SUPER_BOWLS.get(year))
    for d in FOMC_DECISIONS:
        add('fomc', d)
    for mo in range(1, 13):
        add('jobs_report', nth_weekday(year, mo, FRI, 1))
        if dt.date(year, mo, 13).weekday() == FRI:
            add('friday_13', dt.date(year, mo, 13))
    for mo in (3, 6, 9, 12):
        add('quad_witching', nth_weekday(year, mo, FRI, 3))
        add('es_roll', nth_weekday(year, mo, THU, 2))
    return sorted(out, key=lambda o: (o.date, o.moment.id))


def upcoming(today: dt.date, days: Optional[int] = None) -> List[Occurrence]:
    """Moments from today forward. With days=None, only those inside their own lead window."""
    found = []
    for year in (today.year, today.year + 1):
        for o in occurrences(year):
            away = (o.date - today).days
            limit = o.moment.lead_days if days is None else days
            if 0 <= away <= limit:
                o.days_away = away
                found.append(o)
    return found
