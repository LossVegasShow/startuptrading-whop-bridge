/* Attribution and analytics events for startuptrading.com.
   Pushes events to window.dataLayer for Google Tag Manager / GA4. Nothing here
   sends data anywhere by itself, sets cookies, or reads personal data.
   Full specification: growth/MARKETING_ANALYTICS.md (taxonomy, events, GA4 mapping).

   Attribution (browser storage, key sut_attr): first touch = first visit ever
   recorded (a source, "(direct)" or "(unknown)"); latest touch = most recent
   EXTERNAL source. Our own journey (our domains, GoHighLevel, Whop, payment and
   sign-in pages) never counts as a source. Each touch has a channel (sutChannel).
   A random anonymous visitor id (sut_vid) lets the activation app tie a Whop
   membership to its acquisition (links to activate.* carry sutHandoff). If a
   consent banner declines analytics storage, call sutConsent('denied').

   Events: sut_attribution, free_tool_view, tool_use, calculation_complete,
   free_tool_select, outbound_click, email_subscribe (successful submissions only),
   checkout_intent, checkout_view, file_download, community_join_click, community_join;
   checkout_return comes from app.js.
   Every event carries first_channel / last_channel / first_touch / last_touch.

   This file can be on a page twice (the site-wide header code and a page embed).
   Every event and listener is guarded, so each fires once per page whichever copy
   runs first. */
/*track-core*/
var SUT_ATTR_KEY = 'sut_attr';
var SUT_VID_KEY = 'sut_vid';
var SUT_UTM_KEYS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content'];

// Referrers that are part of our own journey, never an acquisition source:
// GoHighLevel (site builder, forms, CRM links), Whop (checkout, hub), payment pages,
// sign-in pages, and our own domain and subdomains (activate.startuptrading.com).
var SUT_IGNORED_REFERRERS = ['gohighlevel.com', 'leadconnectorhq.com', 'msgsndr.com', 'whop.com',
  'stripe.com', 'paypal.com', 'accounts.google.com', 'appleid.apple.com'];

// Known hosts -> canonical source. Checked by suffix, most specific first.
var SUT_SOURCES = [
  ['gemini.google.com', 'gemini'], ['bard.google.com', 'gemini'], ['mail.google.com', 'gmail'],
  ['chatgpt.com', 'chatgpt'], ['chat.openai.com', 'chatgpt'], ['openai.com', 'chatgpt'],
  ['perplexity.ai', 'perplexity'], ['claude.ai', 'claude'], ['copilot.microsoft.com', 'copilot'],
  ['you.com', 'you.com'], ['phind.com', 'phind'],
  ['youtube.com', 'youtube'], ['youtu.be', 'youtube'],
  ['instagram.com', 'instagram'], ['facebook.com', 'facebook'], ['fb.com', 'facebook'], ['fb.me', 'facebook'],
  ['messenger.com', 'facebook'], ['tiktok.com', 'tiktok'], ['discord.com', 'discord'], ['discord.gg', 'discord'],
  ['discordapp.com', 'discord'], ['reddit.com', 'reddit'], ['t.co', 'x'], ['x.com', 'x'], ['twitter.com', 'x'],
  ['tradingview.com', 'tradingview'], ['outlook.live.com', 'outlook'], ['mail.yahoo.com', 'yahoo_mail'],
  ['bing.com', 'bing'], ['duckduckgo.com', 'duckduckgo'], ['search.yahoo.com', 'yahoo']
];
var SUT_AI = ['chatgpt', 'perplexity', 'claude', 'gemini', 'copilot', 'you.com', 'phind'];
var SUT_SOCIAL_CHANNEL = { youtube: 'youtube', instagram: 'instagram', facebook: 'facebook', tiktok: 'tiktok',
  discord: 'discord', reddit: 'reddit', x: 'x_twitter', twitter: 'x_twitter', tradingview: 'tradingview' };
var SUT_PAID_MEDIUMS = ['cpc', 'ppc', 'paid', 'paidsearch', 'paid_search', 'paidsocial', 'paid_social', 'display', 'cpm', 'cpv', 'ads'];

function sutHostMatch(host, domain) {
  return host === domain || host.slice(-(domain.length + 1)) === '.' + domain;
}

