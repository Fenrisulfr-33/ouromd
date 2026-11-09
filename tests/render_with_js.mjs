// Reads an mdjson document from stdin and prints the Markdown the browser module produces.
import { jsonToMarkdown } from '../js/json2md.js';

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => { input += chunk; });
process.stdin.on('end', () => { process.stdout.write(jsonToMarkdown(input)); });
