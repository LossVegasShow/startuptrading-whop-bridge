"""Build the StartUpTrading sales page.

    python sales-site/build.py

Reads src/*.html, src/styles.css, src/affiliate.js + src/app.js and site.config.json, and writes
(plus dist/affiliate-tracking.html, the GoHighLevel site-wide affiliate snippet),
for each page in PAGES:
  dist/<name>.html        full standalone page (preview it in a browser)
  dist/<name>-embed.html  the block to paste into a GoHighLevel "Code" element

  sales page:     dist/index.html   + dist/ghl-embed.html     (GHL path /)
  thank-you page: dist/welcome.html + dist/welcome-embed.html (GHL path /welcome)
  calculator:     dist/calculator.html + dist/calculator-embed.html
                  (GHL path /futures-position-size-calculator)

Everything is scoped under `.sut` so GoHighLevel's own styles can't clash.
"""
import html
import json
import random
import re
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / 'src'
DIST = HERE / 'dist'

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700'
         '&family=Geist+Mono:wght@400;500;600&display=swap" rel="stylesheet">')


# Whop's embedded-checkout loader (from the @whop/checkout package, v0.7.0).
WHOP_LOADER = 'https://js.whop.com/static/checkout/loader.js'

# name -> (source template, standalone file, embed file, <title>, description)
PAGES = {
    'sales': ('page.html', 'index.html', 'ghl-embed.html',
              'StartUpTrading: proprietary NinjaTrader tools, trade room and masterclasses',
              "Jack's proprietary NinjaTrader 8 tools, licensed to your account automatically, plus the StartUpTrading Discord and masterclasses. "
              '${price_monthly}/month, cancel anytime.'),
    'welcome': ('welcome.html', 'welcome.html', 'welcome-embed.html',
                'Welcome to StartUpTrading',
                'Your StartUpTrading membership: next steps to activate your indicators.'),
    'calculator': ('calculator.html', 'calculator.html', 'calculator-embed.html',
                   'Futures Position Size Calculator & Prop-Firm Risk Planner (Free)',
                   'Free futures position size calculator for ES, NQ, MES, MNQ, CL, GC and more. Size from ATR '
                   'or a fixed stop, and plan risk per trade for a prop-firm drawdown.'),
}


# Where the free-indicator offer appears; each link is tagged so free signups
# from the sales page (and which spot) show up in analytics.
FREE_PLACEMENTS = ('pricing', 'final', 'faq', 'exit')


def tagged(url, placement, campaign='not_ready'):
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query.update({'utm_source': 'startuptrading', 'utm_medium': 'sales_page',
                  'utm_campaign': campaign, 'utm_content': placement})
    return urlunsplit(parts._replace(query=urlencode(query)))


def candles(seed=7, n=64, w=640, h=300):
    """Decorative candlestick backdrop for the demo frame (not real market data)."""
    rnd = random.Random(seed)
    price, rows = 100.0, []
    for _ in range(n):
        o = price
        c = o + rnd.gauss(0.25, 1.6)
        hi = max(o, c) + abs(rnd.gauss(0, .8))
        lo = min(o, c) - abs(rnd.gauss(0, .8))
        rows.append((o, hi, lo, c))
        price = c
    top = max(r[1] for r in rows); bot = min(r[2] for r in rows)
    y = lambda v: round(h - 16 - (v - bot) / (top - bot) * (h - 32), 1)
    step = w / n; body = step * .56
    out = []
    for i, (o, hi, lo, c) in enumerate(rows):
        x = round(i * step + step / 2, 1)
        cls = 'up' if c >= o else 'dn'
        out.append(f'<line class="{cls}" x1="{x}" x2="{x}" y1="{y(hi)}" y2="{y(lo)}"/>')
        y0, y1 = sorted((y(o), y(c)))
        out.append(f'<rect class="{cls}" x="{round(x - body / 2, 1)}" y="{y0}" width="{round(body, 1)}" '
                   f'height="{max(1.0, round(y1 - y0, 1))}"/>')
    return (f'<svg class="sut-candles" viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true">'
            + ''.join(out) + '</svg>')