// Canonical source for a referrer host or a utm_source value.
function sutSourceName(v) {
  var x = String(v || '').toLowerCase().trim().replace(/^www\./, '');
  for (var i = 0; i < SUT_SOURCES.length; i++) {
    if (sutHostMatch(x, SUT_SOURCES[i][0]) || x === SUT_SOURCES[i][1]) return SUT_SOURCES[i][1];
  }
  if (/^(www\.)?google\.[a-z.]+$/.test(x) || x === 'google') return 'google';
  if (x === 'ig') return 'instagram';
  if (x === 'fb') return 'facebook';
  if (x === 'yt') return 'youtube';
  if (x === 'twitter') return 'x';
  return x;
}

// The acquisition channel (StartUpTrading taxonomy; see growth/MARKETING_ANALYTICS.md).
function sutChannel(t) {
  if (!t) return 'unknown';
  var src = sutSourceName(t.utm_source), med = String(t.utm_medium || '').toLowerCase();
  if (t.direct) return 'direct';
  if (src === '(unknown)') return 'unknown';
  if (med === 'affiliate' || src === 'affiliate') return 'affiliate';
  if (med === 'email' || src === 'gmail' || src === 'outlook' || src === 'yahoo_mail' || src === 'newsletter') return 'email';
  if (SUT_AI.indexOf(src) >= 0) return 'ai_referral';
  var paid = !!t.paid || SUT_PAID_MEDIUMS.indexOf(med) >= 0;
  if (src === 'google') return paid ? 'google_paid' : (med === 'organic' || med === 'referral' || !med ? 'google_organic' : 'other_referral');
  if (SUT_SOCIAL_CHANNEL[src]) return SUT_SOCIAL_CHANNEL[src];
  return 'other_referral';
}

function sutIgnoredHost(host, ownHost) {
  var own = String(ownHost || '').replace(/^www\./, '');
  if (own && sutHostMatch(host, own)) return true;
  for (var i = 0; i < SUT_IGNORED_REFERRERS.length; i++) if (sutHostMatch(host, SUT_IGNORED_REFERRERS[i])) return true;
  return false;
}

// Where did this visit come from?
//   UTMs win; then ad click IDs; then an affiliate link (?a=); then an outside referrer.
//   No referrer and nothing in the URL: a direct visit ({direct: true}).
//   A referrer from our own journey (our domains, GoHighLevel, Whop, payment pages): null,
//   so it never replaces a real source.
function sutTouch(search, referrer, ownHost, now, path) {
  var q = new URLSearchParams(search || '');
  var t = { at: now };
  if (path) t.landing = String(path).slice(0, 120);
  var hasUtm = false;
  SUT_UTM_KEYS.forEach(function (k) {
    var v = (q.get(k) || '').slice(0, 100);
    if (v) { t[k] = v; hasUtm = true; }
  });
  var gclid = q.get('gclid') || q.get('gbraid') || q.get('wbraid');
  if (gclid || q.get('msclkid') || q.get('ttclid')) t.paid = true;
  if (!hasUtm) {
    if (gclid) { t.utm_source = 'google'; t.utm_medium = 'cpc'; }
    else if (q.get('msclkid')) { t.utm_source = 'bing'; t.utm_medium = 'cpc'; }
    else if (q.get('ttclid')) { t.utm_source = 'tiktok'; t.utm_medium = 'paid_social'; }
    else if (q.get('fbclid') && !referrer) { t.utm_source = 'facebook'; t.utm_medium = 'social'; }
  }
  var aff = q.get('a');
  if (!t.utm_source && aff && /^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/.test(aff)) {
    t.utm_source = 'affiliate'; t.utm_medium = 'affiliate'; t.utm_campaign = aff;
  }
  if (!t.utm_source) {
    var host = '';
    try { host = referrer ? new URL(referrer).hostname.toLowerCase().replace(/^www\./, '') : ''; } catch (e) { host = ''; }
    if (!referrer) { t.direct = true; t.utm_source = '(direct)'; t.utm_medium = '(none)'; }
    else if (!host || sutIgnoredHost(host, ownHost)) return null;
    else {
      t.utm_source = sutSourceName(host);
      t.utm_medium = t.utm_source === 'google' || t.utm_source === 'bing' || t.utm_source === 'duckduckgo' || t.utm_source === 'yahoo' ? 'organic' : 'referral';
      if (t.utm_source !== host) t.referrer_host = host.slice(0, 100);
    }
  } else {
    t.utm_source = String(t.utm_source).toLowerCase();
    if (t.utm_medium) t.utm_medium = String(t.utm_medium).toLowerCase();
  }
  t.channel = sutChannel(t);
  return t;
}

