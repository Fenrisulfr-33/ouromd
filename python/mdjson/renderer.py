"""
JSON -> Markdown renderer (Python version).

This is a port of js/json2md.js so the server and the browser produce
identical Markdown. If you change one, change the other (the test suite
checks that they match).
"""

import json
import re

MARKDOWN_SPECIAL_CHARACTER_PATTERN = re.compile(r'([\\`*_\[\]<~^|])')
EMOJI_COLON_PATTERN = re.compile(
    r':(?=[A-Za-z0-9_+\-]*[A-Za-z][A-Za-z0-9_+\-]*:|[+\-]1:)')
URL_SCHEME_PATTERN = re.compile(r'(https?):(?=//)', re.I)
WWW_PREFIX_PATTERN = re.compile(r'(?<![A-Za-z0-9])(www)\.', re.I)
ESCAPABLE_BACKSLASH_PATTERN = re.compile(r'\\(?=[!-/:-@\[-`{-~])')
LINE_START_BLOCK_PATTERN = re.compile(
    r'(?:#{1,6}(?:[ \t]|$)|>|[-+](?:[ \t]|$)|-[-=]|:[ \t])')
ORDERED_LIST_START_PATTERN = re.compile(r'(\d{1,9})([.)])(?=[ \t]|$)')
BARE_URL_START_PATTERN = re.compile(r'(?:https?://|www\.)', re.I)
ASCII_PUNCTUATION = set('!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~')
WRAPPED_INLINE_MARKERS = {
    'delete': '~~', 'highlight': '==', 'subscript': '~', 'superscript': '^',
}
TABLE_ALIGNMENT_DELIMITERS = {
    'left': ':---', 'right': '---:', 'center': ':---:',
}


# --------------------------------------------------------------------------
# Escaping
# --------------------------------------------------------------------------

def _escape_text(value, at_line_start):
    escaped = MARKDOWN_SPECIAL_CHARACTER_PATTERN.sub(r'\\\1', value)
    escaped = _escape_equals_signs(escaped)
    escaped = EMOJI_COLON_PATTERN.sub(r'\\:', escaped)
    escaped = URL_SCHEME_PATTERN.sub(r'\1\\:', escaped)
    escaped = WWW_PREFIX_PATTERN.sub(r'\1\\.', escaped)
    if at_line_start:
        escaped = _escape_line_start(escaped)
    return escaped


def _escape_equals_signs(text):
    """'=' only matters as '==' (highlight) or a setext underline."""
    escaped = []
    last_index = len(text) - 1
    for index, character in enumerate(text):
        if character == '=' and (
                index == 0 or index == last_index
                or text[index - 1] == '=' or text[index + 1] == '='):
            escaped.append('\\=')
        else:
            escaped.append(character)
    return ''.join(escaped)


def _escape_line_start(text):
    if LINE_START_BLOCK_PATTERN.match(text):
        return '\\' + text
    ordered_match = ORDERED_LIST_START_PATTERN.match(text)
    if ordered_match:
        number = ordered_match.group(1)
        return number + '\\' + text[len(number):]
    return text


def _render_code_span(value, in_table):
    backtick_run_lengths = {len(run) for run in re.findall(r'`+', value)}
    fence_length = 1
    while fence_length in backtick_run_lengths:
        fence_length += 1
    fence = '`' * fence_length
    padding = ' ' if _needs_code_span_padding(value) else ''
    if in_table:
        value = value.replace('|', '\\|')
    return fence + padding + value + padding + fence


def _needs_code_span_padding(value):
    if value.startswith('`') or value.endswith('`'):
        return True
    return (value.startswith(' ') and value.endswith(' ')
            and value.strip(' ') != '')


def _render_link_target(url, title):
    return ('(' + _render_link_destination(url)
            + _render_link_title(title) + ')')


def _render_link_destination(url):
    if (url == '' or re.search(r'[\s<>]', url)
            or not _has_balanced_parentheses(url)):
        escaped = (url.replace('\\', '\\\\')
                   .replace('<', '\\<').replace('>', '\\>'))
        return '<' + escaped + '>'
    return ESCAPABLE_BACKSLASH_PATTERN.sub(r'\\\\', url)


