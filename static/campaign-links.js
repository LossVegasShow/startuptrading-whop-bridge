/* Campaign link generator (/admin/campaign-links). Mirrors the channel rules in
   sales-site/src/tracking.js (sutChannel). No data leaves the page. */
(function () {
  var form = document.getElementById('mk-links');
  if (!form) return;
  var CH = { youtube: 'YouTube', instagram: 'Instagram', tiktok: 'TikTok', facebook: 'Facebook', x: 'X / Twitter',
    tradingview: 'TradingView', discord: 'Discord', reddit: 'Reddit' };
  var clean = function (v) { return String(v || '').trim().toLowerCase().replace(/[^a-z0-9_-]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 60); };
  function channel(src, med) {
    if (med === 'affiliate') return 'Affiliate referrals';
    if (med === 'email') return 'Email campaigns';
    if (src === 'google') return med === 'cpc' ? 'Google paid advertising' : 'Google organic search';
    if (CH[src]) return CH[src] + (med === 'paid_social' ? ' (paid)' : '');
    return 'Other referrals';
  }
  function update() {
    var f = form.elements, parts = f.placement.value.split('|'), src = parts[0], med = parts[1];
    form.querySelector('.mk-custom').hidden = f.dest.value !== 'custom';
    form.querySelector('.mk-aff').hidden = med !== 'affiliate';
    var out = document.getElementById('mk-url'), msg = document.getElementById('mk-msg');
    var base = f.dest.value === 'custom' ? f.custom.value.trim() : f.dest.value;
    var camp = clean(f.campaign.value), content = clean(f.content.value), aff = String(f.aff.value || '').trim();
    msg.textContent = '';
    document.getElementById('mk-channel').textContent = channel(src, med);
    var url;
    try { url = new URL(base); } catch (e) { out.value = ''; msg.textContent = 'Enter a full https://startuptrading.com/… address.'; return; }
    if (!/(^|\.)startuptrading\.com$/.test(url.hostname)) { out.value = ''; msg.textContent = 'Links must point to startuptrading.com.'; return; }
    if (!camp) { out.value = ''; msg.textContent = 'Add a campaign name.'; return; }
    if (med === 'affiliate' && !/^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/.test(aff)) { out.value = ''; msg.textContent = 'Add the affiliate\'s Whop username.'; return; }
    url.searchParams.set('utm_source', med === 'affiliate' ? 'affiliate' : src);
    url.searchParams.set('utm_medium', med);
    url.searchParams.set('utm_campaign', camp);
    if (content) url.searchParams.set('utm_content', content); else url.searchParams.delete('utm_content');
    if (med === 'affiliate') url.searchParams.set('a', aff); else url.searchParams.delete('a');
    out.value = url.toString();
  }
  form.addEventListener('input', update);
  form.addEventListener('change', update);
  document.getElementById('mk-copy').addEventListener('click', function () {
    var v = document.getElementById('mk-url').value;
    if (!v) return;
    (navigator.clipboard ? navigator.clipboard.writeText(v) : Promise.reject()).then(function () {
      document.getElementById('mk-msg').textContent = 'Copied.';
    }, function () { document.getElementById('mk-url').select(); });
  });
  update();
})();
