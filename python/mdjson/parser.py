"""
Markdown -> JSON parser.

Zero dependencies (Python standard library only).
Covers the basic and extended syntax documented on markdownguide.org:

  Basic:    headings (ATX + setext), paragraphs, line breaks, bold, italic,
            blockquotes (nested), ordered/unordered lists (nested), inline
            code, code blocks (indented + fenced), horizontal rules, links
            (inline, reference-style, autolinks), images, backslash escapes,
            raw HTML.
  Extended: tables (with alignment), fenced code with language, footnotes,
            heading IDs, definition lists, strikethrough, task lists, emoji
            shortcodes, highlight, subscript, superscript, automatic URL
            linking.
  Bonus:    YAML-style front matter (for article metadata).

Usage:
    from mdjson import markdown_to_json
    document = markdown_to_json(open("article.md").read())
"""

import re
import unicodedata

SCHEMA_VERSION = 1
TAB_STOP_WIDTH = 4
CODE_BLOCK_INDENT = 4

# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

ASCII_PUNCTUATION = set('!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~')
BACKSLASH_ESCAPE_PATTERN = re.compile(r'\\([!-/:-@\[-`{-~])')


def _unescape(text):
    return BACKSLASH_ESCAPE_PATTERN.sub(r'\1', text)


def _is_blank(line):
    return line.strip() == ''


def _indent_width(line):
    return len(line) - len(line.lstrip(' '))


def _expand_leading_tabs(line):
    """Turn tabs in leading whitespace into spaces."""
    leading_whitespace = re.match(r'[ \t]*', line).group(0)
    if '\t' not in leading_whitespace:
        return line
    column, expanded = 0, []
    for character in leading_whitespace:
        width = 1
        if character == '\t':
            width = TAB_STOP_WIDTH - (column % TAB_STOP_WIDTH)
        expanded.append(' ' * width)
        column += width
    return ''.join(expanded) + line[len(leading_whitespace):]


def _is_punctuation(character):
    if character in ASCII_PUNCTUATION:
        return True
    return unicodedata.category(character)[0] in ('P', 'S')


def _normalize_label(label):
    return ' '.join(label.split()).casefold()


def _skip_blank_lines(lines, index):
    while index < len(lines) and _is_blank(lines[index]):
        index += 1
    return index


def _end_of_run(text, start, character):
    end = start
    while end < len(text) and text[end] == character:
        end += 1
    return end


def _trim_trailing_url_punctuation(url):
    while url:
        if url[-1] in '?!.,:*_~\'"':
            url = url[:-1]
        elif url[-1] == ')' and url.count(')') > url.count('('):
            url = url[:-1]
        else:
            break
    return url


# --------------------------------------------------------------------------
# Block-level patterns
# --------------------------------------------------------------------------

ATX_HEADING_PATTERN = re.compile(r'^ {0,3}(#{1,6})(?:[ \t]+|$)(.*)$')
ATX_CLOSING_HASHES_PATTERN = re.compile(r'(?:^|[ \t]+)#+[ \t]*$')
HEADING_ID_PATTERN = re.compile(r'[ \t]*(?<!\\)\{#([^\s{}]+)\}[ \t]*$')
THEMATIC_BREAK_PATTERN = re.compile(
    r'^ {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$')
SETEXT_UNDERLINE_PATTERN = re.compile(r'^ {0,3}(=+|-+)[ \t]*$')
CODE_FENCE_PATTERN = re.compile(r'^( {0,3})(`{3,}|~{3,})(.*)$')
BLOCKQUOTE_PATTERN = re.compile(r'^ {0,3}> ?(.*)$')
BULLET_ITEM_PATTERN = re.compile(r'^( {0,3})([-+*])( +|$)(.*)$')
ORDERED_ITEM_PATTERN = re.compile(r'^( {0,3})(\d{1,9})([.)])( +|$)(.*)$')
TABLE_DELIMITER_ROW_PATTERN = re.compile(
    r'^ {0,3}\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$')
FOOTNOTE_DEFINITION_PATTERN = re.compile(
    r'^ {0,3}\[\^([^\]\s]+)\]:[ \t]?(.*)$')
REFERENCE_DEFINITION_PATTERN = re.compile(
    r'''^ {0,3}\[((?:[^\]\\]|\\.)+)\]:[ \t]*(<[^>\n]*>|\S+)'''
    r'''(?:[ \t]+("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|\((?:[^)\\]|\\.)*\)))?'''
    r'''[ \t]*$''')
DEFINITION_DESCRIPTION_PATTERN = re.compile(r'^ {0,3}:[ \t]+(.*)$')
TASK_CHECKBOX_PATTERN = re.compile(r'^\[([ xX])\][ \t]+')

HTML_BLOCK_TAGS = set((
    'address article aside base basefont blockquote body caption center col '
    'colgroup dd details dialog dir div dl dt fieldset figcaption figure '
    'footer form frame frameset h1 h2 h3 h4 h5 h6 head header hr html iframe '
    'legend li link main menu menuitem nav noframes ol optgroup option p '
    'param search section summary table tbody td tfoot th thead title tr '
    'track ul'
).split())
HTML_ATTRIBUTE = (
    r'''(?:\s+[A-Za-z_:][A-Za-z0-9_.:-]*'''
    r'''(?:\s*=\s*(?:[^\s"'=<>`]+|'[^']*'|"[^"]*"))?)''')
