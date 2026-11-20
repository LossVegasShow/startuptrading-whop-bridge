"""Uploads a built video to YouTube with its captions, thumbnail, description and schedule.

    python video/publish.py video/uploads/001-how-many-contracts.json [--privacy private]
                            [--publish-at 2026-11-24T23:00:00Z] [--dry-run]

Needs three secrets in the environment (see video/UPLOAD.md): YT_CLIENT_ID, YT_CLIENT_SECRET,
YT_REFRESH_TOKEN. --dry-run prints exactly what would be sent and needs no secrets.

Safety:
- Title, description and tags go through the same phrase rules as everything else; any hit stops the upload.
- If a video with the same title is already on the channel, nothing is uploaded (safe to re-run).
- The AI-content disclosure (status.containsSyntheticMedia) is set from the upload file.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from marketing import compliance  # noqa: E402  (read-only reuse of the phrase rules)

SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.force-ssl']
EDUCATION = '27'


class PublishError(RuntimeError):
    pass


def load(upload_path):
    up = json.loads(Path(upload_path).read_text())
    out = HERE / 'out' / up['episode']
    files = {'video': out / f"{up['episode']}.mp4", 'captions': out / f"{up['episode']}.srt",
             'chapters': out / 'chapters.txt'}
    thumb = up.get('thumbnail')
    files['thumbnail'] = (HERE.parent / thumb) if thumb else None
    return up, files


def description(up, files):
    chapters = files['chapters'].read_text().strip() if files['chapters'].exists() else ''
    text = up['description']
    text = text.replace('{chapters}', ('Chapters\n' + chapters) if chapters else '')
    return text.strip()


def request_body(up, files, privacy=None, publish_at=None):
    desc = description(up, files)
    privacy = privacy or up.get('privacy', 'private')
    publish_at = publish_at if publish_at is not None else up.get('publish_at')
    status = {'privacyStatus': privacy, 'selfDeclaredMadeForKids': False,
              'containsSyntheticMedia': bool(up.get('contains_synthetic_media', True)),
              'embeddable': True, 'license': 'youtube'}
    if publish_at:
        when = dt.datetime.fromisoformat(publish_at.replace('Z', '+00:00'))
        if when.tzinfo is None:
            raise PublishError('publish_at needs a timezone, e.g. 2026-11-24T23:00:00Z')
        # YouTube only schedules private videos; it publishes them at publish_at.
        status['privacyStatus'] = 'private'
        status['publishAt'] = when.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    return {'snippet': {'title': up['title'], 'description': desc, 'tags': up.get('tags', []),
                        'categoryId': up.get('category_id', EDUCATION), 'defaultLanguage': 'en',
                        'defaultAudioLanguage': 'en'},
            'status': status}


def check(body):
    s = body['snippet']
    if len(s['title']) > 100:
        raise PublishError('Title is over YouTube\'s 100-character limit.')
    if len(s['description']) > 5000:
        raise PublishError('Description is over YouTube\'s 5,000-character limit.')
    hits = compliance.check_pack({'title': s['title'], 'description': s['description'],
                                  'tags': ' '.join(s['tags'])})
    if hits:
        raise PublishError('Phrase rules failed: ' + json.dumps(hits))
    if not compliance.has_risk_line(s['description']):
        raise PublishError('The description is missing the risk line.')
    if re.search(r'\[[^\]]*\]', s['title'] + s['description']):
        raise PublishError('An unfilled [placeholder] is still in the title or description.')


def service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    missing = [k for k in ('YT_CLIENT_ID', 'YT_CLIENT_SECRET', 'YT_REFRESH_TOKEN') if not os.environ.get(k)]
    if missing:
        raise PublishError('Missing secrets: ' + ', '.join(missing) + '. See video/UPLOAD.md.')
    creds = Credentials(None, refresh_token=os.environ['YT_REFRESH_TOKEN'], client_id=os.environ['YT_CLIENT_ID'],
                        client_secret=os.environ['YT_CLIENT_SECRET'],
                        token_uri='https://oauth2.googleapis.com/token', scopes=SCOPES)
    return build('youtube', 'v3', credentials=creds, cache_discovery=False)


def existing_video(yt, title):
    """Video ID of an upload on the channel with exactly this title, else None."""
    ch = yt.channels().list(part='contentDetails', mine=True).execute()
    if not ch.get('items'):
        raise PublishError('No YouTube channel found for this account.')
    uploads = ch['items'][0]['contentDetails']['relatedPlaylists']['uploads']
    token = None
    while True:
        res = yt.playlistItems().list(part='snippet', playlistId=uploads, maxResults=50, pageToken=token).execute()
        for it in res.get('items', []):
            if it['snippet']['title'].strip() == title.strip():
                return it['snippet']['resourceId']['videoId']
        token = res.get('nextPageToken')
        if not token:
            return None


def upload(yt, body, files):
    from googleapiclient.http import MediaFileUpload
    media = MediaFileUpload(str(files['video']), mimetype='video/mp4', chunksize=8 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part='snippet,status', body=body, media_body=media, notifySubscribers=True)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f'  uploaded {int(status.progress() * 100)}%')
    return resp['id']


def add_extras(yt, vid, up, files):
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    notes = []
    if files['captions'].exists():
        yt.captions().insert(part='snippet', body={'snippet': {'videoId': vid, 'language': 'en', 'name': 'English',
                                                               'isDraft': False}},
                             media_body=MediaFileUpload(str(files['captions']), mimetype='application/octet-stream')
                             ).execute()
        notes.append('captions uploaded')
    if files['thumbnail'] and files['thumbnail'].exists():
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(files['thumbnail']))).execute()
            notes.append('thumbnail set')
        except HttpError as e:  # custom thumbnails need a phone-verified channel
            notes.append(f'thumbnail skipped ({e.status_code}): verify the channel by phone to allow custom thumbnails')
    if up.get('playlist_id'):
        yt.playlistItems().insert(part='snippet', body={'snippet': {'playlistId': up['playlist_id'], 'resourceId': {
            'kind': 'youtube#video', 'videoId': vid}}}).execute()
        notes.append('added to playlist')
    return notes


def publish(upload_path, privacy=None, publish_at=None, dry_run=False):
    up, files = load(upload_path)
    body = request_body(up, files, privacy, publish_at)
    check(body)
    if dry_run:
        print(json.dumps(body, indent=2))
        print('files:', {k: str(v) for k, v in files.items()})
        return None
    if not files['video'].exists():
        raise PublishError(f"{files['video']} not found. Build it first: python video/build.py video/episodes/{up['episode']}.json")
    yt = service()
    found = existing_video(yt, body['snippet']['title'])
    if found:
        print(f'Already on the channel: https://youtu.be/{found} (nothing uploaded)')
        return found
    vid = upload(yt, body, files)
    for n in add_extras(yt, vid, up, files):
        print('  ' + n)
    when = body['status'].get('publishAt')
    print(f"Uploaded https://youtu.be/{vid} ({'scheduled for ' + when if when else body['status']['privacyStatus']})")
    return vid


def due(upload_dir, days, now=None):
    """Upload files whose publish_at falls within the next `days` days (or is past but not yet uploaded)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    out = []
    for p in sorted(Path(upload_dir).glob('*.json')):
        up = json.loads(p.read_text())
        if not up.get('publish_at') or up.get('hold'):
            continue
        when = dt.datetime.fromisoformat(up['publish_at'].replace('Z', '+00:00'))
        if when <= now + dt.timedelta(days=days):
            out.append(p)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description='Upload a built video to YouTube.')
    ap.add_argument('upload', nargs='?', help='An upload file in video/uploads/.')
    ap.add_argument('--due', type=int, metavar='DAYS', help='Instead: list upload files due within DAYS days.')
    ap.add_argument('--privacy', choices=['private', 'unlisted', 'public'])
    ap.add_argument('--publish-at', help='ISO 8601 with timezone, e.g. 2026-11-24T23:00:00Z')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    if a.due is not None:
        for p in due(HERE / 'uploads', a.due):
            print(p)
        return 0
    if not a.upload:
        ap.error('give an upload file, or --due DAYS')
    try:
        publish(a.upload, a.privacy, a.publish_at, a.dry_run)
    except PublishError as e:
        print(f'Not uploaded: {e}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
