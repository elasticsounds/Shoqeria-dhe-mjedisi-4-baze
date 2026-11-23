#!/usr/bin/env python3
"""Local picture-review tool for the book.

    python3 tools/image_review/server.py          # then open http://127.0.0.1:8770/tools/image_review/

Shows every picture (PDF / book now / Flamur's version), lets you pick one or
generate a new one with the OpenAI image API, and saves every choice to
tools/image_review/choices.json. Generated pictures go to tools/image_review/generated/.
The OpenAI key is read from $OPENAI_API_KEY, else the last `export OPENAI_API_KEY=` in ~/.zshrc.
"""
import base64
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
STATE = os.path.join(HERE, 'choices.json')
GENERATED = os.path.join(HERE, 'generated')
MODEL = 'gpt-image-2.6-flare'
PORT = int(os.environ.get('PORT', 8770))
LOCK = threading.Lock()


def api_key():
    key = os.environ.get('OPENAI_API_KEY')
    rc = os.path.expanduser('~/.zshrc')
    if not key and os.path.exists(rc):
        found = re.findall(r'^export OPENAI_API_KEY=[\'"]?([^\'"\n]+)', open(rc).read(), re.M)
        key = found[-1] if found else None
    return key


def load_state():
    if os.path.exists(STATE):
        with open(STATE, encoding='utf-8') as f:
            return json.load(f)
    return {'choices': {}, 'generated': {}, 'notes': {}}


def save_state(state):
    tmp = STATE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)


def inside_root(rel):
    path = os.path.realpath(os.path.join(ROOT, rel))
    if not path.startswith(os.path.realpath(ROOT) + os.sep) or not os.path.isfile(path):
        raise ValueError('bad reference path')
    return path


def openai_image(prompt, ref, size, quality):
    key = api_key()
    if not key:
        raise RuntimeError('No OpenAI key found (OPENAI_API_KEY or ~/.zshrc).')
    fields = {'model': MODEL, 'prompt': prompt, 'n': '1'}
    if size and size != 'auto':
        fields['size'] = size
    if quality and quality != 'auto':
        fields['quality'] = quality
    if ref:
        boundary = uuid.uuid4().hex
        parts = []
        for k, v in fields.items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
        path = inside_root(ref)
        mime = 'image/jpeg' if path.lower().endswith(('.jpg', '.jpeg')) else 'image/png'
        parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="image[]"; '
                      f'filename="{os.path.basename(path)}"\r\nContent-Type: {mime}\r\n\r\n').encode()
                     + open(path, 'rb').read() + b'\r\n')
        parts.append(f'--{boundary}--\r\n'.encode())
        req = urllib.request.Request('https://api.openai.com/v1/images/edits', b''.join(parts), {
            'Authorization': 'Bearer ' + key, 'Content-Type': 'multipart/form-data; boundary=' + boundary})
    else:
        fields['n'] = 1
        req = urllib.request.Request('https://api.openai.com/v1/images/generations', json.dumps(fields).encode(), {
            'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', 'replace')
        try:
            body = json.loads(body)['error']['message']
        except Exception:
            body = body[:400]
        raise RuntimeError(f'OpenAI error {e.code}: {body}') from None
    return base64.b64decode(data['data'][0]['b64_json'])


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, fmt, *args):
        if '/api/' in (args[0] if args else ''):
            sys.stderr.write('%s %s\n' % (time.strftime('%H:%M:%S'), fmt % args))

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def reply(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split('?')[0] == '/api/state':
            with LOCK:
                return self.reply(load_state())
        if self.path in ('/', ''):
            self.send_response(302)
            self.send_header('Location', '/tools/image_review/')
            return self.end_headers()
        return super().do_GET()

    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
            route = self.path.split('?')[0]
            if route == '/api/choose':
                with LOCK:
                    state = load_state()
                    if body.get('choice') is None:
                        state['choices'].pop(body['row'], None)
                    else:
                        state['choices'][body['row']] = body['choice']
                    save_state(state)
                return self.reply({'ok': True})
            if route == '/api/note':
                with LOCK:
                    state = load_state()
                    if body.get('note', '').strip():
                        state['notes'][body['row']] = body['note']
                    else:
                        state['notes'].pop(body['row'], None)
                    save_state(state)
                return self.reply({'ok': True})
            if route == '/api/generate':
                row = re.sub(r'[^A-Za-z0-9_]', '', body['row'])
                png = openai_image(body['prompt'], body.get('ref') or '', body.get('size'), body.get('quality'))
                os.makedirs(GENERATED, exist_ok=True)
                name = f'{row}_{time.strftime("%Y%m%d_%H%M%S")}.png'
                with open(os.path.join(GENERATED, name), 'wb') as f:
                    f.write(png)
                item = {'src': f'tools/image_review/generated/{name}', 'prompt': body['prompt'],
                        'ref': body.get('ref') or '', 'size': body.get('size'), 'quality': body.get('quality'),
                        'model': MODEL, 'time': time.strftime('%Y-%m-%d %H:%M:%S')}
                with LOCK:
                    state = load_state()
                    state['generated'].setdefault(body['row'], []).append(item)
                    save_state(state)
                return self.reply({'ok': True, 'item': item})
            if route == '/api/remove-generated':
                with LOCK:
                    state = load_state()
                    items = state['generated'].get(body['row'], [])
                    state['generated'][body['row']] = [i for i in items if i['src'] != body['src']]
                    if state['choices'].get(body['row'], {}).get('src') == body['src']:
                        state['choices'].pop(body['row'])
                    save_state(state)
                return self.reply({'ok': True})
            return self.reply({'error': 'unknown route'}, 404)
        except Exception as e:
            return self.reply({'error': str(e)}, 500)


if __name__ == '__main__':
    print(f'Picture review: http://127.0.0.1:{PORT}/tools/image_review/   (model {MODEL}, key {"found" if api_key() else "MISSING"})')
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
