"""Build the StartUpTrading sales page.

    python sales-site/build.py

Reads src/*.html, src/styles.css, src/affiliate.js + src/app.js and site.config.json, and writes
(plus dist/affiliate-tracking.html, the GoHighLevel site-wide affiliate snippet),
for each page in PAGES:
  dist/<name>.html        full standalone page (preview it in a browser)
  dist/<name>-embed.html  the block to paste into a GoHighLevel "Code" element

  sales page:     dist/index.html   + dist/ghl-embed.html     (GHL path /)
  thank-you page: dist/welcome.html + dist/welcome-embed.html (GHL path /welcome)
  install guide:  dist/setup.html   + dist/setup-embed.html   (GHL path /setup)
  calculator:     dist/calculator.html + dist/calculator-embed.html
                  (GHL path /futures-position-size-calculator)

Everything is scoped under `.sut` so GoHighLevel's own styles can't clash.
"""
import base64
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
              'Futures Indicators for NinjaTrader 8 | StartUpTrading',
              "ATR position sizing and trend scanning indicators for NinjaTrader 8, licensed automatically. "
              "Every new tool, Jack's trade room and masterclasses. ${price_monthly}/mo."),
    'welcome': ('welcome.html', 'welcome.html', 'welcome-embed.html',
                'Welcome to StartUpTrading',
                'Your StartUpTrading membership: next steps to activate your indicators.'),
    'setup': ('setup.html', 'setup.html', 'setup-embed.html',
              'Install your StartUpTrading tools',
              'How to download, import and add your StartUpTrading tools to NinjaTrader 8.'),
    'free_tools': ('free-tools.html', 'free-tools.html', 'free-tools-embed.html',
                   'Free Futures Trading Tools & Indicators | StartUpTrading',
                   'Explore free TradingView indicators, NinjaTrader tools, futures position size calculators '
                   'and risk management resources from StartUpTrading.'),
    'tv_atr': ('tradingview-atr-planner.html', 'tradingview-atr-planner.html', 'tradingview-atr-planner-embed.html',
               'Free TradingView Futures Position Size & Risk Indicator',
               'Free TradingView indicator for ATR position sizing, prop firm drawdown planning, micro futures '
               'comparison and visual trade risk management.'),
    'calculator': ('calculator.html', 'calculator.html', 'calculator-embed.html',
                   'Free Futures Position Size Calculator | ES, NQ, MES, MNQ',
                   'Calculate futures contract size, ATR stops and estimated trade risk for ES, NQ, MES and MNQ. '
                   'Free prop firm risk planner. No sign-up required.'),
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
    js = '\n'.join((SRC / f).read_text() for f in ('affiliate.js', 'tracking.js', 'app.js'))
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
    values['nav'] = nav_html(cfg, name)
    values['tool_filters'], values['tool_cards'] = directory_html(cfg)
    values['subscribe'] = subscribe_html(cfg, name)
    values['membership_note'] = membership_note_html(cfg)
    values['community_note'] = community_note_html(cfg, name)
    # Jack's hero portrait is embedded in the page itself (about 28 KB), so it shows
    # with the HTML: no second server, no wait for the licensing app to wake up.
    values['jack_hero_src'] = hero_image_src(cfg)
    # Footer link to the free community, except on members' pages (they're already in).
    values['footer_community'] = (f'<a href="{html.escape(cfg["community_join_url"], quote=True)}" target="_blank" rel="noopener" '
                                  f'data-community-cta="footer">Free Discord community</a>'
                                  if cfg.get('community_join_url') and name not in ('welcome', 'setup') else '')
    values['tv_cta'] = tv_cta_html(cfg)
    values['product_downloads'], values['product_locations'] = product_downloads_html(cfg)
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
    ld = structured_data(name, cfg, body)
    if ld:
        body += '\n<script type="application/ld+json">' + ld + '</script>'
    has_checkout = '<div data-whop-checkout-plan-id=' in body
    loader = f'<script async defer src="{WHOP_LOADER}"></script>\n' if has_checkout else ''
    embed = f'{FONTS}\n<style>\n{css}\n</style>\n{body}\n<script>\n{js}\n</script>\n{loader}'
    full = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            f'<title>{html.escape(title)}</title>\n'
            + (f'<link rel="canonical" href="{html.escape(canonical_url(cfg, name), quote=True)}">\n'
               if canonical_url(cfg, name) else '') +
            f'<meta name="description" content="{html.escape(description.replace("{price_monthly}", cfg["price_monthly"]), quote=True)}">\n'
            + ('<meta name="robots" content="noindex">\n' if name in ('welcome', 'setup') else '') +
            social_meta(cfg, name, title, description) +
            '<meta name="theme-color" content="#07090d">\n'
            '<style>html,body{margin:0;background:#07090d}</style>\n'
            f'</head>\n<body>\n{embed}</body>\n</html>\n')
    return embed, full


