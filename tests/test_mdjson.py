"""
Run:  python -m unittest discover -s tests -v      (from the repo root)

Checks:
  1. Round-trip stability: md -> json -> md -> json gives the same JSON,
     and rendering is idempotent.
  2. Each Markdown Guide feature parses into the expected node.
  3. The browser renderer (js/json2md.js) produces byte-identical Markdown
     to the Python renderer (skipped if Node.js is not installed).
"""

import glob
import json
import os
import shutil
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'python'))

from mdjson import markdown_to_json, json_to_markdown  # noqa: E402

FIXTURES = sorted(glob.glob(os.path.join(ROOT, 'tests', 'fixtures', '*.md')))


def read_file(path):
    with open(path, encoding='utf-8') as fixture_file:
        return fixture_file.read()


def parse_blocks(markdown):
    return markdown_to_json(markdown)['children']


def parse_inlines(markdown):
    return parse_blocks(markdown)[0]['children']


class RoundTrip(unittest.TestCase):
    def test_fixtures_round_trip(self):
        for path in FIXTURES:
            with self.subTest(fixture=os.path.basename(path)):
                first_json = markdown_to_json(read_file(path))
                rendered_markdown = json_to_markdown(first_json)
                second_json = markdown_to_json(rendered_markdown)
                self.assertEqual(first_json, second_json)
                self.assertEqual(rendered_markdown,
                                 json_to_markdown(second_json))

    def test_json_serialisable(self):
        for path in FIXTURES:
            document = markdown_to_json(read_file(path))
            self.assertEqual(json.loads(json.dumps(document)), document)


class Basic(unittest.TestCase):
    def test_atx_headings(self):
        for level in range(1, 7):
            heading = parse_blocks('#' * level + ' Title')[0]
            self.assertEqual((heading['type'], heading['level']),
                             ('heading', level))

    def test_setext_headings(self):
        self.assertEqual(parse_blocks('Title\n===')[0]['level'], 1)
        self.assertEqual(parse_blocks('Title\n---')[0]['level'], 2)

    def test_heading_id(self):
        heading = parse_blocks('### My Heading {#custom-id}')[0]
        self.assertEqual(heading['id'], 'custom-id')
        self.assertEqual(heading['children'],
                         [{'type': 'text', 'value': 'My Heading'}])

    def test_line_breaks(self):
        node_types = [node['type']
                      for node in parse_inlines('a  \nb\\\nc\nd')]
        self.assertEqual(node_types, ['text', 'break', 'text', 'break',
                                      'text', 'softbreak', 'text'])

    def test_bold_italic(self):
        self.assertEqual(parse_inlines('**b**')[0]['type'], 'strong')
        self.assertEqual(parse_inlines('__b__')[0]['type'], 'strong')
        self.assertEqual(parse_inlines('*i*')[0]['type'], 'emphasis')
        self.assertEqual(parse_inlines('_i_')[0]['type'], 'emphasis')
        nested = parse_inlines('***bi***')[0]
        self.assertEqual((nested['type'], nested['children'][0]['type']),
                         ('emphasis', 'strong'))
        self.assertEqual(parse_inlines('snake_case_name'),
                         [{'type': 'text', 'value': 'snake_case_name'}])

    def test_blockquote_nested(self):
        blockquote = parse_blocks('> a\n>\n>> b')[0]
        self.assertEqual(blockquote['type'], 'blockquote')
        self.assertEqual(blockquote['children'][1]['type'], 'blockquote')

    def test_lists(self):
        ordered_list = parse_blocks('1. a\n2. b\n    1. c')[0]
        self.assertTrue(ordered_list['ordered'])
        self.assertEqual(
            ordered_list['children'][1]['children'][1]['type'], 'list')
        self.assertEqual(parse_blocks('7. a\n8. b')[0]['start'], 7)
        self.assertFalse(parse_blocks('- a\n\n- b')[0]['tight'])

    def test_code(self):
        self.assertEqual(parse_inlines('`x`')[0],
                         {'type': 'inlineCode', 'value': 'x'})
        self.assertEqual(parse_inlines('``a `b` c``')[0]['value'], 'a `b` c')
        self.assertEqual(parse_blocks('    code')[0],
                         {'type': 'code', 'value': 'code'})
        code_block = parse_blocks('```py\nprint(1)\n```')[0]
        self.assertEqual((code_block['lang'], code_block['value']),
                         ('py', 'print(1)'))

    def test_hr(self):
        for markdown in ('***', '---', '___', '* * *'):
            self.assertEqual(parse_blocks(markdown)[0]['type'],
                             'thematicBreak')

    def test_links(self):
        link = parse_inlines('[t](http://x.com "T")')[0]
        self.assertEqual((link['url'], link['title']), ('http://x.com', 'T'))
        autolink = parse_inlines('<https://x.com>')[0]
        self.assertTrue(autolink['autolink'])
        email = parse_inlines('<me@x.com>')[0]
        self.assertEqual(email['url'], 'mailto:me@x.com')
        unresolved = parse_inlines('[t][1]\n\n')
        self.assertEqual(unresolved[0]['type'], 'text')
        reference = parse_blocks(
            '[t][1]\n\n[1]: <http://x.com> "Ref"')[0]['children'][0]
        self.assertEqual(
            (reference['type'], reference['url'], reference['title']),
            ('link', 'http://x.com', 'Ref'))

    def test_images(self):
        image = parse_inlines('![alt *x*](/a.png "T")')[0]
        self.assertEqual(
            (image['type'], image['alt'], image['url'], image['title']),
            ('image', 'alt x', '/a.png', 'T'))
        linked_image = parse_inlines('[![a](i.png)](http://x)')[0]
        self.assertEqual(
            (linked_image['type'], linked_image['children'][0]['type']),
            ('link', 'image'))

    def test_escapes(self):
        self.assertEqual(parse_inlines('\\*not em\\*'),
                         [{'type': 'text', 'value': '*not em*'}])
        self.assertEqual(parse_blocks('\\# no')[0]['type'], 'paragraph')

    def test_html(self):
        self.assertEqual(parse_blocks('<div>\nhi\n</div>')[0]['type'], 'html')
        self.assertEqual(parse_inlines('a <em>b</em>')[1],
                         {'type': 'html', 'value': '<em>'})


