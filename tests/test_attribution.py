"""Browser attribution (sales-site/src/tracking.js, track-core), run in Node.

Scenarios from the attribution spec: first touch preserved, latest touch = most
recent qualifying external source, our own journey (GoHighLevel, Whop, payment
pages, our domains) never overwrites it, direct vs unknown, UTMs over referrers,
click IDs, affiliates, the channel taxonomy and the hand-off to the activation app."""
import pytest

from test_free_tools import node_eval

H = "'startuptrading.com'"


def touch(tmp_path, search='', referrer=''):
    return node_eval(tmp_path, f"sutTouch({search!r}, {referrer!r}, {H}, 5, '/futures-position-size-calculator')")


@pytest.mark.parametrize('search,referrer,source,medium,channel', [
    ('?utm_source=instagram&utm_medium=social&utm_campaign=risk_lab', '', 'instagram', 'social', 'instagram'),
    ('?utm_source=youtube&utm_medium=video&utm_campaign=jack_reacts&utm_content=short25', '', 'youtube', 'video', 'youtube'),
    ('?utm_source=YouTube&utm_medium=Social', '', 'youtube', 'social', 'youtube'),
    ('?utm_source=tradingview&utm_medium=social', '', 'tradingview', 'social', 'tradingview'),
    ('?utm_source=google&utm_medium=cpc&utm_campaign=brand', '', 'google', 'cpc', 'google_paid'),
    ('?utm_source=newsletter&utm_medium=email', '', 'newsletter', 'email', 'email'),
    ('?utm_source=partner&utm_medium=affiliate', '', 'partner', 'affiliate', 'affiliate'),
    ('?utm_source=x&utm_medium=social', '', 'x', 'social', 'x_twitter'),
    ('?gclid=abc', '', 'google', 'cpc', 'google_paid'),
    ('?ttclid=abc', '', 'tiktok', 'paid_social', 'tiktok'),
    ('?a=jackaff', '', 'affiliate', 'affiliate', 'affiliate'),
    ('', 'https://www.google.com/', 'google', 'organic', 'google_organic'),
    ('', 'https://www.google.co.uk/', 'google', 'organic', 'google_organic'),
    ('', 'https://chatgpt.com/', 'chatgpt', 'referral', 'ai_referral'),
    ('', 'https://www.perplexity.ai/search', 'perplexity', 'referral', 'ai_referral'),
    ('', 'https://gemini.google.com/app', 'gemini', 'referral', 'ai_referral'),
    ('', 'https://www.tradingview.com/script/ZBt4abLo/', 'tradingview', 'referral', 'tradingview'),
    ('', 'https://in.tradingview.com/', 'tradingview', 'referral', 'tradingview'),
    ('', 'https://l.instagram.com/', 'instagram', 'referral', 'instagram'),
    ('', 'https://m.facebook.com/', 'facebook', 'referral', 'facebook'),
    ('', 'https://www.youtube.com/watch?v=1', 'youtube', 'referral', 'youtube'),
    ('', 'https://t.co/abc', 'x', 'referral', 'x_twitter'),
    ('', 'https://discord.com/channels/1', 'discord', 'referral', 'discord'),
    ('', 'https://old.reddit.com/r/FuturesTrading', 'reddit', 'referral', 'reddit'),
    ('', 'https://mail.google.com/', 'gmail', 'referral', 'email'),
    ('', 'https://nexusfi.com/thread', 'nexusfi.com', 'referral', 'other_referral'),
    # UTMs win over the referrer (an Instagram link opened from Google's app, etc.).
    ('?utm_source=instagram&utm_medium=social', 'https://www.google.com/', 'instagram', 'social', 'instagram'),
])
def test_sources_and_channels(tmp_path, search, referrer, source, medium, channel):
    t = touch(tmp_path, search, referrer)
    assert (t['utm_source'], t['utm_medium'], t['channel']) == (source, medium, channel)
    assert t['landing'] == '/futures-position-size-calculator'


@pytest.mark.parametrize('referrer', [
    'https://app.gohighlevel.com/v2/location/x/funnels', 'https://api.leadconnectorhq.com/widget/form/x',
    'https://link.msgsndr.com/x', 'https://whop.com/checkout/plan_x', 'https://checkout.stripe.com/c/pay',
    'https://www.paypal.com/checkoutnow', 'https://startuptrading.com/free-tools',
    'https://www.startuptrading.com/', 'https://activate.startuptrading.com/onboarding',
])
def test_our_own_journey_is_never_a_source(tmp_path, referrer):
    assert touch(tmp_path, '', referrer) is None


