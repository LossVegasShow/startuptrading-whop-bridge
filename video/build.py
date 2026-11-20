"""Builds one AI-produced video from an episode file.

    python video/build.py video/episodes/001-how-many-contracts.json [--no-voice] [--shorts]

Steps: phrase-rule check -> narration (ElevenLabs) -> scene timing -> frame capture
(video/engine/render.js) -> ffmpeg assembly -> captions (.srt) and a publish note.
Output goes to video/out/<episode id>/ (git-ignored). Changes nothing outside video/.

Narration uses the ElevenLabs key saved on this environment (the network proxy adds it),
or ELEVENLABS_API_KEY if set. --no-voice builds a silent cut timed at 150 words a minute.
"""
import argparse
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from marketing import compliance  # noqa: E402  (read-only reuse of the phrase rules)

TTS_URL = 'https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128'
TEXT_FIELDS = ('say', 'text', 'sub', 'title', 'subtitle', 'note', 'next', 'label', 'kicker')


# ---- checks -----------------------------------------------------------------

def scene_text(scene):
    parts = [str(scene.get(k, '')) for k in TEXT_FIELDS]
    parts += [str(x) for k in ('lines', 'items') for x in scene.get(k, [])]
    return ' '.join(p for p in parts if p)


def check_episode(ep):
    """Phrase-rule hits per scene index; the build stops if there are any."""
    hits = {}
    for i, s in enumerate(ep['scenes']):
        h = compliance.check_text(scene_text(s))
        if h:
            hits[i] = h
    return hits


# ---- chart data ---------------------------------------------------------------

def atr(bars, n=14):
    """Wilder's average true range for each bar."""
    out, prev_close, val = [], None, None
    for i, (o, h, l, c) in enumerate(bars):
        tr = h - l if prev_close is None else max(h - l, abs(h - prev_close), abs(l - prev_close))
        if i < n:
            val = tr if val is None else (val * i + tr) / (i + 1)
        else:
            val = (val * (n - 1) + tr) / n
        out.append(round(val, 4))
        prev_close = c
    return out


def synthetic_bars(seed, n, start, step_vol, tick=0.25, trend=0.0):
    """A labelled illustration: random-walk bars rounded to the tick. Not market data."""
    rnd = random.Random(seed)
    q = lambda v: round(round(v / tick) * tick, 2)
    bars, price = [], start
    for _ in range(n):
        o = price
        c = o + rnd.gauss(trend, step_vol)
        h = max(o, c) + abs(rnd.gauss(0, step_vol * .6))
        lo = min(o, c) - abs(rnd.gauss(0, step_vol * .6))
        bars.append([q(o), q(h), q(lo), q(c)])
        price = c
    return bars


def load_csv_bars(path):
    """OHLC from a CSV export (NinjaTrader or similar): columns open, high, low, close."""
    import csv
    with open(path, newline='') as f:
        rows = list(csv.DictReader(f))
    key = lambda r, *names: next(float(r[k]) for k in r if k.strip().lower() in names)
    return [[key(r, 'open'), key(r, 'high'), key(r, 'low'), key(r, 'close')] for r in rows]


def prepare_chart(scene, base):
    d = scene.pop('data', None)
    if not d:
        return scene
    if 'csv' in d:
        bars = load_csv_bars(base / d['csv'])[-d.get('last', 80):]
        scene.setdefault('source', d.get('source', 'Chart: ' + Path(d['csv']).stem))
    else:
        bars = synthetic_bars(d.get('seed', 1), d.get('n', 80), d.get('start', 5000), d.get('vol', 2.2),
                              d.get('tick', 0.25), d.get('trend', 0.0))
        scene.setdefault('source', 'Illustration, not live market data')
    scene['bars'] = bars
    if d.get('atr', True):
        scene['atr'] = atr(bars)
    if d.get('stop_atr_mult'):
        last = bars[-1][3]
        a = scene['atr'][-1]
        scene['entryAt'] = last
        scene['stopAt'] = round(last - d['stop_atr_mult'] * a, 2)
        scene.setdefault('stopLabel', f"STOP {d['stop_atr_mult']} x ATR = {d['stop_atr_mult'] * a:.2f} pts")
    return scene


