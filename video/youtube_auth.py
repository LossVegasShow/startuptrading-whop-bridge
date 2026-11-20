"""One-time sign-in: gives this project permission to upload to your YouTube channel.

Run it ON YOUR OWN COMPUTER (it opens a browser), not in the cloud:

    pip install google-auth-oauthlib
    python youtube_auth.py client_secret.json

It prints a refresh token. Save it, with the client ID and secret, as GitHub secrets
(YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN). Never commit client_secret.json or the token.
Steps for getting client_secret.json are in video/UPLOAD.md.
"""
import json
import sys

SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.force-ssl']


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
    creds = flow.run_local_server(port=0, prompt='consent', access_type='offline')
    info = json.load(open(sys.argv[1]))
    client = info.get('installed') or info.get('web') or {}
    print('\nSave these three values as GitHub repository secrets:\n')
    print('YT_CLIENT_ID     =', client.get('client_id'))
    print('YT_CLIENT_SECRET = (the client_secret value inside', sys.argv[1] + ')')
    print('YT_REFRESH_TOKEN =', creds.refresh_token)
    print('\nSign in with the Google account that owns @giannisecchi9682.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
