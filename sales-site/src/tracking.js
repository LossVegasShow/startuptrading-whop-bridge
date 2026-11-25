/* Attribution and analytics events for startuptrading.com.
   Pushes events to window.dataLayer, so Google Tag Manager / GA4 (added through
   GoHighLevel's tracking code) can turn them into reports. Nothing here sends data
   anywhere by itself, sets cookies, or reads personal data.

   Events
     sut_attribution   once per page: first-touch and last-touch source (UTMs, referrer)
     free_tool_view    a free tool's page was opened         {tool_id}
     tool_use          a free tool was used (first input)     {tool_id}
     outbound_click    a TradingView script link was clicked  {destination, tool_id}
     email_subscribe   the optional GoHighLevel sign-up form was submitted successfully
                       (GHL's own success message from the form, not a button click)
                       {source_page, interest, tool_id, form_id}
     checkout_intent   a Become a Member / Join button was clicked {placement}
     checkout_view     the on-page Whop checkout scrolled into view
     sut_purchase      the /welcome page loaded after checkout (sent by app.js)
   Every event carries first_touch / last_touch so sales can be traced to a source.

   This file can be on a page twice (the site-wide header code and a page embed).
   Every event and listener is guarded, so each fires once per page whichever copy
   runs first. */
/*track-core*/
var SUT_ATTR_KEY = 'sut_attr';
var SUT_UTM_KEYS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content'];

// Where did this visit come from? UTMs win; otherwise an external referrer's host; otherwise direct.
function sutTouch(search, referrer, ownHost, now) {
  var q = new URLSearchParams(search || '');
  var t = { at: now };
  var hasUtm = false;
  SUT_UTM_KEYS.forEach(function (k) {
    var v = (q.get(k) || '').slice(0, 100);
    if (v) { t[k] = v; hasUtm = true; }
  });
  if (!hasUtm) {
    var host = '';
    try { host = referrer ? new URL(referrer).hostname.replace(/^www\./, '') : ''; } catch (e) { host = ''; }
    var own = String(ownHost || '').replace(/^www\./, '');
    if (!host || host === own || host.slice(-(own.length + 1)) === '.' + own) return null;   // internal or direct
    t.utm_source = host; t.utm_medium = 'referral';
  }
  return t;
}

// Keep the first touch forever (well, until storage is cleared) and update the last touch.
function sutAttribution(stored, touch) {
  var o = null;
  try { o = JSON.parse(stored || 'null'); } catch (e) { o = null; }
  if (!o || typeof o !== 'object') o = {};
  if (touch) {
    if (!o.first) o.first = touch;
    o.last = touch;
  }
  return o;
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
  var first = (attr && attr.first) || {}, last = (attr && attr.last) || {};
  SUT_FORM_UTM.forEach(function (k) {
    p['first_' + k] = first[k] || '';
    p['last_' + k] = last[k] || '';
  });
  var out = {};
  for (var k in p) if (p[k]) out[k] = String(p[k]).slice(0, 100);
  return out;
}

// Is this window message GoHighLevel's "lead collected" notice for one of our
// form iframes? The form posts it once, after the submission succeeds:
// ["set-sticky-contacts", "embedded_iframe_<iframe id>", "<iframe id>", locationId, fingerprint]
function sutFormSubmitted(data, iframeId) {
  return Object.prototype.toString.call(data) === '[object Array]' && data[0] === 'set-sticky-contacts' &&
    !!iframeId && data[1] === 'embedded_iframe_' + iframeId;
}
/*end-track-core*/

(function () {
  var w = window, d = document;
  w.dataLayer = w.dataLayer || [];
  // Shared across both copies of this file on a page: what has already happened.
  var once = w.__sutOnce = w.__sutOnce || {};
  var first = function (key) { if (once[key]) return false; once[key] = true; return true; };
  var stored = null;
  try { stored = w.localStorage.getItem(SUT_ATTR_KEY); } catch (e) { /* storage blocked */ }
  var attr = sutAttribution(stored, sutTouch(w.location.search, d.referrer, w.location.hostname, Date.now()));
  try { w.localStorage.setItem(SUT_ATTR_KEY, JSON.stringify(attr)); } catch (e) { /* this page only */ }
  var base = { first_touch: attr.first || null, last_touch: attr.last || null, affiliate: w.SUT_AFFILIATE || '' };
  var push = function (event, data) {
    var o = { event: event };
    for (var k in base) o[k] = base[k];
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
      }, true);
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
  };
  if (d.readyState === 'loading') d.addEventListener('DOMContentLoaded', ready); else ready();
})();