# ---- narration --------------------------------------------------------------

def tts(text, voice, model, cache, prev_text='', next_text=''):
    key = hashlib.sha1(json.dumps([text, voice, model, prev_text, next_text]).encode()).hexdigest()[:16]
    out = cache / f'{key}.mp3'
    if out.exists() and out.stat().st_size > 1000:
        return out
    body = {'text': text, 'model_id': model,
            'voice_settings': {'stability': 0.45, 'similarity_boost': 0.8, 'style': 0.15, 'use_speaker_boost': True}}
    if prev_text:
        body['previous_text'] = prev_text
    if next_text:
        body['next_text'] = next_text
    req = urllib.request.Request(TTS_URL.format(voice=voice), data=json.dumps(body).encode(), method='POST',
                                 headers={'xi-api-key': os.environ.get('ELEVENLABS_API_KEY', 'proxy-injected'),
                                          'Content-Type': 'application/json', 'Accept': 'audio/mpeg'})
    with urllib.request.urlopen(req, timeout=120) as r:
        out.write_bytes(r.read())
    return out


def duration(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(path)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


# ---- captions ---------------------------------------------------------------

def srt_time(t):
    ms = int(round(t * 1000))
    return f'{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}'


def captions(timed):
    """timed: [(start, spoken_seconds, text)] per scene -> SRT, split by sentence, timed by length."""
    cues = []
    for start, spoken, text in timed:
        if not text:
            continue
        sents = [s for s in re.split(r'(?<=[.?!])\s+', text.strip()) if s]
        total = sum(len(s) for s in sents) or 1
        t = start
        for s in sents:
            d = spoken * len(s) / total
            for chunk in split_chunk(s):
                cd = d * len(chunk) / len(s)
                cues.append((t, t + cd, chunk))
                t += cd
    return '\n'.join(f'{i}\n{srt_time(a)} --> {srt_time(b)}\n{c}\n' for i, (a, b, c) in enumerate(cues, 1))


def split_chunk(s, maxlen=84):
    if len(s) <= maxlen:
        return [s]
    words, out, cur = s.split(), [], ''
    for w in words:
        if len(cur) + len(w) + 1 > maxlen and cur:
            out.append(cur)
            cur = w
        else:
            cur = f'{cur} {w}'.strip()
    return out + [cur]


# ---- build -----------------------------------------------------------------

def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def build(ep_path, voice_on=True, keep_frames=False):
    ep_path = Path(ep_path)
    ep = json.loads(ep_path.read_text())
    hits = check_episode(ep)
    if hits:
        for i, h in hits.items():
            print(f'scene {i}: ' + '; '.join(f"\"{x['match']}\" ({x['why']})" for x in h), file=sys.stderr)
        raise SystemExit('Phrase rules failed; fix the episode before building.')

    w, h, fps = ep.get('w', 1920), ep.get('h', 1080), ep.get('fps', 30)
    out = HERE / 'out' / ep['id']
    cache = HERE / 'cache'
    frames = out / 'frames'
    for d in (out, cache):
        d.mkdir(parents=True, exist_ok=True)
    if frames.exists():
        shutil.rmtree(frames)

    scenes = [prepare_chart(dict(s), ep_path.parent) for s in ep['scenes']]
    says = [s.get('say', '') for s in scenes]
    pad = ep.get('pad', 0.55)
    timeline, timed, audio_parts, chapters, t = [], [], [], [], 0.0
    for i, s in enumerate(scenes):
        say = says[i]
        if say and voice_on:
            mp3 = tts(say, ep['voice_id'], ep.get('model', 'eleven_multilingual_v2'), cache,
                      prev_text=says[i - 1] if i else '', next_text=says[i + 1] if i + 1 < len(says) else '')
            spoken = duration(mp3)
        else:
            mp3, spoken = None, len(say.split()) / 2.5 if say else 0.0
        dur = max(s.get('min', 0), spoken + pad if say else s.get('min', 2.5))
        anim = min(dur, s.get('anim', 2.5))
        s.update({'brand': ep.get('brand', ''), 'disclaimer': ep.get('disclaimer', ''), 'anim': anim})
        s.pop('say', None)
        timeline.append(s)
        if s.get('chapter'):
            chapters.append((t, s['chapter']))
        timed.append((t + 0.15, spoken, say))
        audio_parts.append((mp3, dur))
        t += dur
    (out / 'timeline.json').write_text(json.dumps({'w': w, 'h': h, 'fps': fps, 'frames_dir': str(frames),
                                                   'scenes': timeline}))
    env = dict(os.environ)
    env.setdefault('NODE_PATH', subprocess.run(['npm', 'root', '-g'], capture_output=True, text=True).stdout.strip())
    subprocess.run(['node', str(HERE / 'engine' / 'render.js'), str(out / 'timeline.json')], check=True, env=env)

    segs = out / 'segments'
    segs.mkdir(exist_ok=True)
    seg_list, aud_list = [], []
    for i, (s, (mp3, dur)) in enumerate(zip(timeline, audio_parts)):
        seg = segs / f'{i:03d}.mp4'
        hold = max(0.0, dur - s['anim'])
        run(['ffmpeg', '-y', '-framerate', str(fps), '-i', str(frames / f's{i:03d}' / 'f%05d.jpg'),
             '-vf', f'tpad=stop_mode=clone:stop_duration={hold:.3f},format=yuv420p', '-t', f'{dur:.3f}',
             '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-r', str(fps), str(seg)])
        seg_list.append(f"file '{seg}'")
        aud = segs / f'{i:03d}.wav'
        if mp3:
            run(['ffmpeg', '-y', '-i', str(mp3), '-af', 'adelay=150|150,apad', '-t', f'{dur:.3f}', '-ar', '44100',
                 '-ac', '2', str(aud)])
        else:
            run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-t', f'{dur:.3f}', str(aud)])
        aud_list.append(f"file '{aud}'")
    (segs / 'video.txt').write_text('\n'.join(seg_list))
    (segs / 'audio.txt').write_text('\n'.join(aud_list))
    run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(segs / 'video.txt'), '-c', 'copy', str(out / 'video.mp4')])
    run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(segs / 'audio.txt'), '-c:a', 'pcm_s16le',
         str(out / 'narration.wav')])
    final = out / f"{ep['id']}.mp4"
    run(['ffmpeg', '-y', '-i', str(out / 'video.mp4'), '-i', str(out / 'narration.wav'), '-c:v', 'copy',
         '-c:a', 'aac', '-b:a', '192k', '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-ar', '48000', '-shortest',
         '-movflags', '+faststart', str(final)])
    (out / f"{ep['id']}.srt").write_text(captions(timed))
    (out / 'chapters.txt').write_text(''.join(f'{int(c // 60)}:{int(c % 60):02d} {name}\n' for c, name in chapters))
    if not keep_frames:
        shutil.rmtree(frames)
        shutil.rmtree(segs)
        for f in ('video.mp4', 'narration.wav'):
            (out / f).unlink(missing_ok=True)
    print(f'built {final} ({t / 60:.1f} min, {len(timeline)} scenes)')
    return final, t


def main(argv=None):
    ap = argparse.ArgumentParser(description='Build an AI-produced video from an episode file.')
    ap.add_argument('episode')
    ap.add_argument('--no-voice', action='store_true', help='Silent cut timed at 150 words a minute.')
    ap.add_argument('--keep-frames', action='store_true')
    a = ap.parse_args(argv)
    build(a.episode, voice_on=not a.no_voice, keep_frames=a.keep_frames)


if __name__ == '__main__':
    main()