def _has_balanced_parentheses(text):
    depth = 0
    for character in text:
        if character == '(':
            depth += 1
        elif character == ')':
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _render_link_title(title):
    if title is None:
        return ''
    escaped = ESCAPABLE_BACKSLASH_PATTERN.sub(r'\\\\', title)
    return ' "' + escaped.replace('"', '\\"') + '"'


def _plain_text(nodes):
    parts = []
    for node in nodes:
        if node['type'] == 'text':
            parts.append(node['value'])
        elif 'children' in node:
            parts.append(_plain_text(node['children']))
    return ''.join(parts)


# --------------------------------------------------------------------------
# Inlines
# --------------------------------------------------------------------------

def _render_inlines(nodes, context=None):
    """Context keys: single_line, in_table, at_start, parent,
    parent_emphasis_character, at_edge, previous_character."""
    context = context or {}
    rendered = ''
    at_start = context.get('at_start', True)
    last_index = len(nodes) - 1
    for index, node in enumerate(nodes):
        node_context = dict(context, at_edge=index in (0, last_index),
                            previous_character=rendered[-1:])
        piece = _render_inline(node, node_context, at_start)
        if node['type'] == 'text' and rendered:
            piece = _protect_text_after_bare_url(rendered, piece)
        if (node['type'] == 'link' and piece.startswith('[')
                and rendered.endswith('!')):
            # a literal '!' before a link would make it an image
            rendered = rendered[:-1] + '\\!'
        rendered += piece
        at_start = (node['type'] in ('break', 'softbreak')
                    and not context.get('single_line'))
    return rendered


def _emphasis_character(node_type, context):
    """Pick '*' or '_' so nested emphasis re-parses with the same nesting."""
    parent_character = context.get('parent_emphasis_character')
    # same kind nested (em in em, strong in strong), or em at the edge of a
    # strong (`***x***` would read back as em(strong)): flip the character
    same_kind_nested = context.get('parent') == node_type
    emphasis_at_edge = node_type == 'emphasis' and context.get('at_edge')
    if parent_character and (same_kind_nested or emphasis_at_edge):
        return '_' if parent_character == '*' else '*'
    # don't glue onto a neighbouring run of the same character (`*a**b*`)
    if context.get('previous_character') == '*':
        return '_'
    return '*'


def _wrap_inline(marker, node, context):
    inner_context = dict(context, at_start=False, parent=node['type'])
    if marker[0] in '*_':
        inner_context['parent_emphasis_character'] = marker[0]
    else:
        inner_context.pop('parent_emphasis_character', None)
    inner = _render_inlines(node.get('children', []), inner_context)
    return marker + inner + marker


def _trim_trailing_url_punctuation(url):
    while url:
        if url[-1] in '?!.,:*_~\'"':
            url = url[:-1]
        elif url[-1] == ')' and url.count(')') > url.count('('):
            url = url[:-1]
        else:
            break
    return url


def _bare_url_text(node):
    """The text a bare URL link renders as, or None if it can't render bare."""
    if node['type'] != 'link' or not node.get('bare') or node.get('autolink'):
        return None
    url, text = node['url'], _plain_text(node.get('children', []))
    if text != url and 'http://' + text != url:
        return None
    if re.search(r'[\s<>\\]', text):
        return None
    if _trim_trailing_url_punctuation(text) != text:
        return None
    return text


def _protect_text_after_bare_url(before, piece):
    """Stop text right after a bare URL from being read back as part of it."""
    if not piece or piece[0] not in ASCII_PUNCTUATION or piece[0] == '\\':
        return piece
    url = _trailing_bare_url(before)
    if url is None:
        return piece
    continuation = re.match(r'[^\s<>\\]*', piece).group(0)
    if (_trim_trailing_url_punctuation(url + continuation)
            != _trim_trailing_url_punctuation(url)):
        return '\\' + piece
    return piece


def _trailing_bare_url(text):
    tail = re.search(r'[^\s<>\\]*\Z', text).group(0)
    for url_match in BARE_URL_START_PATTERN.finditer(tail):
        start = url_match.start()
        if start == 0 or tail[start - 1] in '*_~(':
            return tail[start:]
    return None