HTML_RAW_TEXT_START_PATTERN = re.compile(
    r'^ {0,3}<(script|pre|style|textarea)(?:\s|>|$)', re.I)
HTML_RAW_TEXT_END_PATTERN = re.compile(
    r'</(?:script|pre|style|textarea)>', re.I)
HTML_COMMENT_START_PATTERN = re.compile(r'^ {0,3}<!--')
HTML_COMMENT_END_PATTERN = re.compile('-->')
HTML_BLOCK_TAG_PATTERN = re.compile(
    r'^ {0,3}</?([A-Za-z][A-Za-z0-9-]*)(?:\s|/?>|$)')
HTML_COMPLETE_TAG_LINE_PATTERN = re.compile(
    r'^ {0,3}(?:<[A-Za-z][A-Za-z0-9-]*' + HTML_ATTRIBUTE
    + r'*\s*/?>|</[A-Za-z][A-Za-z0-9-]*\s*>)\s*$')

HTML_RAW_TEXT = 'raw_text'
HTML_COMMENT = 'comment'
HTML_BLOCK_TAG = 'block_tag'
HTML_COMPLETE_TAG = 'complete_tag'
HTML_BLOCK_END_PATTERNS = {
    HTML_RAW_TEXT: HTML_RAW_TEXT_END_PATTERN,
    HTML_COMMENT: HTML_COMMENT_END_PATTERN,
}


def _html_block_kind(line, in_paragraph=False):
    if HTML_RAW_TEXT_START_PATTERN.match(line):
        return HTML_RAW_TEXT
    if HTML_COMMENT_START_PATTERN.match(line):
        return HTML_COMMENT
    tag_match = HTML_BLOCK_TAG_PATTERN.match(line)
    if tag_match and tag_match.group(1).lower() in HTML_BLOCK_TAGS:
        return HTML_BLOCK_TAG
    if not in_paragraph and HTML_COMPLETE_TAG_LINE_PATTERN.match(line):
        return HTML_COMPLETE_TAG
    return None


def _is_valid_fence(fence_match):
    fence, info = fence_match.group(2), fence_match.group(3)
    return not (fence[0] == '`' and '`' in info)


def _list_marker(line):
    """Return info about a list-item marker on this line, or None."""
    if THEMATIC_BREAK_PATTERN.match(line):
        return None
    bullet_match = BULLET_ITEM_PATTERN.match(line)
    if bullet_match:
        indent, marker, spacing, content = bullet_match.groups()
        marker_info = {'ordered': False, 'delimiter': marker, 'start': None}
    else:
        ordered_match = ORDERED_ITEM_PATTERN.match(line)
        if not ordered_match:
            return None
        indent, number, delimiter, spacing, content = ordered_match.groups()
        marker = number + delimiter
        marker_info = {
            'ordered': True, 'delimiter': delimiter, 'start': int(number)}
    marker_width = len(indent) + len(marker)
    marker_info.update(_list_item_content(marker_width, spacing, content))
    return marker_info


def _list_item_content(marker_width, spacing, content):
    if content.strip() == '':
        return {'content_indent': marker_width + 1, 'content': ''}
    if len(spacing) > CODE_BLOCK_INDENT:
        return {'content_indent': marker_width + 1,
                'content': ' ' * (len(spacing) - 1) + content}
    return {'content_indent': marker_width + len(spacing), 'content': content}


def _interrupts_paragraph(line):
    """Does this line start a block that can interrupt a paragraph?"""
    if _indent_width(line) >= CODE_BLOCK_INDENT:
        return False
    if (ATX_HEADING_PATTERN.match(line)
            or THEMATIC_BREAK_PATTERN.match(line)
            or BLOCKQUOTE_PATTERN.match(line)):
        return True
    fence_match = CODE_FENCE_PATTERN.match(line)
    if fence_match and _is_valid_fence(fence_match):
        return True
    if _html_block_kind(line, in_paragraph=True):
        return True
    if FOOTNOTE_DEFINITION_PATTERN.match(line):
        return True
    marker = _list_marker(line)
    if not marker or not marker['content'].strip():
        return False
    return not marker['ordered'] or marker['start'] == 1


def _is_lazy_continuation(previous_lines, line):
    return (bool(previous_lines)
            and not _is_blank(previous_lines[-1])
            and not _is_blank(line)
            and not _interrupts_paragraph(line)
            and not _list_marker(line))


# --------------------------------------------------------------------------
# Block parser
# --------------------------------------------------------------------------

