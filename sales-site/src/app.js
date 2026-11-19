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
  var year = document.querySelector('.sut [data-year]');
  if (year) year.textContent = new Date().getFullYear();
})();