def test_the_reported_contamination_is_fixed(tmp_path):
    """The real contact: first chatgpt.com, last app.gohighlevel.com (stored by the old script)."""
    stored = ("{first:{at:1,utm_source:'chatgpt.com',utm_medium:'referral'},"
              "last:{at:2,utm_source:'app.gohighlevel.com',utm_medium:'referral'}}")
    a = node_eval(tmp_path, f"sutAttribution(JSON.stringify({stored}), sutTouch('', 'https://app.gohighlevel.com/', {H}, 3), {H}, 3)")
    assert a['first']['utm_source'] == 'chatgpt.com' and a['first']['channel'] == 'ai_referral'
    assert 'last' not in a or a['last'] is None
    p = node_eval(tmp_path, f"sutFormParams(sutAttribution(JSON.stringify({stored}), null, {H}, 3), '', {{source_page:'calculator'}})")
    # Latest falls back to the first touch, never to GoHighLevel.
    assert p['last_utm_source'] == 'chatgpt.com' and p['last_channel'] == 'ai_referral'


def test_journey_first_preserved_latest_external_only(tmp_path):
    a = node_eval(tmp_path, f"""(function () {{
      var s = null, o;
      [['?utm_source=youtube&utm_medium=social', ''],          // 1. YouTube link
       ['', ''],                                                // 2. returns directly
       ['', 'https://startuptrading.com/free-tools'],           // 3. internal navigation
       ['', 'https://api.leadconnectorhq.com/widget/form/x'],   // 4. embedded form
       ['', 'https://whop.com/checkout/plan_x'],                // 5. back from checkout
       ['', 'https://www.tradingview.com/u/Jack_Gleason/']      // 6. TradingView profile
      ].forEach(function (v, i) {{ o = sutAttribution(s, sutTouch(v[0], v[1], {H}, i), {H}, i); s = JSON.stringify(o); }});
      return o; }})()""")
    assert a['first']['channel'] == 'youtube' and a['last']['channel'] == 'tradingview'


def test_direct_and_unknown_are_distinct(tmp_path):
    direct = node_eval(tmp_path, f"sutAttribution(null, sutTouch('', '', {H}, 1), {H}, 1)")
    assert direct['first']['channel'] == 'direct' and 'last' not in direct
    unknown = node_eval(tmp_path, f"sutAttribution(null, sutTouch('', 'https://app.gohighlevel.com/', {H}, 1), {H}, 1)")
    assert unknown['first'] == {'at': 1, 'utm_source': '(unknown)', 'utm_medium': '(none)', 'channel': 'unknown'}
    # A later real source becomes the latest touch, the first stays unknown (not fabricated).
    later = node_eval(tmp_path, f"sutAttribution(JSON.stringify(sutAttribution(null, null, {H}, 1)), sutTouch('?utm_source=instagram&utm_medium=social', '', {H}, 2), {H}, 2)")
    assert later['first']['channel'] == 'unknown' and later['last']['channel'] == 'instagram'


def test_returning_direct_visit_keeps_latest_source(tmp_path):
    a = node_eval(tmp_path, f"""sutAttribution(JSON.stringify(sutAttribution(null, sutTouch('', 'https://www.google.com/', {H}, 1), {H}, 1)),
                                sutTouch('', '', {H}, 9), {H}, 9)""")
    assert a['first']['channel'] == 'google_organic' and a['last']['channel'] == 'google_organic'


def test_form_and_handoff_params(tmp_path):
    attr = f"sutAttribution(JSON.stringify(sutAttribution(null, sutTouch('?utm_source=youtube&utm_medium=social&utm_campaign=jack_reacts', '', {H}, 1, '/free-tools'), {H}, 1)), sutTouch('', 'https://chatgpt.com/', {H}, 2), {H}, 2)"
    form = node_eval(tmp_path, f"sutFormParams({attr}, 'jackaff', {{source_page:'calculator', interest:'calculators', tool_id:'x'}})")
    assert form['first_channel'] == 'youtube' and form['first_utm_campaign'] == 'jack_reacts'
    assert form['last_channel'] == 'ai_referral' and form['affiliate'] == 'jackaff'
    hand = node_eval(tmp_path, f"sutHandoff({attr}, 'jackaff', 'a1b2c3d4e5f6a1b2c3d4e5f6')")
    assert hand == {'sut_fs': 'youtube', 'sut_fm': 'social', 'sut_fc': 'jack_reacts', 'sut_fch': 'youtube',
                    'sut_fl': '/free-tools', 'sut_ft': '1', 'sut_ls': 'chatgpt', 'sut_lm': 'referral',
                    'sut_lch': 'ai_referral', 'sut_aff': 'jackaff', 'sut_vid': 'a1b2c3d4e5f6a1b2c3d4e5f6'}
    # Nothing personal: only marketing keys and the random visitor id.
    assert not any('@' in str(v) for v in hand.values())
