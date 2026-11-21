#!/usr/bin/env python3
"""Cut illustrations for the lesson screens.

  python3 tools/imgtool.py pdf PAGE X0 Y0 X1 Y1 OUT.png
      Cut a region out of PDF page PAGE. Coordinates are pixels of the 80-dpi
      page preview (710 x 962), i.e. what you see in pg-NNN.jpg.

  python3 tools/imgtool.py img SRC X0 Y0 X1 Y1 OUT.png
      Cut a region out of an existing image. Coordinates are fractions (0-1) of
      the source width/height, e.g. 0 0.27 1 0.93.

  python3 tools/imgtool.py view FILE
      Write a small preview and print its path, so the result can be looked at.

OUT is relative to the repository root (normally images/pgNNN_xxx.png).
Results are scaled down to at most 1600 px on the long side.
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = os.environ.get('BOOK_PDF', '/Users/eliasc/Library/CloudStorage/OneDrive-UNICEF/'
                     'OOI Learning Hub - ADT - Kaleidoscope/PDF Resources/Kosovo/Shoqeria-dhe-mjedisi-4-Baze.pdf')
PREVIEWS = os.environ.get('PREVIEW_DIR', '/tmp')
SCALE = 220 / 80


def size(path):
    out = subprocess.run(['sips', '-g', 'pixelWidth', '-g', 'pixelHeight', path],
                         capture_output=True, text=True, check=True).stdout
    return (int(re.search(r'pixelWidth: (\d+)', out).group(1)),
            int(re.search(r'pixelHeight: (\d+)', out).group(1)))


def shrink(path):
    w, h = size(path)
    if max(w, h) > 1600:
        subprocess.run(['sips', '-Z', '1600', path], capture_output=True, check=True)
    print(path, 'x'.join(map(str, size(path))), f'{os.path.getsize(path) // 1024}KB')


def main(argv):
    cmd = argv[0]
    if cmd == 'pdf':
        page = int(argv[1])
        x0, y0, x1, y1 = (float(v) * SCALE for v in argv[2:6])
        out = os.path.join(ROOT, argv[6])
        subprocess.run(['pdftoppm', '-f', str(page), '-l', str(page), '-r', '220', '-x', str(round(x0)),
                        '-y', str(round(y0)), '-W', str(round(x1 - x0)), '-H', str(round(y1 - y0)),
                        '-png', '-singlefile', PDF, out[:-4]], check=True)
        shrink(out)
    elif cmd == 'img':
        src = os.path.join(ROOT, argv[1])
        w, h = size(src)
        x0, y0, x1, y1 = (float(v) for v in argv[2:6])
        out = os.path.join(ROOT, argv[6])
        cw, ch = round((x1 - x0) * w), round((y1 - y0) * h)
        # sips refuses a crop that ends exactly on the edge, so stay one pixel inside
        cw, ch = min(cw, w - round(x0 * w) - 1), min(ch, h - round(y0 * h) - 1)
        subprocess.run(['sips', '-c', str(ch), str(cw), '--cropOffset', str(round(y0 * h)), str(round(x0 * w)),
                        src, '--out', out], capture_output=True, check=True)
        got = size(out)
        if abs(got[0] - cw) > 2 or abs(got[1] - ch) > 2:
            sys.exit(f'crop failed: wanted {cw}x{ch}, got {got[0]}x{got[1]}')
        shrink(out)
    elif cmd == 'view':
        src = os.path.join(ROOT, argv[1])
        out = os.path.join(PREVIEWS, re.sub(r'[^A-Za-z0-9_.-]', '_', argv[1]) + '.preview.png')
        subprocess.run(['sips', '-Z', '700', '-s', 'format', 'png', src, '--out', out], capture_output=True, check=True)
        print(out)
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1:])