def social_meta(cfg, name, title, description):
    """Open Graph / Twitter tags for the indexable pages. On the live site GoHighLevel
    writes these from each page's SEO settings; the values here are the ones to enter."""
    url = canonical_url(cfg, name)
    if not url:
        return ''
    e = lambda v: html.escape(v, quote=True)
    desc = description.replace('{price_monthly}', cfg['price_monthly'])
    tags = [('property', 'og:type', 'website'), ('property', 'og:site_name', 'StartUpTrading'),
            ('property', 'og:url', url), ('property', 'og:title', title), ('property', 'og:description', desc),
            ('name', 'twitter:card', 'summary_large_image' if cfg.get('og_image_url') else 'summary')]
    if cfg.get('og_image_url'):
        tags.append(('property', 'og:image', cfg['og_image_url']))
    return ''.join(f'<meta {a}="{k}" content="{e(v)}">\n' for a, k, v in tags)


def canonical_url(cfg, name):
    """The one URL search engines should index for each page (members-only pages: none)."""
    return {'sales': cfg['site_url'] + '/', 'free_tools': cfg['free_tools_url'], 'tv_atr': cfg['tv_atr_page_url'],
            'calculator': cfg['calculator_url']}.get(name, '')


def breadcrumbs(site, trail):
    items = [{'@type': 'ListItem', 'position': 1, 'name': 'Home', 'item': site + '/'}]
    items += [{'@type': 'ListItem', 'position': i, 'name': n, 'item': u} for i, (n, u) in enumerate(trail, 2)]
    return {'@type': 'BreadcrumbList', 'itemListElement': items}


def _text(fragment):
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', fragment)).split())


