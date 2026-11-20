# YouTube production kit

Everything needed to film, edit and publish the first weeks of the channel.
The strategy and the week-by-week plan live in the shared doc ("YouTube launch
plan" tab); this folder is what the team works from.

| Path | What it is |
|---|---|
| `production/000-channel-setup.md` | Channel name, handle, About text, trailer script, setup checklist |
| `production/001-…/package.md` to `004-…` | The first four Lessons: brief, beat sheet, full script, publish sheet (titles, description with tagged links, chapters, pinned comment), Shorts, gate checklist |
| `production/series-stopped-out-friday/` | The weekly losing-trades episode template |
| `production/event-cpi-day/` | The CPI-day breakdown, published on each CPI release day |
| `ideas.csv` | The 100 ranked video ideas. `status` is `idea` or `packaged`; the Lesson desk drafts the next `idea` rows each week |
| `assets/risk-card.html` | The Risk Card overlay. Add it to OBS as a Browser source (1920x1080); build the URL with `assets/risk-card-maker.html` |
| `assets/thumbnail.html` | The thumbnail template (1280x720): `?words=THE%20MATH&face=jack.png&chart=chart.png&market=ES&stop=24&qty=1` |
| `assets/banner.html`, `avatar.html`, `end-screen.html` | Channel art templates |
| `assets/out/` | Rendered PNGs: banner, avatar, end screen, Risk Card examples, thumbnail layouts for videos 001–004 |

## Weekly loop

1. **Sunday:** the marketing-weekly GitHub Action runs. Besides content, outreach and clips, it now drafts
   **2 Lesson packages** from the top unused ideas (`marketing/out/<date>/lessons/`).
2. **Monday:** review the drafts. Copy the ones you approve to `production/NNN-slug/package.md` and set their
   row in `ideas.csv` to `packaged`. Jack fills the `[Jack: …]` brackets.
3. **Tuesday / Thursday:** record after the stream, edit, publish at 6:00 pm ET using the package's publish sheet.
4. **Every gate** in the package's checklist is ticked before the video moves on.

## Rendering images

```bash
NODE_PATH=$(npm root -g) node youtube/assets/render.js
```

Edit `assets/renders.json` to add a thumbnail: copy a `thumb-` entry, change `out` and `params`. Use a real
photo of Jack (`face`) and a real chart crop (`chart`), both as paths relative to `youtube/assets/`.

## Rules that never bend

- Results are shown in ticks only, never dollars; account balances never on screen.
- Every title, description and caption passes `marketing/compliance.py` (the tests check every file here).
- Jack's own voice and face only. AI drafts; people approve and post.