class Extended(unittest.TestCase):
    def test_table(self):
        table = parse_blocks('| a | b |\n| :-- | --: |\n| 1 | 2 |')[0]
        self.assertEqual(table['type'], 'table')
        self.assertEqual(table['align'], ['left', 'right'])
        self.assertEqual(len(table['children']), 2)

    def test_footnotes(self):
        blocks = parse_blocks('x[^1]\n\n[^1]: note')
        self.assertEqual(blocks[0]['children'][1],
                         {'type': 'footnoteReference', 'label': '1'})
        self.assertEqual(blocks[1]['type'], 'footnoteDefinition')

    def test_definition_list(self):
        definition_list = parse_blocks('Term\n: one\n: two')[0]
        self.assertEqual(definition_list['type'], 'definitionList')
        first_item = definition_list['children'][0]
        self.assertEqual(
            [child['type'] for child in first_item['children']],
            ['definitionTerm', 'definitionDescription',
             'definitionDescription'])

    def test_strike_highlight_sub_sup(self):
        self.assertEqual(parse_inlines('~~x~~')[0]['type'], 'delete')
        self.assertEqual(parse_inlines('==x==')[0]['type'], 'highlight')
        self.assertEqual(parse_inlines('H~2~O')[1]['type'], 'subscript')
        self.assertEqual(parse_inlines('X^2^')[1]['type'], 'superscript')

    def test_task_list(self):
        items = parse_blocks('- [x] done\n- [ ] todo')[0]['children']
        self.assertEqual([item['checked'] for item in items], [True, False])

    def test_emoji(self):
        self.assertEqual(parse_inlines('hi :tent:')[1],
                         {'type': 'emoji', 'name': 'tent'})
        self.assertEqual(parse_inlines('10:30:45'),
                         [{'type': 'text', 'value': '10:30:45'}])

    def test_bare_urls(self):
        link = parse_inlines('see https://x.com/a_b.')[1]
        self.assertEqual((link['url'], link['bare']),
                         ('https://x.com/a_b', True))
        www_link = parse_inlines('www.x.com')[0]
        self.assertEqual(www_link['url'], 'http://www.x.com')

    def test_front_matter(self):
        document = markdown_to_json(
            '---\ntitle: "Hi"\ntags: [a, b]\n---\n\nBody')
        self.assertEqual(document['meta'],
                         {'title': 'Hi', 'tags': ['a', 'b']})
        self.assertEqual(document['children'][0]['type'], 'paragraph')


@unittest.skipUnless(shutil.which('node'), 'Node.js not installed')
class JsParity(unittest.TestCase):
    def test_js_matches_python(self):
        script = os.path.join(ROOT, 'tests', 'render_with_js.mjs')
        for path in FIXTURES:
            with self.subTest(fixture=os.path.basename(path)):
                document = markdown_to_json(read_file(path))
                completed = subprocess.run(
                    ['node', script], input=json.dumps(document),
                    capture_output=True, text=True, encoding='utf-8',
                    check=True)
                self.assertEqual(completed.stdout, json_to_markdown(document))


if __name__ == '__main__':
    unittest.main()
