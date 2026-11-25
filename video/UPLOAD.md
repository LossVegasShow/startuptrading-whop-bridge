# Automatic YouTube uploads

> **Channel change:** per `growth/AWARENESS_FIRST_PLAN.md` §1, uploads move to **Jack's own channel**. Re-run the auth step below signed in as a Manager on Jack's channel and replace `YT_REFRESH_TOKEN`. Until then, upload files stay on `"hold": true`.

The `video-publish` GitHub Action renders each episode and uploads it to the connected channel
(originally `@giannisecchi9682`), scheduled for its `publish_at` time. It runs daily and picks up every
episode due in the next 3 days. It skips anything whose title is already on the channel, so a
re-run never double-posts. It sets the AI-content disclosure, uploads the captions and thumbnail,
and fills the chapters into the description.

## One-time setup (about 15 minutes)

**1. Google Cloud project**

1. Go to console.cloud.google.com and create a project (e.g. "Risk Desk uploads").
2. *APIs & Services → Library* → enable **YouTube Data API v3**.
3. *APIs & Services → OAuth consent screen*: User type **External**; app name; your email.
   Add yourself under **Test users**, then **Publish app** to "In production". In testing
   mode, sign-ins expire after 7 days and the action would stop working.
4. *APIs & Services → Credentials → Create credentials → OAuth client ID*, type **Desktop app**.
   Download the JSON file (`client_secret_….json`).

**2. Sign in once, on your own computer**

```bash
pip install google-auth-oauthlib
```

```bash
python video/youtube_auth.py client_secret.json
```

A browser opens. Sign in with the Google account that owns `@giannisecchi9682`, pick that channel,
and allow access. (Google warns the app is unverified: choose *Advanced → Go to … (unsafe)*.
It's your own app.) The script prints three values.

**3. GitHub secrets**

Repository → *Settings → Secrets and variables → Actions → New repository secret*:

| Secret | Value |
|---|---|
| `YT_CLIENT_ID` | from the script |
| `YT_CLIENT_SECRET` | the `client_secret` inside the downloaded JSON |
| `YT_REFRESH_TOKEN` | from the script |
| `ELEVENLABS_API_KEY` | your ElevenLabs key (the narration) |

Delete the downloaded JSON afterwards, and never commit it.

**4. Custom thumbnails**: verify the channel by phone at youtube.com/verify, or the upload works
but the thumbnail is skipped.

## Day to day

- **New episode:** add `video/episodes/<id>.json` (the script) and `video/uploads/<id>.json` (title,
  description with `{chapters}`, tags, thumbnail, `publish_at`). It uploads automatically 3 days
  before `publish_at` and goes live at that time.
- **Pause one:** add `"hold": true` to its upload file.
- **Run now:** *Actions → video-publish → Run workflow*, with an episode id.
- **Check before it's live:** it sits in YouTube Studio as *Scheduled* until `publish_at`, so you
  can watch it and change anything first.

## Rules the uploader enforces

- Title, description and tags pass the phrase rules, or nothing is uploaded.
- The description must carry the risk line and no unfilled `[placeholders]`.
- `containsSyntheticMedia` is set to true (AI narration).