def _render_inline(node, context, at_start):
    node_type = node['type']
    if node_type == 'text':
        return _escape_text(node['value'], at_start)
    if node_type == 'softbreak':
        return ' ' if context.get('single_line') else '\n'
    if node_type == 'break':
        return ' ' if context.get('single_line') else '\\\n'
    if node_type == 'emphasis':
        marker = _emphasis_character(node_type, context)
        return _wrap_inline(marker, node, context)
    if node_type == 'strong':
        marker = _emphasis_character(node_type, context) * 2
        return _wrap_inline(marker, node, context)
    if node_type in WRAPPED_INLINE_MARKERS:
        return _wrap_inline(WRAPPED_INLINE_MARKERS[node_type], node, context)
    if node_type == 'inlineCode':
        return _render_code_span(node['value'], context.get('in_table'))
    if node_type == 'html':
        return node['value']
    if node_type == 'emoji':
        return ':' + node['name'] + ':'
    if node_type == 'footnoteReference':
        return '[^' + node['label'] + ']'
    if node_type == 'image':
        return _render_image(node)
    if node_type == 'link':
        return _render_link(node, context)
    if 'children' in node:
        child_context = dict(context, at_start=False, parent=node_type,
                             parent_emphasis_character=None)
        return _render_inlines(node['children'], child_context)
    return ''


def _render_image(node):
    alt_text = _escape_text(node.get('alt', ''), False)
    return '![' + alt_text + ']' + _render_link_target(
        node['url'], node.get('title'))


def _render_link(node, context):
    url = node['url']
    if node.get('autolink'):
        autolink = _render_autolink(
            url, _plain_text(node.get('children', [])))
        if autolink is not None:
            return autolink
    bare_text = _bare_url_text(node)
    if bare_text is not None:
        return bare_text
    label_context = dict(context, at_start=False, parent='link',
                         parent_emphasis_character=None)
    label = _render_inlines(node.get('children', []), label_context)
    return '[' + label + ']' + _render_link_target(url, node.get('title'))


def _render_autolink(url, text):
    if url.startswith('mailto:') and text == url[len('mailto:'):]:
        return '<' + text + '>'
    if text == url and not re.search(r'[\s<>]', url):
        return '<' + url + '>'
    return None


# --------------------------------------------------------------------------
# Blocks
# --------------------------------------------------------------------------

def _indent_lines(text, first_prefix, rest_prefix):
    indented = []
    for index, line in enumerate(text.split('\n')):
        prefix = first_prefix if index == 0 else rest_prefix
        indented.append((prefix + line) if line else prefix.rstrip())
    return '\n'.join(indented)


def _render_blocks(blocks, tight=False):
    # Two lists in a row with the same marker would merge into one list when
    # re-parsed, so the second one switches marker (- <-> *, . <-> )).
    parts = []
    previous, previous_marker = None, None
    for block in blocks:
        alternate_marker = _repeats_previous_list(
            block, previous, previous_marker)
        parts.append(_render_block(block, alternate_marker))
        previous = block
        previous_marker = None
        if block['type'] == 'list':
            previous_marker = _list_marker(block, alternate_marker)
    return ('\n' if tight else '\n\n').join(parts)


def _repeats_previous_list(block, previous, previous_marker):
    return (block['type'] == 'list'
            and previous is not None
            and previous['type'] == 'list'
            and bool(previous.get('ordered')) == bool(block.get('ordered'))
            and previous_marker == _default_list_marker(block))


def _default_list_marker(list_node):
    marker = list_node.get('marker')
    if list_node.get('ordered'):
        return marker if marker in ('.', ')') else '.'
    return marker if marker in ('-', '*', '+') else '-'


def _list_marker(list_node, alternate):
    marker = _default_list_marker(list_node)
    if not alternate:
        return marker
    if list_node.get('ordered'):
        return ')' if marker == '.' else '.'
    return '*' if marker == '-' else '-'


def _render_block(node, alternate_marker=False):
    node_type = node['type']
    if node_type == 'paragraph':
        return _render_inlines(node.get('children', []))
    if node_type == 'heading':
        return _render_heading(node)
    if node_type == 'thematicBreak':
        return '***'
    if node_type == 'blockquote':
        return _render_blockquote(node)
    if node_type == 'code':
        return _render_code_block(node)
    if node_type == 'html':
        return node.get('value', '')
    if node_type == 'list':
        return _render_list(node, alternate_marker)
    if node_type == 'table':
        return _render_table(node)
    if node_type == 'definitionList':
        return _render_definition_list(node)
    if node_type == 'footnoteDefinition':
        return _render_footnote_definition(node)
    if 'children' in node:
        return _render_blocks(node['children'])
    return ''