def structured_data(name, cfg, body):
    """schema.org JSON-LD that search engines read: the business, the membership
    with its two prices, the FAQ, and the free calculator. Built from the same
    config and copy as the page, so it can't drift from what visitors see."""
    site = cfg['site_url'].rstrip('/')
    org = {'@type': 'Organization', '@id': site + '/#org', 'name': 'StartUpTrading', 'url': site + '/'}
    if cfg.get('youtube_url'):
        org['sameAs'] = [cfg['youtube_url']]
    if name == 'sales':
        offers = [{'@type': 'Offer', 'name': label, 'price': price, 'priceCurrency': 'USD', 'url': site + '/#pricing',
                   'availability': 'https://schema.org/InStock',
                   'priceSpecification': {'@type': 'UnitPriceSpecification', 'price': price, 'priceCurrency': 'USD',
                                          'billingDuration': 1, 'unitCode': unit}}
                  for label, price, unit in (('Monthly membership', cfg['price_monthly'], 'MON'),
                                             ('Annual membership', cfg['price_annual'], 'ANN'))]
        app = {'@type': 'SoftwareApplication', 'name': 'StartUpTrading membership',
               'applicationCategory': 'FinanceApplication', 'operatingSystem': 'Windows (NinjaTrader 8)',
               'description': 'Proprietary NinjaTrader 8 tools (ATR Order Automation and Trend Scanner & Market '
                              'Selector) licensed automatically to the member\'s NinjaTrader account, every new tool as '
                              'it is released, a members-only trade room and masterclasses.',
               'url': site + '/', 'publisher': {'@id': site + '/#org'}, 'offers': offers}
        faq = [{'@type': 'Question', 'name': _text(q), 'acceptedAnswer': {'@type': 'Answer', 'text': _text(a)}}
               for q, a in re.findall(r'<details><summary>(.*?)</summary><p>(.*?)</p></details>', body, re.S)]
        graph = [org, {'@type': 'WebSite', '@id': site + '/#site', 'name': 'StartUpTrading', 'url': site + '/',
                       'publisher': {'@id': site + '/#org'}}, app]
        if faq:
            graph.append({'@type': 'FAQPage', 'mainEntity': faq})
    elif name == 'free_tools':
        reg = load_tools()
        items = []
        for i, t in enumerate(reg['tools'], 1):
            items.append({'@type': 'ListItem', 'position': i, 'url': cfg.get(t['page'], ''), 'name': t['name']})
        graph = [org, {'@type': 'CollectionPage', 'name': 'Free futures trading tools', 'url': cfg['free_tools_url'],
                       'publisher': {'@id': site + '/#org'},
                       'mainEntity': {'@type': 'ItemList', 'itemListElement': items}},
                 breadcrumbs(site, [('Free tools', cfg['free_tools_url'])])]
    elif name == 'tv_atr':
        app = {'@type': 'SoftwareApplication', 'name': 'StartUpTrading Futures Risk Planner',
               'alternateName': 'Futures Position Size Calculator - ATR & Prop Firm Risk',
               'author': {'@type': 'Person', 'name': 'Jack Gleason'},
               'applicationCategory': 'FinanceApplication', 'operatingSystem': 'TradingView',
               'description': 'Free, open-source TradingView indicator for ATR position sizing, prop firm '
                              'drawdown planning, standard-versus-micro futures comparison and visual trade '
                              'risk planning.',
               'url': cfg['tv_atr_page_url'], 'publisher': {'@id': site + '/#org'},
               'offers': {'@type': 'Offer', 'price': '0', 'priceCurrency': 'USD'}}
        if cfg.get('tv_atr_script_url'):
            app['downloadUrl'] = cfg['tv_atr_script_url']
        graph = [org, app, breadcrumbs(site, [('Free tools', cfg['free_tools_url']),
                                              ('Futures Risk Planner for TradingView', cfg['tv_atr_page_url'])])]
    elif name == 'calculator':
        graph = [org, {'@type': 'WebApplication', 'name': 'Futures Position Size Calculator & Prop-Firm Risk Planner',
                       'applicationCategory': 'FinanceApplication', 'operatingSystem': 'Any (web browser)',
                       'url': site + '/futures-position-size-calculator', 'publisher': {'@id': site + '/#org'},
                       'offers': {'@type': 'Offer', 'price': '0', 'priceCurrency': 'USD'}}]
    else:
        return ''
    # </ can't appear inside a <script> block.
    return json.dumps({'@context': 'https://schema.org', '@graph': graph}, separators=(',', ':')).replace('</', '<\\/')


def main():
    cfg = json.loads((HERE / 'site.config.json').read_text())
    DIST.mkdir(exist_ok=True)
    for name, (_, full_name, embed_name, _, _) in PAGES.items():
        embed, full = render(cfg, name)
        (DIST / embed_name).write_text(embed)
        (DIST / full_name).write_text(full)
        print(f'{name}: wrote dist/{full_name} and dist/{embed_name} ({len(embed) // 1024} KB)')
    (DIST / 'affiliate-tracking.html').write_text(affiliate_snippet())
    (DIST / 'site-tracking.html').write_text(site_tracking_snippet(cfg))
    (DIST / 'site-tracking-body.html').write_text(site_tracking_body_snippet(cfg))
    print('tracking: wrote dist/site-tracking.html (GoHighLevel site-wide tracking code; replaces affiliate-tracking.html)')


