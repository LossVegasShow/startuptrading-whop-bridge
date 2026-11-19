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
    _, embed, full = rendered()
    assert (SITE / 'dist' / 'ghl-embed.html').read_text() == embed, 'run: python sales-site/build.py'
    assert (SITE / 'dist' / 'index.html').read_text() == full, 'run: python sales-site/build.py'


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
        assert f'data-whop-checkout-return-url="{cfg["activation_url"]}"' in attrs
    # Page-wide Join buttons scroll to the checkout; fallback links still go to Whop.
    assert embed.count('href="#checkout"') >= 3 and 'id="checkout"' in embed
    assert_links_match_plans(cfg, checkout_links(embed))


def test_hosted_checkout_mode_when_embed_disabled():
    cfg = json.loads((SITE / 'site.config.json').read_text())
    cfg['embed_checkout'] = 'false'
    embed, _ = load_build().render(cfg)
    assert '<div data-whop-checkout-plan-id=' not in embed and 'js.whop.com' not in embed
    assert '#checkout' not in embed
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
