#!/usr/bin/env python3
"""One-off batch: asks the review server for an inclusive variant of selected pictures.
The changes were chosen picture by picture; pictures where a change would not make sense are not listed."""
import concurrent.futures, json, os, subprocess, sys, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
CHANGES = {
 'pg009_im001_pdf': 'among the children in the street, one child uses a wheelchair and plays with the others, and one of the adult residents is an older person walking with a white cane',
 'pg011_im001_pdf': 'one of the three dancing children dances sitting in a wheelchair, arms raised and smiling like the others',
 'pg011_im002_pdf': 'add a girl in sports clothes playing football together with the boy, running for the same ball',
 'p012_1': 'one of the two pupils carrying gift boxes uses a wheelchair and carries her box on her lap',
 'pg015_im001': 'one of the pupils listening at the desks sits in a wheelchair at the desk',
 'p017_1': 'on the television screen, add a small inset in the corner showing a sign-language interpreter signing next to the news presenter',
 'p018_4': 'one of the pupils in the school scene uses a wheelchair and wears a mask like the others',
 'p019_1': 'one of the two pupils crossing the road at the zebra crossing uses a wheelchair, with the school bag on the back of the chair',
 'p021_1': 'one of the children listening to the doctor sits in a wheelchair',
 'p026_1': 'one of the four pupils at the table sits in a wheelchair and takes part in the discussion',
 'p033_1': 'add a boy sitting in a wheelchair next to the sofa as one more child of the family, thinking and worried like the others',
 'p039_1': 'one of the two boys stands with forearm crutches, still talking cheerfully with his friend next to the football',
 'p042_1': 'one of the five children at the table has a visible hearing aid behind the ear and another sits in a wheelchair',
 'p043_1': 'one of the six children uses a wheelchair and another child holds a white cane; all stand together as one group',
 'p044_1': 'one of the two pupils sits in a wheelchair at the desk',
 'p045_1': 'one of the family members at the table, the grandfather, sits in a wheelchair at the table and joins the conversation',
 'p046_1': 'one of the five pupils at the table sits in a wheelchair; keep the pupil speaking with a raised hand',
 'p047_1': 'one of the three pupils talking with the teacher stands with forearm crutches',
 'p048_1': 'one of the four pupils sitting in the circle sits in a wheelchair instead of a chair',
 'pg050_im004': 'one of the two children of the family uses a wheelchair and sits in it next to the others under the roof symbol',
 'p051_1': 'one of the adults at the family table sits in a wheelchair and takes part in the discussion',
 'p052_1': 'add a girl in a wheelchair waiting at the bus stop to board the bus, and show a small wheelchair-access symbol by the bus door',
 'p053_1': 'one of the two pupils stands with forearm crutches',
 'p058_1': 'one of the four pupils at the table sits in a wheelchair',
 'p058_2': 'one of the classmates listening has a visible hearing aid behind the ear, and another one sits in a wheelchair',
 'p058_3': 'one of the four pupils has a prosthetic leg visible below shorts, standing and talking like the others',
 'p067_1': 'the border police officer checking the passport is a woman in the same uniform',
 'p085_1': 'one of the children celebrating at the birthday table sits in a wheelchair, laughing with the others',
 'p094_1': 'one of the four young tourists uses a wheelchair, dressed formally and smiling like the others',
 'p106_1': 'one of the pupils listening in the classroom sits in a wheelchair at the desk',
 'p110_1': 'the man walking the dog is blind: he holds a white cane and the dog wears a guide-dog harness',
 'p111_1': 'the child next to the recycling bins uses a wheelchair and is putting a bottle into one of the bins',
 'p113_1': 'one of the three children cleaning the river bank has a prosthetic leg, working alongside the others',
 'p114_1': 'one of the three pupils at the desks sits in a wheelchair at the desk',
 'p116_1': 'one of the three pupils at the table has forearm crutches leaning against the chair',
 'p118_1': 'the bus has its ramp lowered at the middle door and a person in a wheelchair is boarding; add a wheelchair-access symbol on the bus',
 'p121_1': 'one of the five pupils sits in a wheelchair at the table',
}
PROMPT = ('Redraw this illustration for a grade 4 school textbook in Kosovo. Keep the same scene, composition, characters, '
          'clothing, colours, background and flat illustration style as the reference picture. Do not add any text. '
          'The changed person takes part in the scene like everyone else, drawn naturally and respectfully.\nChange only this: {}')

def size_for(path):
    out = subprocess.run(['sips', '-g', 'pixelWidth', '-g', 'pixelHeight', path], capture_output=True, text=True).stdout.split()
    a = int(out[out.index('pixelWidth:') + 1]) / int(out[out.index('pixelHeight:') + 1])
    return '1536x1024' if a > 1.25 else '1024x1536' if a < 0.8 else '1024x1024'

def main():
    rows = {r['id']: r for r in json.load(open(os.path.join(HERE, 'catalog.json')))['rows']}
    state = json.load(urllib.request.urlopen('http://127.0.0.1:8770/api/state'))
    todo = [i for i in (sys.argv[1:] or CHANGES) if not state['generated'].get(i)]
    missing = [i for i in todo if i not in rows]
    if missing: print('unknown rows:', missing)
    def work(i):
        r = rows[i]
        ref = (r['pdf'] or [b['src'] for b in r['book']])[0]
        body = json.dumps({'row': i, 'prompt': PROMPT.format(CHANGES[i]), 'ref': ref,
                           'size': size_for(os.path.join(ROOT, ref)), 'quality': 'medium'}).encode()
        for attempt in range(2):
            try:
                req = urllib.request.Request('http://127.0.0.1:8770/api/generate', body, {'Content-Type': 'application/json'})
                json.load(urllib.request.urlopen(req, timeout=600)); return i, 'ok'
            except Exception as e:
                err = getattr(e, 'read', lambda: b'')().decode('utf-8', 'replace')[:300] or str(e)
        return i, err
    with concurrent.futures.ThreadPoolExecutor(6) as pool:
        for i, res in pool.map(work, [i for i in todo if i in rows]):
            print(i, res, flush=True)

main()
