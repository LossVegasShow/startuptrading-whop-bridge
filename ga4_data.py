"""GA4 Data API for the marketing dashboard (read-only).

Needs, in Render:
  GA4_PROPERTY_ID            the numeric property ID (GA4 Admin -> Property details)
  GA4_SERVICE_ACCOUNT_JSON   a Google Cloud service account key (JSON, raw or base64)
                             whose email has the Viewer role on the GA4 property,
                             with the Google Analytics Data API enabled in its project.

Results are cached for 6 hours (ga4_cache), so the dashboard stays fast and well
within the API quota. Every failure is reported, never papered over: the dashboard
then shows the GA4 columns as unavailable.
"""
import base64
import json
import time

import httpx

SCOPE = 'https://www.googleapis.com/auth/analytics.readonly'
API = 'https://analyticsdata.googleapis.com/v1beta/properties/{pid}:runReport'
CACHE_SECONDS = 6 * 3600
FUNNEL_EVENTS = ['free_tool_view', 'tool_use', 'calculation_complete', 'select_content', 'tradingview_click',
                 'generate_lead', 'select_promotion', 'begin_checkout', 'checkout_return', 'file_download',
                 'purchase', 'ninjatrader_linked', 'activation_complete']


class GA4Unavailable(Exception):
    pass


def configured(cfg):
    return bool(cfg.ga4_property_id and cfg.ga4_property_id.isdigit() and cfg.ga4_service_account_json.strip())


def _credentials(cfg):
    raw = cfg.ga4_service_account_json.strip()
    if not raw.startswith('{'):
        try:
            raw = base64.b64decode(raw).decode()
        except (ValueError, UnicodeDecodeError):
            raise GA4Unavailable('GA4_SERVICE_ACCOUNT_JSON is neither JSON nor base64 JSON')
    try:
        info = json.loads(raw)
        return info['client_email'], info['private_key'], info.get('token_uri') or 'https://oauth2.googleapis.com/token'
    except (ValueError, KeyError):
        raise GA4Unavailable('GA4_SERVICE_ACCOUNT_JSON is missing client_email or private_key')


def _jwt(email, key_pem, aud, now):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    def b64(b):
        return base64.urlsafe_b64encode(b).rstrip(b'=')
    head = b64(json.dumps({'alg': 'RS256', 'typ': 'JWT'}).encode())
    body = b64(json.dumps({'iss': email, 'scope': SCOPE, 'aud': aud, 'iat': now, 'exp': now + 3600}).encode())
    key = serialization.load_pem_private_key(key_pem.encode(), password=None)
    sig = key.sign(head + b'.' + body, padding.PKCS1v15(), hashes.SHA256())
    return (head + b'.' + body + b'.' + b64(sig)).decode()


async def _token(cfg, client):
    email, key, uri = _credentials(cfg)
    assertion = _jwt(email, key, uri, int(time.time()))
    r = await client.post(uri, data={'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer', 'assertion': assertion})
    if r.status_code != 200:
        raise GA4Unavailable(f'Google sign-in failed (HTTP {r.status_code}); check the service account key')
    return r.json()['access_token']


def _rows(resp):
    out = []
    for row in resp.get('rows', []):
        dims = [d.get('value', '') for d in row.get('dimensionValues', [])]
        mets = [float(m.get('value') or 0) for m in row.get('metricValues', [])]
        out.append((dims, mets))
    return out


def _requests(start, end):
    rng = [{'startDate': start, 'endDate': end}]
    events = {'filter': {'fieldName': 'eventName', 'inListFilter': {'values': FUNNEL_EVENTS}}}
    return {
        'totals': {'dateRanges': rng, 'metrics': [{'name': 'totalUsers'}, {'name': 'newUsers'}, {'name': 'sessions'},
                                                   {'name': 'engagedSessions'}]},
        'channels': {'dateRanges': rng, 'dimensions': [{'name': 'customUser:first_channel'}],
                     'metrics': [{'name': 'totalUsers'}, {'name': 'sessions'}], 'limit': 50},
        'channel_events': {'dateRanges': rng, 'dimensions': [{'name': 'customUser:first_channel'}, {'name': 'eventName'}],
                           'metrics': [{'name': 'eventCount'}], 'dimensionFilter': events, 'limit': 500},
        'landing': {'dateRanges': rng, 'dimensions': [{'name': 'landingPage'}],
                    'metrics': [{'name': 'sessions'}, {'name': 'totalUsers'}, {'name': 'keyEvents'}], 'limit': 25},
        'devices': {'dateRanges': rng, 'dimensions': [{'name': 'deviceCategory'}], 'metrics': [{'name': 'totalUsers'}]},
        'countries': {'dateRanges': rng, 'dimensions': [{'name': 'country'}], 'metrics': [{'name': 'totalUsers'}],
                      'orderBys': [{'metric': {'metricName': 'totalUsers'}, 'desc': True}], 'limit': 10},
        'default_channels': {'dateRanges': rng, 'dimensions': [{'name': 'sessionDefaultChannelGroup'}],
                             'metrics': [{'name': 'sessions'}, {'name': 'totalUsers'}], 'limit': 25},
    }


