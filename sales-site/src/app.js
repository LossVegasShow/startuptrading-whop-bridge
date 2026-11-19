(function () {
  // Forward UTM tags (and Whop's ?a= affiliate code) from this page's URL to
  // every checkout link, so Whop can attribute the sale to the campaign.
  var keep = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'a'];
  var here = new URLSearchParams(window.location.search);
  var links = document.querySelectorAll('.sut a[data-checkout]');
  for (var i = 0; i < links.length; i++) {
    try {
      var url = new URL(links[i].href);
      keep.forEach(function (k) {
        if (here.has(k) && !url.searchParams.has(k)) url.searchParams.set(k, here.get(k));
      });
      links[i].href = url.toString();
    } catch (e) { /* leave the link as it is */ }
  }
  // Embedded Whop checkout: pass a Whop affiliate code (?a=) through. UTM tags
  // are forwarded by Whop's loader itself. Runs before the async loader mounts.
  var embeds = document.querySelectorAll('.sut [data-whop-checkout-plan-id]');
  for (var j = 0; j < embeds.length; j++) {
    if (here.get('a')) embeds[j].setAttribute('data-whop-checkout-affiliate-code', here.get('a'));
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

  var year = document.querySelector('.sut [data-year]');
  if (year) year.textContent = new Date().getFullYear();
})();
