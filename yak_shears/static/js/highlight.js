// Note: relies on global `djot` object

if (
	typeof HTMLElement !== "undefined" &&
	!("innerText" in HTMLElement.prototype)
) {
	Object.defineProperty(HTMLElement.prototype, "innerText", {
		get() {
			return this.textContent;
		},
		set(v) {
			this.textContent = v;
		},
	});
}

// PLANNED: consider better escaping logic
function _escapeHTML(ch) {
	switch (ch) {
		case "&":
			return "&amp;";
		case "<":
			return "&lt;";
		case ">":
			return "&gt;";
		case '"':
			return "&quot;";
		case "'":
			return "&#39;";
		default:
			return ch;
	}
}

function highlight(editor) {
	const src = editor.textContent || "";
	const opens = Object.create(null);
	const closes = Object.create(null);
	const add = (map, i, val) => {
		if (i < 0 || i > src.length) return;
		(map[i] || (map[i] = [])).push(val);
	};

	if (!globalThis.djot) throw new Error("Could not find djot library");

	const events = [...globalThis.djot.parseEvents(src)];
	for (const ev of events) {
		const { annot } = ev;
		const start = Math.max(0, Math.min(ev.startpos, src.length));
		const end = Math.max(0, Math.min(ev.endpos, src.length - 1));
		const closeIndex = end;
		switch (annot) {
			case "+emph":
				add(opens, start, "<em>");
				break;
			case "-emph":
				add(closes, closeIndex, "</em>");
				break;
			case "+strong":
				add(opens, start, "<strong>");
				break;
			case "-strong":
				add(closes, closeIndex, "</strong>");
				break;
			case "+block_quote":
				add(opens, start, '<span class="quote">');
				break;
			case "-block_quote":
				add(closes, closeIndex, "</span>");
				break;
			case "+heading": {
				const markerLen = end - start + 1;
				const level = Math.min(6, Math.max(1, markerLen));
				add(opens, start, `<span class="heading h${level}">`);
				break;
			}
			case "-heading":
				add(closes, closeIndex, "</span>");
				break;
			case "checkbox_checked": {
				add(opens, start, '<span class="checkbox checked">');
				const bracketEnd = src.indexOf("]", start);
				if (bracketEnd !== -1 && bracketEnd < closeIndex) {
					add(closes, Math.max(0, bracketEnd), "</span>");
				} else {
					add(closes, closeIndex, "</span>");
				}
				break;
			}
			case "checkbox_unchecked": {
				add(opens, start, '<span class="checkbox unchecked">');
				const bracketEnd = src.indexOf("]", start);
				if (bracketEnd !== -1 && bracketEnd < closeIndex) {
					add(closes, Math.max(0, bracketEnd), "</span>");
				} else {
					add(closes, closeIndex, "</span>");
				}
				break;
			}
			case "+code_block": {
				add(opens, start, "<pre>");
				break;
			}
			case "code_language": {
				const lang = src.substring(start, end + 1);
				add(opens, start, `<code class="language-${lang}">`);
				break;
		   }
			case "-code_block":
				add(closes, closeIndex, "</code></pre>");
				break;
			default:
				break;
		}
	}
	for (const k in closes) closes[k].reverse();

	let out = "";
	for (const idx of Array(src.length).keys()) {
		if (opens[idx]) out += opens[idx].join("");
		if (idx < src.length) out += _escapeHTML(src[idx]);
		if (closes[idx]) out += closes[idx].join("");
	}

	// Save cursor position
	const sel = window.getSelection();
	let cursorOffset = null;
	if (sel.rangeCount > 0) {
		const range = sel.getRangeAt(0);
		cursorOffset = getTextOffset(
			editor,
			range.startContainer,
			range.startOffset,
		);
	}

	editor.innerHTML = out;

	// Restore cursor position. A null offset means the caret was somewhere else on
	// the page, and moving it here would take it away from whatever the reader is
	// actually pointing at.
	if (cursorOffset !== null) {
		const newRange = document.createRange();
		const { node, offset } = getNodeAtOffset(editor, cursorOffset);
		if (node) {
			newRange.setStart(node, offset);
			newRange.setEnd(node, offset);
			sel.removeAllRanges();
			sel.addRange(newRange);
		}
	}

}

// Text offset of a DOM position within `root`, or null when the position is not
// inside `root`. An element container's offset is a child index rather than a
// character count, which is how the browser reports a caret in a node whose
// children have just been replaced; a range measures the text ahead of either
// kind of position, including a boundary child that holds no text of its own.
function getTextOffset(root, node, offset) {
	if (!node || !root.contains(node)) return null;

	const range = document.createRange();
	range.selectNodeContents(root);
	try {
		range.setEnd(node, offset);
	} catch {
		return null;
	}
	return range.toString().length;
}

// Helper function to get node and offset at a given text offset
function getNodeAtOffset(root, targetOffset) {
	const target = Math.max(0, targetOffset);
	let totalOffset = 0;
	let lastNode = null;
	const walker = document.createTreeWalker(
		root,
		NodeFilter.SHOW_TEXT,
		null,
		false,
	);
	let currentNode = walker.nextNode();
	while (currentNode) {
		const nodeLength = currentNode.textContent.length;
		if (totalOffset + nodeLength >= target) {
			return { node: currentNode, offset: target - totalOffset };
		}
		totalOffset += nodeLength;
		lastNode = currentNode;
		currentNode = walker.nextNode();
	}
	// An offset past the text lands at its end rather than nowhere, so a caret is
	// never left wherever the last DOM rewrite happened to drop it.
	return lastNode
		? { node: lastNode, offset: lastNode.textContent.length }
		: { node: null, offset: 0 };
}
