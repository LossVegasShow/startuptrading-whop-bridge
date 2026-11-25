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