// A stored touch recorded by an older version: drop it if it came from our own
// journey (for example app.gohighlevel.com), and fill in its channel.
function sutCleanTouch(t, ownHost) {
  if (!t || typeof t !== 'object') return null;
  var src = String(t.utm_source || '').toLowerCase();
  if (String(t.utm_medium || '') === 'referral' && src.indexOf('.') > 0 && sutIgnoredHost(src, ownHost)) return null;
  if (!t.channel) t.channel = sutChannel(t);
  return t;
}

// First touch: the first visit ever recorded in this browser (a real source, a
// direct visit, or "unknown" when the first visit came through our own journey).
// Latest touch: the most recent qualifying EXTERNAL source. Direct visits and our
// own journey never replace it; if there has never been one it stays empty.
function sutAttribution(stored, touch, ownHost, now) {
  var o = null;
  try { o = JSON.parse(stored || 'null'); } catch (e) { o = null; }
  if (!o || typeof o !== 'object') o = {};
  o.first = sutCleanTouch(o.first, ownHost) || undefined;
  o.last = sutCleanTouch(o.last, ownHost) || undefined;
  if (o.last && o.last.direct) o.last = undefined;
  if (touch) {
    if (!o.first) o.first = touch;
    if (!touch.direct) o.last = touch;
  } else if (!o.first) {
    o.first = { at: now || 0, utm_source: '(unknown)', utm_medium: '(none)', channel: 'unknown' };
  }
  return o;
}

// GA4's client id from its _ga cookie ("GA1.1.<random>.<timestamp>"), or ''.
// Lets the licensing app send verified server events (purchase, activation) to
// the same GA4 user. Not personal data: a random number GA itself creates.
function sutGaClientId(cookie) {
  var m = /(?:^|;\s*)_ga=GA\d\.\d\.(\d{4,12}\.\d{6,12})(?:;|$)/.exec(cookie || '');
  return m ? m[1] : '';
}

// The latest qualifying touch, falling back to the first (which may be direct or unknown).
function sutLatest(attr) {
  return (attr && (attr.last || attr.first)) || null;
}
// The sign-up form's query parameters (= the form's hidden-field query keys).
// First and latest touch use their own keys, so GoHighLevel's built-in
// attribution (from the page URL's own utm_*) is left untouched.
var SUT_FORM_UTM = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content'];
function sutFormParams(attr, affiliate, page) {
  var p = {
    source_page: page.source_page || '',
    interest: page.interest || '',
    tool_id: page.tool_id || '',
    affiliate: affiliate || ''
  };
  var first = (attr && attr.first) || {}, last = sutLatest(attr) || {};
  SUT_FORM_UTM.forEach(function (k) {
    p['first_' + k] = first[k] || '';
    p['last_' + k] = last[k] || '';
  });
  p.first_channel = first.channel || '';
  p.last_channel = last.channel || '';
  var out = {};
  for (var k in p) if (p[k]) out[k] = String(p[k]).slice(0, 100);
  return out;
}

// Attribution handed to the activation app (activate.<site>) on links from our pages,
// so a Whop membership can be tied to how its buyer found us. Short keys, no
// personal data: the anonymous visitor id, first and latest touch, landing page,
// affiliate code.
function sutHandoff(attr, affiliate, vid, gcid) {
  var first = (attr && attr.first) || {}, last = sutLatest(attr) || {};
  var map = { fs: first.utm_source, fm: first.utm_medium, fc: first.utm_campaign, fx: first.utm_content,
    fch: first.channel, fl: first.landing, ft: first.at ? String(first.at) : '',
    ls: last.utm_source, lm: last.utm_medium, lc: last.utm_campaign, lx: last.utm_content, lch: last.channel,
    aff: affiliate, vid: vid, gcid: gcid };
  var out = {};
  for (var k in map) if (map[k]) out['sut_' + k] = String(map[k]).slice(0, 120);
  return out;
}

// Is this window message GoHighLevel's "lead collected" notice for one of our
// form iframes? The form posts it once, after the submission succeeds:
// ["set-sticky-contacts", "embedded_iframe_<iframe id>", "<iframe id>", locationId, fingerprint]
function sutFormSubmitted(data, iframeId) {
  return Object.prototype.toString.call(data) === '[object Array]' && data[0] === 'set-sticky-contacts' &&
    !!iframeId && data[1] === 'embedded_iframe_' + iframeId;
}

