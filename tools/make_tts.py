#!/usr/bin/env python3
"""Generates the read-aloud audio (MP3) for the whole book with Gemini TTS.

    python3 tools/make_tts.py                                 # everything that is missing or changed
                                                              # (key: $GEMINI_API_KEY or ~/.config/adt-tts/gemini-key)
    python3 tools/make_tts.py --limit 5                       # a small test run
    python3 tools/make_tts.py --ids pg008_n0006 gl001         # specific text IDs
    python3 tools/make_tts.py --list-models                   # show the TTS models the key can use
    python3 tools/make_tts.py --dry-run                       # count what would be generated

What gets a recording: every text ID shown on a page (including picture
descriptions), its easy-read variant where one exists, and every glossary word
and definition. The wording comes from content/i18n/sq-XK/speech_texts.json.

Output: content/i18n/sq-XK/audio/<id>.mp3 and content/i18n/sq-XK/audios.json.
A manifest (tools/tts_manifest.json) remembers which text each file was made
from, so a later run only regenerates what changed. Run
`python3 tools/build_lessons.py` afterwards to refresh the offline copy.
"""
import argparse
import base64
import concurrent.futures
import hashlib
import http.client
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANG = 'sq-XK'
I18N = os.path.join(ROOT, 'content', 'i18n', LANG)
AUDIO_DIR = os.path.join(I18N, 'audio')
MANIFEST = os.path.join(ROOT, 'tools', 'tts_manifest.json')
KEY_FILE = os.path.expanduser('~/.config/adt-tts/gemini-key')
API = 'https://generativelanguage.googleapis.com/v1beta'
VOICE = 'Kore'           # the voice ADT Studio uses for Albanian
MODEL_PATTERN = re.compile(r'^gemini-3[.-]8-flash-tts', re.I)   # Gemini 3.8 Flash TTS (not the -lite variant)
LANGUAGE_CODE = 'sq-XK'  # Albanian (Kosovo)
# Same prompt shape ADT Studio sends (performance notes, then the transcript).
PERFORMANCE = ('Language: Albanian as spoken in Kosovo (sq-XK). Read the transcript in clear standard Albanian '
               'with natural Kosovo pronunciation. You are reading a school textbook aloud to nine- and '
               'ten-year-old pupils: warm, calm, friendly, unhurried, every word clearly articulated. '
               'Read exactly the transcript and nothing else; do not translate it and do not add comments.')
SEED = 4
TEMPERATURE = 0.3
RETRIES = {}   # why requests had to be repeated, for the progress line


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def api_key(env_file=None):
    key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
    if not key and env_file and os.path.exists(env_file):
        m = re.search(r'^(?:export\s+)?(?:GEMINI|GOOGLE)_API_KEY=["\']?([^"\'\s]+)', open(env_file).read(), re.M)
        key = m.group(1) if m else None
    if not key and os.path.exists(KEY_FILE):
        key = open(KEY_FILE).read().strip()
    if not key:
        sys.exit(f'No API key. Set GEMINI_API_KEY, or put the key in {KEY_FILE}.')
    return key


