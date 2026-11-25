/* Google Tag Manager loader with Consent Mode v2 defaults (StartUpTrading).
   One copy of this logic runs on every page that loads GTM:
     - startuptrading.com: inlined in the site-wide header code (sales-site/dist/site-tracking.html)
     - activate.startuptrading.com: /static/gtm.js on customer pages (never on /admin)
   Consent defaults: analytics allowed except in the EEA, UK and Switzerland, where it
   waits for a consent banner; ad storage and ad personalisation are always denied.
   A banner (or sutConsent() in tracking.js) updates analytics_storage. */
(function (w, d) {
  if (w.__sutGtmLoaded) return;
  var cur = d.currentScript;
  var id = w.SUT_GTM_ID || (cur && cur.getAttribute('data-gtm')) || '';
  if (!/^GTM-[A-Z0-9]{4,12}$/.test(id)) return;
  w.__sutGtmLoaded = true;
  w.dataLayer = w.dataLayer || [];
  function gtag() { w.dataLayer.push(arguments); }
  w.gtag = w.gtag || gtag;
  gtag('consent', 'default', { ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied',
    analytics_storage: 'granted', functionality_storage: 'granted', security_storage: 'granted', wait_for_update: 500 });
  gtag('consent', 'default', { analytics_storage: 'denied', region: ['AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE',
    'FI', 'FR', 'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE',
    'IS', 'LI', 'NO', 'GB', 'CH'] });
  gtag('set', 'ads_data_redaction', true);
  var saved = null;
  try { saved = w.localStorage.getItem('sut_consent'); } catch (e) { /* storage blocked */ }
  if (saved === 'granted' || saved === 'denied') gtag('consent', 'update', { analytics_storage: saved });
  w.dataLayer.push({ 'gtm.start': new Date().getTime(), event: 'gtm.js' });
  var s = d.createElement('script');
  s.async = true;
  s.src = 'https://www.googletagmanager.com/gtm.js?id=' + encodeURIComponent(id);
  (d.head || d.documentElement).appendChild(s);
})(window, document);