// GoHighLevel resizes its form iframe with iframe-resizer: the form posts
// "[iFrameSizer]<iframe id>:<height>:<width>:<event>" whenever its content changes
// (load, validation messages, the thank-you message). Returns that height, or null.
var SUT_FORM_PAD = 24;   // GHL measures the form's body without its top margin (10px on desktop)
function sutSizerHeight(data, iframeId) {
  if (typeof data !== 'string' || !iframeId) return null;
  var prefix = '[iFrameSizer]' + iframeId + ':';
  if (data.indexOf(prefix) !== 0) return null;
  var h = parseFloat(data.slice(prefix.length).split(':')[0]);
  return h > 0 && h < 20000 ? h : null;
}
/*end-track-core*/

(function () {
  var w = window, d = document;
  w.dataLayer = w.dataLayer || [];
  // Shared across both copies of this file on a page: what has already happened.
  var once = w.__sutOnce = w.__sutOnce || {};
  var first = function (key) { if (once[key]) return false; once[key] = true; return true; };
  // Consent: if a consent banner (or window.SUT_CONSENT = 'denied') declines
  // analytics storage, attribution is kept for this page only and nothing is stored.
  // sutConsent('granted' | 'denied') is the hook a consent banner calls.
  var store = function () {
    var c = w.SUT_CONSENT;
    try { c = c || w.localStorage.getItem('sut_consent'); } catch (e) { return null; }
    return c === 'denied' ? null : w.localStorage;
  };
  w.sutConsent = function (state) {
    var v = state === 'denied' ? 'denied' : 'granted';
    if (typeof w.gtag === 'function') w.gtag('consent', 'update', { analytics_storage: v });
    try {
      w.localStorage.setItem('sut_consent', state === 'denied' ? 'denied' : 'granted');
      if (state === 'denied') { w.localStorage.removeItem(SUT_ATTR_KEY); w.localStorage.removeItem(SUT_VID_KEY); }
    } catch (e) { /* storage blocked */ }
  };
  var ls = null, stored = null, vid = '';
  try { ls = store(); stored = ls && ls.getItem(SUT_ATTR_KEY); vid = (ls && ls.getItem(SUT_VID_KEY)) || ''; } catch (e) { ls = null; }
  var now = Date.now();
  var attr = sutAttribution(stored, sutTouch(w.location.search, d.referrer, w.location.hostname, now, w.location.pathname),
    w.location.hostname, now);
  if (!ls) attr.storage = 'unavailable';
  if (!/^[a-f0-9]{16,32}$/.test(vid)) {
    vid = '';
    try {
      var b = new Uint8Array(12); w.crypto.getRandomValues(b);
      for (var i = 0; i < b.length; i++) vid += ('0' + b[i].toString(16)).slice(-2);
    } catch (e) { vid = ''; }
  }
  try { if (ls) { ls.setItem(SUT_ATTR_KEY, JSON.stringify(attr)); if (vid) ls.setItem(SUT_VID_KEY, vid); } } catch (e) { /* this page only */ }
  w.SUT_VISITOR = ls ? vid : '';
  var base = { first_touch: attr.first || null, last_touch: sutLatest(attr), first_channel: (attr.first || {}).channel || 'unknown',
    last_channel: (sutLatest(attr) || {}).channel || 'unknown', affiliate: w.SUT_AFFILIATE || '' };
  // Event-specific parameters. GTM's data model keeps the last value of every key,
  // so each event explicitly clears the ones it doesn't set (no leftovers such as a
  // previous event's calculator on tool_use).
  var EVENT_KEYS = ['tool_id', 'calculator', 'source_page', 'interest', 'form_id', 'placement', 'destination',
    'file_name', 'file_extension', 'link_url', 'group_id'];
  var push = function (event, data) {
    var o = { event: event };
    for (var k in base) o[k] = base[k];
    for (var i = 0; i < EVENT_KEYS.length; i++) o[EVENT_KEYS[i]] = undefined;
    for (var j in (data || {})) o[j] = data[j];
    w.dataLayer.push(o);
  };
  if (!w.SUT_TRACK) w.SUT_TRACK = push;
  if (first('attribution')) push('sut_attribution');

  // The optional GoHighLevel sign-up form: add the attribution parameters, load it once,
  // and count a sign-up only when the form reports a successful submission.
  var wireForms = function () {
    var frames = d.querySelectorAll('iframe[data-ghl-form][data-sut-src]');
    var any = false;
    for (var f = 0; f < frames.length; f++) {
      var fr = frames[f];
      if (fr.getAttribute('data-sut-wired')) continue;
      fr.setAttribute('data-sut-wired', '1');
      any = true;
      start(fr);
    }
    if (any && first('ghl_form_listener')) listen();
  };
  // Load a form only when the reader scrolls near it, so the free tools above it load first.
  var start = function (fr) {
    if (!w.IntersectionObserver) return load(fr);
    var io = new IntersectionObserver(function (entries) {
      if (entries.some(function (e) { return e.isIntersecting; })) { io.disconnect(); load(fr); }
    }, { rootMargin: '800px 0px' });
    io.observe(fr.parentNode || fr);
  };
  var load = function (fr) {
    try {
      var src = new URL(fr.getAttribute('data-sut-src'));
      var params = sutFormParams(attr, w.SUT_AFFILIATE, {
        source_page: fr.getAttribute('data-source-page'),
        interest: fr.getAttribute('data-interest'),
        tool_id: fr.getAttribute('data-tool-id')
      });
      for (var k in params) src.searchParams.set(k, params[k]);
      fr.src = src.toString();
    } catch (e) { fr.src = fr.getAttribute('data-sut-src'); }
    if (first('ghl_form_embed') && !d.querySelector('script[src*="/js/form_embed.js"]')) {
      var sc = d.createElement('script');
      sc.src = 'https://link.msgsndr.com/js/form_embed.js';
      sc.async = true;
      d.body.appendChild(sc);
    }
  };
  var listen = function () {
    w.addEventListener('message', function (ev) {
      var frs = d.querySelectorAll('iframe[data-ghl-form]');
      for (var i = 0; i < frs.length; i++) {
        // Only our own form iframe, and only its success message.
        if (ev.source !== frs[i].contentWindow || !sutFormSubmitted(ev.data, frs[i].id)) continue;
        // One event per form per page view, however many messages arrive.
        if (first('email_subscribe:' + frs[i].id)) {
          push('email_subscribe', {
            source_page: frs[i].getAttribute('data-source-page') || '',
            interest: frs[i].getAttribute('data-interest') || '',
            tool_id: frs[i].getAttribute('data-tool-id') || '',
            form_id: frs[i].getAttribute('data-form-id') || ''
          });
        }
        return;
      }
    });
  };

  // Fit each form to its content using GoHighLevel's own height reports, plus a
  // margin for what its measurement leaves out, so the form never scrolls inside.
  // Guarded on its own, so it runs even when an older copy of this file wired the form.
  var fitForms = function () {
    var frames = d.querySelectorAll('iframe[data-ghl-form]');
    for (var f = 0; f < frames.length; f++) {
      var fr = frames[f];
      if (fr.getAttribute('data-sut-fit')) continue;
      fr.setAttribute('data-sut-fit', '1');
      // GoHighLevel's resizer rewrites style.height on every report; re-apply ours after it.
      if (w.MutationObserver) {
        new MutationObserver((function (el) {
          return function () { applyFit(el); };
        })(fr)).observe(fr, { attributes: true, attributeFilter: ['style'] });
      }
    }
    if (frames.length && first('ghl_form_fit')) {
      w.addEventListener('message', function (ev) {
        var frs = d.querySelectorAll('iframe[data-ghl-form]');
        for (var i = 0; i < frs.length; i++) {
          if (ev.source !== frs[i].contentWindow) continue;
          var h = sutSizerHeight(ev.data, frs[i].id);
          if (h === null) return;
          frs[i].setAttribute('data-sut-height', String(h));
          // Sized: drop the space reserved while loading, so a short thank-you message fits too.
          frs[i].setAttribute('data-sut-sized', '1');
          var el = frs[i];
          applyFit(el);
          setTimeout(function () { applyFit(el); }, 0);
          return;
        }
      });
    }
  };
  var applyFit = function (fr) {
    var h = parseFloat(fr.getAttribute('data-sut-height'));
    if (!(h > 0)) return;
    var want = Math.ceil(h + SUT_FORM_PAD) + 'px';
    if (fr.style.height !== want) fr.style.height = want;
  };

  var ready = function () {
    // Free tool page views and first use.
    var root = d.querySelector('.sut[data-tool-id]');
    if (root) {
      var tool = root.getAttribute('data-tool-id');
      if (first('free_tool_view:' + tool)) push('free_tool_view', { tool_id: tool });
      var forms = root.querySelectorAll('[data-tool-use]');
      for (var i = 0; i < forms.length; i++) {
        if (forms[i].getAttribute('data-sut-use-bound')) continue;
        forms[i].setAttribute('data-sut-use-bound', '1');
        forms[i].addEventListener('input', function () {
          if (first('tool_use:' + tool)) push('tool_use', { tool_id: tool });
        });
      }
    }
    // Outbound TradingView clicks, and Become a Member / Join clicks.
    if (first('click_listener')) {
      d.addEventListener('click', function (ev) {
        var a = ev.target.closest ? ev.target.closest('a') : null;
        if (!a) return;
        if (a.hasAttribute('data-outbound')) {
          push('outbound_click', { destination: a.getAttribute('data-outbound'), tool_id: a.getAttribute('data-tool-id') || '' });
        }
        if (a.hasAttribute('data-member-cta')) {
          push('checkout_intent', { placement: a.getAttribute('data-member-cta') });
        }
        // A tool chosen from the free tools directory.
        var card = a.closest('article[data-tool-id]');
        if (card && !a.hasAttribute('data-outbound')) push('free_tool_select', { tool_id: card.getAttribute('data-tool-id') });
        // The free community (Discord) offer clicked.
        if (a.hasAttribute('data-community-cta')) {
          push('community_join_click', { placement: a.getAttribute('data-community-cta') });
        }
        // A product file download started (GA4's recommended file_download event).
        if (a.hasAttribute('data-download')) {
          var file = a.getAttribute('data-download');
          push('file_download', { file_name: file, file_extension: file.split('.').pop(), link_url: a.href });
        }
      }, true);
      // A calculator produced a result (sent by the calculator page), once per calculator.
      d.addEventListener('sut:calculated', function (ev) {
        var calc = (ev.detail && ev.detail.calculator) || 'calculator';
        if (first('calculation_complete:' + calc)) push('calculation_complete', { tool_id: (root && root.getAttribute('data-tool-id')) || '', calculator: calc });
      });
    }
    // Links to the activation app carry the anonymous attribution (see sutHandoff).
    var handoff = sutHandoff(attr, w.SUT_AFFILIATE, w.SUT_VISITOR, sutGaClientId(d.cookie));
    var acts = d.querySelectorAll('a[href]');
    for (var h = 0; h < acts.length; h++) {
      try {
        var u = new URL(acts[h].href);
        var own = w.location.hostname.replace(/^www\./, '');
        if (u.hostname !== 'activate.' + own || u.searchParams.has('sut_fs') || acts[h].getAttribute('data-sut-handoff')) continue;
        for (var key in handoff) u.searchParams.set(key, handoff[key]);
        acts[h].href = u.toString();
        acts[h].setAttribute('data-sut-handoff', '1');
      } catch (e) { /* leave the link as it is */ }
    }
    // The embedded checkout coming into view.
    var checkout = d.getElementById('checkout');
    if (checkout && w.IntersectionObserver && first('checkout_observer')) {
      var seen = false;
      new IntersectionObserver(function (entries, obs) {
        if (!seen && entries.some(function (e) { return e.isIntersecting; })) {
          seen = true; push('checkout_view'); obs.disconnect();
        }
      }, { threshold: 0.4 }).observe(checkout);
    }
    wireForms();
    fitForms();
    // Back from joining the free community: Whop redirects to a page with
    // ?community=joined. Counted once per browser (reloads and shared links don't
    // repeat it); the verified count comes from Whop in the licensing app.
    if (new URLSearchParams(w.location.search).get('community') === 'joined' && first('community_join')) {
      var already = false;
      try { already = !!(ls && ls.getItem('sut_community_joined')); if (ls) ls.setItem('sut_community_joined', '1'); } catch (e) { /* storage blocked */ }
      if (!already) push('community_join', { group_id: 'startuptrading_community' });
    }
  };
  if (d.readyState === 'loading') d.addEventListener('DOMContentLoaded', ready); else ready();
})();
