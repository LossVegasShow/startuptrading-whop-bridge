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