class _BlockParser:
    def __init__(self):
        self.references = {}
        self.block_parsers = (
            self._try_fenced_code,
            self._try_indented_code,
            self._try_atx_heading,
            self._try_thematic_break,
            self._try_blockquote,
            self._try_html,
            self._try_footnote,
            self._try_reference_definition,
            self._try_list,
            self._try_table,
            self._try_definition_list,
            self._parse_paragraph,
        )

    def parse(self, lines):
        blocks = []
        index = 0
        while index < len(lines):
            if _is_blank(lines[index]):
                index += 1
                continue
            index = self._parse_block(lines, index, blocks)
        return blocks

    def _parse_block(self, lines, index, blocks):
        """Parse the block starting at lines[index]; return the next index."""
        for parse_block in self.block_parsers:
            next_index = parse_block(lines, index, blocks)
            if next_index is not None:
                return next_index

    # ---- leaf blocks -----------------------------------------------------

    def _try_fenced_code(self, lines, index, blocks):
        fence_match = CODE_FENCE_PATTERN.match(lines[index])
        if not fence_match or not _is_valid_fence(fence_match):
            return None
        fence_indent = len(fence_match.group(1))
        fence = fence_match.group(2)
        closing_fence = re.compile(
            r'^ {0,3}' + re.escape(fence[0])
            + '{' + str(len(fence)) + r',}[ \t]*$')
        content, next_index = [], index + 1
        while next_index < len(lines):
            line = lines[next_index]
            next_index += 1
            if closing_fence.match(line):
                break
            content.append(line[min(fence_indent, _indent_width(line)):])
        blocks.append(_code_node(fence_match.group(3).strip(), content))
        return next_index

    def _try_indented_code(self, lines, index, blocks):
        if _indent_width(lines[index]) < CODE_BLOCK_INDENT:
            return None
        content, next_index = [], index
        while next_index < len(lines) and _is_code_line(lines[next_index]):
            line = lines[next_index]
            content.append(line[min(CODE_BLOCK_INDENT, _indent_width(line)):])
            next_index += 1
        while content and content[-1].strip() == '':
            content.pop()
        blocks.append({'type': 'code', 'value': '\n'.join(content)})
        return next_index

    def _try_atx_heading(self, lines, index, blocks):
        heading_match = ATX_HEADING_PATTERN.match(lines[index])
        if not heading_match:
            return None
        level = len(heading_match.group(1))
        text = ATX_CLOSING_HASHES_PATTERN.sub('', heading_match.group(2))
        blocks.append(_heading_node(level, text))
        return index + 1

    def _try_thematic_break(self, lines, index, blocks):
        if not THEMATIC_BREAK_PATTERN.match(lines[index]):
            return None
        blocks.append({'type': 'thematicBreak'})
        return index + 1

    def _try_html(self, lines, index, blocks):
        kind = _html_block_kind(lines[index])
        if not kind:
            return None
        end_pattern = HTML_BLOCK_END_PATTERNS.get(kind)
        if end_pattern:
            html_lines = _collect_until_end_pattern(lines, index, end_pattern)
        else:
            html_lines = _collect_until_blank(lines, index)
        blocks.append({'type': 'html', 'value': '\n'.join(html_lines)})
        return index + len(html_lines)

    def _try_reference_definition(self, lines, index, blocks):
        definition_match = REFERENCE_DEFINITION_PATTERN.match(lines[index])
        if not definition_match or definition_match.group(1).startswith('^'):
            return None
        self._store_reference(*definition_match.groups())
        return index + 1

    def _store_reference(self, label, url, title):
        if url.startswith('<') and url.endswith('>'):
            url = url[1:-1]
        if title is not None:
            title = _unescape(title[1:-1])
        key = _normalize_label(label)
        if key not in self.references:
            self.references[key] = (_unescape(url), title)

    def _parse_paragraph(self, lines, index, blocks):
        paragraph_lines = [lines[index].lstrip()]
        next_index = index + 1
        while next_index < len(lines):
            line = lines[next_index]
            if _is_blank(line):
                break
            underline_match = SETEXT_UNDERLINE_PATTERN.match(line)
            if underline_match:
                level = 1 if underline_match.group(1)[0] == '=' else 2
                text = ' '.join(part.strip() for part in paragraph_lines)
                blocks.append(_heading_node(level, text))
                return next_index + 1
            if _interrupts_paragraph(line):
                break
            paragraph_lines.append(line.lstrip())
            next_index += 1
        raw = '\n'.join(paragraph_lines).rstrip()
        blocks.append({'type': 'paragraph', 'raw': raw})
        return next_index

    def _try_table(self, lines, index, blocks):
        if not _starts_table(lines, index):
            return None
        header = _split_table_row(lines[index])
        delimiter_row = _split_table_row(lines[index + 1])
        if len(header) != len(delimiter_row):
            return None
        body_rows, next_index = _collect_table_rows(
            lines, index + 2, len(header))
        alignments = [_cell_alignment(cell) for cell in delimiter_row]
        blocks.append(_table_node(alignments, [header] + body_rows))
        return next_index

    # ---- container blocks ------------------------------------------------

    def _try_blockquote(self, lines, index, blocks):
        if not BLOCKQUOTE_PATTERN.match(lines[index]):
            return None
        quoted_lines = []
        while index < len(lines):
            line = lines[index]
            quote_match = BLOCKQUOTE_PATTERN.match(line)
            if quote_match:
                quoted_lines.append(quote_match.group(1))
            elif _is_lazy_continuation(quoted_lines, line):
                quoted_lines.append(line)
            else:
                break
            index += 1
        children = self.parse(quoted_lines)
        blocks.append({'type': 'blockquote', 'children': children})
        return index

    def _try_footnote(self, lines, index, blocks):
        footnote_match = FOOTNOTE_DEFINITION_PATTERN.match(lines[index])
        if not footnote_match:
            return None
        body, next_index = _collect_container_lines(
            lines, index + 1, CODE_BLOCK_INDENT, footnote_match.group(2))
        blocks.append({'type': 'footnoteDefinition',
                       'label': footnote_match.group(1),
                       'children': self.parse(body)})
        return next_index

    def _try_list(self, lines, index, blocks):
        first_marker = _list_marker(lines[index])
        if not first_marker:
            return None
        items, loose = [], False
        while True:
            item, item_is_loose, index = self._parse_list_item(lines, index)
            items.append(item)
            loose = loose or item_is_loose
            next_item_index = _skip_blank_lines(lines, index)
            if not _continues_list(lines, next_item_index, first_marker):
                break
            if next_item_index > index:
                loose = True
            index = next_item_index
        blocks.append(_list_node(first_marker, items, loose))
        return index

    def _parse_list_item(self, lines, index):
        marker = _list_marker(lines[index])
        item_lines, next_index = _collect_container_lines(
            lines, index + 1, marker['content_indent'], marker['content'])
        children = self.parse(item_lines)
        item = {'type': 'listItem', 'children': children}
        _apply_task_checkbox(item)
        is_loose = _has_blank_line_between_children(item_lines, children)
        return item, is_loose, next_index

    def _try_definition_list(self, lines, index, blocks):
        if not _next_line_is_description(lines, index):
            return None
        items = []
        while True:
            item, index = _parse_definition_item(lines, index)
            items.append(item)
            next_term_index = _skip_blank_lines(lines, index)
            if not _starts_definition_item(lines, next_term_index):
                break
            index = next_term_index
        blocks.append({'type': 'definitionList', 'children': items})
        return index


