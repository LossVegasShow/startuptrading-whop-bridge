# AI video engine

Turns an episode file into a finished, narrated 1080p video, with no filming. Every frame
is drawn from code: real numbers, the sizing math, contract comparisons, the Risk Card and
charts. The narration comes from ElevenLabs; captions are generated with it.

```bash
python video/build.py video/episodes/001-how-many-contracts.json
```

Output, in `video/out/<id>/` (git-ignored): `<id>.mp4` (1920x1080, 30 fps, H.264, AAC 48 kHz,
loudness -14 LUFS) and `<id>.srt` (upload it as the caption file).

## How it avoids looking like AI slop

- **No stock footage, no AI faces, no AI images.** Every visual is a precise motion graphic
  carrying a real number from the script.
- **Original analysis in every video**: worked sizing math, contract comparisons, rules.
  This is what YouTube's inauthentic-content policy rewards, and what generic AI channels skip.
- **One consistent visual system**: brand palette, Geist type, the Risk Card. A viewer
  recognises the channel with the sound off.
- **Charts are labelled honestly.** A chart built from illustrative data says so on screen.
  Replace it with real data by exporting bars from NinjaTrader as CSV and pointing the scene
  at it: `"data": {"csv": "data/es-5min-2026-12-04.csv", "last": 70}`.
- **Phrase rules first:** the build stops if any narration or on-screen text breaks
  `marketing/compliance.py`.

## Episode files

`episodes/<id>.json`: `voice_id` (ElevenLabs), `brand`, `disclaimer`, and a list of `scenes`.
Every scene has a `type` and `say` (the narration). Its length is the narration plus a short
pause, and `anim` is how long it animates before holding. Scene types:

| Type | Shows |
|---|---|
| `hook` | Big statement, words revealed in order, one word highlighted |
| `statement` | One line, with a small label |
| `steps` | The three-step roadmap with the current step highlighted |
| `chart` | Candles from data (CSV or a labelled illustration), ATR panel, entry and ATR-based stop |
| `formula` | Contracts = risk / (stop x $ per point), filled in and rounded down |
| `contracts` | Contract cards side by side (ES / MES / E-nano, NQ / MNQ) with size and real risk |
| `riskcard` | The Risk Card (plan or result; results in ticks only) |
| `recap` | Ticked recap list |
| `endcard` | Next video and space for YouTube's end-screen elements (the last 20 s) |

## Voice

`voice_id` picks the ElevenLabs voice. The default narrator is a stock voice. To use your
own voice, clone it in ElevenLabs and paste its ID into the episode. Under YouTube's rules,
using your own cloned voice needs no AI label.

## Previewing a scene layout

```bash
NODE_PATH=$(npm root -g) node video/engine/preview.js video/out/<id>/timeline.json video/out/preview
```

Fonts: Geist and Geist Mono (SIL Open Font License, `engine/fonts/LICENSE-Geist.txt`).
