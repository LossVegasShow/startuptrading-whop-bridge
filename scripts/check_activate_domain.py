"""Check that activate.startuptrading.com is set up correctly.

    python scripts/check_activate_domain.py
    python scripts/check_activate_domain.py --domain activate.startuptrading.com \
        --old startuptrading-whop-bridge.onrender.com

Run it after each step in ACTIVATE_DOMAIN.md. It only reads (DNS lookups and
GET requests); it never changes anything.
"""
import argparse
import os
import socket
import sys
from urllib.parse import parse_qs, urlsplit

DEFAULT_DOMAIN = 'activate.startuptrading.com'
DEFAULT_OLD = 'startuptrading-whop-bridge.onrender.com'


def run_checks(domain, old_host, get, resolve, proxied=False):
    """Return a list of (ok, title, detail). `get(url)` returns (status, headers, json_or_None);
    `resolve(host)` returns a list of IPs or raises OSError."""
    results = []

    def add(ok, title, detail=''):
        results.append((ok, title, detail))
        return ok

    try:
        ips = resolve(domain)
        add(bool(ips), 'DNS: domain resolves', ', '.join(ips))
    except OSError as exc:
        if not proxied:
            add(False, 'DNS: domain resolves',
                f'{exc}. Add the Namecheap CNAME "activate" -> {old_host} and wait a few minutes.')
            return results
        # Behind an HTTPS proxy the proxy resolves names; a local lookup can fail
        # even when DNS is fine, so let the HTTPS check below decide.
        add(True, 'DNS: checked via HTTPS (local lookup unavailable behind a proxy)', str(exc))

    base = f'https://{domain}'
    try:
        status, _, body = get(base + '/health')
    except Exception as exc:  # TLS not issued yet, connection refused, etc.
        add(False, 'HTTPS: /health reachable on the new domain',
            f'{exc}. In Render, add the custom domain and wait for "Certificate issued".')
        return results
    add(status == 200, 'HTTPS: /health reachable on the new domain', f'HTTP {status}')
    host = (body or {}).get('public_host', '')
    add(host == domain, 'Render: PUBLIC_BASE_URL points at the new domain',
        f'app reports public_host={host or "?"}' + ('' if host == domain else
        f'. Set PUBLIC_BASE_URL=https://{domain} in Render (after adding the Whop redirect URI).'))

    status, headers, _ = get(base + '/oauth/login')
    if status == 503:
        add(False, 'Whop sign-in configured', 'WHOP_CLIENT_ID / WHOP_CLIENT_SECRET are not set in Render.')
    else:
        location = headers.get('location', '')
        redirect = parse_qs(urlsplit(location).query).get('redirect_uri', [''])[0]
        want = base + '/oauth/callback'
        add(redirect == want, 'Whop sign-in sends users back to the new domain',
            f'redirect_uri={redirect or "?"}' + ('' if redirect == want else f' (expected {want})'))

    status, _, _ = get(base + '/')
    add(status == 200, 'Activation page loads on the new domain', f'HTTP {status}')

    if old_host:
        try:
            status, _, _ = get(f'https://{old_host}/health')
            add(status == 200, 'Old address still answers /health (webhooks keep working)', f'HTTP {status}')
            status, headers, _ = get(f'https://{old_host}/')
            moved = status in (301, 302, 307, 308) and headers.get('location', '').startswith(base)
            add(True, 'Old address: visitors ' + ('are redirected to the new domain' if moved else
                'are NOT redirected yet'),
                'CANONICAL_REDIRECT is on' if moved else 'Optional last step: set CANONICAL_REDIRECT=true in Render.')
        except Exception as exc:
            add(False, 'Old address reachable', str(exc))
    return results


def _get(url):
    import httpx
    r = httpx.get(url, follow_redirects=False, timeout=15)
    try:
        body = r.json()
    except ValueError:
        body = None
    return r.status_code, {k.lower(): v for k, v in r.headers.items()}, body


def _resolve(host):
    return sorted({info[4][0] for info in socket.getaddrinfo(host, 443)})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--domain', default=DEFAULT_DOMAIN)
    ap.add_argument('--old', default=DEFAULT_OLD, help='old Render hostname ("" to skip)')
    args = ap.parse_args(argv)
    proxied = bool(os.getenv('HTTPS_PROXY') or os.getenv('https_proxy'))
    results = run_checks(args.domain, args.old, _get, _resolve, proxied=proxied)
    for ok, title, detail in results:
        print(f'{"PASS" if ok else "FAIL"}  {title}' + (f'\n      {detail}' if detail else ''))
    failed = [r for r in results if not r[0]]
    print(f'\n{len(results) - len(failed)}/{len(results)} checks passed.')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