# --------------------------------------------------------------------------
# Block helpers
# --------------------------------------------------------------------------

def _heading_node(level, text):
    text = text.strip()
    node = {'type': 'heading', 'level': level}
    id_match = HEADING_ID_PATTERN.search(text)
    if id_match:
        node['id'] = id_match.group(1)
        text = text[:id_match.start()]
    node['raw'] = text
    return node


def _code_node(info, content_lines):
    node = {'type': 'code'}
    if info:
        info_parts = info.split(None, 1)
        node['lang'] = _unescape(info_parts[0])
        if len(info_parts) > 1:
            node['meta'] = info_parts[1]
    node['value'] = '\n'.join(content_lines)
    return node


def _is_code_line(line):
    return _is_blank(line) or _indent_width(line) >= CODE_BLOCK_INDENT


def _collect_until_end_pattern(lines, index, end_pattern):
    collected = []
    while index < len(lines):
        collected.append(lines[index])
        index += 1
        if end_pattern.search(collected[-1]):
            break
    return collected


def _collect_until_blank(lines, index):
    collected = []
    while index < len(lines) and not _is_blank(lines[index]):
        collected.append(lines[index])
        index += 1
    return collected


def _collect_container_lines(lines, index, content_indent, first_line):
    """Gather the lines of a list item or footnote; return (body, index)."""
    body = [first_line]
    while index < len(lines):
        line = lines[index]
        if _is_blank(line):
            next_content_index = _skip_blank_lines(lines, index)
            if (next_content_index < len(lines)
                    and _indent_width(lines[next_content_index])
                    >= content_indent):
                body.extend([''] * (next_content_index - index))
                index = next_content_index
                continue
            break
        if _indent_width(line) >= content_indent:
            body.append(line[content_indent:])
        elif _is_lazy_continuation(body, line):
            body.append(line.lstrip())
        else:
            break
        index += 1
    return body, index


def _continues_list(lines, index, first_marker):
    if index >= len(lines):
        return False
    marker = _list_marker(lines[index])
    return (bool(marker)
            and marker['ordered'] == first_marker['ordered']
            and marker['delimiter'] == first_marker['delimiter'])


def _has_blank_line_between_children(item_lines, children):
    if len(children) < 2:
        return False
    for line_number in range(1, len(item_lines) - 1):
        next_line = item_lines[line_number + 1]
        if (item_lines[line_number] == '' and next_line.strip()
                and _indent_width(next_line) == 0):
            return True
    return False


def _apply_task_checkbox(item):
    children = item['children']
    if not children or children[0]['type'] != 'paragraph':
        return
    checkbox_match = TASK_CHECKBOX_PATTERN.match(children[0]['raw'])
    if not checkbox_match:
        return
    item['checked'] = checkbox_match.group(1) != ' '
    children[0]['raw'] = children[0]['raw'][checkbox_match.end():]


def _list_node(first_marker, items, loose):
    node = {'type': 'list', 'ordered': first_marker['ordered']}
    if first_marker['ordered']:
        node['start'] = first_marker['start']
    node['marker'] = first_marker['delimiter']
    node['tight'] = not loose
    node['children'] = items
    return node


def _starts_table(lines, index):
    if index + 1 >= len(lines):
        return False
    line, next_line = lines[index], lines[index + 1]
    return ('|' in line and '|' in next_line
            and bool(TABLE_DELIMITER_ROW_PATTERN.match(next_line)))


def _cell_alignment(delimiter_cell):
    cell = delimiter_cell.strip()
    aligned_left, aligned_right = cell.startswith(':'), cell.endswith(':')
    if aligned_left and aligned_right:
        return 'center'
    if aligned_left:
        return 'left'
    if aligned_right:
        return 'right'
    return None


def _collect_table_rows(lines, index, width):
    rows = []
    while (index < len(lines) and not _is_blank(lines[index])
           and not _interrupts_paragraph(lines[index])):
        cells = _split_table_row(lines[index])
        rows.append((cells + [''] * width)[:width])
        index += 1
    return rows, index


def _table_node(alignments, rows):
    return {'type': 'table', 'align': alignments, 'children': [
        {'type': 'tableRow',
         'children': [{'type': 'tableCell', 'raw': cell} for cell in row]}
        for row in rows
    ]}