def call(url, key, body=None, timeout=180):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={'x-goog-api-key': key, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def tts_models(key):
    names, token = [], ''
    while True:
        data = call(f'{API}/models?pageSize=200' + (f'&pageToken={token}' if token else ''), key)
        names += [m['name'].split('/')[-1] for m in data.get('models', []) if 'tts' in m['name'].lower()]
        token = data.get('nextPageToken')
        if not token:
            return names


def wanted_ids():
    """Text IDs that the reader can ask audio for."""
    speech = load(os.path.join(I18N, 'speech_texts.json'))
    pages = load(os.path.join(ROOT, 'content', 'pages.json'))
    ids = []
    for p in pages:
        html = open(os.path.join(ROOT, p['href']), encoding='utf-8').read()
        ids += re.findall(r'data-id="([^"]+)"', html)
    glossary = load(os.path.join(I18N, 'glossary.json'))
    for entry in glossary.values():
        if entry.get('id'):
            ids += [entry['id'], entry['id'] + '_def']
    out, seen = {}, set()
    for i in ids:
        for key in (i, i + '_easy_read'):
            if key in seen or key not in speech:
                continue
            seen.add(key)
            text = speech[key].strip()
            # nothing to say: empty, bare punctuation or numbers, or a web address
            if not re.search(r'[A-Za-zÇçËë]{2,}', text) or re.match(r'^https?://\S+(\s*\(foto\))?$', text):
                continue
            out[key] = text
    return out


def spoken(text):
    """Easy-read strings use line breaks and '- ' bullets; give the voice sentence breaks instead."""
    lines = [re.sub(r'^[-–•]\s+', '', line.strip()) for line in text.split('\n') if line.strip()]
    lines = [line if re.search(r'[.!?:;…"”]$', line) else line + '.' for line in lines] if len(lines) > 1 else lines
    return ' '.join(lines)


def synthesize(key, model, text, seed=SEED):
    body = {
        'contents': [{'parts': [{'text': f'### PERFORMANCE\n{PERFORMANCE}\n\n#### TRANSCRIPT\n{spoken(text)}'}]}],
        'generationConfig': {
            'responseModalities': ['AUDIO'], 'temperature': TEMPERATURE, 'seed': seed,
            'speechConfig': {'languageCode': LANGUAGE_CODE,
                             'voiceConfig': {'prebuiltVoiceConfig': {'voiceName': VOICE}}},
        },
    }
    delay = 4
    for attempt in range(7):
        try:
            data = call(f'{API}/models/{model}:generateContent', key, body)
            part = data['candidates'][0]['content']['parts'][0]['inlineData']
            return base64.b64decode(part['data']), part.get('mimeType', '')
        except urllib.error.HTTPError as e:
            detail = e.read().decode('utf-8', 'replace')[:300]
            RETRIES[e.code] = RETRIES.get(e.code, 0) + 1
            if e.code in (429, 500, 502, 503, 504) and attempt < 6:
                time.sleep(delay)
                delay = min(delay * 2, 90)
                continue
            raise RuntimeError(f'HTTP {e.code}: {detail}') from None
        except (KeyError, IndexError, TypeError, urllib.error.URLError, TimeoutError, ConnectionError,
                http.client.HTTPException) as e:
            # an empty candidate or a dropped connection: try again a few times
            RETRIES[type(e).__name__] = RETRIES.get(type(e).__name__, 0) + 1
            if attempt < 6:
                time.sleep(delay)
                delay = min(delay * 2, 90)
                continue
            raise RuntimeError(f'no audio returned: {e!r}') from None


def to_mp3(audio, mime, path):
    """The API returns either a WAV file or headerless 16-bit PCM (audio/L16;rate=24000)."""
    source = []
    if 'wav' not in mime.lower() and not audio.startswith(b'RIFF'):
        rate = re.search(r'rate=(\d+)', mime)
        source = ['-f', 's16le', '-ar', rate.group(1) if rate else '24000', '-ac', '1']
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', *source, '-i', 'pipe:0',
                    '-codec:a', 'libmp3lame', '-b:a', '64k', path], input=audio, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--model', help='exact model name; default: the Gemini 3.8 Flash TTS model the key offers')
    ap.add_argument('--env-file')
    ap.add_argument('--limit', type=int)
    ap.add_argument('--ids', nargs='*')
    ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--list-models', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    texts = wanted_ids()
    manifest = load(MANIFEST) if os.path.exists(MANIFEST) else {}
    if args.dry_run:
        chars = sum(len(t) for t in texts.values())
        print(f'{len(texts)} recordings, {chars} characters of text.')
        return

    key = api_key(args.env_file)
    models = tts_models(key)
    if args.list_models:
        print('\n'.join(models))
        return
    model = args.model or next((m for m in models if MODEL_PATTERN.search(m)), None)
    if not model:
        sys.exit('This key offers no Gemini 3.8 Flash TTS model. Available TTS models: ' + ', '.join(models)
                 + '\nPass --model NAME to choose one explicitly.')
    print('model:', model, '| voice:', VOICE)

    def stamp(text):
        return hashlib.sha1(f'{model}|{VOICE}|{LANGUAGE_CODE}|{SEED}|{PERFORMANCE}|{text}'.encode()).hexdigest()

    todo = [i for i in (args.ids or texts) if i in texts and not (
        manifest.get(i) == stamp(texts[i]) and os.path.exists(os.path.join(AUDIO_DIR, i + '.mp3')))]
    if args.limit:
        todo = todo[:args.limit]
    print(f'{len(texts)} recordings in the book, {len(todo)} to generate now.')
    os.makedirs(AUDIO_DIR, exist_ok=True)
    lock, done, failed = threading.Lock(), [0], {}

    def work(i):
        try:
            # Now and then the model rambles or repeats itself. A recording far longer than its
            # text warrants is thrown away and made again with another seed; the shortest is kept.
            best = None
            for attempt in range(4):
                audio, mime = synthesize(key, model, texts[i], SEED + attempt)
                seconds = len(audio) / 48000          # 24 kHz, 16-bit mono
                if best is None or len(audio) < len(best[0]):
                    best = (audio, mime)
                if 0.3 < seconds <= len(spoken(texts[i])) / 9 + 4.5:
                    break
            audio, mime = best
            if len(audio) < 4000:
                raise RuntimeError('audio shorter than 0.1 s')
            to_mp3(audio, mime, os.path.join(AUDIO_DIR, i + '.mp3'))
            with lock:
                manifest[i] = stamp(texts[i])
        except Exception as e:  # keep going; report at the end
            with lock:
                failed[i] = str(e)[:200]
        with lock:
            done[0] += 1
            if done[0] % 50 == 0 or done[0] == len(todo):
                print(f'  {done[0]}/{len(todo)} ({len(failed)} failed; retries {RETRIES})', flush=True)
                with open(MANIFEST, 'w', encoding='utf-8') as f:
                    json.dump(manifest, f, indent=0, sort_keys=True)

    with concurrent.futures.ThreadPoolExecutor(args.workers) as pool:
        list(pool.map(work, todo))

    with open(MANIFEST, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=0, sort_keys=True)
    audios = {i: i + '.mp3' for i in texts if os.path.exists(os.path.join(AUDIO_DIR, i + '.mp3'))}
    with open(os.path.join(I18N, 'audios.json'), 'w', encoding='utf-8') as f:
        json.dump(audios, f, ensure_ascii=False, indent=2)
    print(f'{len(audios)} of {len(texts)} recordings exist. audios.json updated.')
    if failed:
        print(f'{len(failed)} failed:')
        for i, why in list(failed.items())[:20]:
            print('  ', i, '-', why)
        sys.exit(1)


if __name__ == '__main__':
    main()
