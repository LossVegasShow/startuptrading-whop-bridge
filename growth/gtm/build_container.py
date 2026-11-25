"""Builds the importable Google Tag Manager container for startuptrading.com.

    python growth/gtm/build_container.py   ->  growth/gtm/startuptrading-gtm-container.json

Import: GTM -> Admin -> Import container -> choose the file -> workspace "Default"
-> Merge -> "Overwrite conflicting tags, triggers and variables". Then Preview and
Publish (growth/MARKETING_ANALYTICS.md section 6).

What it sets up (and nothing else):
  - Google tag (GA4 G-S0PT1NK0FK): ONE page_view per page, page_location cleaned of
    tokens and non-marketing query parameters, user properties first/last channel.
    Fires once per page load on the site's own sut_attribution event (sent once per
    page by tracking.js) or, on the activation app (no tracking.js), on page load.
  - GA4 event tags for the dataLayer events in sales-site/src/tracking.js, renamed to
    GA4 recommended events where one exists. Purchases are NOT sent from the browser:
    the licensing app sends them from verified Whop payments (Measurement Protocol).
  - No personal data: no emails, names, affiliate codes or full first-touch objects.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GA4_ID = 'G-S0PT1NK0FK'
GTM_ID = 'GTM-ML2LKZ7C'
ACTIVATE_HOST = 'activate.startuptrading.com'
INITIALIZATION_ALL_PAGES = '2147479573'   # GTM built-in trigger "Initialization - All Pages"

# dataLayer event -> GA4 event name (one generic tag)
GENERIC = {'free_tool_view': 'free_tool_view', 'tool_use': 'tool_use', 'calculation_complete': 'calculation_complete',
           'email_subscribe': 'generate_lead', 'checkout_view': 'begin_checkout', 'checkout_return': 'checkout_return',
           'file_download': 'file_download'}
DLV = ['first_channel', 'last_channel', 'tool_id', 'source_page', 'interest', 'form_id', 'calculator', 'placement',
       'destination', 'file_name', 'file_extension', 'link_url']
EVENT_PARAMS = ['tool_id', 'source_page', 'interest', 'form_id', 'calculator', 'file_name', 'file_extension', 'link_url']

CLEAN_URL_JS = """function () {
  var raw = {{Page URL}};
  try {
    var u = new URL(raw);
    var keep = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'gclid', 'gbraid', 'wbraid'];
    var q = [];
    for (var i = 0; i < keep.length; i++) {
      var v = u.searchParams.get(keep[i]);
      if (v) q.push(keep[i] + '=' + encodeURIComponent(v.slice(0, 100)));
    }
    var path = u.pathname.replace(/^\\/activate\\/[^\\/]+/, '/activate/(token)');
    return u.protocol + '//' + u.host + path + (q.length ? '?' + q.join('&') : '');
  } catch (e) {
    return String(raw).split('?')[0];
  }
}"""

USER_PROPS_JS = """function () {
  return { first_channel: {{DLV - first_channel}} || 'unknown', last_channel: {{DLV - last_channel}} || 'unknown' };
}"""


def p(type_, key, value):
    return {'type': type_, 'key': key, 'value': value}


def kv(pairs, k='parameter', v='parameterValue'):
    return {'type': 'LIST', 'key': None, 'list': [{'type': 'MAP', 'map': [p('TEMPLATE', k, a), p('TEMPLATE', v, b)]}
                                                 for a, b in pairs]}


def table(key, pairs, k='parameter', v='parameterValue'):
    t = kv(pairs, k, v)
    t['key'] = key
    return t


def build():
    ids = iter(range(1, 1000))
    base = {'accountId': '0', 'containerId': '0'}
    variables, triggers, tags = [], [], []

    def var(name, type_, params):
        variables.append({**base, 'variableId': str(next(ids)), 'name': name, 'type': type_, 'parameter': params,
                          'fingerprint': '0', 'formatValue': {}})

    for name in DLV:
        var(f'DLV - {name}', 'v', [p('INTEGER', 'dataLayerVersion', '2'), p('BOOLEAN', 'setDefaultValue', 'false'),
                                   p('TEMPLATE', 'name', name)])
    var('GA4 measurement ID', 'c', [p('TEMPLATE', 'value', GA4_ID)])
    var('Page location (clean)', 'jsm', [p('TEMPLATE', 'javascript', CLEAN_URL_JS)])
    var('GA4 user properties', 'jsm', [p('TEMPLATE', 'javascript', USER_PROPS_JS)])
    var('GA4 event name', 'smm', [p('BOOLEAN', 'setDefaultValue', 'true'), p('TEMPLATE', 'input', '{{Event}}'),
                                  table('map', [(k, v) for k, v in GENERIC.items() if k != v], 'key', 'value'),
                                  p('TEMPLATE', 'defaultValue', '{{Event}}')])

    def trigger(name, type_, **extra):
        tid = str(next(ids))
        triggers.append({**base, 'triggerId': tid, 'name': name, 'type': type_, 'fingerprint': '0', **extra})
        return tid

    def event_filter(regex):
        return [{'type': 'MATCH_REGEX', 'parameter': [p('TEMPLATE', 'arg0', '{{_event}}'), p('TEMPLATE', 'arg1', regex)]}]

    t_attr = trigger('SUT - attribution (once per page)', 'CUSTOM_EVENT', customEventFilter=event_filter('^sut_attribution$'))
    t_activate = trigger('Activation app - page load', 'PAGEVIEW', filter=[{'type': 'EQUALS', 'parameter': [
        p('TEMPLATE', 'arg0', '{{Page Hostname}}'), p('TEMPLATE', 'arg1', ACTIVATE_HOST)]}])
    t_generic = trigger('SUT - analytics events', 'CUSTOM_EVENT',
                        customEventFilter=event_filter('^(' + '|'.join(GENERIC) + ')$'))
    t_select = trigger('SUT - free tool selected', 'CUSTOM_EVENT', customEventFilter=event_filter('^free_tool_select$'))
    t_promo = trigger('SUT - membership CTA clicked', 'CUSTOM_EVENT', customEventFilter=event_filter('^checkout_intent$'))
    t_tv = trigger('SUT - TradingView link clicked', 'CUSTOM_EVENT', customEventFilter=event_filter('^outbound_click$'),
                   filter=[{'type': 'EQUALS', 'parameter': [p('TEMPLATE', 'arg0', '{{DLV - destination}}'),
                                                            p('TEMPLATE', 'arg1', 'tradingview')]}])

    user_props = table('userProperties', [('first_channel', '{{DLV - first_channel}}'), ('last_channel', '{{DLV - last_channel}}')],
                       'name', 'value')

    def ga4_event(name, event_name, params, trig):
        tags.append({**base, 'tagId': str(next(ids)), 'name': name, 'type': 'gaawe', 'fingerprint': '0',
                     'parameter': [p('BOOLEAN', 'sendEcommerceData', 'false'), p('TEMPLATE', 'eventName', event_name),
                                   p('TEMPLATE', 'measurementIdOverride', '{{GA4 measurement ID}}'),
                                   table('eventSettingsTable', params), user_props],
                     'firingTriggerId': [trig], 'tagFiringOption': 'ONCE_PER_EVENT',
                     'monitoringMetadata': {'type': 'MAP'}, 'consentSettings': {'consentStatus': 'NOT_SET'}})

    tags.append({**base, 'tagId': str(next(ids)), 'name': 'GA4 - Google tag (page view)', 'type': 'googtag', 'fingerprint': '0',
                 'parameter': [p('TEMPLATE', 'tagId', '{{GA4 measurement ID}}'),
                               table('configSettingsTable', [('send_page_view', 'true'),
                                                             ('page_location', '{{Page location (clean)}}'),
                                                             ('user_properties', '{{GA4 user properties}}')])],
                 'firingTriggerId': [t_attr, t_activate], 'tagFiringOption': 'ONCE_PER_LOAD',
                 'monitoringMetadata': {'type': 'MAP'}, 'consentSettings': {'consentStatus': 'NOT_SET'}})
    ga4_event('GA4 - SUT events', '{{GA4 event name}}', [(k, '{{DLV - ' + k + '}}') for k in EVENT_PARAMS], t_generic)
    ga4_event('GA4 - select_content (free tool)', 'select_content',
              [('content_type', 'free_tool'), ('content_id', '{{DLV - tool_id}}')], t_select)
    ga4_event('GA4 - select_promotion (membership CTA)', 'select_promotion',
              [('promotion_id', 'membership'), ('promotion_name', 'StartUpTrading membership'),
               ('creative_slot', '{{DLV - placement}}')], t_promo)
    ga4_event('GA4 - tradingview_click', 'tradingview_click', [('tool_id', '{{DLV - tool_id}}')], t_tv)

    built_in = [{**base, 'type': t, 'name': n} for t, n in (
        ('PAGE_URL', 'Page URL'), ('PAGE_HOSTNAME', 'Page Hostname'), ('PAGE_PATH', 'Page Path'),
        ('REFERRER', 'Referrer'), ('EVENT', 'Event'))]
    return {
        'exportFormatVersion': 2, 'exportTime': '2026-11-25 00:00:00',
        'containerVersion': {
            'path': 'accounts/0/containers/0/versions/0', **base, 'containerVersionId': '0',
            'container': {'path': 'accounts/0/containers/0', **base, 'name': 'startuptrading.com', 'publicId': GTM_ID,
                          'usageContext': ['WEB'], 'fingerprint': '0'},
            'tag': tags, 'trigger': triggers, 'variable': variables, 'builtInVariable': built_in, 'fingerprint': '0'}}


if __name__ == '__main__':
    out = HERE / 'startuptrading-gtm-container.json'
    out.write_text(json.dumps(build(), indent=2) + '\n')
    print(f'wrote {out}')
