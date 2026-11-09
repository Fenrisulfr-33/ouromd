# mdjson

Markdown → JSON → Markdown, with zero dependencies.

- **`python/mdjson`**: parses `.md` files into JSON for storing in your database. It can also turn JSON back into Markdown.
- **`js/json2md.js`**: a browser ES module. It turns the JSON your API returns back into Markdown for your existing renderer.

Both renderers produce **byte-identical** Markdown, and the test suite checks this.

```
your .md ──(python)──▶ JSON ──▶ database ──▶ API ──▶ browser ──(json2md.js)──▶ markdown ──▶ your renderer
```

## Supported syntax

Everything on [markdownguide.org](https://www.markdownguide.org) basic and extended syntax:

| Basic | Extended |
|---|---|
| Headings (`#` and `===`/`---` underline) | Tables (with column alignment) |
| Paragraphs and line breaks (two spaces or `\`) | Fenced code with language (```` ```js ````) |
| Bold, italic, bold-italic (`*` and `_`) | Footnotes (`[^1]`, multi-paragraph) |
| Blockquotes (nested, containing other blocks) | Heading IDs (`### Title {#custom-id}`) |
| Ordered and unordered lists (nested, loose or tight) | Definition lists (`Term` / `: definition`) |
| Inline code and double-backtick code | Strikethrough (`~~x~~`) |
| Indented and fenced code blocks | Task lists (`- [x]`) |
| Horizontal rules | Emoji shortcodes (`:tent:`) |
| Links: inline, titled, reference-style, `<autolinks>` | Highlight (`==x==`) |
| Images, including linked images | Subscript (`H~2~O`) and superscript (`X^2^`) |
| Backslash escapes | Automatic URL linking (`https://…`, `www.…`) |
| Raw HTML (block and inline, passed through untouched) | **Bonus:** front matter (`---` YAML block at the top) |

## Python: Markdown → JSON

Requires Python 3.8+ and nothing else.

```bash
cd python
python -m mdjson to-json article.md -o article.json          # one file
python -m mdjson to-json posts/*.md --out-dir build/json     # many files
python -m mdjson to-json article.md --compact                # minified, smaller to store
python -m mdjson to-md   article.json -o article.md          # back to Markdown
cat article.md | python -m mdjson to-json -                  # stdin → stdout
```

As a library (this is what a future GUI would call):

```python
from mdjson import markdown_to_json, json_to_markdown

doc = markdown_to_json(open("article.md", encoding="utf-8").read())
doc["meta"]          # {'title': ..., 'date': ..., 'tags': [...]} from front matter
doc["children"]      # the article body as a node tree
db.articles.insert_one(doc)          # e.g. MongoDB, which stores this shape natively
```

## Browser: JSON → Markdown

Copy `js/json2md.js` into your site. It has no build step and no dependencies, and it also works in Node.

```html
<script type="module">
  import { jsonToMarkdown, jsonToMarkdownBody } from './json2md.js';

  const doc = await (await fetch('/api/articles/my-post')).json();

  document.title = doc.meta?.title ?? 'Article';
  const markdown = jsonToMarkdownBody(doc);   // body only, without the front matter
  // const markdown = jsonToMarkdown(doc);    // or include the --- front matter block

  yourMarkdownRenderer(markdown);
</script>
```

Both functions accept either the parsed object or the raw JSON string.

## JSON format

Every node has a `type`. Containers have `children`, and leaves have a `value`. The root:

```json
{ "type": "document", "version": 1, "meta": {…}, "frontMatter": "raw yaml", "children": [ …blocks ] }
```

`meta` and `frontMatter` only appear when the file starts with a `---` block. Check `version` if the format ever changes.

**Block nodes**

| type | fields |
|---|---|
| `heading` | `level` (1–6), `id`?, `children` (inline) |
| `paragraph` | `children` (inline) |
| `blockquote` | `children` (blocks) |
| `list` | `ordered`, `start`? (ordered only), `marker` (`-` `*` `+` or `.` `)`), `tight`, `children` (listItem) |
| `listItem` | `checked`? (`true`/`false` for task items), `children` (blocks) |
| `code` | `value`, `lang`?, `meta`? (rest of the info string, e.g. `title="x.py"`) |
| `thematicBreak` | none |
| `html` | `value` (raw HTML) |
| `table` | `align` (`"left"`/`"center"`/`"right"`/`null` per column), `children` (tableRow; the first row is the header) |
| `tableRow` / `tableCell` | `children` (cells / inline) |
| `definitionList` | `children` (definitionItem) |
| `definitionItem` | `children`: one `definitionTerm`, then one or more `definitionDescription` (both inline) |
| `footnoteDefinition` | `label`, `children` (blocks) |

**Inline nodes**

| type | fields |
|---|---|
| `text` | `value` (already unescaped: `\*` is stored as `*`) |
| `emphasis` `strong` `delete` `highlight` `subscript` `superscript` | `children` |
| `inlineCode` | `value` |
| `link` | `url`, `title`?, `children`, `autolink`? (`<url>` form), `bare`? (plain `https://…` in text) |
| `image` | `url`, `alt`, `title`? |
| `footnoteReference` | `label` |
| `emoji` | `name` (e.g. `"tent"`) |
| `html` | `value` (inline raw HTML) |
| `break` / `softbreak` | none (hard line break / ordinary newline) |

## What "round trip" means here

`md → json → md` gives back **equivalent** Markdown, not byte-identical. The output is normalised:

- Headings become `#` style, rules become `***`, code blocks are always fenced, and `__bold__` becomes `**bold**`.
- Reference-style links are resolved into inline links. The URL and title are kept.
- Hard breaks are written as `\` at the end of the line.
- Special characters in text get backslash-escaped, so `snake_case` becomes `snake\_case` and `2 * 3` becomes `2 \* 3`. Any Markdown renderer displays these exactly as the original.

The meaning is preserved. Running it again (`json → md → json`) always gives the same JSON. That's what the tests check.

## Tests

```bash
python -m unittest discover -s tests -v
```

The tests cover:

- round-trip stability on `tests/fixtures/*.md`
- a feature check for every syntax element
- a JS-vs-Python output comparison (runs only if Node is installed)

Add your own articles to `tests/fixtures/` and they'll be tested automatically.

## Known limits

- Tabs are expanded to 4 spaces in **leading** indentation. That includes the start of lines inside code blocks, so tab-indented code (e.g. Makefiles) comes back space-indented.
- HTML entities (`&copy;`) are kept as literal text. Your renderer turns them into characters as usual.
- Front matter parsing understands `key: value`, `key: [a, b]`, and `- item` lists. Anything fancier is still kept verbatim in `frontMatter`.
- The parser follows CommonMark rules closely but isn't a full spec implementation. Heavily malformed input (random symbol soup) is handled without crashing. In fuzz testing, about 1 in 10,000 such inputs doesn't round-trip perfectly. Real articles are fine.
- If you change one renderer (`python/mdjson/renderer.py` or `js/json2md.js`), make the same change in the other. The parity test will tell you if you forgot.
