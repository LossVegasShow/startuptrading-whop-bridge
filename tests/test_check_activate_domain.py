"""The domain check script's logic, with fake DNS and HTTP."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    'check_domain', Path(__file__).resolve().parents[1] / 'scripts' / 'check_activate_domain.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

D, OLD = 'activate.startuptrading.com', 'startuptrading-whop-bridge.onrender.com'


def fake_get(public_host=D, redirect_host=D, canonical=True):
    def get(url):
        if url.endswith('/health'):
            return 200, {}, {'public_host': public_host}
        if url.endswith('/oauth/login'):
            return 302, {'location': f'https://api.whop.com/oauth/authorize?redirect_uri=https%3A%2F%2F{redirect_host}%2Foauth%2Fcallback'}, None
        if url == f'https://{OLD}/' and canonical:
            return 302, {'location': f'https://{D}/'}, None
        return 200, {}, None
    return get


def ok_resolve(host):
    return ['216.24.57.1']


def test_all_green_when_fully_switched():
    results = check.run_checks(D, OLD, fake_get(), ok_resolve)
    assert all(ok for ok, _, _ in results), results


def test_dns_missing_stops_early_with_namecheap_hint():
    def bad(host): raise OSError('Name or service not known')
    results = check.run_checks(D, OLD, fake_get(), bad)
    assert len(results) == 1 and not results[0][0] and 'Namecheap' in results[0][2]


def test_flags_public_base_url_not_switched():
    results = check.run_checks(D, OLD, fake_get(public_host=OLD, redirect_host=OLD), ok_resolve)
    failed = {title for ok, title, _ in results if not ok}
    assert 'Render: PUBLIC_BASE_URL points at the new domain' in failed
    assert 'Whop sign-in sends users back to the new domain' in failed


def test_tls_not_ready_has_render_hint():
    def get(url): raise ConnectionError('SSL: certificate verify failed')
    results = check.run_checks(D, OLD, get, ok_resolve)
    assert not results[-1][0] and 'Render' in results[-1][2]


def test_behind_a_proxy_dns_failure_defers_to_https():
    def no_local_dns(host): raise OSError('Name or service not known')
    results = check.run_checks(D, OLD, fake_get(), no_local_dns, proxied=True)
    assert all(ok for ok, _, _ in results) and len(results) > 1