def _split_table_row(line):
    row = line.strip()
    if row.startswith('|'):
        row = row[1:]
    if row.endswith('|') and not row.endswith('\\|'):
        row = row[:-1]
    cells, current_cell, position = [], [], 0
    while position < len(row):
        character = row[position]
        if character == '\\' and position + 1 < len(row):
            escaped = row[position + 1]
            current_cell.append(
                '|' if escaped == '|' else row[position:position + 2])
            position += 2
            continue
        if character == '|':
            cells.append(''.join(current_cell).strip())
            current_cell = []
        else:
            current_cell.append(character)
        position += 1
    cells.append(''.join(current_cell).strip())
    return cells


def _next_line_is_description(lines, index):
    return (index + 1 < len(lines)
            and bool(DEFINITION_DESCRIPTION_PATTERN.match(lines[index + 1])))


def _starts_definition_item(lines, index):
    return (_next_line_is_description(lines, index)
            and not _interrupts_paragraph(lines[index])
            and _indent_width(lines[index]) < CODE_BLOCK_INDENT)


def _parse_definition_item(lines, index):
    children = [{'type': 'definitionTerm', 'raw': lines[index].strip()}]
    index += 1
    while index < len(lines):
        description_match = DEFINITION_DESCRIPTION_PATTERN.match(lines[index])
        if not description_match:
            break
        text, index = _collect_description_text(
            lines, index + 1, description_match.group(1))
        children.append(
            {'type': 'definitionDescription', 'raw': text.rstrip()})
    return {'type': 'definitionItem', 'children': children}, index


def _collect_description_text(lines, index, text):
    while index < len(lines) and _continues_description(lines, index):
        text += '\n' + lines[index].strip()
        index += 1
    return text, index


def _continues_description(lines, index):
    line = lines[index]
    if (_is_blank(line) or DEFINITION_DESCRIPTION_PATTERN.match(line)
            or _interrupts_paragraph(line)):
        return False
    return not _next_line_is_description(lines, index)


# --------------------------------------------------------------------------
# Inline parser
# --------------------------------------------------------------------------

AUTOLINK_PATTERN = re.compile(r'<([A-Za-z][A-Za-z0-9+.-]{1,31}:[^\s<>]*)>')
EMAIL_AUTOLINK_PATTERN = re.compile(
    r"<([A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*)>")
INLINE_HTML_PATTERN = re.compile(
    r'<[A-Za-z][A-Za-z0-9-]*' + HTML_ATTRIBUTE
    + r'*\s*/?>|</[A-Za-z][A-Za-z0-9-]*\s*>|<!--[\s\S]*?-->')
FOOTNOTE_REFERENCE_PATTERN = re.compile(r'\[\^([^\]\s]+)\]')
EMOJI_SHORTCODE_PATTERN = re.compile(r':([A-Za-z0-9_+\-]+):')
BARE_URL_PATTERN = re.compile(r'(?:https?://|www\.)[^\s<>\\]*', re.I)
BARE_URL_PREFIX_PATTERN = re.compile(r'^(?:https?://|www\.)', re.I)
HOSTNAME_PATTERN = re.compile(r'[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*')

DELIMITER_CHARACTERS = '*_~=^'
EMPHASIS_TYPES = {
    ('*', 1): 'emphasis', ('*', 2): 'strong',
    ('_', 1): 'emphasis', ('_', 2): 'strong',
    ('~', 1): 'subscript', ('~', 2): 'delete',
    ('=', 2): 'highlight', ('^', 1): 'superscript',
}


class _InlineState:
    """Cursor and output for one pass of the inline parser."""

    def __init__(self, source, in_link):
        self.source = source
        self.in_link = in_link
        self.position = 0
        self.nodes = []
        self.delimiters = []
        self.pending_text = []

    def character_at(self, offset=0):
        index = self.position + offset
        if 0 <= index < len(self.source):
            return self.source[index]
        return None

    def append_text(self, text, end):
        self.pending_text.append(text)
        self.position = end

    def append_node(self, node, end):
        self.flush_text()
        self.nodes.append(node)
        self.position = end

    def flush_text(self):
        if self.pending_text:
            text = ''.join(self.pending_text)
            self.nodes.append({'type': 'text', 'value': text})
            self.pending_text.clear()

    def strip_trailing_spaces(self):
        """Strip spaces before a line ending; return how many were removed."""
        text = ''.join(self.pending_text)
        stripped = text.rstrip(' ')
        self.pending_text.clear()
        if stripped:
            self.pending_text.append(stripped)
        return len(text) - len(stripped)

    def skip_spaces(self):
        while self.character_at() == ' ':
            self.position += 1


