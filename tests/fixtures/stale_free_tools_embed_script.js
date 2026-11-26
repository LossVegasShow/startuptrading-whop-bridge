/* Captured from the live /free-tools page on 2026-11-26: the pre-channel
   tracking.js (plus affiliate.js and app.js) that caused undefined
   first_channel / last_channel in GTM. Regression fixture only. */

/* Whop affiliate attribution.
   Affiliates share startuptrading.com/join?a=THEIR_CODE (or any startuptrading.com
   page with ?a=). The code is remembered in this browser for AFF_DAYS, most recent
   affiliate wins, and is passed to both embedded Whop checkouts (monthly and annual)
   and to any Whop checkout or /join link on the page. It never changes the
   checkout's return URL, plan or price. Used by the sales pages and, standalone,
   as GoHighLevel's site-wide tracking code (dist/affiliate-tracking.html). */
/*aff-core*/
var SUT_AFF_KEY = 'sut_aff';
var SUT_AFF_DAYS = 30;

// Whop affiliate codes are usernames: letters, digits, dot, dash, underscore.
function sutAffClean(v) {
  v = String(v == null ? '' : v).trim();
  return /^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/.test(v) ? v : '';
}

// Decide the code for this visit. `search` is location.search, `stored` the saved
// JSON (or null). Returns {code, save}: save is the JSON to store, or null.
function sutAffPick(search, stored, now) {
  var fromUrl = sutAffClean(new URLSearchParams(search || '').get('a'));
  if (fromUrl) {
    return { code: fromUrl, save: JSON.stringify({ code: fromUrl, exp: now + SUT_AFF_DAYS * 86400000 }) };
  }
  try {
    var o = JSON.parse(stored || 'null');
    var kept = o && o.exp > now ? sutAffClean(o.code) : '';
    return { code: kept, save: null };
  } catch (e) {
    return { code: '', save: null };
  }
}

