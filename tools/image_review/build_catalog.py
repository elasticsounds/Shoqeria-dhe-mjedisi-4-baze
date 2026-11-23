#!/usr/bin/env python3
"""Builds tools/image_review/catalog.json: every picture in the PDF, the picture
the book shows for it now, and the picture in Flamur's first version, lined up.

    uv run --with opencv-python-headless --with numpy tools/image_review/build_catalog.py

PDF pictures are taken from the images embedded in the PDF (no text on them),
split into separate pictures where one page-sized image holds several.
Pictures are lined up by visual similarity, within neighbouring pages.
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PDF = os.environ.get('BOOK_PDF', os.path.expanduser(
    '~/Library/CloudStorage/OneDrive-UNICEF/OOI Learning Hub - ADT - Kaleidoscope/'
    'PDF Resources/Kosovo/Shoqeria-dhe-mjedisi-4-Baze.pdf'))
FLAMUR_COMMIT = 'ac0f3cf'
OUT_PDF = os.path.join(HERE, 'pdf')
OUT_PAGES = os.path.join(HERE, 'pages')
# bundle page -> PDF page where they differ
B2P = {84: 86, 85: 87, 86: 88, 87: 89, 88: 90, 89: 91, 90: 84, 91: 85, 128: None, 129: 128}


def pdf_page_of(bundle_page):
    return B2P.get(bundle_page, bundle_page)


def run(*args):
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout


def to_bgr(img):
    if img is None:
        return None
    if img.dtype != np.uint8:
        img = (img / 257).astype(np.uint8)
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.shape[2] == 4:
        a = img[:, :, 3:4].astype(np.float32) / 255
        return (img[:, :, :3] * a + 255 * (1 - a)).astype(np.uint8)
    return img


def save(img, path, longest=1400):
    h, w = img.shape[:2]
    if max(h, w) > longest:
        f = longest / max(h, w)
        img = cv2.resize(img, (round(w * f), round(h * f)), interpolation=cv2.INTER_AREA)
    cv2.imwrite(path, img)


def is_flat(crop):
    """A plain colour band or box rather than a picture."""
    h, w = crop.shape[:2]
    f = 160 / max(h, w)
    small = cv2.resize(crop, (max(8, round(w * f)), max(8, round(h * f))), interpolation=cv2.INTER_AREA)
    edges = cv2.Canny(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), 40, 120)
    inner = edges[3:-3, 3:-3]
    return inner.size == 0 or (inner > 0).mean() < 0.02


def is_plain(img):
    """White plus a single colour: a text box or header band."""
    small = cv2.resize(img, (96, 96), interpolation=cv2.INTER_AREA) >> 4
    codes = small[:, :, 0].astype(np.int32) * 256 + small[:, :, 1] * 16 + small[:, :, 2]
    counts = np.sort(np.bincount(codes.ravel()))[::-1]
    return counts[:2].sum() >= 0.97 * codes.size


def pictures_in(img, split=True):
    """Split one image (or a page canvas) into the separate pictures it holds."""
    h, w = img.shape[:2]
    ink = (img.min(axis=2) < 243).astype(np.uint8)
    if ink.mean() < 0.004:
        return []
    f = 400 / max(h, w)
    small = cv2.resize(ink * 255, (max(1, round(w * f)), max(1, round(h * f))), interpolation=cv2.INTER_AREA)
    small = (small > 8).astype(np.uint8)
    sh, sw = small.shape
    if not split:
        ys, xs = np.where(small)
        boxes = [(xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)]
    else:
        k = max(3, round(sw * 0.02)) | 1
        grown = cv2.dilate(small, np.ones((k, k), np.uint8))
        n, _, stats, _ = cv2.connectedComponentsWithStats(grown)
        boxes = []
        for i in range(1, n):
            x, y, bw, bh, area = stats[i]
            real = small[y:y + bh, x:x + bw].sum()
            if bw * bh < 0.012 * sw * sh or min(bw, bh) < 0.07 * sw or real < 0.006 * sw * sh:
                continue
            boxes.append((x, y, x + bw, y + bh))
        boxes.sort(key=lambda b: (b[1], b[0]))
    out = []
    for x0, y0, x1, y1 in boxes:
        pad = 3
        X0, Y0 = max(0, int((x0 - pad) / f)), max(0, int((y0 - pad) / f))
        X1, Y1 = min(w, int((x1 + pad) / f)), min(h, int((y1 + pad) / f))
        crop = img[Y0:Y1, X0:X1]
        if crop.shape[0] < 110 or crop.shape[1] < 110 or is_flat(crop):
            continue
        out.append(crop)
    return out


def placed_images(p, tmp):
    """Embedded images of page p with their position on the page (poppler units)."""
    base = os.path.join(tmp, 'x')
    subprocess.run(['pdftohtml', '-xml', '-q', '-f', str(p), '-l', str(p), PDF, base], capture_output=True)
    xml = open(base + '.xml', encoding='utf-8', errors='replace').read()
    page = re.search(r'<page[^>]*height="(\d+)" width="(\d+)"', xml)
    out = []
    for m in re.finditer(r'<image top="(-?\d+)" left="(-?\d+)" width="(-?\d+)" height="(-?\d+)" src="([^"]+)"', xml):
        top, left, w, h = (int(v) for v in m.groups()[:4])
        if w < 12 or h < 12:
            continue
        out.append({'box': (left, top, left + w, top + h), 'file': m.group(5)})
    return out, (int(page.group(2)), int(page.group(1)))


def extract_pdf_pictures():
    shutil.rmtree(OUT_PDF, ignore_errors=True)
    os.makedirs(OUT_PDF)
    os.makedirs(OUT_PAGES, exist_ok=True)
    pages = int(re.search(r'Pages:\s+(\d+)', run('pdfinfo', PDF)).group(1))
    found = []
    for p in range(1, pages + 1):
        page_jpg = os.path.join(OUT_PAGES, f'p{p:03d}.jpg')
        if not os.path.exists(page_jpg):
            subprocess.run(['pdftoppm', '-f', str(p), '-l', str(p), '-r', '90', '-jpeg', '-singlefile',
                            PDF, page_jpg[:-4]], check=True)
        with tempfile.TemporaryDirectory() as tmp:
            items, (pw, ph) = placed_images(p, tmp)
            # images that touch each other are tiles of one picture
            group = list(range(len(items)))

            def root(i):
                while group[i] != i:
                    i = group[i]
                return i
            for i, a in enumerate(items):
                for j in range(i + 1, len(items)):
                    A, B = a['box'], items[j]['box']
                    if A[0] <= B[2] + 1 and B[0] <= A[2] + 1 and A[1] <= B[3] + 1 and B[1] <= A[3] + 1:
                        group[root(j)] = root(i)
            clusters = {}
            for i, it in enumerate(items):
                clusters.setdefault(root(i), []).append(it)
            pics = []
            for members in clusters.values():
                x0 = min(m['box'][0] for m in members); y0 = min(m['box'][1] for m in members)
                x1 = max(m['box'][2] for m in members); y1 = max(m['box'][3] for m in members)
                if x1 - x0 < 45 or y1 - y0 < 45:
                    continue
                imgs = [(m, to_bgr(cv2.imread(m['file'], cv2.IMREAD_UNCHANGED))) for m in members]
                imgs = [(m, im) for m, im in imgs if im is not None and not is_plain(im)]
                if not imgs:
                    continue
                if len(imgs) == 1:
                    im = imgs[0][1]
                    big = (x1 - x0) > 0.6 * pw and (y1 - y0) > 0.45 * ph
                    got = pictures_in(im, split=big)
                else:
                    scale = min(3.2, max(im.shape[1] / max(1, m['box'][2] - m['box'][0]) for m, im in imgs))
                    canvas = np.full((round((y1 - y0) * scale), round((x1 - x0) * scale), 3), 255, np.uint8)
                    for m, im in imgs:
                        bx0, by0, bx1, by1 = m['box']
                        X0, Y0 = round((bx0 - x0) * scale), round((by0 - y0) * scale)
                        X1, Y1 = round((bx1 - x0) * scale), round((by1 - y0) * scale)
                        if X1 - X0 < 2 or Y1 - Y0 < 2:
                            continue
                        piece = cv2.resize(im, (X1 - X0, Y1 - Y0), interpolation=cv2.INTER_AREA)
                        canvas[Y0:Y1, X0:X1] = np.minimum(canvas[Y0:Y1, X0:X1], piece)
                    got = pictures_in(canvas, split=True)
                pics += [(y0, x0, g) for g in got]
            pics.sort(key=lambda t: (t[0], t[1]))
            n, seen = 0, []
            for _, _, pic in pics:
                sig = cv2.resize(pic, (24, 24), interpolation=cv2.INTER_AREA).astype(np.float32)
                if any(np.abs(s - sig).mean() < 4 for s in seen):
                    continue        # the same picture placed twice on the page
                seen.append(sig)
                n += 1
                name = f'p{p:03d}_{n}.png'
                save(pic, os.path.join(OUT_PDF, name))
                found.append({'kind': 'pdf', 'src': f'tools/image_review/pdf/{name}', 'pages': {p}})
        print(f'page {p}: {n} picture(s)', flush=True)
    return found


def book_images():
    """Pictures the lesson screens show now: file -> screens, description."""
    texts = json.load(open(os.path.join(ROOT, 'content/i18n/sq-XK/texts.json'), encoding='utf-8'))
    order = [p['section_id'] for p in json.load(open(os.path.join(ROOT, 'content/pages.json')))]
    out = {}
    for sid in order:
        html = open(os.path.join(ROOT, sid + '.html'), encoding='utf-8').read()
        for tag in re.findall(r'<img\b[^>]*>', html):
            src = re.search(r'src="((?:images|studio/assets)/[^"]+)"', tag)
            did = re.search(r'data-id="([^"]+)"', tag)
            # pictures carry a description id; the chapter symbols in studio/assets do not
            if not src or (not src.group(1).startswith('images/') and not did):
                continue
            e = out.setdefault(src.group(1), {'screens': [], 'ids': [], 'alt': ''})
            if sid not in e['screens']:
                e['screens'].append(sid)
            if did and did.group(1) not in e['ids']:
                e['ids'].append(did.group(1))
                e['alt'] = e['alt'] or texts.get(did.group(1), '')
    return out


SIFT = cv2.SIFT_create(nfeatures=1500, contrastThreshold=0.02)


def features(path):
    img = to_bgr(cv2.imread(path, cv2.IMREAD_UNCHANGED))
    if img is None:
        return None
    h, w = img.shape[:2]
    f = 520 / max(h, w)
    if f < 1:
        img = cv2.resize(img, (round(w * f), round(h * f)), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    kp, des = SIFT.detectAndCompute(gray, None)
    return kp, des, cv2.GaussianBlur(gray, (0, 0), 2)


def similarity(a, b):
    """(feature matches agreeing on one placement, how alike the pictures are once laid over each other)."""
    if a is None or b is None or a[1] is None or b[1] is None or len(a[0]) < 8 or len(b[0]) < 8:
        return 0, 0.0
    pairs = cv2.BFMatcher().knnMatch(a[1], b[1], k=2)
    good = [m for m, n in (p for p in pairs if len(p) == 2) if m.distance < 0.72 * n.distance]
    if len(good) < 8:
        return 0, 0.0
    src = np.float32([a[0][m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([b[0][m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 6.0)
    if H is None or mask is None:
        return 0, 0.0
    inliers = int(mask.sum())
    if inliers < 10:
        return inliers, 0.0
    hb, wb = b[2].shape
    warped = cv2.warpPerspective(a[2], H, (wb, hb), flags=cv2.INTER_LINEAR, borderValue=0)
    valid = cv2.warpPerspective(np.full(a[2].shape, 255, np.uint8), H, (wb, hb), borderValue=0) > 200
    area = int(valid.sum())
    if area < 0.2 * min(a[2].size, b[2].size) or area > 4 * a[2].size:
        return inliers, 0.0
    x, y = warped[valid].astype(np.float32), b[2][valid].astype(np.float32)
    if x.std() < 2 or y.std() < 2:
        return inliers, 0.0
    return inliers, float(np.corrcoef(x, y)[0, 1])


def near(a, b):
    for x in a['pages']:
        for y in b['pages']:
            if abs(x - y) <= 2 or (84 <= x <= 91 and 84 <= y <= 91):
                return True
    return False


def main():
    nodes = extract_pdf_pictures()
    book = book_images()
    flamur_files = [f for f in run('git', '-C', ROOT, 'ls-tree', '-r', '--name-only', FLAMUR_COMMIT, 'images/').split()]
    # the pictures his pages actually showed are in studio/assets (the small files there are icons)
    for f in run('git', '-C', ROOT, 'ls-tree', '-r', '--name-only', FLAMUR_COMMIT, 'studio/assets/').split():
        if re.match(r'studio/assets/pg\d{3}', f) and f.lower().endswith(('.png', '.jpg', '.jpeg')) and os.path.exists(os.path.join(ROOT, f)):
            im = cv2.imread(os.path.join(ROOT, f), cv2.IMREAD_UNCHANGED)
            if im is not None and max(im.shape[:2]) >= 500:
                flamur_files.append(f)
    by_src = {}
    for src, info in book.items():
        pages = {pdf_page_of(int(s[2:5])) for s in info['screens']} - {None}
        m = re.match(r'(?:images|studio/assets)/pg(\d{3})', src)
        if m and pdf_page_of(int(m.group(1))):
            pages.add(pdf_page_of(int(m.group(1))))
            pages.add(int(m.group(1)))
        node = {'kind': 'book', 'src': src, 'pages': pages, 'book': info, 'flamur': src in flamur_files,
                'from_pdf': '_pdf' in src}
        nodes.append(node)
        by_src[src] = node
    for src in flamur_files:
        if src in by_src or not os.path.exists(os.path.join(ROOT, src)):
            continue
        n = int(re.match(r'(?:images|studio/assets)/pg(\d{3})', src).group(1))
        nodes.append({'kind': 'flamur', 'src': src, 'pages': {n, pdf_page_of(n) or n}})

    print('features…', flush=True)
    for n in nodes:
        n['f'] = features(os.path.join(ROOT, n['src']))

    parent = list(range(len(nodes)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    scores = {}
    log = []
    for i, a in enumerate(nodes):
        for j in range(i + 1, len(nodes)):
            b = nodes[j]
            if a['kind'] == b['kind'] == 'pdf' or not near(a, b):
                continue
            s, corr = similarity(a['f'], b['f'])
            if s >= 10:
                log.append(f"{s}\t{corr:.2f}\t{a['src']}\t{b['src']}")
            if s >= 12 and corr >= 0.55:
                scores[(i, j)] = s * corr
    open(os.path.join(HERE, 'match_log.tsv'), 'w').write('\n'.join(log))
    # strongest links first; never put two different PDF pictures in one row
    has_pdf = {i: {i} if n['kind'] == 'pdf' else set() for i, n in enumerate(nodes)}
    for (i, j), s in sorted(scores.items(), key=lambda kv: -kv[1]):
        ri, rj = find(i), find(j)
        if ri == rj or (has_pdf[ri] and has_pdf[rj]):
            continue
        parent[rj] = ri
        has_pdf[ri] |= has_pdf[rj]

    groups = {}
    for i, n in enumerate(nodes):
        groups.setdefault(find(i), []).append(n)

    rows = []
    for members in groups.values():
        pdf = [m for m in members if m['kind'] == 'pdf']
        books = [m for m in members if m['kind'] == 'book']
        flam = [m for m in members if m['kind'] == 'flamur'] + [m for m in books if m['flamur']]
        if not pdf:      # a cut I made from the PDF page counts as the PDF picture
            pdf = [m for m in books if m['from_pdf']]
        if pdf and pdf[0]['kind'] == 'pdf':
            page = min(pdf[0]['pages'])
        elif books:
            page = min(pdf_page_of(int(s[2:5])) or 999 for b in books for s in b['book']['screens'])
        else:
            page = min(min(m['pages']) for m in members)
        key = (pdf or books or flam)[0]['src']
        rows.append({
            'id': re.sub(r'[^A-Za-z0-9]+', '_', os.path.splitext(os.path.basename(key))[0]),
            'page': page,
            'pdf': [m['src'] for m in pdf],
            'book': [{'src': m['src'], 'screens': m['book']['screens'], 'ids': m['book']['ids']} for m in books],
            'flamur': [{'src': m['src'], 'same_as_book': m['kind'] == 'book'} for m in flam],
            'alt': next((m['book']['alt'] for m in books if m['book']['alt']), ''),
        })
    rows.sort(key=lambda r: (r['page'], r['id']))
    ids = set()
    for r in rows:
        while r['id'] in ids:
            r['id'] += '_b'
        ids.add(r['id'])
    json.dump({'rows': rows}, open(os.path.join(HERE, 'catalog.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    c = lambda k: sum(1 for r in rows if r[k])
    print(f'{len(rows)} rows: {c("pdf")} with a PDF picture, {c("book")} in the book, {c("flamur")} with a Flamur picture')
    print('PDF only:', sum(1 for r in rows if r['pdf'] and not r['book']),
          '| book but no PDF:', sum(1 for r in rows if r['book'] and not r['pdf']),
          '| Flamur only:', sum(1 for r in rows if r['flamur'] and not r['book'] and not r['pdf']))


if __name__ == '__main__':
    sys.exit(main())