class _InlineParser:
    def __init__(self, references):
        self.references = references
        self.character_handlers = {
            '\\': self._parse_backslash,
            '`': self._parse_code_span,
            '<': self._parse_angle_bracket,
            '!': self._parse_image,
            '[': self._parse_bracket,
            ':': self._parse_emoji,
            '\n': self._parse_line_ending,
        }
        for character in DELIMITER_CHARACTERS:
            self.character_handlers[character] = self._parse_delimiter_run

    def parse(self, source, in_link=False):
        state = _InlineState(source, in_link)
        while state.position < len(source):
            self._parse_next(state)
        state.flush_text()
        _process_emphasis(state.nodes, state.delimiters)
        return _merge_text(state.nodes)

    def _parse_next(self, state):
        character = state.character_at()
        handler = self.character_handlers.get(character)
        if handler and handler(state):
            return
        if _is_bare_url_start(state) and _append_match(
                state, _match_bare_url(state.source, state.position)):
            return
        state.append_text(character, state.position + 1)

    # ---- character handlers: return True when they consumed input -------

    def _parse_backslash(self, state):
        next_character = state.character_at(1)
        if next_character == '\n':
            state.append_node({'type': 'break'}, state.position + 2)
            state.skip_spaces()
            return True
        if next_character in ASCII_PUNCTUATION:
            state.append_text(next_character, state.position + 2)
            return True
        return False

    def _parse_code_span(self, state):
        code_span = _match_code_span(state.source, state.position)
        if code_span:
            state.append_node(*code_span)
            return True
        run_end = _end_of_run(state.source, state.position, '`')
        state.append_text(state.source[state.position:run_end], run_end)
        return True

    def _parse_angle_bracket(self, state):
        match = None
        if not state.in_link:
            match = _match_autolink(state.source, state.position)
        if not match:
            match = _match_inline_html(state.source, state.position)
        return _append_match(state, match)

    def _parse_image(self, state):
        if state.character_at(1) != '[':
            return False
        image = self._match_link(state.source, state.position + 1, image=True)
        return _append_match(state, image)

    def _parse_bracket(self, state):
        footnote_match = FOOTNOTE_REFERENCE_PATTERN.match(
            state.source, state.position)
        if footnote_match:
            node = {'type': 'footnoteReference',
                    'label': footnote_match.group(1)}
            return _append_match(state, (node, footnote_match.end()))
        if state.in_link:
            return False
        link = self._match_link(state.source, state.position, image=False)
        return _append_match(state, link)

    def _parse_delimiter_run(self, state):
        source, start = state.source, state.position
        character = source[start]
        end = _end_of_run(source, start, character)
        run_length = end - start
        if character == '=' and run_length < 2:
            state.append_text(character, end)
            return True
        before = source[start - 1] if start > 0 else ' '
        after = source[end] if end < len(source) else ' '
        can_open, can_close = _delimiter_flags(character, before, after)
        node = {'type': 'text', 'value': source[start:end]}
        state.append_node(node, end)
        if can_open or can_close:
            state.delimiters.append({
                'node': node, 'character': character, 'count': run_length,
                'original_count': run_length,
                'can_open': can_open, 'can_close': can_close})
        return True

    def _parse_emoji(self, state):
        emoji_match = EMOJI_SHORTCODE_PATTERN.match(
            state.source, state.position)
        if not emoji_match:
            return False
        name = emoji_match.group(1)
        previous = state.character_at(-1)
        if previous is not None and previous.isalnum():
            return False
        if not re.search('[A-Za-z]', name) and name not in ('+1', '-1'):
            return False
        state.append_node({'type': 'emoji', 'name': name}, emoji_match.end())
        return True

    def _parse_line_ending(self, state):
        is_hard_break = state.strip_trailing_spaces() >= 2
        node = {'type': 'break' if is_hard_break else 'softbreak'}
        state.append_node(node, state.position + 1)
        state.skip_spaces()
        return True

    # ---- links -----------------------------------------------------------

    def _match_link(self, source, open_bracket, image):
        close_bracket = _find_closing_bracket(source, open_bracket)
        if close_bracket is None:
            return None
        label = source[open_bracket + 1:close_bracket]
        destination = self._link_destination(
            source, close_bracket + 1, label)
        if destination is None:
            return None
        (url, title), end = destination
        if image:
            alt_text = _plain_text(self.parse(label))
            node = {'type': 'image', 'url': url, 'alt': alt_text}
        else:
            children = self.parse(label, in_link=True)
            node = {'type': 'link', 'url': url, 'children': children}
        if title is not None:
            node['title'] = title
        return node, end

    def _link_destination(self, source, after_label, label):
        """Return ((url, title), end) for a link whose label ends here."""
        if source.startswith('(', after_label):
            inline_destination = _parse_inline_destination(
                source, after_label)
            if inline_destination:
                url, title, end = inline_destination
                return (url, title), end
        if source.startswith('[', after_label):
            close_bracket = _find_closing_bracket(source, after_label)
            if close_bracket is not None:
                reference = source[after_label + 1:close_bracket]
                key = _normalize_label(
                    reference if reference.strip() else label)
                if key in self.references:
                    return self.references[key], close_bracket + 1
                if reference.strip():
                    return None
        key = _normalize_label(label)
        if key and key in self.references:
            return self.references[key], after_label
        return None


# --------------------------------------------------------------------------
# Inline helpers
# --------------------------------------------------------------------------

def _append_match(state, match):
    if not match:
        return False
    node, end = match
    state.append_node(node, end)
    return True


def _match_code_span(source, start):
    content_start = _end_of_run(source, start, '`')
    backtick_count = content_start - start
    search_from = content_start
    while True:
        closing_start = source.find('`', search_from)
        if closing_start == -1:
            return None
        closing_end = _end_of_run(source, closing_start, '`')
        if closing_end - closing_start == backtick_count:
            content = source[content_start:closing_start].replace('\n', ' ')
            node = {'type': 'inlineCode',
                    'value': _strip_code_span_padding(content)}
            return node, closing_end
        search_from = closing_end


def _strip_code_span_padding(content):
    if (len(content) >= 2 and content[0] == ' ' and content[-1] == ' '
            and content.strip(' ')):
        return content[1:-1]
    return content


