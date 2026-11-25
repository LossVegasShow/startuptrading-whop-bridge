/* Attribution and analytics events for startuptrading.com.
   Pushes events to window.dataLayer, so Google Tag Manager / GA4 (added through
   GoHighLevel's tracking code) can turn them into reports. Nothing here sends data
   anywhere by itself, sets cookies, or reads personal data.

   Events
     sut_attribution   once per page: first-touch and last-touch source (UTMs, referrer)
     free_tool_view    a free tool's page was opened         {tool_id}
     tool_use          a free tool was used (first input)     {tool_id}
     outbound_click    a TradingView script link was clicked  {destination, tool_id}
     email_subscribe   the optional sign-up form was submitted (GHL redirect ?subscribed=1)
     checkout_intent   a Become a Member / Join button was clicked {placement}
     checkout_view     the on-page Whop checkout scrolled into view
     sut_purchase      the /welcome page loaded after checkout (sent by app.js)
   Every event carries first_touch / last_touch so sales can be traced to a source. */
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
/*end-track-core*/

(function () {
  var w = window, d = document;
  w.dataLayer = w.dataLayer || [];
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
  w.SUT_TRACK = push;
  push('sut_attribution');

  var ready = function () {
    // Free tool page views and first use.
    var root = d.querySelector('.sut[data-tool-id]');
    if (root) {
      var tool = root.getAttribute('data-tool-id');
      push('free_tool_view', { tool_id: tool });
      var used = false;
      var forms = root.querySelectorAll('[data-tool-use]');
      for (var i = 0; i < forms.length; i++) {
        forms[i].addEventListener('input', function () {
          if (!used) { used = true; push('tool_use', { tool_id: tool }); }
        });
      }
    }
    // Outbound TradingView clicks, and Become a Member / Join clicks.
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
    // The embedded checkout coming into view.
    var checkout = d.getElementById('checkout');
    if (checkout && w.IntersectionObserver) {
      var seen = false;
      new IntersectionObserver(function (entries, obs) {
        if (!seen && entries.some(function (e) { return e.isIntersecting; })) {
          seen = true; push('checkout_view'); obs.disconnect();
        }
      }, { threshold: 0.4 }).observe(checkout);
    }
    // Optional sign-up: GoHighLevel redirects back with ?subscribed=1.
    if (new URLSearchParams(w.location.search).get('subscribed') === '1') {
      push('email_subscribe', { source_page: (d.querySelector('.sut') || {}).getAttribute ? d.querySelector('.sut').getAttribute('data-page') : '' });
    }
    // Pass the source to the sign-up form so the CRM records it (GHL hidden fields).
    var frames = d.querySelectorAll('iframe[data-ghl-form]');
    for (var f = 0; f < frames.length; f++) {
      try {
        var src = new URL(frames[f].src);
        var t = attr.first || {};
        SUT_UTM_KEYS.forEach(function (k) { if (t[k] && !src.searchParams.has(k)) src.searchParams.set(k, t[k]); });
        if (w.SUT_AFFILIATE) src.searchParams.set('affiliate', w.SUT_AFFILIATE);
        frames[f].src = src.toString();
      } catch (e) { /* keep the static src */ }
    }
  };
  if (d.readyState === 'loading') d.addEventListener('DOMContentLoaded', ready); else ready();
})();