def summarize(results):
    """Raw runReport responses -> what the dashboard shows."""
    out = {'available': True, 'errors': {}}
    t = _rows(results.get('totals', {}))
    out['totals'] = dict(zip(['users', 'new_users', 'sessions', 'engaged_sessions'], t[0][1])) if t else \
        {'users': 0, 'new_users': 0, 'sessions': 0, 'engaged_sessions': 0}
    out['returning_users'] = max(0, out['totals']['users'] - out['totals']['new_users'])
    out['channels'] = {d[0] or 'unknown': {'users': m[0], 'sessions': m[1], 'leads': 0} for d, m in _rows(results.get('channels', {}))}
    out['funnel'] = {e: 0 for e in FUNNEL_EVENTS}
    for (ch, ev), (n,) in [(d, m) for d, m in _rows(results.get('channel_events', {}))]:
        out['funnel'][ev] = out['funnel'].get(ev, 0) + n
        if ev == 'generate_lead':
            out['channels'].setdefault(ch or 'unknown', {'users': 0, 'sessions': 0, 'leads': 0})['leads'] += n
    out['landing'] = [{'page': d[0], 'sessions': m[0], 'users': m[1], 'key_events': m[2]} for d, m in _rows(results.get('landing', {}))]
    out['devices'] = {d[0]: m[0] for d, m in _rows(results.get('devices', {}))}
    out['countries'] = [(d[0], m[0]) for d, m in _rows(results.get('countries', {}))]
    out['default_channels'] = [(d[0], m[0], m[1]) for d, m in _rows(results.get('default_channels', {}))]
    out['leads'] = out['funnel'].get('generate_lead', 0)
    return out


async def fetch(cfg, start, end, post=None):
    """Run every report for a date range. start/end: 'YYYY-MM-DD' or GA's '30daysAgo'/'today'."""
    if not configured(cfg):
        raise GA4Unavailable('GA4 Data API not configured (GA4_PROPERTY_ID, GA4_SERVICE_ACCOUNT_JSON)')
    results, errors = {}, {}
    async with httpx.AsyncClient(timeout=20) as client:
        token = await _token(cfg, client) if post is None else 'test'
        for name, body in _requests(start, end).items():
            url = API.format(pid=cfg.ga4_property_id)
            r = await (post(url, body) if post else client.post(url, json=body, headers={'Authorization': 'Bearer ' + token}))
            if r.status_code == 200:
                results[name] = r.json()
            else:
                errors[name] = f'HTTP {r.status_code}'
    if not results:
        raise GA4Unavailable('GA4 returned no reports: ' + ', '.join(f'{k} {v}' for k, v in errors.items()))
    out = summarize(results)
    out['errors'] = errors
    return out


async def cached(cfg, connect, start, end, post=None, now=None):
    now = now or int(time.time())
    key = f'{cfg.ga4_property_id}:{start}:{end}'
    with connect(cfg) as db:
        row = db.execute('SELECT body,fetched_at FROM ga4_cache WHERE cache_key=?', (key,)).fetchone()
    if row and now - row['fetched_at'] < CACHE_SECONDS:
        data = json.loads(row['body'])
        data['fetched_at'] = row['fetched_at']
        return data
    data = await fetch(cfg, start, end, post=post)
    with connect(cfg) as db:
        db.execute('INSERT INTO ga4_cache(cache_key,body,fetched_at) VALUES(?,?,?) ON CONFLICT(cache_key) '
                   'DO UPDATE SET body=excluded.body, fetched_at=excluded.fetched_at', (key, json.dumps(data), now))
    data['fetched_at'] = now
    return data
