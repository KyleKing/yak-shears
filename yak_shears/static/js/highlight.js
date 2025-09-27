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

	const events = globalThis.djot.parseEvents(src);
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
			case "+code_block":
				// TODO: Add syntax highlighting!
				const lang = "TBD";
				add(opens, start, `<pre><code class="language-${lang}">`);
				break;
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
	editor.innerHTML = out;
}