NAV_HOME_ANCHORS = (('Technology', '#indicators'), ('Free Tools', None), ('Education', None),
                    ('Community', '#room'), ('About Jack', '#jack'))


def membership_open(cfg):
    return str(cfg.get('membership_open', '')).strip().lower() == 'true'


def nav_html(cfg, name):
    """Main navigation. On the sales page, section links are on-page anchors. On
    other pages they point at the sales page, but only once the membership is
    open (membership_open); until then free pages link only to free resources.
    Education goes to /learn when learn_url is set, otherwise to the sales page's
    education section, so there are never links to pages that don't exist."""
    e = lambda v: html.escape(v, quote=True)
    on_sales = name == 'sales'
    sales = '' if on_sales else cfg['sales_page_url']
    show_sales = on_sales or membership_open(cfg)
    links = []
    for label, anchor in NAV_HOME_ANCHORS:
        if label == 'Free Tools':
            links.append((label, cfg['free_tools_url'], ''))
        elif label == 'Education':
            if cfg.get('learn_url'):
                links.append((label, cfg['learn_url'], ''))
            elif show_sales:
                links.append((label, sales + '#room', ''))
        elif show_sales:
            links.append((label, sales + anchor, ''))
    items = ''.join(f'<a href="{e(href)}"{attr}>{label}</a>' for label, href, attr in links)
    if on_sales:
        attr = '' if cfg.get('embed_checkout') else ' data-checkout'
        cta = f'<a class="sut-btn sut-btn-sm" href="{e(cfg["cta_href"])}"{attr} data-member-cta="nav">Become a Member</a>'
    elif show_sales:
        cta = f'<a class="sut-btn sut-btn-sm" href="{e(sales)}#pricing" data-member-cta="nav">Become a Member</a>'
    elif cfg.get('ghl_subscribe_form_url'):
        cta = '<a class="sut-btn sut-btn-sm" href="#subscribe">Get updates</a>'
    else:
        cta = ''
    home = '#top' if on_sales else cfg['site_url'] + '/'
    logo = ('<a class="sut-logo" href="' + e(home) + '" aria-label="StartUpTrading home">'
            '<svg width="20" height="20" viewBox="0 0 22 22" aria-hidden="true"><rect x="2" y="9" width="4" height="9" rx="1" fill="#fa7b39" opacity=".45"/><rect x="3.5" y="6" width="1" height="15" fill="#fa7b39" opacity=".45"/><rect x="9" y="5" width="4" height="10" rx="1" fill="#fa7b39" opacity=".7"/><rect x="10.5" y="2" width="1" height="16" fill="#fa7b39" opacity=".7"/><rect x="16" y="2" width="4" height="11" rx="1" fill="#fa7b39"/><rect x="17.5" y="0" width="1" height="16" fill="#fa7b39"/></svg>'
            'STARTUPTRADING</a>')
    return (f'<header class="sut-nav">\n  <div class="sut-wrap sut-nav-in">\n    {logo}\n'
            f'    <nav class="sut-links" aria-label="Main">{items}</nav>\n    {cta}\n  </div>\n</header>')


def load_tools():
    return json.loads((HERE / 'tools.json').read_text())


def tool_links(cfg, tool):
    page = cfg.get(tool['page'], '')
    ext = cfg.get(tool.get('external_url', ''), '') if tool.get('external_url') else ''
    return page, ext


