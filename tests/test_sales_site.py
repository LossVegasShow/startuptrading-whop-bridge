"""Sales page build checks: committed dist matches source, links and CSS scoping are correct."""
import importlib.util
import json
import re
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / 'sales-site'


def load_build():
    spec = importlib.util.spec_from_file_location('sales_build', SITE / 'build.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def rendered():
    cfg = json.loads((SITE / 'site.config.json').read_text())
    return cfg, *load_build().render(cfg)


def test_committed_dist_is_up_to_date():
    cfg = json.loads((SITE / 'site.config.json').read_text())
    build = load_build()
    for name, (_, full_name, embed_name, _, _) in build.PAGES.items():
        embed, full = build.render(cfg, name)
        assert (SITE / 'dist' / embed_name).read_text() == embed, f'{name}: run python sales-site/build.py'
        assert (SITE / 'dist' / full_name).read_text() == full, f'{name}: run python sales-site/build.py'


def test_no_unfilled_template_tokens():
    _, embed, full = rendered()
    assert '{{' not in embed and '<!--if:' not in embed and '<!--endif:' not in embed


def checkout_links(embed):
    return re.findall(r'<a[^>]*data-checkout[^>]*>', embed)


def assert_links_match_plans(cfg, links):
    annual = [t for t in links if 'data-plan="annual"' in t]
    assert len(annual) == 1
    for tag in links:
        expected = cfg['checkout_url_annual'] if tag in annual else cfg['checkout_url']
        assert f'href="{expected}"' in tag, tag


def test_checkout_urls_are_whop_plans():
    cfg, _, _ = rendered()
    for key in ('checkout_url', 'checkout_url_annual'):
        assert cfg[key].startswith('https://whop.com/checkout/plan_'), key
    assert cfg['checkout_url'] != cfg['checkout_url_annual']


def test_embedded_checkout_mode():
    cfg, embed, _ = rendered()
    assert cfg['embed_checkout'] == 'true'
    build = load_build()
    # Loader script from Whop, loaded once, after the page's own script.
    assert embed.count(build.WHOP_LOADER) == 1
    assert embed.index('<script>') < embed.index(build.WHOP_LOADER)
    # One embed per plan, dark theme, returning buyers to the activation page.
    mounts = re.findall(r'<div data-whop-checkout-plan-id="([^"]+)"([^>]*)>', embed)
    assert [m[0] for m in mounts] == [re.search(r'plan_\w+', cfg['checkout_url']).group(0),
                                      re.search(r'plan_\w+', cfg['checkout_url_annual']).group(0)]
    for _, attrs in mounts:
        assert 'data-whop-checkout-theme="dark"' in attrs
        assert f'data-whop-checkout-return-url="{cfg["thank_you_url"]}"' in attrs
    # Page-wide Join buttons scroll to the checkout; fallback links still go to Whop.
    assert embed.count('href="#checkout"') >= 3 and 'id="checkout"' in embed
    assert_links_match_plans(cfg, checkout_links(embed))


def test_hosted_checkout_mode_when_embed_disabled():
    cfg = json.loads((SITE / 'site.config.json').read_text())
    cfg['embed_checkout'] = 'false'
    embed, _ = load_build().render(cfg)
    assert '<div data-whop-checkout-plan-id=' not in embed and 'js.whop.com' not in embed
    assert 'href="#checkout"' not in embed
    links = checkout_links(embed)
    assert len(links) >= 5
    assert_links_match_plans(cfg, links)


def test_annual_numbers_are_consistent():
    cfg, embed, _ = rendered()
    monthly, annual = float(cfg['price_monthly']), float(cfg['price_annual'])
    assert f'{annual / 12:.2f}' == cfg['price_annual_per_month']
    assert str(round((1 - annual / (monthly * 12)) * 100)) == cfg['annual_savings_pct']
    # Plan IDs must be the ones the licensing bridge accepts.
    import sys
    sys.path.insert(0, str(SITE.parent))
    from config import PLANS
    for key in ('checkout_url', 'checkout_url_annual'):
        plan = re.search(r'(plan_[A-Za-z0-9]+)', cfg[key]).group(1)
        assert plan in PLANS, (key, plan)


def test_billing_toggle_is_css_only():
    _, embed, _ = rendered()
    assert 'id="sut-bill-m" checked' in embed and 'id="sut-bill-y"' in embed
    assert embed.count('class="sut-amount sut-y"') == 1 and embed.count('class="sut-amount sut-m"') == 1


def test_embed_is_a_fragment_for_ghl():
    _, embed, _ = rendered()
    for pattern in (r'<html[\s>]', r'<head[\s>]', r'<body[\s>]', r'<!doctype'):
        assert not re.search(pattern, embed, re.I), pattern


def test_css_is_scoped_under_sut():
    css = (SITE / 'src' / 'styles.css').read_text()
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    css = re.sub(r'@keyframes[^{]+\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}', '', css)
    for block in re.findall(r'([^{}]+)\{', css):
        block = re.sub(r'\([^()]*\)', '()', block)  # commas inside :where(...) aren't separators
        for selector in block.split(','):
            s = selector.strip()
            if not s or s.startswith('@') or s.startswith(('from', 'to', '50%')):
                continue
            assert s.startswith('.sut'), f'unscoped selector: {s}'


def test_no_fabricated_social_proof():
    # Quotes and numbers about results must come from real members, not the template.
    page = (SITE / 'src' / 'page.html').read_text().lower()
    for phrase in ('profit', '% win', 'win rate', 'made $', 'members trust', '5-star', 'guarantee'):
        assert phrase not in page, phrase


def welcome():
    cfg = json.loads((SITE / 'site.config.json').read_text())
    return cfg, *load_build().render(cfg, 'welcome')


def test_thank_you_url_is_the_ghl_welcome_page():
    cfg, _, _ = welcome()
    assert cfg['thank_you_url'] == 'https://startuptrading.com/welcome'


def test_welcome_page_points_to_activation_and_sells_nothing():
    cfg, embed, full = welcome()
    assert '{{' not in embed and '<!--if' not in embed and '<!--include' not in embed
    assert re.search(r'<a class="sut-btn sut-btn-lg" href="' + re.escape(cfg['activation_url']) + '"', embed)
    assert embed.count(f'href="{cfg["activation_url"]}"') >= 3
    # No checkout, no Join buttons, no Whop loader on the thank-you page.
    assert 'data-checkout' not in re.sub(r'<script>.*?</script>', '', embed, flags=re.S)
    assert '<div data-whop-checkout-plan-id=' not in embed and 'js.whop.com' not in embed
    assert not re.search(r'>\s*Join (StartUpTrading|for|monthly|annually|·)', embed)
    # Shared legal footer, and kept out of search results.
    assert 'Risk disclosure' in embed
    assert '<meta name="robots" content="noindex">' in full
    assert 'sut_purchase' in embed


def test_sales_page_is_indexable_and_shares_footer():
    _, embed, full = rendered()
    assert 'noindex' not in full and 'Risk disclosure' in embed


def test_not_ready_free_offer():
    cfg, embed, _ = rendered()
    build = load_build()
    links = re.findall(r'<a[^>]*href="([^"]+)"[^>]*data-free="(\w+)"', embed)
    assert {place for _, place in links} == set(build.FREE_PLACEMENTS)
    for href, place in links:
        href = href.replace('&amp;', '&')
        assert href.startswith(cfg['free_indicator_url'] + '?')
        assert 'utm_medium=sales_page' in href and 'utm_campaign=not_ready' in href
        assert f'utm_content={place}' in href
    # The paid offer stays the main action: free links are never the primary button
    # in the hero or the nav.
    hero = embed.split('class="sut-strip"')[0]
    assert 'data-free' not in hero
    assert 'Free' in embed and 'Membership' in embed       # comparison table


def test_exit_offer_is_accessible_and_switchable():
    cfg, embed, _ = rendered()
    assert 'role="dialog" aria-modal="true"' in embed and 'id="sut-exit" hidden' in embed
    assert 'data-exit-close aria-label="Close"' in embed
    cfg = dict(cfg, exit_offer='false')
    off, _ = load_build().render(cfg)
    assert 'id="sut-exit"' not in off and 'data-free="pricing"' in off   # offer stays, popup goes
    cfg = dict(cfg, free_indicator_url='')
    none, _ = load_build().render(cfg)
    assert 'data-free' not in none.split('<script>')[0] and 'id="sut-exit"' not in none
