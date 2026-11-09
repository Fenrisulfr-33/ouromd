/**
 * json2md.js — turn an mdjson document (JSON) back into Markdown.
 *
 * Zero dependencies. Works in the browser (ES module) and in Node.
 * This is a port of python/mdjson/renderer.py; the test suite checks that
 * both produce byte-identical output.
 *
 *   import { jsonToMarkdown } from './json2md.js';
 *   const article = await (await fetch('/api/articles/my-post')).json();
 *   const markdown = jsonToMarkdown(article);
 *
 * The argument may be the parsed object or a JSON string.
 */

const MARKDOWN_SPECIAL_CHARACTER_PATTERN = /([\\`*_\[\]<~^|])/g;
const EMOJI_COLON_PATTERN = /:(?=[A-Za-z0-9_+\-]*[A-Za-z][A-Za-z0-9_+\-]*:|[+\-]1:)/g;
const URL_SCHEME_PATTERN = /(https?):(?=\/\/)/gi;
const WWW_PREFIX_PATTERN = /(?<![A-Za-z0-9])(www)\./gi;
const ESCAPABLE_BACKSLASH_PATTERN = /\\(?=[!-\/:-@\[-`{-~])/g;
const LINE_START_BLOCK_PATTERN = /^(?:#{1,6}(?:[ \t]|$)|>|[-+](?:[ \t]|$)|-[-=]|:[ \t])/;
const ORDERED_LIST_START_PATTERN = /^(\d{1,9})([.)])(?=[ \t]|$)/;
const ASCII_PUNCTUATION = new Set('!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~');
const WRAPPED_INLINE_MARKERS = {
	delete: '~~', highlight: '==', subscript: '~', superscript: '^',
};
const TABLE_ALIGNMENT_DELIMITERS = {
	left: ':---', right: '---:', center: ':---:',
};

// ---------------------------------------------------------------------------
// Escaping
// ---------------------------------------------------------------------------

function escapeText(value, atLineStart) {
	let escaped = value.replace(MARKDOWN_SPECIAL_CHARACTER_PATTERN, '\\$1');
	escaped = escapeEqualsSigns(escaped);
	escaped = escaped.replace(EMOJI_COLON_PATTERN, '\\:');
	escaped = escaped.replace(URL_SCHEME_PATTERN, '$1\\:');
	escaped = escaped.replace(WWW_PREFIX_PATTERN, '$1\\.');
	if (atLineStart) escaped = escapeLineStart(escaped);
	return escaped;
}

function escapeEqualsSigns(text) {
	// '=' only matters as '==' (highlight) or a setext underline
	let escaped = '';
	const lastIndex = text.length - 1;
	for (let index = 0; index < text.length; index++) {
		const character = text[index];
		if (character === '=' && (index === 0 || index === lastIndex ||
			text[index - 1] === '=' || text[index + 1] === '=')) {
			escaped += '\\=';
		} else {
			escaped += character;
		}
	}
	return escaped;
}

function escapeLineStart(text) {
	if (LINE_START_BLOCK_PATTERN.test(text)) return '\\' + text;
	const orderedMatch = ORDERED_LIST_START_PATTERN.exec(text);
	if (orderedMatch) {
		const number = orderedMatch[1];
		return number + '\\' + text.slice(number.length);
	}
	return text;
}

function renderCodeSpan(value, inTable) {
	const backtickRunLengths = new Set((value.match(/`+/g) || []).map((run) => run.length));
	let fenceLength = 1;
	while (backtickRunLengths.has(fenceLength)) fenceLength++;
	const fence = '`'.repeat(fenceLength);
	const padding = needsCodeSpanPadding(value) ? ' ' : '';
	if (inTable) value = value.replace(/\|/g, '\\|');
	return fence + padding + value + padding + fence;
}

function needsCodeSpanPadding(value) {
	if (value.startsWith('`') || value.endsWith('`')) return true;
	return value.startsWith(' ') && value.endsWith(' ') && value.replace(/^ +| +$/g, '') !== '';
}

function renderLinkTarget(url, title) {
	return '(' + renderLinkDestination(url) + renderLinkTitle(title) + ')';
}

function renderLinkDestination(url) {
	if (url === '' || /[\s<>]/.test(url) || !hasBalancedParentheses(url)) {
		const escaped = url.replace(/\\/g, '\\\\').replace(/</g, '\\<').replace(/>/g, '\\>');
		return '<' + escaped + '>';
	}
	return url.replace(ESCAPABLE_BACKSLASH_PATTERN, '\\\\');
}

function hasBalancedParentheses(text) {
	let depth = 0;
	for (const character of text) {
		if (character === '(') {
			depth++;
		} else if (character === ')') {
			depth--;
			if (depth < 0) return false;
		}
	}
	return depth === 0;
}

function renderLinkTitle(title) {
	if (title === undefined || title === null) return '';
	const escaped = title.replace(ESCAPABLE_BACKSLASH_PATTERN, '\\\\');
	return ' "' + escaped.replace(/"/g, '\\"') + '"';
}

function plainText(nodes) {
	let text = '';
	for (const node of nodes) {
		if (node.type === 'text') text += node.value;
		else if (node.children) text += plainText(node.children);
	}
	return text;
}

// ---------------------------------------------------------------------------
// Inlines
// ---------------------------------------------------------------------------

function renderInlines(nodes, context) {
	// Context keys: singleLine, inTable, atStart, parent,
	// parentEmphasisCharacter, atEdge, previousCharacter
	context = context || {};
	let rendered = '';
	let atStart = 'atStart' in context ? context.atStart : true;
	const lastIndex = nodes.length - 1;
	nodes.forEach((node, index) => {
		const nodeContext = {
			...context,
			atEdge: index === 0 || index === lastIndex,
			previousCharacter: rendered.slice(-1),
		};
		let piece = renderInline(node, nodeContext, atStart);
		if (node.type === 'text' && rendered) piece = protectTextAfterBareUrl(rendered, piece);
		if (node.type === 'link' && piece.startsWith('[') && rendered.endsWith('!')) {
			// a literal '!' before a link would make it an image
			rendered = rendered.slice(0, -1) + '\\!';
		}
		rendered += piece;
		atStart = (node.type === 'break' || node.type === 'softbreak') && !context.singleLine;
	});
	return rendered;
}

function emphasisCharacter(nodeType, context) {
	// Pick '*' or '_' so nested emphasis re-parses with the same nesting.
	const parentCharacter = context.parentEmphasisCharacter;
	// same kind nested (em in em, strong in strong), or em at the edge of a
	// strong (`***x***` would read back as em(strong)): flip the character
	const sameKindNested = context.parent === nodeType;
	const emphasisAtEdge = nodeType === 'emphasis' && context.atEdge;
	if (parentCharacter && (sameKindNested || emphasisAtEdge)) {
		return parentCharacter === '*' ? '_' : '*';
	}
	// don't glue onto a neighbouring run of the same character (`*a**b*`)
	if (context.previousCharacter === '*') return '_';
	return '*';
}

function wrapInline(marker, node, context) {
	const innerContext = { ...context, atStart: false, parent: node.type };
	innerContext.parentEmphasisCharacter = (marker[0] === '*' || marker[0] === '_') ? marker[0] : undefined;
	return marker + renderInlines(node.children || [], innerContext) + marker;
}

function countOccurrences(text, character) {
	return text.split(character).length - 1;
}

function trimTrailingUrlPunctuation(url) {
	while (url) {
		const lastCharacter = url[url.length - 1];
		if ('?!.,:*_~\'"'.includes(lastCharacter)) {
			url = url.slice(0, -1);
		} else if (lastCharacter === ')' && countOccurrences(url, ')') > countOccurrences(url, '(')) {
			url = url.slice(0, -1);
		} else {
			break;
		}
	}
	return url;
}

function bareUrlText(node) {
	// The text a bare URL link renders as, or null if it can't render bare.
	if (node.type !== 'link' || !node.bare || node.autolink) return null;
	const url = node.url;
	const text = plainText(node.children || []);
	if (text !== url && 'http://' + text !== url) return null;
	if (/[\s<>\\]/.test(text)) return null;
	if (trimTrailingUrlPunctuation(text) !== text) return null;
	return text;
}

function protectTextAfterBareUrl(before, piece) {
	// Stop text right after a bare URL from being read back as part of it.
	if (!piece || !ASCII_PUNCTUATION.has(piece[0]) || piece[0] === '\\') return piece;
	const url = trailingBareUrl(before);
	if (url === null) return piece;
	const continuation = /^[^\s<>\\]*/.exec(piece)[0];
	if (trimTrailingUrlPunctuation(url + continuation) !== trimTrailingUrlPunctuation(url)) {
		return '\\' + piece;
	}
	return piece;
}

function trailingBareUrl(text) {
	const tail = /[^\s<>\\]*$/.exec(text)[0];
	const bareUrlStartPattern = /(?:https?:\/\/|www\.)/gi;
	let urlMatch;
	while ((urlMatch = bareUrlStartPattern.exec(tail)) !== null) {
		const start = urlMatch.index;
		if (start === 0 || '*_~('.includes(tail[start - 1])) return tail.slice(start);
	}
	return null;
}

function renderInline(node, context, atStart) {
	const nodeType = node.type;
	switch (nodeType) {
		case 'text': return escapeText(node.value, atStart);
		case 'softbreak': return context.singleLine ? ' ' : '\n';
		case 'break': return context.singleLine ? ' ' : '\\\n';
		case 'emphasis': return wrapInline(emphasisCharacter(nodeType, context), node, context);
		case 'strong': return wrapInline(emphasisCharacter(nodeType, context).repeat(2), node, context);
		case 'delete':
		case 'highlight':
		case 'subscript':
		case 'superscript':
			return wrapInline(WRAPPED_INLINE_MARKERS[nodeType], node, context);
		case 'inlineCode': return renderCodeSpan(node.value, context.inTable);
		case 'html': return node.value;
		case 'emoji': return ':' + node.name + ':';
		case 'footnoteReference': return '[^' + node.label + ']';
		case 'image': return renderImage(node);
		case 'link': return renderLink(node, context);
		default: {
			if (!node.children) return '';
			const childContext = {
				...context, atStart: false, parent: nodeType, parentEmphasisCharacter: undefined,
			};
			return renderInlines(node.children, childContext);
		}
	}
}

function renderImage(node) {
	const altText = escapeText(node.alt || '', false);
	return '![' + altText + ']' + renderLinkTarget(node.url, node.title);
}

function renderLink(node, context) {
	const url = node.url;
	if (node.autolink) {
		const autolink = renderAutolink(url, plainText(node.children || []));
		if (autolink !== null) return autolink;
	}
	const bareText = bareUrlText(node);
	if (bareText !== null) return bareText;
	const labelContext = {
		...context, atStart: false, parent: 'link', parentEmphasisCharacter: undefined,
	};
	const label = renderInlines(node.children || [], labelContext);
	return '[' + label + ']' + renderLinkTarget(url, node.title);
}

function renderAutolink(url, text) {
	if (url.startsWith('mailto:') && text === url.slice('mailto:'.length)) return '<' + text + '>';
	if (text === url && !/[\s<>]/.test(url)) return '<' + url + '>';
	return null;
}

// ---------------------------------------------------------------------------
// Blocks
// ---------------------------------------------------------------------------

function indentLines(text, firstPrefix, restPrefix) {
	return text.split('\n').map((line, index) => {
		const prefix = index === 0 ? firstPrefix : restPrefix;
		return line ? prefix + line : prefix.replace(/\s+$/, '');
	}).join('\n');
}

function renderBlocks(blocks, tight) {
	// Two lists in a row with the same marker would merge into one list when
	// re-parsed, so the second one switches marker (- <-> *, . <-> )).
	const parts = [];
	let previous = null;
	let previousMarker = null;
	for (const block of blocks) {
		const alternateMarker = repeatsPreviousList(block, previous, previousMarker);
		parts.push(renderBlock(block, alternateMarker));
		previous = block;
		previousMarker = block.type === 'list' ? listMarker(block, alternateMarker) : null;
	}
	return parts.join(tight ? '\n' : '\n\n');
}

function repeatsPreviousList(block, previous, previousMarker) {
	return block.type === 'list' &&
		previous !== null &&
		previous.type === 'list' &&
		Boolean(previous.ordered) === Boolean(block.ordered) &&
		previousMarker === defaultListMarker(block);
}

function defaultListMarker(listNode) {
	const marker = listNode.marker;
	if (listNode.ordered) return (marker === '.' || marker === ')') ? marker : '.';
	return ['-', '*', '+'].includes(marker) ? marker : '-';
}

function listMarker(listNode, alternate) {
	const marker = defaultListMarker(listNode);
	if (!alternate) return marker;
	if (listNode.ordered) return marker === '.' ? ')' : '.';
	return marker === '-' ? '*' : '-';
}

function renderBlock(node, alternateMarker) {
	switch (node.type) {
		case 'paragraph': return renderInlines(node.children || []);
		case 'heading': return renderHeading(node);
		case 'thematicBreak': return '***';
		case 'blockquote': return renderBlockquote(node);
		case 'code': return renderCodeBlock(node);
		case 'html': return node.value || '';
		case 'list': return renderList(node, alternateMarker);
		case 'table': return renderTable(node);
		case 'definitionList': return renderDefinitionList(node);
		case 'footnoteDefinition': return renderFootnoteDefinition(node);
		default:
			if (node.children) return renderBlocks(node.children);
			return '';
	}
}

function renderHeading(node) {
	let text = renderInlines(node.children || [], { singleLine: true });
	if (text.endsWith('#')) text = text.slice(0, -1) + '\\#';
	text = text.replace(/\{(#[^\s{}]+\}[ \t]*)$/, '\\{$1');
	let heading = '#'.repeat(Math.max(1, Math.min(6, node.level || 1)));
	if (text) heading += ' ' + text;
	if (node.id) heading += ' {#' + node.id + '}';
	return heading;
}

function renderBlockquote(node) {
	const inner = renderBlocks(node.children || []);
	return inner ? indentLines(inner, '> ', '> ') : '>';
}

function renderFootnoteDefinition(node) {
	const body = renderBlocks(node.children || []);
	return indentLines(body, '[^' + node.label + ']: ', '    ');
}

function renderCodeBlock(node) {
	const value = node.value || '';
	let info = node.lang || '';
	if (node.meta) info += ' ' + node.meta;
	const fenceCharacter = info.includes('`') ? '~' : '`';
	const runPattern = new RegExp(fenceCharacter + '+', 'g');
	const runLengths = (value.match(runPattern) || []).map((run) => run.length);
	const fence = fenceCharacter.repeat(Math.max(3, Math.max(0, ...runLengths) + 1));
	const body = value ? value + '\n' : '';
	return fence + info + '\n' + body + fence;
}

function renderList(node, alternateMarker) {
	const ordered = Boolean(node.ordered);
	const tight = 'tight' in node ? node.tight : true;
	const start = ordered ? ('start' in node ? node.start : 1) : null;
	const marker = listMarker(node, alternateMarker);
	const items = (node.children || []).map((item, offset) => {
		const itemMarker = ordered ? String(start + offset) + marker : marker;
		return renderListItem(item, itemMarker, tight);
	});
	return items.join(tight ? '\n' : '\n\n');
}

function renderListItem(item, itemMarker, tight) {
	let content = renderBlocks(item.children || [], tight);
	if (item.checked !== undefined && item.checked !== null) {
		content = (item.checked ? '[x] ' : '[ ] ') + content;
	}
	if (!content) return itemMarker;
	const continuationIndent = ' '.repeat(itemMarker.length + 1);
	return indentLines(content, itemMarker + ' ', continuationIndent);
}

function renderTable(node) {
	const rows = node.children || [];
	if (!rows.length) return '';
	const alignments = node.align || [];
	let width = Math.max(...rows.map((row) => (row.children || []).length));
	width = Math.max(width, alignments.length, 1);
	const delimiterCells = [];
	for (let column = 0; column < width; column++) {
		delimiterCells.push(alignmentDelimiter(alignments, column));
	}
	const lines = [renderTableRow(renderTableCells(rows[0], width)), renderTableRow(delimiterCells)];
	for (const row of rows.slice(1)) lines.push(renderTableRow(renderTableCells(row, width)));
	return lines.join('\n');
}

function alignmentDelimiter(alignments, column) {
	const alignment = column < alignments.length ? alignments[column] : null;
	return TABLE_ALIGNMENT_DELIMITERS[alignment] || '---';
}

function renderTableCells(row, width) {
	const cellContext = { singleLine: true, inTable: true };
	const cells = (row.children || []).map((cell) => renderInlines(cell.children || [], cellContext));
	while (cells.length < width) cells.push('');
	return cells;
}

function renderTableRow(cells) {
	return '| ' + cells.join(' | ') + ' |';
}

function renderDefinitionList(node) {
	return (node.children || []).map((item) => {
		return (item.children || []).map(renderDefinitionChild).join('\n');
	}).join('\n\n');
}

function renderDefinitionChild(child) {
	const children = child.children || [];
	if (child.type === 'definitionTerm') return renderInlines(children, { singleLine: true });
	return ': ' + renderInlines(children, { atStart: false });
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

function loadDocument(jsonDocument) {
	return typeof jsonDocument === 'string' ? JSON.parse(jsonDocument) : jsonDocument;
}

/**
 * Render a document (object or JSON string) to Markdown text.
 * @param {object|string} jsonDocument
 * @returns {string}
 */
export function jsonToMarkdown(jsonDocument) {
	const markdownDocument = loadDocument(jsonDocument);
	const parts = [];
	const frontMatter = markdownDocument.frontMatter;
	if (frontMatter !== undefined && frontMatter !== null) {
		const separator = frontMatter ? '\n' : '';
		parts.push('---\n' + frontMatter + separator + '---');
	}
	const body = renderBlocks(markdownDocument.children || []);
	if (body) parts.push(body);
	return parts.join('\n\n') + '\n';
}

/** Markdown for the body only (no front matter); handy when you show `meta` yourself. */
export function jsonToMarkdownBody(jsonDocument) {
	const body = renderBlocks(loadDocument(jsonDocument).children || []);
	return body ? body + '\n' : '';
}

export default jsonToMarkdown;