def directory_html(cfg):
    """Filter buttons and one card per tool, from tools.json."""
    e = lambda v: html.escape(str(v), quote=True)
    reg = load_tools()
    used = {c for t in reg['tools'] for c in t['categories']}
    filters = ''.join(
        f'<button type="button" class="sut-filter" data-filter="{key}" aria-pressed="{"true" if key == "all" else "false"}">'
        f'{e(label)}</button>' for key, label in reg['categories'].items())
    cards = []
    for t in reg['tools']:
        page, ext = tool_links(cfg, t)
        status = 'is-live' if t['status'] == 'available' else 'is-soon'
        extra = ''
        if ext:
            extra = (f' <a class="sut-tool-ext" href="{e(ext)}" target="_blank" rel="noopener" data-outbound="tradingview" '
                     f'data-tool-id="{e(t["id"])}">Open on TradingView ↗</a>')
        cards.append(
            f'<article class="sut-tool" data-categories="{" ".join(t["categories"])}" data-tool-id="{e(t["id"])}">'
            f'<div class="sut-tool-top"><span class="sut-tool-platform">{e(t["platform"])}</span>'
            f'<span class="sut-tool-status {status}">{e(t["status_label"])}</span></div>'
            f'<h3>{e(t["name"])}</h3><p>{e(t["summary"])}</p>'
            f'<div class="sut-tool-actions"><a class="sut-btn sut-btn-ghost" href="{e(page)}">{e(t["cta"])} '
            f'<span class="sut-arrow" aria-hidden="true">→</span></a>{extra}</div></article>')
    empty = ''.join(
        f'<p class="sut-tool-empty" data-empty-for="{key}" hidden>{e(label)} resources are on the way. '
        + ('<a href="#subscribe">Get notified</a> when they land.' if cfg.get('ghl_subscribe_form_url') else 'Check back soon.')
        + '</p>' for key, label in reg['categories'].items() if key != 'all' and key not in used)
    return filters, ''.join(cards) + empty


# The optional sign-up form's interest tag, per page. A new educational page gets
# the form by adding {{subscribe}} to its template and, optionally, a row here
# (pages not listed are tagged "education").
SUBSCRIBE_INTEREST = {'tv_atr': 'tradingview', 'calculator': 'calculators', 'free_tools': 'free-tools'}
GHL_FORM_EMBED_JS = 'https://link.msgsndr.com/js/form_embed.js'


def ghl_form_id(url):
    m = re.search(r'/widget/form/([A-Za-z0-9]+)', url or '')
    return m.group(1) if m else ''


def subscribe_html(cfg, name):
    """Optional email sign-up: the GoHighLevel form, embedded inline. Never required
    to use a tool. Omitted entirely until ghl_subscribe_form_url is set.

    The form carries its own headline and description, so this block adds only a
    short reassurance line. The iframe has no src in the HTML: tracking.js adds the
    page, interest, first/latest touch and affiliate parameters, sets the src once,
    then loads GoHighLevel's form_embed.js (which passes them to the form's hidden
    fields and resizes the iframe). The noscript link keeps it usable without JS."""
    url = cfg.get('ghl_subscribe_form_url', '')
    form_id = ghl_form_id(url)
    if not form_id:
        return ''
    e = lambda v: html.escape(str(v), quote=True)
    interest = SUBSCRIBE_INTEREST.get(name, 'education')
    tool = ''
    m = re.search(r'data-tool-id="([^"]+)"', (SRC / PAGES[name][0]).read_text()) if name in PAGES else None
    if m:
        tool = m.group(1)
    base = url.split('?')[0]
    iframe_id = f'inline-{form_id}'
    return (f'<section class="sut-section sut-alt sut-sub-section" id="subscribe" aria-label="Optional email updates">'
            f'<div class="sut-wrap sut-sub">'
            f'<p class="sut-sub-note"><span class="sut-eyebrow">Optional</span> '
            f'Everything on this page works without an email.</p>'
            f'<div class="sut-sub-frame">'
            f'<iframe class="sut-sub-form" data-ghl-form data-sut-src="{e(base)}" '
            f'data-source-page="{e(name)}" data-interest="{e(interest)}" data-tool-id="{e(tool)}" '
            f'id="{e(iframe_id)}" data-layout="{{\'id\':\'INLINE\'}}" data-trigger-type="alwaysShow" data-trigger-value="" '
            f'data-activation-type="alwaysActivated" data-activation-value="" '
            f'data-deactivation-type="neverDeactivate" data-deactivation-value="" '
            f'data-form-name="Free tools updates" data-height="519" data-layout-iframe-id="{e(iframe_id)}" '
            f'data-form-id="{e(form_id)}" data-cookie-consent="true" data-cookie-consent-provider="auto" '
            f'title="Optional email updates"></iframe>'
            f'<noscript><a class="sut-btn sut-btn-ghost" href="{e(base)}?source_page={e(name)}&amp;interest={e(interest)}" '
            f'target="_blank" rel="noopener">Open the sign-up form</a></noscript>'
            f'</div></div></section>')