def _match_autolink(source, start):
    url_match = AUTOLINK_PATTERN.match(source, start)
    if url_match:
        url = url_match.group(1)
        return _autolink_node(url, url), url_match.end()
    email_match = EMAIL_AUTOLINK_PATTERN.match(source, start)
    if email_match:
        email = email_match.group(1)
        return _autolink_node('mailto:' + email, email), email_match.end()
    return None


def _autolink_node(url, text):
    return {'type': 'link', 'url': url, 'autolink': True,
            'children': [{'type': 'text', 'value': text}]}


def _match_inline_html(source, start):
    html_match = INLINE_HTML_PATTERN.match(source, start)
    if not html_match:
        return None
    return {'type': 'html', 'value': html_match.group(0)}, html_match.end()


def _is_bare_url_start(state):
    if state.in_link or state.character_at() not in 'hHwW':
        return False
    previous = state.character_at(-1)
    return previous is None or previous.isspace() or previous in '*_~(\n'


def _match_bare_url(source, start):
    url_match = BARE_URL_PATTERN.match(source, start)
    if not url_match:
        return None
    raw = _trim_trailing_url_punctuation(url_match.group(0))
    host = BARE_URL_PREFIX_PATTERN.sub('', raw)
    if not host or not HOSTNAME_PATTERN.match(host):
        return None
    starts_with_www = raw.lower().startswith('www.')
    if starts_with_www and '.' not in host:
        return None
    url = 'http://' + raw if starts_with_www else raw
    node = {'type': 'link', 'url': url, 'bare': True,
            'children': [{'type': 'text', 'value': raw}]}
    return node, start + len(raw)


def _find_closing_bracket(source, open_bracket):
    depth, position = 0, open_bracket
    while position < len(source):
        character = source[position]
        if character == '\\':
            position += 2
            continue
        if character == '`':
            code_span = _match_code_span(source, position)
            if code_span:
                position = code_span[1]
            else:
                position = _end_of_run(source, position, '`')
            continue
        if character == '[':
            depth += 1
        elif character == ']':
            depth -= 1
            if depth == 0:
                return position
        position += 1
    return None


def _skip_whitespace(source, position):
    while position < len(source) and source[position] in ' \t\n':
        position += 1
    return position


def _parse_inline_destination(source, open_parenthesis):
    """Parse `(url "title")` at source[open_parenthesis].

    Return (url, title, end) or None.
    """
    position = _skip_whitespace(source, open_parenthesis + 1)
    parsed_url = _parse_link_url(source, position)
    if parsed_url is None:
        return None
    url, url_end = parsed_url
    position = _skip_whitespace(source, url_end)
    title = None
    if (position > url_end and position < len(source)
            and source[position] in '"\'('):
        parsed_title = _parse_link_title(source, position)
        if parsed_title is None:
            return None
        title, title_end = parsed_title
        position = _skip_whitespace(source, title_end)
    if position < len(source) and source[position] == ')':
        return _unescape(url), title, position + 1
    return None


def _parse_link_url(source, position):
    if source.startswith('<', position):
        return _parse_angle_bracket_url(source, position)
    return _parse_plain_url(source, position)


def _parse_angle_bracket_url(source, position):
    end = position + 1
    while end < len(source) and source[end] not in '>\n<':
        if source[end] == '\\':
            end += 1
        end += 1
    if end >= len(source) or source[end] != '>':
        return None
    return source[position + 1:end], end + 1


def _parse_plain_url(source, position):
    end, depth = position, 0
    while end < len(source):
        character = source[end]
        if (character == '\\' and end + 1 < len(source)
                and source[end + 1] in ASCII_PUNCTUATION):
            end += 2
            continue
        if character.isspace() or ord(character) < 32:
            break
        if character == '(':
            depth += 1
        elif character == ')':
            if depth == 0:
                break
            depth -= 1
        end += 1
    return source[position:end], end


def _parse_link_title(source, position):
    closing_character = ')' if source[position] == '(' else source[position]
    end = position + 1
    while end < len(source) and source[end] != closing_character:
        if source[end] == '\\':
            end += 1
        end += 1
    if end >= len(source):
        return None
    return _unescape(source[position + 1:end]), end + 1


def _delimiter_flags(character, before, after):
    """Return (can_open, can_close) for a delimiter run."""
    before_is_space, after_is_space = before.isspace(), after.isspace()
    before_is_punctuation = _is_punctuation(before)
    after_is_punctuation = _is_punctuation(after)
    left_flanking = not after_is_space and (
        not after_is_punctuation or before_is_space or before_is_punctuation)
    right_flanking = not before_is_space and (
        not before_is_punctuation or after_is_space or after_is_punctuation)
    if character == '_':
        return (left_flanking
                and (not right_flanking or before_is_punctuation),
                right_flanking
                and (not left_flanking or after_is_punctuation))
    return left_flanking, right_flanking


def _delimiters_to_use(opener, closer):
    character = opener['character']
    both_doubled = opener['count'] >= 2 and closer['count'] >= 2
    if character in '*_':
        if _breaks_rule_of_three(opener, closer):
            return 0
        return 2 if both_doubled else 1
    if character == '~':
        if both_doubled:
            return 2
        if opener['count'] == 1 and closer['count'] == 1:
            return 1
        return 0
    if character == '=':
        return 2 if both_doubled else 0
    return 1


