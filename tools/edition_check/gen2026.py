#!/usr/bin/env python3
"""Generates the replacement pictures for the 2026 edition (pages 9 and 65) with the OpenAI image API.
Usage: gen2026.py <job> [n]   -> writes tools/edition_check/generated/<job>_<k>.png"""
import base64, json, os, re, sys, urllib.request, urllib.error, uuid, concurrent.futures
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
MODEL = 'gpt-image-2.6-flare'
JOBS = {
 'p009': dict(refs=['tools/edition_check/pdf2026/p009_1.png'], size='1024x1024', prompt=(
   'Redraw this illustration for a grade 4 school textbook in Kosovo. Keep the same scene, composition, brick apartment building, '
   'balconies, characters, clothing, colours, dogs and cartoon illustration style as the reference picture. Do not add any text. '
   'The changed persons take part in the scene like everyone else, drawn naturally and respectfully.\nChange only this: '
   'in the group of children talking in the street, the girl in the yellow trousers sits in a wheelchair and chats with her friends; '
   'the boy with the red cap on the right is blind: he holds a white cane and his big dog wears a guide-dog harness; '
   'on the middle-floor balcony on the right, the grandmother sits in a wheelchair instead of the armchair.')),
 'p065': dict(refs=['images/pg065_im002.jpg', 'tools/edition_check/pdf2026/p065_2.png'], size='1024x1024', prompt=(
   'Draw a new illustration for a grade 4 school textbook in Kosovo. Use exactly the drawing style of the FIRST reference image '
   '(the girl and grandmother on the sofa): flat vector illustration, flat solid colours without shading or texture, simple rounded shapes, '
   'simple minimal faces, plain white background with one flat green oval of ground under the figures. '
   'The SECOND reference image only shows the scene and the flag; do not copy its painted style. '
   'Scene: two happy boys hold up the flag of Kosovo together. One boy stands and holds the flagpole with both hands; the other boy sits '
   'in a wheelchair and holds the free edge of the flag with one raised hand. Both look at the flag and smile. '
   'The flag must be accurate: a plain blue field, the golden-yellow map silhouette of Kosovo in the centre, and exactly six white '
   'five-pointed stars in a gentle arc above the map. No text, no letters, no frame.')),
}
def key():
    k = os.environ.get('OPENAI_API_KEY')
    if not k:
        f = re.findall(r'^export OPENAI_API_KEY=[\'"]?([^\'"\n]+)', open(os.path.expanduser('~/.zshrc')).read(), re.M); k = f[-1]
    return k
def gen(job, k):
    j = JOBS[job]; b = uuid.uuid4().hex; parts = []
    for n, v in {'model': MODEL, 'prompt': j['prompt'], 'n': '1', 'size': j['size'], 'quality': 'high'}.items():
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{n}"\r\n\r\n{v}\r\n'.encode())
    for r in j['refs']:
        p = os.path.join(ROOT, r); mime = 'image/jpeg' if p.endswith('.jpg') else 'image/png'
        parts.append((f'--{b}\r\nContent-Disposition: form-data; name="image[]"; filename="{os.path.basename(p)}"\r\nContent-Type: {mime}\r\n\r\n').encode() + open(p, 'rb').read() + b'\r\n')
    parts.append(f'--{b}--\r\n'.encode())
    req = urllib.request.Request('https://api.openai.com/v1/images/edits', b''.join(parts), {'Authorization': 'Bearer ' + key(), 'Content-Type': 'multipart/form-data; boundary=' + b})
    try:
        data = json.load(urllib.request.urlopen(req, timeout=900))
    except urllib.error.HTTPError as e:
        return f'{job}_{k}: HTTP {e.code} {e.read().decode("utf-8","replace")[:300]}'
    out = os.path.join(HERE, 'generated', f'{job}_{k}.png'); os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'wb').write(base64.b64decode(data['data'][0]['b64_json'])); return out
todo = [(a.split(':')[0], k) for a in sys.argv[1:] for k in range(1, int(a.split(':')[1]) + 1)]
with concurrent.futures.ThreadPoolExecutor(4) as pool:
    for r in pool.map(lambda t: gen(*t), todo): print(r, flush=True)