def hero_image_src(cfg):
    path = HERE.parent / 'static' / 'brand' / 'jack-hero.webp'
    if path.is_file():
        return 'data:image/webp;base64,' + base64.b64encode(path.read_bytes()).decode()
    return html.escape(cfg.get('jack_hero_url', ''), quote=True)


def community_note_html(cfg, name):
    """The free StartUpTrading Community (Discord) offer on free pages. A separate,
    free Whop product: joining never grants indicator licenses or the paid offer.
    Omitted until community_join_url is set."""
    url = cfg.get('community_join_url', '')
    if not url:
        return ''
    e = lambda v: html.escape(str(v), quote=True)
    return ('<aside class="sut-free sut-community-note"><div class="sut-free-copy">'
            '<p class="sut-eyebrow muted">Free community</p>'
            '<h3>Talk risk with other futures traders.</h3>'
            '<p>Join the free StartUpTrading Discord: help with the free tools, market talk and announcements from Jack. '
            'Members get the live trade room and members-only channels on top.</p>'
            f'<a class="sut-btn sut-btn-ghost" href="{e(url)}" target="_blank" rel="noopener" data-community-cta="{e(name)}">'
            'Join the free Discord <span class="sut-arrow" aria-hidden="true">↗</span></a>'
            '<p class="sut-fine">Free, through Whop.</p></div></aside>')


def membership_note_html(cfg):
    """Secondary membership introduction on free pages: a link only once the
    membership is open; until then, an optional 'get notified'."""
    e = lambda v: html.escape(str(v), quote=True)
    head = ('<p class="sut-eyebrow muted">Trade on NinjaTrader?</p>'
            '<h3>The membership does this for you.</h3>'
            '<p>ATR Order Automation sets the position size and places the stop and target in NinjaTrader 8 as you enter, '
            'alongside the Trend Scanner &amp; Market Selector, Jack\'s trade room and masterclasses. Every new tool is included.</p>')
    if membership_open(cfg):
        link = (f'<a class="sut-btn sut-btn-ghost" href="{e(cfg["sales_page_url"])}" data-member-cta="free_page">'
                f'See the membership <span class="sut-arrow" aria-hidden="true">→</span></a>')
    elif cfg.get('ghl_subscribe_form_url'):
        link = '<a class="sut-btn sut-btn-ghost" href="#subscribe">Get notified when it opens</a>'
    else:
        link = '<p class="sut-fine">Opening soon.</p>'
    return f'<aside class="sut-free sut-member-note"><div class="sut-free-copy">{head}{link}</div></aside>'


def load_products():
    """The membership's products: ../products.json, shared with the licensing app."""
    return json.loads((HERE.parent / 'products.json').read_text())['products']


