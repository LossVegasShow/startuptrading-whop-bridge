"""The YouTube uploader, offline: request body, safety checks, scheduling. No network."""
import datetime as dt
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'video'))
import publish  # noqa: E402

UPLOADS = sorted((ROOT / 'video' / 'uploads').glob('*.json'))


def write_upload(tmp_path, **over):
    up = json.loads((ROOT / 'video' / 'uploads' / '001-how-many-contracts.json').read_text())
    up.update(over)
    p = tmp_path / 'x.json'
    p.write_text(json.dumps(up))
    return p


@pytest.mark.parametrize('path', UPLOADS, ids=lambda p: p.stem)
def test_every_upload_file_passes_the_checks(path):
    up, files = publish.load(path)
    assert (ROOT / 'video' / 'episodes' / f"{up['episode']}.json").is_file()
    assert files['thumbnail'] and files['thumbnail'].is_file()
    body = publish.request_body(up, files)
    publish.check(body)
    assert body['status']['containsSyntheticMedia'] is True
    assert body['snippet']['categoryId'] == '27'


def test_scheduling_forces_private_and_utc(tmp_path):
    up, files = publish.load(write_upload(tmp_path, publish_at='2026-11-24T18:00:00-05:00'))
    body = publish.request_body(up, files, privacy='public')
    assert body['status']['privacyStatus'] == 'private'
    assert body['status']['publishAt'] == '2026-11-24T23:00:00.000Z'


def test_publish_at_needs_a_timezone(tmp_path):
    up, files = publish.load(write_upload(tmp_path, publish_at='2026-11-24T18:00:00'))
    with pytest.raises(publish.PublishError):
        publish.request_body(up, files)


def test_no_schedule_uses_requested_privacy(tmp_path):
    up, files = publish.load(write_upload(tmp_path, publish_at=None))
    assert publish.request_body(up, files, privacy='unlisted')['status'] == {
        **publish.request_body(up, files, privacy='unlisted')['status'], 'privacyStatus': 'unlisted'}
    assert 'publishAt' not in publish.request_body(up, files)['status']


@pytest.mark.parametrize('over, msg', [
    ({'title': 'The most profitable setup'}, 'Phrase rules'),
    ({'title': 'x' * 101}, '100-character'),
    ({'description': 'A plain description without the disclosure. {chapters}'}, 'risk line'),
    ({'title': 'Sizing [TITLE TBD]'}, 'placeholder'),
])
def test_unsafe_uploads_are_refused(tmp_path, over, msg):
    up, files = publish.load(write_upload(tmp_path, **over))
    with pytest.raises(publish.PublishError, match=msg):
        publish.check(publish.request_body(up, files))


def test_chapters_fill_the_description(tmp_path, monkeypatch):
    up, files = publish.load(write_upload(tmp_path))
    ch = tmp_path / 'chapters.txt'
    ch.write_text('0:00 Start\n1:00 Next\n')
    files['chapters'] = ch
    d = publish.description(up, files)
    assert 'Chapters\n0:00 Start\n1:00 Next' in d and '{chapters}' not in d
    files['chapters'] = tmp_path / 'missing.txt'
    assert '{chapters}' not in publish.description(up, files)


def test_due_window_and_hold(tmp_path):
    now = dt.datetime(2026, 11, 22, 12, tzinfo=dt.timezone.utc)
    for name, when, hold in [('a', '2026-11-24T23:00:00Z', False), ('b', '2026-12-10T23:00:00Z', False),
                             ('c', '2026-11-23T23:00:00Z', True), ('d', None, False)]:
        (tmp_path / f'{name}.json').write_text(json.dumps({'publish_at': when, 'hold': hold}))
    assert [p.name for p in publish.due(tmp_path, 3, now)] == ['a.json']


def test_missing_secrets_are_reported(monkeypatch):
    for k in ('YT_CLIENT_ID', 'YT_CLIENT_SECRET', 'YT_REFRESH_TOKEN'):
        monkeypatch.delenv(k, raising=False)
    pytest.importorskip('googleapiclient')
    with pytest.raises(publish.PublishError, match='Missing secrets'):
        publish.service()