def render(cfg, name='sales'):
    template, _, _, title, description = PAGES[name]
    page = (SRC / template).read_text()
    # <!--include:_file.html--> pulls in a shared partial from src/.
    page = re.sub(r'<!--include:([\w.-]+\.html)-->', lambda m: (SRC / m.group(1)).read_text(), page)
    css = (SRC / 'styles.css').read_text()
    # affiliate.js runs first: it sets window.SUT_AFFILIATE for app.js.
    js = (SRC / 'affiliate.js').read_text() + '\n' + (SRC / 'app.js').read_text()
    cfg = dict(cfg)
    # Plan IDs come from the checkout URLs so there is a single source of truth.
    for url_key, plan_key in (('checkout_url', 'plan_monthly'), ('checkout_url_annual', 'plan_annual')):
        m = re.search(r'(plan_[A-Za-z0-9]+)', cfg.get(url_key, ''))
        if not m:
            raise ValueError(f'{url_key} must contain a Whop plan ID (plan_...)')
        cfg[plan_key] = m.group(1)
    embed_on = str(cfg.get('embed_checkout', '')).lower() == 'true'
    cfg['embed_checkout'] = 'true' if embed_on else ''
    # Page-wide Join buttons scroll to the on-page checkout when it's embedded,
    # otherwise they go straight to Whop's hosted checkout.
    cfg['cta_href'] = '#checkout' if embed_on else cfg['checkout_url']
    values = {k: html.escape(str(v), quote=True) for k, v in cfg.items()}
    values['candles'] = candles()
    values['cta_attr'] = '' if embed_on else ' data-checkout'
    cfg['exit_offer'] = 'true' if str(cfg.get('exit_offer', '')).lower() == 'true' and cfg.get('free_indicator_url') else ''
    for place in FREE_PLACEMENTS:
        values[f'free_url_{place}'] = html.escape(tagged(cfg['free_indicator_url'], place), quote=True) if cfg.get('free_indicator_url') else ''
    # The free calculator is its own campaign, so its free-indicator signups are counted separately.
    values['free_url_calc'] = html.escape(tagged(cfg['free_indicator_url'], 'calculator', campaign='calculator'),
                                          quote=True) if cfg.get('free_indicator_url') else ''

    def sub(m):
        key = m.group(1)
        if key not in values:
            raise KeyError(f'page.html uses {{{{{key}}}}} but site.config.json has no "{key}"')
        return values[key]

    body = re.sub(r'\{\{\s*([a-z_]+)\s*\}\}', sub, page)
    # Optional blocks: <!--if:key--> ... <!--endif:key--> are removed when the value is blank.
    # <!--ifnot:key--> ... <!--endifnot:key--> is the reverse.
    for key, val in cfg.items():
        on = bool(str(val).strip())
        pattern = re.compile(rf'<!--if:{key}-->(.*?)<!--endif:{key}-->', re.S)
        body = pattern.sub(lambda m: m.group(1) if on else '', body)
        pattern = re.compile(rf'<!--ifnot:{key}-->(.*?)<!--endifnot:{key}-->', re.S)
        body = pattern.sub(lambda m: '' if on else m.group(1), body)
    has_checkout = '<div data-whop-checkout-plan-id=' in body
    loader = f'<script async defer src="{WHOP_LOADER}"></script>\n' if has_checkout else ''
    embed = f'{FONTS}\n<style>\n{css}\n</style>\n{body}\n<script>\n{js}\n</script>\n{loader}'
    full = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            f'<title>{html.escape(title)}</title>\n'
            f'<meta name="description" content="{html.escape(description.replace("{price_monthly}", cfg["price_monthly"]), quote=True)}">\n'
            + ('<meta name="robots" content="noindex">\n' if name == 'welcome' else '') +
            '<meta name="theme-color" content="#07090d">\n'
            '<style>html,body{margin:0;background:#07090d}</style>\n'
            f'</head>\n<body>\n{embed}</body>\n</html>\n')
    return embed, full


def main():
    cfg = json.loads((HERE / 'site.config.json').read_text())
    DIST.mkdir(exist_ok=True)
    for name, (_, full_name, embed_name, _, _) in PAGES.items():
        embed, full = render(cfg, name)
        (DIST / embed_name).write_text(embed)
        (DIST / full_name).write_text(full)
        print(f'{name}: wrote dist/{full_name} and dist/{embed_name} ({len(embed) // 1024} KB)')
    (DIST / 'affiliate-tracking.html').write_text(affiliate_snippet())
    print('affiliate: wrote dist/affiliate-tracking.html (GoHighLevel site-wide tracking code)')


def affiliate_snippet():
    """Paste into GoHighLevel → Settings → Tracking code (header), site-wide, so an
    affiliate's ?a= is captured on ANY startuptrading.com page, not just /join."""
    return ('<!-- StartUpTrading: Whop affiliate attribution (sales-site/src/affiliate.js) -->\n'
            '<script>\n' + (SRC / 'affiliate.js').read_text() + '</script>\n')


if __name__ == '__main__':
    main()