def product_downloads_html(cfg):
    """/setup: one download button per product (its download_url in products.json,
    hosted outside GitHub), and where each appears in NinjaTrader."""
    e = lambda v: html.escape(str(v), quote=True)
    items, where = [], []
    for p in load_products():
        url = p.get('download_url', '')
        if url:
            action = (f'<a class="sut-btn" href="{e(url)}" download '
                      f'data-download="{e(p["file"])}">Download {e(p["name"])} <span class="sut-arrow" aria-hidden="true">↓</span></a>')
        else:
            action = (f'<div class="sut-ph sut-ph-text"><strong>Download link goes here</strong>'
                      f'<small>Set download_url for this product in products.json.</small></div>')
        items.append(f'<li><b>{e(p["name"])}</b><span>{e(p["file"])}</span>{action}</li>')
        menu, _, folder = p['ninjatrader_location'].partition(', ')
        where.append(f'<li><b>{e(p["name"])}</b>: right-click the chart, choose <b>{e(menu)}…</b>, open the '
                     f'<b>{e(folder.replace(" folder", ""))}</b> folder and add <b>{e(p["ninjatrader_name"])}</b>.</li>')
    return (f'<ul class="sut-downloads">{"".join(items)}</ul>', f'<ul class="sut-list-plain">{"".join(where)}</ul>')


def tv_cta_html(cfg):
    """The TradingView button: a real link once the script is published, a
    clear 'coming soon' (never a dead link) until then."""
    e = lambda v: html.escape(str(v), quote=True)
    if cfg.get('tv_atr_script_url'):
        return (f'<a class="sut-btn sut-btn-lg" href="{e(cfg["tv_atr_script_url"])}" target="_blank" rel="noopener" '
                f'data-outbound="tradingview" data-tool-id="atr-position-size-planner">Open on TradingView ↗</a>')
    return ('<span class="sut-btn sut-btn-lg sut-btn-disabled" aria-disabled="true">Coming soon to TradingView</span>'
            f'<a class="sut-btn sut-btn-ghost sut-btn-lg" href="{e(cfg["calculator_url"])}">Use the web calculator now</a>')


def site_tracking_snippet(cfg=None):
    """Site-wide GoHighLevel tracking code (Settings -> Tracking code -> Header):
    Google Tag Manager with Consent Mode defaults (../static/gtm.js, shared with the
    activation app), then affiliate capture and attribution/analytics events
    (src/affiliate.js + tracking.js). GTM is loaded here ONLY, never by page embeds,
    so each page view is counted once."""
    cfg = cfg if cfg is not None else json.loads((HERE / 'site.config.json').read_text())
    gtm = cfg.get('gtm_container_id', '')
    head = ''
    if re.fullmatch(r'GTM-[A-Z0-9]{4,12}', gtm or ''):
        head = ('<!-- Google Tag Manager with Consent Mode v2 defaults (static/gtm.js) -->\n<script>\n'
                f"window.SUT_GTM_ID = '{gtm}';\n" + (HERE.parent / 'static' / 'gtm.js').read_text() + '</script>\n')
    return (head + '<!-- StartUpTrading: affiliate attribution + analytics (sales-site/src/affiliate.js, tracking.js) -->\n'
            '<script>\n' + (SRC / 'affiliate.js').read_text() + '\n' + (SRC / 'tracking.js').read_text() + '</script>\n')


def site_tracking_body_snippet(cfg=None):
    """GTM's <noscript> fallback for GoHighLevel's body / footer tracking code."""
    cfg = cfg if cfg is not None else json.loads((HERE / 'site.config.json').read_text())
    gtm = cfg.get('gtm_container_id', '')
    if not re.fullmatch(r'GTM-[A-Z0-9]{4,12}', gtm or ''):
        return ''
    return ('<!-- Google Tag Manager (noscript) -->\n<noscript><iframe src="https://www.googletagmanager.com/ns.html?id='
            f'{gtm}" height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>\n')


def affiliate_snippet():
    """Paste into GoHighLevel → Settings → Tracking code (header), site-wide, so an
    affiliate's ?a= is captured on ANY startuptrading.com page, not just the homepage."""
    return ('<!-- StartUpTrading: Whop affiliate attribution (sales-site/src/affiliate.js) -->\n'
            '<script>\n' + (SRC / 'affiliate.js').read_text() + '</script>\n')


if __name__ == '__main__':
    main()
