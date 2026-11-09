## Project
ouromd — A markdown to json to markdown tool.

## Stack
- JavaScript (Node.js 24+)
- Python 3.11+

## Structure
- js/json2md.js — browser renderer: JSON → Markdown, for the frontend client
- python/mdjson — parser (Markdown → JSON) and renderer (JSON → Markdown)
- tests/ — test files
- README.md — documentation

## Commands
- Test: `python -m unittest discover -s tests -v`

## Verification
After every change, run in this order:
1. `python -m unittest discover -s tests -v` — fix failing tests

## Conventions
- All python code should follow PEP-8
- Follow principles from "Clean Code" by Robert. C. Martin
- Function and variable naming should describe what is it or what it does, don't shortcut or make assumptions.
- JS indentations should be tabs, Python should be 4 spaces.

## Don't
- Don't overcomplicate things, functions should be easily read
- Don't use outside packages, this is mean to work by itself no dependencies.