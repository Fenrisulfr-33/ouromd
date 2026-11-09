"""
Command-line interface.

    python -m mdjson to-json  article.md            # prints JSON
    python -m mdjson to-json  article.md -o a.json  # writes a file
    python -m mdjson to-md    article.json -o a.md  # JSON back to Markdown
    python -m mdjson to-json  posts/*.md --out-dir build/   # batch

Use "-" as the input to read from stdin.
"""

import argparse
import json
import os
import sys

from .parser import markdown_to_json
from .renderer import json_to_markdown

OUTPUT_EXTENSIONS = {'to-json': '.json', 'to-md': '.md'}


def _read_input(path):
    if path == '-':
        return sys.stdin.read()
    with open(path, encoding='utf-8') as input_file:
        return input_file.read()


def _write_output(path, text):
    if path in (None, '-'):
        sys.stdout.write(text)
        return
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as output_file:
        output_file.write(text)


def convert(mode, text, compact=False):
    if mode == 'to-md':
        return json_to_markdown(json.loads(text))
    document = markdown_to_json(text)
    if compact:
        return json.dumps(document, ensure_ascii=False,
                          separators=(',', ':')) + '\n'
    return json.dumps(document, ensure_ascii=False, indent=2) + '\n'


def _build_argument_parser():
    argument_parser = argparse.ArgumentParser(
        prog='mdjson', description='Markdown <-> JSON converter')
    argument_parser.add_argument('mode', choices=list(OUTPUT_EXTENSIONS))
    argument_parser.add_argument(
        'inputs', nargs='+', help='input file(s), or - for stdin')
    argument_parser.add_argument(
        '-o', '--output', help='output file (single input only)')
    argument_parser.add_argument(
        '--out-dir', help='output directory (for several inputs)')
    argument_parser.add_argument(
        '--compact', action='store_true', help='minified JSON')
    return argument_parser


def _output_path(arguments, input_path):
    if not arguments.out_dir:
        return arguments.output
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_name = base_name + OUTPUT_EXTENSIONS[arguments.mode]
    return os.path.join(arguments.out_dir, output_name)


def main(argv=None):
    argument_parser = _build_argument_parser()
    arguments = argument_parser.parse_args(argv)
    if len(arguments.inputs) > 1 and arguments.output:
        argument_parser.error('use --out-dir with several inputs')
    for input_path in arguments.inputs:
        result = convert(
            arguments.mode, _read_input(input_path), arguments.compact)
        _write_output(_output_path(arguments, input_path), result)


if __name__ == '__main__':
    main()
