"""The product registry (products.json) and product delivery. The product files
are proprietary and never committed: this repository is public. They're hosted
elsewhere and linked from /setup through each product's download_url."""
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

import pytest

import config

ROOT = Path(__file__).resolve().parent.parent
REG = json.loads((ROOT / 'products.json').read_text())


def test_registry_drives_licensing():
    assert config.INDICATORS == {2067: 'ATR Order Automation', 2071: 'Trend Scanner & Market Selector'}
    assert config.RETIRED_INDICATORS == {2205: 'TSMS & Fibs'}
    assert not set(config.INDICATORS) & set(config.RETIRED_INDICATORS)
    for p in REG['products']:
        assert len(p['sha256']) == 64 and p['file'].endswith('.zip') and 'download_url' in p
        assert not p['download_url'] or p['download_url'].startswith('https://')


def test_no_product_file_is_ever_tracked_in_git():
    tracked = subprocess.run(['git', 'ls-files'], cwd=ROOT, capture_output=True, text=True).stdout.split()
    assert not [f for f in tracked if f.lower().endswith(('.zip', '.dll')) or f.startswith('downloads/')]
    ignore = (ROOT / '.gitignore').read_text()
    assert 'downloads/' in ignore and '*.zip' in ignore


@pytest.mark.parametrize('p', REG['products'], ids=lambda p: p['file'])
def test_local_copy_matches_registry_when_present(p):
    """Runs only where the files exist locally (never in CI or the public repo)."""
    path = ROOT / 'downloads' / p['file']
    if not path.is_file():
        pytest.skip('product file not present locally (expected: never committed)')
    assert hashlib.sha256(path.read_bytes()).hexdigest() == p['sha256']
    stem = p['file'][:-4]
    z = zipfile.ZipFile(path)
    assert sorted(z.namelist()) == sorted(['Info.xml', stem + '.cs', stem + '.dll'])
    assert 'AgileDotNet' in z.read(stem + '.dll').decode('latin-1')


def test_setup_page_uses_each_products_download_url(monkeypatch):
    from test_sales_site import load_build, SITE
    cfg = json.loads((SITE / 'site.config.json').read_text())
    b = load_build()
    reg = json.loads(json.dumps(REG['products']))
    for i, p in enumerate(reg):
        p['download_url'] = f'https://files.example.com/{i}/{p["file"]}'
    monkeypatch.setattr(b, 'load_products', lambda: reg)
    embed = b.render(cfg, 'setup')[0]
    for p in reg:
        assert f'href="{p["download_url"]}"' in embed and p['ninjatrader_name'] in embed
    assert 'Download link goes here' not in embed
    for p in reg:
        p['download_url'] = ''
    assert 'Download link goes here' in b.render(cfg, 'setup')[0]
