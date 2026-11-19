"""Deploy smoke test: the app must import and serve /health from a clean checkout.

A missing module (for example clients.py) previously broke the Render deploy
while every other test still ran. This catches that before merge.
"""
import importlib, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient


def test_app_imports_and_health_responds(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'smoke.db'))
    monkeypatch.delenv('RUN_RECONCILER', raising=False)
    for mod in ('config', 'store', 'clients', 'engine', 'app'):
        sys.modules.pop(mod, None)
    app = importlib.import_module('app')
    assert app.cfg.run_reconciler is False, 'reconciler must be opt-in'
    with TestClient(app.app) as client:
        r = client.get('/health')
    assert r.status_code == 200
    body = r.json()
    assert body['status'] == 'ok'
    assert body['mode'] == 'observe_only'


def test_every_local_import_resolves():
    root = Path(__file__).resolve().parents[1]
    local = {p.stem for p in root.glob('*.py')}
    for mod in ('app', 'engine', 'diagnostics', 'member_lookup', 'purchaser_intake', 'customer_communications'):
        assert mod in local, f'{mod}.py missing from project root'
    assert 'clients' in local, 'clients.py missing from project root'