def _breaks_rule_of_three(opener, closer):
    opener_count = opener['original_count']
    closer_count = closer['original_count']
    return ((opener['can_close'] or closer['can_open'])
            and (opener_count + closer_count) % 3 == 0
            and not (opener_count % 3 == 0 and closer_count % 3 == 0))


def _index_of(nodes, target):
    for index, node in enumerate(nodes):
        if node is target:
            return index
    raise ValueError('node not found')


def _process_emphasis(nodes, delimiters):
    closer_index = 0
    while closer_index < len(delimiters):
        opener_index, count = None, 0
        if delimiters[closer_index]['can_close']:
            opener_index, count = _find_opener(delimiters, closer_index)
        if opener_index is None:
            closer_index += 1
            continue
        closer_index = _wrap_emphasis(
            nodes, delimiters, opener_index, closer_index, count)


def _find_opener(delimiters, closer_index):
    closer = delimiters[closer_index]
    for opener_index in range(closer_index - 1, -1, -1):
        opener = delimiters[opener_index]
        if opener['character'] != closer['character']:
            continue
        if not opener['can_open']:
            continue
        count = _delimiters_to_use(opener, closer)
        if count:
            return opener_index, count
    return None, 0


def _wrap_emphasis(nodes, delimiters, opener_index, closer_index, count):
    """Wrap the nodes between two delimiters; return the next closer index."""
    opener, closer = delimiters[opener_index], delimiters[closer_index]
    start = _index_of(nodes, opener['node'])
    end = _index_of(nodes, closer['node'])
    node_type = EMPHASIS_TYPES[(opener['character'], count)]
    nodes[start + 1:end] = [
        {'type': node_type, 'children': nodes[start + 1:end]}]
    opener['count'] -= count
    closer['count'] -= count
    opener['node']['value'] = opener['character'] * opener['count']
    closer['node']['value'] = closer['character'] * closer['count']
    del delimiters[opener_index + 1:closer_index]
    closer_index = opener_index + 1
    if opener['count'] == 0:
        nodes.pop(_index_of(nodes, opener['node']))
        del delimiters[opener_index]
        closer_index -= 1
    if closer['count'] == 0:
        nodes.pop(_index_of(nodes, closer['node']))
        del delimiters[closer_index]
    return closer_index


def _merge_text(nodes):
    merged = []
    for node in nodes:
        if 'children' in node:
            node['children'] = _merge_text(node['children'])
        if node['type'] == 'text':
            if not node['value']:
                continue
            if merged and merged[-1]['type'] == 'text':
                merged[-1] = {'type': 'text',
                              'value': merged[-1]['value'] + node['value']}
                continue
        merged.append(node)
    return merged


def _plain_text(nodes):
    parts = []
    for node in nodes:
        node_type = node['type']
        if node_type in ('text', 'inlineCode'):
            parts.append(node['value'])
        elif node_type == 'image':
            parts.append(node['alt'])
        elif node_type in ('break', 'softbreak'):
            parts.append(' ')
        elif node_type == 'emoji':
            parts.append(':' + node['name'] + ':')
        elif 'children' in node:
            parts.append(_plain_text(node['children']))
    return ''.join(parts)


# --------------------------------------------------------------------------
# Front matter
# --------------------------------------------------------------------------

def _extract_front_matter(lines, document):
    """Move front matter into the document; return the remaining lines."""
    if lines[0].rstrip() != '---':
        return lines
    for closing_index in range(1, len(lines)):
        if lines[closing_index].rstrip() in ('---', '...'):
            front_matter_lines = lines[1:closing_index]
            document['frontMatter'] = '\n'.join(front_matter_lines)
            document['meta'] = _parse_front_matter(front_matter_lines)
            return lines[closing_index + 1:]
    return lines


def _parse_front_matter(front_matter_lines):
    """Very small YAML subset: `key: value`, `key: [a, b]`, `- item` lists."""
    meta, key = {}, None
    for line in front_matter_lines:
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key_match = re.match(r'^([A-Za-z0-9_\-]+):\s*(.*)$', line)
        if key_match:
            key, value = key_match.group(1), key_match.group(2).strip()
            meta[key] = _yaml_scalar(value) if value else []
            continue
        item_match = re.match(r'^\s+-\s+(.*)$', line)
        if item_match and key is not None and isinstance(meta.get(key), list):
            meta[key].append(_yaml_scalar(item_match.group(1).strip()))
    return meta


def _yaml_scalar(value):
    if value.startswith('[') and value.endswith(']'):
        items = value[1:-1].split(',')
        return [_yaml_scalar(item.strip()) for item in items if item.strip()]
    if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
        return value[1:-1]
    return value


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def markdown_to_json(markdown):
    """Parse a Markdown string into a JSON-serialisable dict."""
    text = markdown.replace('\r\n', '\n').replace('\r', '\n')
    lines = [_expand_leading_tabs(line) for line in text.split('\n')]
    document = {'type': 'document', 'version': SCHEMA_VERSION}
    lines = _extract_front_matter(lines, document)
    block_parser = _BlockParser()
    blocks = block_parser.parse(lines)
    _parse_inline_content(blocks, _InlineParser(block_parser.references))
    document['children'] = blocks
    return document


def _parse_inline_content(blocks, inline_parser):
    """Replace every temporary 'raw' string with parsed inline children."""
    for block in blocks:
        if 'raw' in block:
            block['children'] = inline_parser.parse(block.pop('raw'))
        elif 'children' in block:
            _parse_inline_content(block['children'], inline_parser)