def _render_heading(node):
    text = _render_inlines(node.get('children', []), {'single_line': True})
    if text.endswith('#'):
        text = text[:-1] + '\\#'
    text = re.sub(r'\{(#[^\s{}]+\}[ \t]*)$', r'\\{\1', text)
    heading = '#' * max(1, min(6, node.get('level', 1)))
    if text:
        heading += ' ' + text
    if node.get('id'):
        heading += ' {#' + node['id'] + '}'
    return heading


def _render_blockquote(node):
    inner = _render_blocks(node.get('children', []))
    return _indent_lines(inner, '> ', '> ') if inner else '>'


def _render_footnote_definition(node):
    body = _render_blocks(node.get('children', []))
    return _indent_lines(body, '[^' + node['label'] + ']: ', '    ')


def _render_code_block(node):
    value = node.get('value', '')
    info = node.get('lang', '') or ''
    if node.get('meta'):
        info += ' ' + node['meta']
    fence_character = '~' if '`' in info else '`'
    run_lengths = [len(run) for run in
                   re.findall(re.escape(fence_character) + '+', value)]
    fence = fence_character * max(3, max(run_lengths, default=0) + 1)
    body = value + '\n' if value else ''
    return fence + info + '\n' + body + fence


def _render_list(node, alternate_marker):
    ordered = bool(node.get('ordered'))
    tight = node.get('tight', True)
    start = node.get('start', 1) if ordered else None
    marker = _list_marker(node, alternate_marker)
    items = []
    for offset, item in enumerate(node.get('children', [])):
        item_marker = str(start + offset) + marker if ordered else marker
        items.append(_render_list_item(item, item_marker, tight))
    return ('\n' if tight else '\n\n').join(items)


def _render_list_item(item, item_marker, tight):
    content = _render_blocks(item.get('children', []), tight)
    if item.get('checked') is not None:
        content = ('[x] ' if item['checked'] else '[ ] ') + content
    if not content:
        return item_marker
    continuation_indent = ' ' * (len(item_marker) + 1)
    return _indent_lines(content, item_marker + ' ', continuation_indent)


def _render_table(node):
    rows = node.get('children', [])
    if not rows:
        return ''
    alignments = node.get('align', [])
    width = max(len(row.get('children', [])) for row in rows)
    width = max(width, len(alignments), 1)
    delimiter_cells = [_alignment_delimiter(alignments, column)
                       for column in range(width)]
    lines = [_render_table_row(_render_table_cells(rows[0], width)),
             _render_table_row(delimiter_cells)]
    lines += [_render_table_row(_render_table_cells(row, width))
              for row in rows[1:]]
    return '\n'.join(lines)


def _alignment_delimiter(alignments, column):
    alignment = alignments[column] if column < len(alignments) else None
    return TABLE_ALIGNMENT_DELIMITERS.get(alignment, '---')


def _render_table_cells(row, width):
    cell_context = {'single_line': True, 'in_table': True}
    cells = [_render_inlines(cell.get('children', []), cell_context)
             for cell in row.get('children', [])]
    return cells + [''] * (width - len(cells))


def _render_table_row(cells):
    return '| ' + ' | '.join(cells) + ' |'


def _render_definition_list(node):
    groups = []
    for item in node.get('children', []):
        lines = [_render_definition_child(child)
                 for child in item.get('children', [])]
        groups.append('\n'.join(lines))
    return '\n\n'.join(groups)


def _render_definition_child(child):
    children = child.get('children', [])
    if child['type'] == 'definitionTerm':
        return _render_inlines(children, {'single_line': True})
    return ': ' + _render_inlines(children, {'at_start': False})


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def _load_document(json_document):
    if isinstance(json_document, str):
        return json.loads(json_document)
    return json_document


def json_to_markdown(json_document):
    """Render a document (dict or JSON string) back to Markdown text."""
    document = _load_document(json_document)
    parts = []
    front_matter = document.get('frontMatter')
    if front_matter is not None:
        separator = '\n' if front_matter else ''
        parts.append('---\n' + front_matter + separator + '---')
    body = _render_blocks(document.get('children', []))
    if body:
        parts.append(body)
    return '\n\n'.join(parts) + '\n'


def json_to_markdown_body(json_document):
    """Markdown for the body only (no front matter)."""
    document = _load_document(json_document)
    body = _render_blocks(document.get('children', []))
    return body + '\n' if body else ''
