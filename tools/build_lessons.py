#!/usr/bin/env python3
"""Builds every lesson screen of the ADT from data files and one shared template.

    python3 tools/build_lessons.py                 build the whole book
    python3 tools/build_lessons.py --only FILE     write only the screens of one spec file
                                                   (for previewing; nothing else is touched)

Content lives in tools/specs/*.json (see tools/specs/README.md for the format).
Styling lives in book-design/lesson.css. Text is never typed into a page: every
string comes from content/i18n/sq-XK/texts.json by its text ID (a spec file may
add new IDs under "texts").

A full build also rewrites the reading order (content/pages.json), renumbers
page-section-id in every page, and keeps toc.json, the contents pages,
imsmanifest.xml and assets/offline-preloader.js in sync.
"""
import glob
import html
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANG = 'sq-XK'
SPEC_DIR = os.path.join(ROOT, 'tools', 'specs')


def read(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def write(rel, text):
    with open(os.path.join(ROOT, rel), 'w', encoding='utf-8') as f:
        f.write(text)


def load(rel):
    return json.loads(read(rel))


def dump(rel, data, newline=False):
    write(rel, json.dumps(data, ensure_ascii=False, indent=2) + ('\n' if newline else ''))


TEXTS = load(f'content/i18n/{LANG}/texts.json')
SPEECH = load(f'content/i18n/{LANG}/speech_texts.json')


def esc(text):
    return html.escape(text, quote=False)


def attr(text):
    return html.escape(text, quote=True)


class SpecError(Exception):
    pass


def text_of(text_id):
    if text_id not in TEXTS:
        raise SpecError(f'unknown text id: {text_id}')
    return TEXTS[text_id]


USED = set()


def node(tag, text_id, cls=None, extra=''):
    USED.add(text_id)
    c = f' class="{cls}"' if cls else ''
    return f'<{tag}{c}{extra} data-id="{text_id}">{esc(text_of(text_id))}</{tag}>'


def paragraphs(groups, cls=None):
    """groups: list of paragraphs, each a list of sentence text IDs."""
    c = f' class="{cls}"' if cls else ''
    out = []
    for g in groups:
        if isinstance(g, str):
            g = [g]
        out.append(f'<p{c}>' + ' '.join(node('span', i) for i in g) + '</p>')
    return '\n'.join(out)


_dims = {}


def dims(rel):
    if rel not in _dims:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            raise SpecError(f'missing image: {rel}')
        out = subprocess.run(['sips', '-g', 'pixelWidth', '-g', 'pixelHeight', path],
                             capture_output=True, text=True, check=True).stdout
        _dims[rel] = (int(re.search(r'pixelWidth: (\d+)', out).group(1)),
                      int(re.search(r'pixelHeight: (\d+)', out).group(1)))
    return _dims[rel]


IMAGES = set()


def img(fig):
    w, h = dims(fig['src'])
    IMAGES.add(fig['src'])
    USED.add(fig['id'])
    return (f'<img src="{fig["src"]}" width="{w}" height="{h}" data-id="{fig["id"]}" '
            f'alt="{attr(text_of(fig["id"]))}">')


def figure(fig):
    cap = node('figcaption', fig['caption']) if fig.get('caption') else ''
    return f'<figure class="lx-figure">{img(fig)}{cap}</figure>'


def svg(body):
    return f'<svg viewBox="0 0 48 48" aria-hidden="true" focusable="false">{body}</svg>'


LINE = 'fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"'
BOOK = svg(f'<path {LINE} d="M24 13c-4-3-10-4-17-3v26c7-1 13 0 17 3 4-3 10-4 17-3V10c-7-1-13 0-17 3zM24 13v26"/>')
PEN = svg(f'<path {LINE} d="M8 40l3-11L31 9l8 8-20 20zM27 13l8 8"/>')

# The chapter symbols are the book's own, taken from its contents pages.
CHAPTERS = [(8, 14, 'pg003_sec001-people'), (15, 21, 'pg003_sec001-scales'), (22, 43, 'pg003_sec001-heart'),
            (44, 59, 'pg003_sec001-speech'), (60, 68, 'pg003_sec001-kosovo'), (69, 81, 'pg004_sec001-hourglass'),
            (82, 91, 'pg004_sec001-frame'), (92, 109, 'pg004_sec001-wheat'), (110, 127, 'pg004_sec001-leaf')]


def chapter_icon(page):
    for first, last, name in CHAPTERS:
        if first <= page <= last:
            return f'studio/assets/{name}.png'
    return None


def head(screen):
    title = node('h1', screen['title'], 'lx-title', ' id="lx-title"')
    if not screen.get('chapter'):
        return f'<header class="lx-head lx-head--plain">{title}</header>'
    icon = chapter_icon(screen['page'])
    tile = (f'<span class="lx-head__icon" aria-hidden="true"><img src="{icon}" alt=""></span>' if icon else '')
    plain = '' if icon else ' lx-head--noicon'
    return (f'<header class="lx-head{plain}">{tile}<div class="lx-head__text">'
            f'{node("p", screen["chapter"], "lx-chapter")}{title}</div></header>')


# ---------------------------------------------------------------- blocks

class Ctx:
    """Per-screen state: numbering of answer fields and whether answers are checked."""

    def __init__(self):
        self.items = 0
        self.activity = False
        self.answers = {}
        self.kind = None

    def field(self):
        self.items += 1
        self.activity = True
        return self.items


def with_figure(body, fig, place=None):
    if not fig:
        return body
    w, h = dims(fig['src'])
    if place is None:
        place = 'below' if w / h > 1.7 else 'side'
    if place == 'side':
        return f'<div class="lx-split lx-split--side">\n{body}\n{figure(fig)}\n</div>'
    return f'{body}\n{figure(fig)}'


def b_story(b, ctx):
    parts = []
    if b.get('tag'):
        second = re.search(r'\b2\b', text_of(b['tag']))
        parts.append(node('p', b['tag'], 'lx-tag lx-tag--2' if second else 'lx-tag'))
    parts.append(paragraphs(b['paras']))
    if b.get('prompt'):
        parts.append(node('p', b['prompt'], 'lx-prompt'))
    prose = '<div class="lx-prose">\n' + '\n'.join(parts) + '\n</div>'
    return with_figure(prose, b.get('figure'), b.get('place'))


def b_text(b, ctx):
    cls = 'lx-prompt' if b.get('style') == 'prompt' else None
    prose = '<div class="lx-prose">\n' + paragraphs(b['paras'], cls) + '\n</div>'
    return with_figure(prose, b.get('figure'), b.get('place'))


def b_gallery(b, ctx):
    figs = b['figures']
    size = len(figs) if len(figs) <= 4 else 'many'
    return (f'<div class="lx-gallery lx-gallery--{size}">\n'
            + '\n'.join(figure(f) for f in figs) + '\n</div>')


def answer_box(ctx, label_html, rows=2):
    i = ctx.field()
    return ('<div class="lx-q">' + label_html.replace('{for}', f'lx-answer-{i}')
            + f'<div><textarea id="lx-answer-{i}" class="lx-input lx-answer" rows="{rows}" '
              f'data-activity-item="item-{i}" data-aria-id="aria-{i}"></textarea></div></div>')


DASH = re.compile(r'^[–—-]\s+')
FOLLOW_UP = re.compile(r'^(Pse|Si|Ku|Kur)\?$')


def undash(text_id):
    """List items and questions are drawn with their own bullet, so a typed dash is dropped."""
    for key in (text_id, text_id + '_easy_read'):
        for store in (TEXTS, SPEECH):
            if key in store and DASH.match(store[key]):
                store[key] = DASH.sub('', store[key])


def question_groups(ids):
    """A bare follow-up such as "Pse?" belongs to the question before it, not in a box of its own.
    An entry may also be an explicit list of IDs that form one question."""
    groups = []
    for entry in ids:
        if isinstance(entry, list):
            groups.append(list(entry))
        elif groups and FOLLOW_UP.match(DASH.sub('', text_of(entry)).strip()):
            groups[-1].append(entry)
        else:
            groups.append([entry])
    return groups


def question_label(group):
    for i in group:
        undash(i)
    if len(group) == 1:
        return node('label', group[0], extra=' for="{for}"')
    return '<label for="{for}">' + ' '.join(node('span', i) for i in group) + '</label>'


def b_questions(b, ctx):
    """Each question gets an answer box (the reader's open-ended activity)."""
    items = [answer_box(ctx, question_label(g)) for g in question_groups(b['ids'])]
    box = ('<div class="lx-box lx-box--questions">\n'
           '<span class="lx-badge lx-badge--q" aria-hidden="true">?</span>\n'
           '<div class="lx-box__body lx-qlist">\n' + '\n'.join(items) + '\n</div>\n</div>')
    return with_figure(box, b.get('figure'), b.get('place', 'side' if b.get('figure') else None))


def b_info(b, ctx):
    return ('<aside class="lx-box lx-box--info" aria-label="Për të mësuar">\n'
            f'<span class="lx-badge" aria-hidden="true">{BOOK}</span>\n'
            f'<div class="lx-box__body">\n{paragraphs(b["paras"])}\n</div>\n</aside>')


def b_keywords(b, ctx):
    ids = b['ids']
    if len(ids) == 2:
        return f'<p class="lx-keywords">{node("strong", ids[0])} {node("span", ids[1])}</p>'
    return node('p', ids[0], 'lx-keywords')


def b_note(b, ctx):
    """Coloured box: advice lists, group tasks, closing remarks."""
    parts = []
    if b.get('title'):
        parts.append(node('h2', b['title'], 'lx-note__title'))
    if b.get('paras'):
        parts.append(paragraphs(b['paras']))
    if b.get('items'):
        for i in b['items']:
            undash(i)
        parts.append('<ul class="lx-list" role="list">\n' + '\n'.join(node('li', i) for i in b['items']) + '\n</ul>')
    colour = b.get('color', 'plain')
    return (f'<div class="lx-box lx-box--note lx-box--{colour}"><div class="lx-box__body">\n'
            + '\n'.join(parts) + '\n</div></div>')


def b_write(b, ctx):
    """A writing task: instruction plus one or more answer boxes."""
    parts = []
    prompt_ids = [i for g in b.get('prompt', []) for i in ([g] if isinstance(g, str) else g)]
    for i in prompt_ids:
        undash(i)
    if b.get('prompt'):
        parts.append(paragraphs(b['prompt'], 'lx-prompt'))
    fields = b.get('fields') or [{} for _ in range(b.get('count', 1))]
    base = ' '.join(text_of(i) for i in prompt_ids) or 'Përgjigjja jote'
    for n, f in enumerate(fields, 1):
        if f.get('label'):
            label = node('label', f['label'], extra=' for="{for}"')
        else:
            suffix = f' ({n})' if len(fields) > 1 else ''
            label = f'<label class="lx-sr" for="{{for}}">{esc(base + suffix)}</label>'
        parts.append(answer_box(ctx, label, b.get('rows', 3)))
    return ('<div class="lx-box lx-box--task">\n'
            f'<span class="lx-badge" aria-hidden="true">{PEN}</span>\n'
            '<div class="lx-box__body lx-qlist">\n' + '\n'.join(parts) + '\n</div>\n</div>')


def b_table_write(b, ctx):
    """A table the learner fills in. rows: row-header text IDs, or row_count for blank rows.
    prefilled: {"row,col": [text ids]} for cells the book already filled (1-based)."""
    cols = b['columns']
    rows = b.get('rows') or [None] * b['row_count']
    pre = b.get('prefilled', {})
    has_head = any(rows)
    out = ['<div class="lx-table-wrap"><table class="lx-table">', '<thead><tr>']
    if has_head:
        out.append(node('th', b['corner'], extra=' scope="col"') if b.get('corner') else '<td></td>')
    out.append(''.join(node('th', c, extra=' scope="col"') for c in cols) + '</tr></thead>\n<tbody>')
    for r, rid in enumerate(rows, 1):
        cells = []
        for c, cid in enumerate(cols, 1):
            key = f'{r},{c}'
            if key in pre:
                cells.append('<td>' + paragraphs([pre[key]]) + '</td>')
                continue
            i = ctx.field()
            name = text_of(rid) if rid else f'Rreshti {r}'
            cells.append(f'<td><input class="lx-input" type="text" autocomplete="off" '
                         f'data-activity-item="item-{i}" data-aria-id="aria-{i}" '
                         f'aria-label="{attr(name)} – {attr(text_of(cid))}"></td>')
        head_cell = node('th', rid, extra=' scope="row"') if rid else ''
        out.append(f'<tr>{head_cell}{"".join(cells)}</tr>')
    out.append('</tbody></table></div>')
    return '\n'.join(out)


def b_table(b, ctx):
    """A read-only table. Each cell is a list of paragraphs (lists of text IDs)."""
    out = ['<div class="lx-table-wrap"><table class="lx-table lx-table--read">']
    if b.get('columns'):
        out.append('<thead><tr>' + ''.join(node('th', c, extra=' scope="col"') for c in b['columns'])
                   + '</tr></thead>')
    out.append('<tbody>')
    for row in b['rows']:
        out.append('<tr>' + ''.join('<td>' + paragraphs(cell) + '</td>' for cell in row) + '</tr>')
    out.append('</tbody></table></div>')
    return '\n'.join(out)


def b_cards(b, ctx):
    """Cards with an optional picture, title and text. With "answer" on the items,
    each card gets a short field that the reader checks (fill-in-the-blank)."""
    cards = []
    for it in b['items']:
        parts = []
        if it.get('figure'):
            parts.append(img(it['figure']))
        if it.get('figures'):
            parts.append('<div class="lx-card__pics">' + ''.join(img(f) for f in it['figures']) + '</div>')
        if it.get('title'):
            parts.append(node('h2', it['title']))
        if it.get('paras'):
            parts.append('<div class="lx-card__text">' + paragraphs(it['paras']) + '</div>')
        if 'answer' in it:
            i = ctx.field()
            ctx.answers[f'item-{i}'] = it['answer']
            parts.append(node('label', it['label'], extra=f' for="lx-answer-{i}"'))
            parts.append(f'<input id="lx-answer-{i}" class="lx-input" type="text" autocomplete="off" '
                         f'inputmode="{it.get("inputmode", "text")}" data-activity-item="item-{i}" '
                         f'data-aria-id="aria-{i}">')
        elif it.get('label'):
            parts.append(node('p', it['label'], 'lx-card__label'))
        colour = f' lx-card--{it["color"]}' if it.get('color') else ''
        cards.append(f'<div class="lx-card{colour}">' + ''.join(parts) + '</div>')
    n = b.get('columns') or min(len(cards), 3)
    return f'<div class="lx-cards lx-cards--{n}">\n' + '\n'.join(cards) + '\n</div>'


def b_html(b, ctx):
    """Escape hatch for a one-off layout. Use lx- classes; register text IDs it uses."""
    for i in b.get('ids', []):
        text_of(i)
        USED.add(i)
    for src in b.get('images', []):
        dims(src)
        IMAGES.add(src)
    for _ in range(b.get('fields', 0)):
        ctx.field()
    ctx.answers.update(b.get('answers', {}))
    return b['html']

def b_rating(b, ctx):
    """Self-assessment: the learner rates each statement from 1 to 5 squares."""
    ctx.kind = 'activity_custom_rating'
    parts = []
    if b.get('title'):
        parts.append(node('h2', b['title'], 'lx-note__title'))
    if b.get('paras'):
        parts.append(paragraphs(b['paras']))
    for n, text_id in enumerate(b['ids'], 1):
        undash(text_id)
        squares = ''.join(
            f'<label class="lx-rate__sq"><input type="radio" name="lx-rate-{n}" value="{v}">'
            f'<span aria-hidden="true"></span><span class="lx-sr">{v} nga 5</span></label>'
            for v in range(1, 6))
        parts.append(f'<fieldset class="lx-rate" data-lx-rate="{n}">{node("legend", text_id)}'
                     f'<div class="lx-rate__scale">{squares}</div></fieldset>')
    parts.append(f'<p class="lx-status" role="status" aria-live="polite" data-lx-status></p>'
                 f'<span hidden data-lx-string="incomplete" data-id="{b["incomplete"]}">'
                 f'{esc(text_of(b["incomplete"]))}</span>')
    USED.add(b['incomplete'])
    return ('<div class="lx-box lx-box--task" data-lx-rating>\n'
            f'<span class="lx-badge" aria-hidden="true">{PEN}</span>\n'
            '<div class="lx-box__body lx-qlist">\n' + '\n'.join(parts) + '\n</div>\n</div>')


def b_sorting(b, ctx):
    """Sort cards into categories; the reader's sorting activity checks the answers."""
    ctx.kind = 'activity_sorting'
    parts = []
    if b.get('prompt'):
        parts.append('<div class="lx-prose">' + paragraphs(b['prompt'], 'lx-prompt') + '</div>')
    cards = []
    for it in b['items']:
        i = ctx.field()
        ctx.answers[f'item-{i}'] = it['category']
        if it.get('figure'):
            label = text_of(it['figure']['id'])
            inner = img(it['figure'])
        else:
            label = text_of(it['text'])
            inner = node('span', it['text'])
        cards.append(f'<div class="word-card lx-sort__card" data-activity-item="item-{i}" tabindex="0" '
                     f'role="option" draggable="true" aria-label="{attr(label)}">{inner}</div>')
    parts.append(f'<div class="lx-sort__bank" role="listbox" aria-label="{attr(text_of(b["bank_label"]))}">'
                 + ''.join(cards) + '</div>')
    USED.add(b['bank_label'])
    cats = ''.join(
        f'<div class="category lx-sort__cat" data-activity-category="{c["id"]}" tabindex="0" '
        f'aria-label="{attr(text_of(c["title"]))}">{node("p", c["title"], "font-semibold lx-sort__title")}'
        '<div class="word-list lx-sort__list"></div></div>' for c in b['categories'])
    parts.append(f'<div class="lx-sort__cats lx-sort__cats--{len(b["categories"])}">{cats}</div>')
    return '<div class="lx-sort">\n' + '\n'.join(parts) + '\n</div>'


def b_game(b, ctx):
    """Two-player question game: draw a numbered card, answer aloud, score 2 points."""
    ctx.kind = 'activity_custom_game'
    strings = ''.join(f'<span hidden data-lx-string="{k}" data-id="{v}">{esc(text_of(v))}</span>'
                      for k, v in b['strings'].items())
    USED.update(b['strings'].values())
    players = ''.join(f'<p class="lx-game__player" data-lx-player="{n}">{node("span", pid)}: '
                      f'<output data-lx-score="{n}">0</output></p>' for n, pid in enumerate(b['players']))
    items = '\n'.join(f'<li data-lx-q="{n}" data-id="{qid}">{esc(text_of(qid))}</li>'
                      for n, qid in enumerate(b['questions'], 1))
    USED.update(b['questions'])
    s = b['strings']
    return ('<div class="lx-game" data-lx-game>\n'
            f'<div class="lx-game__score">{players}</div>\n'
            '<p class="lx-status" role="status" aria-live="polite" data-lx-status></p>\n'
            f'<button type="button" class="lx-btn" data-lx-draw>{node("span", s["draw"])}</button>\n'
            '<div class="lx-game__card" data-lx-card hidden><p class="lx-game__q" data-lx-question></p>'
            f'<div class="lx-game__actions"><button type="button" class="lx-btn" data-lx-right>'
            f'{node("span", s["right"])}</button><button type="button" class="lx-btn lx-btn--plain" data-lx-wrong>'
            f'{node("span", s["wrong"])}</button></div></div>\n'
            f'<ol class="lx-game__list">\n{items}\n</ol>\n{strings}\n</div>')


BLOCKS = {'story': b_story, 'text': b_text, 'gallery': b_gallery, 'questions': b_questions, 'info': b_info,
          'keywords': b_keywords, 'note': b_note, 'write': b_write, 'table_write': b_table_write,
          'table': b_table, 'cards': b_cards, 'html': b_html, 'rating': b_rating, 'sorting': b_sorting,
          'game': b_game}

PAGE = '''<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="title-id" content="{sid}">
<meta name="page-section-id" content="0">
<link href="./content/tailwind_output.css" rel="stylesheet">
<link href="./assets/libs/fontawesome/css/all.min.css" rel="stylesheet">
<link href="./assets/fonts.css" rel="stylesheet">
<link href="./book-design/design-system.css?v=31b9b116916778a8" data-book-style="plan" rel="stylesheet">
<link href="./book-design/lesson.css" rel="stylesheet">
</head>
<body>
<main>
<div id="content" class="bk lx" data-family="lesson" data-source-page="{page}" data-reader-title="{title_attr}">
<section data-section-type="{kind}" data-section-id="{sid}" aria-labelledby="lx-title"{extra}>
{blocks}
</section>
</div>
</main>
<script>window.activityAnswerTextIds = JSON.parse('{{}}'); window.correctAnswers = {answers};</script>
<div class="relative z-50" id="interface-container"></div>
<div class="relative z-50" id="nav-container"></div>
<script src="./assets/offline-preloader.js"></script>
<script src="./assets/scorm.js"></script>
<script src="./assets/base.bundle.local.js"></script>
<script>(function(){{if(window.BookLesson){{window.BookLesson.init();return;}}var s=document.createElement('script');s.src='./book-design/lesson.js';document.body.appendChild(s);}})();</script>
</body>
</html>
'''


def render(screen):
    ctx = Ctx()
    try:
        blocks = [head(screen)]
        for b in screen['blocks']:
            if b['type'] not in BLOCKS:
                raise SpecError(f'unknown block type: {b["type"]}')
            blocks.append(BLOCKS[b['type']](b, ctx))
    except (SpecError, KeyError) as e:
        raise SpecError(f'{screen.get("id")}: {e!r}') from e
    if screen.get('kind') or ctx.kind:
        kind = screen.get('kind') or ctx.kind
    elif ctx.answers:
        kind = 'activity_fill_in_the_blank'
    elif ctx.activity:
        kind = 'activity_open_ended_answer'
    else:
        kind = 'text_and_images' if any('<img' in x for x in blocks[1:]) else 'text_only'
    answers = dict(ctx.answers)
    answers.update(screen.get('correct_answers', {}))
    title = text_of(screen['title'])
    return PAGE.format(lang=LANG, title=esc(title), title_attr=attr(title), sid=screen['id'],
                       page=screen['page'], kind=kind, blocks='\n'.join(blocks),
                       extra=screen.get('section_attrs', ''),
                       answers=json.dumps(answers, ensure_ascii=False).replace('</', '<\\/'))


def load_specs(paths):
    screens = []
    for path in paths:
        with open(path, encoding='utf-8') as f:
            spec = json.load(f)
        for key, value in spec.get('texts', {}).items():
            TEXTS[key] = value
            SPEECH[key] = value
        for s in spec['screens']:
            s['_file'] = os.path.basename(path)
            screens.append(s)
    return screens


def relink_fix(m, starts, norm, resolve):
    """m: 1 = '<a ... href="', 2 = old section id, 3 = rest up to the label's data-id, 4 = label text id."""
    href = starts.get(norm(TEXTS.get(m.group(4), ''))) or (resolve(m.group(2)) + '.html')
    return f'{m.group(1)}{href}"{m.group(3)}'


FRONT = [{'section_id': 'pg001_sec001', 'href': 'pg001_sec001.html'},
         {'section_id': 'pg003_sec001', 'href': 'pg003_sec001.html', 'page_number': 3},
         {'section_id': 'pg004_sec001', 'href': 'pg004_sec001.html'}]
SCREEN_FILE = re.compile(r'^pg\d{3}_sec[^/]*\.html$')


def build(only=None):
    paths = [only] if only else sorted(glob.glob(os.path.join(SPEC_DIR, '*.json')))
    screens = load_specs(paths)
    ids = [s['id'] for s in screens]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise SpecError(f'duplicate screen ids: {sorted(dupes)}')
    for s in screens:
        write(s['id'] + '.html', render(s))
    if only:
        print(f'{len(screens)} screens written from {os.path.basename(only)} (preview only).')
        return

    # reading order: front matter, then every lesson screen; drop pages that no longer exist
    # reading order: front matter, then every lesson screen in page order.
    # Old screens that no spec replaces are dropped (their content now sits on another screen).
    covered = {s['page'] for s in screens}
    entries = [(s['page'], n, {'section_id': s['id'], 'href': s['id'] + '.html', 'page_number': s['page']})
               for n, s in enumerate(screens)]
    pages = list(FRONT) + [e[2] for e in sorted(entries, key=lambda e: (e[0], e[1]))]
    valid = {p['section_id'] for p in pages}
    for name in os.listdir(ROOT):
        if SCREEN_FILE.match(name) and name[:-5] not in valid:
            os.remove(os.path.join(ROOT, name))
    dump('content/pages.json', pages)
    for i, p in enumerate(pages, 1):
        text = read(p['href'])
        new, n = re.subn(r'(<meta\s+name="page-section-id"\s+content=")[^"]*(")', rf'\g<1>{i}\g<2>', text)
        assert n == 1, (p['href'], n)
        if new != text:
            write(p['href'], new)

    dump(f'content/i18n/{LANG}/texts.json', TEXTS)
    dump(f'content/i18n/{LANG}/speech_texts.json', SPEECH)

    def resolve(section_id):
        """A lesson that used to start on another screen now starts on the first screen of its page."""
        if section_id in valid:
            return section_id
        page = int(section_id[2:5])
        later = [p['section_id'] for p in pages[len(FRONT):] if int(p['section_id'][2:5]) >= page]
        assert later, f'no screen for {section_id}'
        return later[0]

    toc = load('content/toc.json')
    for e in toc:
        e['section_id'] = resolve(e['section_id'])
        e['href'] = e['section_id'] + '.html'
    dump('content/toc.json', toc, newline=True)
    # The printed contents pages link each lesson to the screen where it starts (taken from toc.json by title).
    def norm(text):
        return re.sub(r'[^a-zëç0-9]', '', text.lower())

    starts = {}
    for e in toc:
        starts.setdefault(norm(e['title']), e['href'])
    for name in ('pg003_sec001.html', 'pg004_sec001.html'):
        text = read(name)

        new = re.sub(r'(<a class="book-contents-link[^"]*" href=")(pg\d{3}_sec[^".#]*)\.html(?:#[^"]*)?"'
                     r'((?:(?!</a>).)*?data-id="([^"]+)")', lambda m: relink_fix(m, starts, norm, resolve), text, flags=re.S)
        if new != text:
            write(name, new)

    manifest = read('imsmanifest.xml')
    file_tag = r'[ \t]*<file href="pg\d{3}_sec[^"]*\.html"/>\n?'
    first = re.search(r'([ \t]*)<file href="pg\d{3}_sec', manifest)
    indent = first.group(1)
    block = ''.join(f'{indent}<file href="{p["href"]}"/>\n' for p in pages)
    manifest = manifest[:first.start()] + '\0' + manifest[first.start():]
    manifest = re.sub(file_tag, '', manifest).replace('\0', block)
    extras = ['book-design/lesson.css', 'book-design/lesson.js'] + sorted(IMAGES)
    audio_dir = f'content/i18n/{LANG}/audio'
    if os.path.isdir(os.path.join(ROOT, audio_dir)):
        extras += [f'{audio_dir}/{name}' for name in sorted(os.listdir(os.path.join(ROOT, audio_dir)))
                   if name.endswith('.mp3')]
    anchor = '<file href="book-design/reading.css"/>'
    assert anchor in manifest
    manifest = manifest.replace(anchor, anchor + ''.join(
        f'<file href="{e}"/>' for e in extras if f'"{e}"' not in manifest))
    write('imsmanifest.xml', manifest)

    # offline preloader: the reader serves these files from this inline copy
    pre = read('assets/offline-preloader.js')
    start = pre.index('var INLINE = ') + len('var INLINE = ')
    inline, end = json.JSONDecoder().raw_decode(pre, start)
    fresh = {}
    for key in inline:
        rel = key[2:]
        if SCREEN_FILE.match(rel) and rel[:-5] not in valid:
            continue
        if not os.path.exists(os.path.join(ROOT, rel)):
            continue
        fresh[key] = load(rel) if rel.endswith('.json') else read(rel)
    for p in pages:
        fresh.setdefault('./' + p['href'], read(p['href']))
    write('assets/offline-preloader.js',
          pre[:start] + json.dumps(fresh, ensure_ascii=False, separators=(',', ':')) + pre[end:])

    unused = [k for k in TEXTS if re.match(r'pg\d{3}_', k) and not k.endswith(('_easy_read', '_eli5'))
              and k not in USED and int(k[2:5]) in covered]
    print(f'{len(screens)} lesson screens, {len(pages)} screens in the book.')
    print(f'{len(unused)} text ids on rebuilt pages are not shown on any screen:')
    print('  ' + ' '.join(unused))


if __name__ == '__main__':
    try:
        build(sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == '--only' else None)
    except SpecError as e:
        sys.exit(f'SPEC ERROR: {e}')
