# Lesson spec files

Each `*.json` file here describes a run of screens. `python3 tools/build_lessons.py`
turns all of them into the book's HTML pages with one shared template
(`book-design/lesson.css`). Files are read in name order, so name them by page
range: `p021_033.json`.

```json
{
  "texts": { "pg022_fig1": "Alt text or other new string that has no ID yet" },
  "screens": [ { ...screen... }, ... ]
}
```

## Screen

```json
{ "id": "pg022_sec001", "page": 22,
  "chapter": "pg022_n0002", "title": "pg022_n0003",
  "blocks": [ ... ] }
```

- `id`: `pgNNN_secXXX`; NNN is the bundle page where the screen's content starts,
  XXX counts up from 001 within that page. This becomes the file name.
- `page`: the bundle page number (same NNN).
- `chapter` / `title`: text IDs of the chapter name and the lesson title. Every
  screen of a lesson repeats them. Leave `chapter` out only if the page has none.
- The chapter symbol is chosen from the page number automatically.

Every piece of text is given by its **text ID** (the key in
`content/i18n/sq-XK/texts.json`). `paras` is always a list of paragraphs, each a
list of sentence IDs: `[["id1","id2"],["id3"]]`.

A figure is `{"src": "images/pg022_im001_crop_v1.png", "id": "pg022_im001_crop_v1"}`;
`id` is the text ID of its description (alt text). Optional `"caption": "<text id>"`.

## Blocks

| type | fields | what it is |
|---|---|---|
| `story` | `tag`?, `paras`, `prompt`?, `figure`?, `place`? | The "Situata" text with its picture. `tag` is the "Situata 1." label. `place`: `side` or `below` (default: wide pictures go below). |
| `text` | `paras`, `style`? (`"prompt"` = bold instruction), `figure`? | Plain paragraphs. |
| `gallery` | `figures` | 1–4 pictures in a row. |
| `questions` | `ids`, `figure`? | The "?" box. Each question gets an answer box. |
| `info` | `paras` | The outlined "book" box (what to remember). |
| `keywords` | `ids` (one ID, or label ID + list ID) | "Fjalët kyçe: …" line. |
| `note` | `color`? (`plain`,`yellow`,`green`,`blue`), `title`?, `paras`?, `items`? | Coloured box, e.g. "Këshilla" lists. `items` are bullet points. |
| `write` | `prompt`? (paras), `count`? or `fields`? (`[{"label": id}]`), `rows`? | Writing task: instruction + answer boxes. |
| `table_write` | `columns`, `rows` (row-header IDs) or `row_count`, `corner`?, `prefilled`? (`{"1,2": [ids]}`) | A table the learner fills in. |
| `table` | `columns`?, `rows` (each cell = paras) | Read-only table. |
| `cards` | `items`: `{figure?, figures?, title?, paras?, label?, color?, answer?}`, `columns`? | Cards. With `answer` + `label` the card gets a checked short-answer field. |
| `html` | `html`, `ids`?, `images`?, `fields`?, `answers`? | Escape hatch for a one-off layout. Avoid. |

Any block with answer boxes makes the screen an ADT activity
(`activity_open_ended_answer`, or `activity_fill_in_the_blank` when answers are
checked), which gives it the reader's Submit button and saving. Optional screen
fields `kind`, `correct_answers`, `section_attrs` override this for other
activity templates.

## How a lesson is split into screens

One step per screen, in the order of the book:

1. the story ("Situata") with its picture,
2. the questions,
3. the info box with the key words (advice boxes go here too, or on their own
   screen if long),
4. any writing task or table on its own screen.

Front matter that is not a lesson (foreword, references) stays on one screen.
