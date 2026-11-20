# The AI marketing team

Every Sunday evening a team of AI agents researches the market, plans the
week, writes the content and checks it for compliance. It hands you a
**review queue**. Nothing is ever posted automatically: in futures marketing
one bad claim can do more damage than a month of good posts.

```
Researcher ──► Strategist ──► Copywriter ──► Compliance ──► Review queue ──► you approve ──► post
(web search)   (theme +       (YouTube,      (AI review +    (queue.md)
               5 briefs)      Short, X,      phrase rules,
     Analyst ──┘              email)         risk line)
 (your metrics)
```

| Agent | Does | Effort |
|---|---|---|
| Researcher | Searches the web for the week's indicator releases, trade-room offers, NinjaTrader news and the questions traders are asking. Every finding comes with its source link. | medium |
| Analyst | Reads the CSV exports in `marketing/metrics/` and compares them with the targets. It's skipped when the folder is empty. | medium |
| Strategist | Picks one theme and writes 5 briefs. Each brief says what Jack needs to show on his normal morning stream, so one session feeds the whole week. | high |
| Copywriter | Writes each brief as a YouTube title and description, a Shorts script, X posts and an email, in Jack's voice. | medium |
| Compliance | An AI review against CFTC, NFA and FTC rules, plus fixed phrase rules in `compliance.py` that the AI can't overrule. It also adds the risk line to every piece. | high |

Two more desks run in the same job:

| Desk | Does | Output |
|---|---|---|
| Outreach | Searches for podcasts, prop firms, trading Discords, newsletters, YouTube channels, journalists and events that fit Jack, then drafts a personal pitch and a 7-day follow-up for each. Contact routes are copied only from what each prospect publishes, never guessed. | `outreach.md` |
| Lessons | Takes the next unused ideas from `youtube/ideas.csv` and drafts full Lesson packages (titles, thumbnail words, hook, beat sheet, description, chapters, pinned comment, Shorts), with every fact only Jack can supply left as a bracket. See `youtube/README.md`. | `lessons/` |
| Clips | Reads stream transcripts in `marketing/transcripts/` and picks the best 30–60 s moments, with timestamps, a hook, and captions in English and Spanish. Each caption carries the risk line. | `clips.md` |

Pitches and captions go through the same phrase rules, including Spanish
profit and guarantee words.

All agents share one source of truth: **`brand_brief.md`**. When Jack changes
a fact there, the next run uses it. Anything not in that file can't be stated
as fact.

## Setup (once)

1. Create an API key at console.anthropic.com (Settings → API keys). Add it to
   this GitHub repository: **Settings → Secrets and variables → Actions → New
   repository secret**, name `ANTHROPIC_API_KEY`.
2. Have Jack confirm the facts in `brand_brief.md`, especially the
   `[TO CONFIRM WITH JACK]` line.
3. Run it once by hand: **Actions → marketing-weekly → Run workflow**.

After that it runs every Sunday at 5:17 pm ET.

## Each week

1. Open the latest **marketing-weekly** run in Actions. The queue is shown on
   the run page and attached as a download (`queue.md` and `queue.json`).
2. Give Jack the **"Record this week"** checklist before Monday's stream.
3. For each piece:
   - **ready_for_review**: read it, edit it if needed, then schedule it.
   - **needs_changes**: the flagged phrases are listed. Fix them or drop the piece.
   - **failed**: the agent couldn't write it. Ignore it this week.
4. **Outreach:** send the ready pitches from your own email, or through the
   contact route listed. Then add each name to `marketing/outreach/contacted.txt`
   so it isn't pitched again.
5. **Clips:** before Sunday, download the week's stream captions from YouTube
   Studio (Subtitles → ⋮ → Download, `.srt` or `.vtt`) into `marketing/transcripts/`
   and commit them. The clip desk picks the moments, and whoever edits video cuts them.
6. Optional: drop that week's numbers into `marketing/metrics/` as a CSV, for
   example `metric,value` rows for leads, new members, churn and views. Use
   **totals only**. Never commit member names or emails: this repository is
   not the place for personal data.

## Run it on your own computer

```bash
pip install -r marketing/requirements.txt
```

```bash
ANTHROPIC_API_KEY=sk-ant-... python -m marketing --briefs 5
```

The queue is written to `marketing/out/<date>/`, which git ignores.

## Cost

One run makes about 15–20 model calls (more when there are several transcripts), plus up to 16 web searches. It uses
`claude-opus-5-5`, with the brand brief cached across calls. Check the real
cost of the first run in the Anthropic console (Usage) and lower `--briefs`
if it's more than you want.

## Changing the rules

- Banned phrases and the risk line live in `compliance.py`. `tests/test_marketing.py`
  shows what is caught and what is allowed. "Profit target" is fine, "profitable" is not.
- Agent instructions live at the bottom of `agents.py`.
- Tests run offline with a fake client: `python -m pytest tests/test_marketing.py`.
