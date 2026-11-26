#!/usr/bin/env python3
"""Compares the pictures on the ADT screens with the pictures of the 2026 PDF (and the 2024 PDF).
   uv run --with opencv-python-headless --with numpy python3 tools/edition_check/check_images.py  -> image_check.json"""
import os, sys, json, re, glob, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'image_review'))
os.environ['BOOK_PDF'] = os.path.join(ROOT, 'tools/page_map/Shoqeria dhe mjedisi 4 Baze.pdf')
import build_catalog as bc
import cv2, numpy as np
bc.OUT_PDF = os.path.join(HERE, 'pdf2026'); bc.OUT_PAGES = os.path.join(HERE, 'pages2026')
os.chdir(ROOT)
if not glob.glob(bc.OUT_PDF + '/*.png'):
    bc.extract_pdf_pictures()
P24 = {84: 90, 85: 91, 86: 84, 87: 85, 88: 86, 89: 87, 90: 88, 91: 89, 128: 129}   # 2024 page -> 2026 page
def pg(name): return int(re.search(r'p(\d{3})', os.path.basename(name)).group(1))
pics26 = {f: pg(f) for f in sorted(glob.glob('tools/edition_check/pdf2026/*.png'))}
pics24 = {f: P24.get(pg(f), pg(f)) for f in sorted(glob.glob('tools/image_review/pdf/p[0-9]*.png'))}
os.makedirs(HERE + '/pages2026_hi', exist_ok=True)
def page_feat(p):
    f = f'{HERE}/pages2026_hi/p{p:03d}.jpg'
    if not os.path.exists(f):
        subprocess.run(['pdftoppm', '-f', str(p), '-l', str(p), '-r', '100', '-jpeg', '-singlefile', os.environ['BOOK_PDF'], f[:-4]], check=True)
    gray = cv2.cvtColor(cv2.imread(f), cv2.COLOR_BGR2GRAY)
    kp, des = cv2.SIFT_create(nfeatures=6000, contrastThreshold=0.02).detectAndCompute(gray, None)
    return kp, des, cv2.GaussianBlur(gray, (0, 0), 2)
F = {}
def feat(f):
    if f not in F: F[f] = bc.features(f)
    return F[f]
PF = {}
def pfeat(p):
    if p not in PF: PF[p] = page_feat(p)
    return PF[p]
def ok(s): return s[0] >= 12 and s[1] >= 0.55
book = bc.book_images(); out = {'book': [], 'pdf2026': []}
used26 = {}
for src, e in book.items():
    pages = sorted({int(s[2:5]) for s in e['screens']})
    cand = lambda d: [f for f, p in d.items() if any(abs(p - q) <= 1 for q in pages)]
    a = feat(src)
    b26 = max(((bc.similarity(a, feat(f)), f) for f in cand(pics26)), default=((0, 0.0), ''))
    b24 = max(((bc.similarity(a, feat(f)), f) for f in cand(pics24)), default=((0, 0.0), ''))
    bpg = max(((bc.similarity(a, pfeat(p)), p) for q in pages for p in (q, q + 1) if 1 <= p <= 129), default=((0, 0.0), 0))
    in26 = ok(b26[0]) or ok(bpg[0])
    for f in cand(pics26):
        if ok(bc.similarity(a, feat(f))): used26.setdefault(f, []).append(src)
    out['book'].append(dict(src=src, screens=e['screens'], ids=e['ids'], alt=e['alt'], in2026=in26, in2024=ok(b24[0]),
                            best2026=b26[1], s2026=[b26[0][0], round(b26[0][1], 2)], page2026=bpg[1], spage=[bpg[0][0], round(bpg[0][1], 2)],
                            best2024=b24[1], s2024=[b24[0][0], round(b24[0][1], 2)]))
    print(src, in26, ok(b24[0]), flush=True)
for f, p in pics26.items():
    a = feat(f)
    b24 = max(((bc.similarity(a, feat(g)), g) for g, q in pics24.items() if abs(q - p) <= 1), default=((0, 0.0), ''))
    out['pdf2026'].append(dict(src=f, page=p, in_adt=used26.get(f, []), in2024=ok(b24[0]), best2024=b24[1]))
json.dump(out, open(HERE + '/image_check.json', 'w'), ensure_ascii=False, indent=1)
B = out['book']; print(len(B), 'ADT pictures:', sum(b['in2026'] for b in B), 'match 2026;', sum(b['in2024'] and not b['in2026'] for b in B), '2024 only;', sum(not b['in2024'] and not b['in2026'] for b in B), 'neither')
Q = out['pdf2026']; print(len(Q), '2026 pictures:', sum(bool(q['in_adt']) for q in Q), 'in ADT;', sum(not q['in_adt'] for q in Q), 'not matched')