// Add ?a=CODE to Whop checkout links and to links to the /join page, unless the
// link already names an affiliate. Other links are returned unchanged.
function sutAffDecorate(href, code, siteHost) {
  if (!code) return href;
  try {
    var url = new URL(href);
    var host = url.hostname.replace(/^www\./, '');
    var site = String(siteHost || '').replace(/^www\./, '');
    var whop = host === 'whop.com' && (/^\/checkout\//.test(url.pathname) || /^\/startuptrading\/?/i.test(url.pathname));
    var join = host === site && /^\/join\/?$/.test(url.pathname);
    if (!(whop || join) || url.searchParams.has('a')) return href;
    url.searchParams.set('a', code);
    return url.toString();
  } catch (e) {
    return href;
  }
}
/*end-aff-core*/

(function () {
  var stored = null;
  try { stored = window.localStorage.getItem(SUT_AFF_KEY); } catch (e) { /* storage blocked */ }
  var pick = sutAffPick(window.location.search, stored, Date.now());
  if (pick.save) { try { window.localStorage.setItem(SUT_AFF_KEY, pick.save); } catch (e) { /* this visit only */ } }
  window.SUT_AFFILIATE = pick.code;
  if (!pick.code) return;
  var decorate = function () {
    var links = document.querySelectorAll('a[href]');
    for (var i = 0; i < links.length; i++) {
      var next = sutAffDecorate(links[i].href, pick.code, window.location.hostname);
      if (next !== links[i].href) links[i].href = next;
    }
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', decorate);
  else decorate();
})();

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

(function () {
  // Forward UTM tags from this page's URL to every checkout link, so Whop can
  // attribute the sale to the campaign. The affiliate code comes from
  // affiliate.js (this visit's ?a=, or the one remembered from an earlier visit).
  var keep = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content'];
  var here = new URLSearchParams(window.location.search);
  var aff = window.SUT_AFFILIATE || '';
  var links = document.querySelectorAll('.sut a[data-checkout]');
  for (var i = 0; i < links.length; i++) {
    try {
      var url = new URL(links[i].href);
      keep.forEach(function (k) {
        if (here.has(k) && !url.searchParams.has(k)) url.searchParams.set(k, here.get(k));
      });
      if (aff && !url.searchParams.has('a')) url.searchParams.set('a', aff);
      links[i].href = url.toString();
    } catch (e) { /* leave the link as it is */ }
  }
  // Embedded Whop checkout: pass the affiliate code to EVERY mount (monthly and
  // annual), so the sale is attributed whichever plan is chosen. UTM tags are
  // forwarded by Whop's loader itself. Runs before the async loader mounts.
  // Only adds this attribute: plan, theme and return URL are left as they are.
  var embeds = document.querySelectorAll('.sut [data-whop-checkout-plan-id]');
  for (var j = 0; j < embeds.length; j++) {
    if (aff) embeds[j].setAttribute('data-whop-checkout-affiliate-code', aff);
    (function (box) {
      // Hide the "Loading…" note once Whop's iframe has loaded.
      var wrap = box.parentNode;
      var mark = function () { wrap.classList.add('is-loaded'); };
      if (!window.MutationObserver) return;
      new MutationObserver(function (_, obs) {
        var frame = box.querySelector('iframe');
        if (frame) { frame.addEventListener('load', mark); obs.disconnect(); }
      }).observe(box, { childList: true });
    })(embeds[j]);
  }

  // Thank-you page: tell any tag manager on the page that a purchase finished,
  // once per browser session (GTM can map 'sut_purchase' to Meta/Google tags).
  if (document.querySelector('.sut[data-page="welcome"]')) {
    try {
      if (!sessionStorage.getItem('sut_purchase_sent')) {
        window.dataLayer = window.dataLayer || [];
        window.dataLayer.push({ event: 'sut_purchase' });
        sessionStorage.setItem('sut_purchase_sent', '1');
      }
    } catch (e) { /* storage blocked: skip */ }
  }

  // Free-indicator links: keep the visitor's original campaign (e.g. YouTube)
  // when there is one; the placement tag (utm_content) always says which spot.
  var free = document.querySelectorAll('.sut a[data-free]');
  for (var f = 0; f < free.length; f++) {
    try {
      var furl = new URL(free[f].href);
      ['utm_source', 'utm_medium', 'utm_campaign'].forEach(function (k) {
        if (here.get(k)) furl.searchParams.set(k, here.get(k));
      });
      free[f].href = furl.toString();
    } catch (e) { /* keep the static link */ }
  }

  // Exit-intent offer: desktop only, after 8s on the page, at most once a week,
  // and never for someone who clicked Join or started the checkout.
  var exitBox = document.getElementById('sut-exit');
  if (exitBox && window.matchMedia && window.matchMedia('(pointer: fine) and (min-width: 900px)').matches) {
    var store = {
      get: function () { try { return Number(localStorage.getItem('sut_exit_seen') || 0); } catch (e) { return 0; } },
      set: function () { try { localStorage.setItem('sut_exit_seen', String(Date.now())); } catch (e) {} }
    };
    var armed = false, committed = false, lastFocus = null;
    setTimeout(function () { armed = true; }, 8000);
    document.addEventListener('click', function (ev) {
      var t = ev.target.closest && ev.target.closest('a');
      if (t && (t.hasAttribute('data-checkout') || t.getAttribute('href') === '#checkout')) committed = true;
    });
    var checkoutBox = document.getElementById('checkout');
    if (checkoutBox) checkoutBox.addEventListener('pointerdown', function () { committed = true; });
    var close = function () {
      exitBox.hidden = true;
      document.removeEventListener('keydown', onKey);
      if (lastFocus && lastFocus.focus) lastFocus.focus();
    };
    var onKey = function (ev) {
      if (ev.key === 'Escape') close();
      if (ev.key === 'Tab') {            // keep focus inside the dialog
        var items = exitBox.querySelectorAll('a, button');
        var first = items[0], last = items[items.length - 1];
        if (ev.shiftKey && document.activeElement === first) { ev.preventDefault(); last.focus(); }
        else if (!ev.shiftKey && document.activeElement === last) { ev.preventDefault(); first.focus(); }
      }
    };
    var closers = exitBox.querySelectorAll('[data-exit-close]');
    for (var c = 0; c < closers.length; c++) closers[c].addEventListener('click', close);
    document.addEventListener('mouseout', function (ev) {
      if (!armed || committed || !exitBox.hidden || ev.relatedTarget || ev.clientY > 0) return;
      if (Date.now() - store.get() < 7 * 24 * 3600 * 1000) return;
      store.set();
      lastFocus = document.activeElement;
      exitBox.hidden = false;
      document.addEventListener('keydown', onKey);
      var cta = exitBox.querySelector('a[data-free]');
      if (cta) cta.focus();
    });
  }

  var year = document.querySelector('.sut [data-year]');
  if (year) year.textContent = new Date().getFullYear();

  // Free tools directory: category filters (all cards stay visible without JS).
  var filterBar = document.querySelector('.sut .sut-filters');
  if (filterBar) {
    filterBar.hidden = false;
    var cards = document.querySelectorAll('.sut .sut-tool');
    var empties = document.querySelectorAll('.sut [data-empty-for]');
    filterBar.addEventListener('click', function (ev) {
      var btn = ev.target.closest('[data-filter]');
      if (!btn) return;
      var key = btn.getAttribute('data-filter');
      var shown = 0;
      Array.prototype.forEach.call(filterBar.querySelectorAll('[data-filter]'), function (b) {
        b.setAttribute('aria-pressed', b === btn ? 'true' : 'false');
      });
      Array.prototype.forEach.call(cards, function (c) {
        var hit = key === 'all' || (' ' + c.getAttribute('data-categories') + ' ').indexOf(' ' + key + ' ') >= 0;
        c.hidden = !hit; if (hit) shown++;
      });
      Array.prototype.forEach.call(empties, function (p) { p.hidden = !(shown === 0 && p.getAttribute('data-empty-for') === key); });
    });
  }
})();

