"""Convert `_notesimport/note_import.py` output into Djot notes in the vault.

Run the exporter first, then point this at the directory it wrote:

```sh
uv run python scripts/notes_import.py ~/notes-export
```

Apple's exported HTML is malformed in ways that silently corrupt a naive
conversion, so the pipeline works around each one:

- Every character entity is missing its semicolon (`&quot`, `&amp`), which
  pandoc passes through as literal text instead of decoding
- Empty `<b><i><br></i></b>` wrappers become stray Djot markup that a URL
  pattern will otherwise absorb into the link
- Every line is its own `<div>`, which pandoc renders as a `:::` block rather
  than a paragraph
- Notes hold hand-typed (or LLM-pasted) Markdown that pandoc escapes, so
  emphasis, code spans, links, and bullets need converting to Djot

The Markdown rules only fire on unambiguous pairs. A literal asterisk (a glob,
a multiplication, a door code) stays escaped, because guessing wrong silently
rewrites the note's content.
"""

import asyncio
import base64
import operator
import os
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from anyio import Path

from yak_shears._log_utils import log  # ruff: ignore[import-private-name]
from yak_shears._yak.filenames import canonical_stem  # ruff: ignore[import-private-name]
from yak_shears._yak.media import process_upload  # ruff: ignore[import-private-name]

# Exports predating the exporter's timezone fix carry Apple's naive local time,
# so they need the zone the export ran in. Offset-aware exports ignore this.
EXPORT_TZ = ZoneInfo("America/Mexico_City")
CATEGORY = "notes-export"

META_RE = re.compile(r"^: (?P<key>[^=\n]+)=(?P<value>.*)$")
HTML_RE = re.compile(r"`````+ =html\n(?P<html>.*?)\n`````+", re.DOTALL)
IMG_RE = re.compile(r'<img[^>]*src="data:(?P<mime>[^;]+);base64,(?P<data>[^"]+)"[^>]*>')
SOURCE_ID_RE = re.compile(r"^source-id: (?P<id>.*)$", re.MULTILINE)
BARE_ENTITY_RE = re.compile(r"&(quot|amp|gt|lt|apos|nbsp)(?!;)")
EMPTY_TAG_RE = re.compile(r"<(b|i|u|em|strong|font|span)\b[^>]*>(?:\s|<br\s*/?>)*</\1>", re.IGNORECASE)

ATTR_RE = re.compile(r"^\{[^}\n]*\}$", re.MULTILINE)
NOISY_ESCAPE_RE = re.compile(r"\\([\"'|.$])")
UNDERLINE_RE = re.compile(r"\[(?P<text>[^\]\n]*)\]\{\.underline\}")
EMPTY_UNDERLINE_RE = re.compile(r"\[\s*\]\{\.underline\}")
PLACEHOLDER_RE = re.compile(r"ximgplaceholderx(?P<index>\d+)x")
BARE_URL_RE = re.compile(r"(?<![(<\[])\bhttps?://[^\s<>()\[\]*{}`]+[^\s<>()\[\]*{}`.,;:]")
EMPTY_HEADING_RE = re.compile(r"\n#+\n")
TRAILING_BREAK_RE = re.compile(r"[ \t]*\\$", re.MULTILINE)

HAND_RULE_RE = re.compile(r"^\\[-*](\\?[-*]){2,}$", re.MULTILINE)
HAND_STRONG_RE = re.compile(r"\\\*\\\*(?P<text>[^*\n]+?)\\\*\\\*")
# Djot forbids whitespace inside emphasis delimiters; requiring a letter keeps
# the rule off multiplication (`8 \* 2.25`) and codes (`\*1433\*`).
HAND_EM_RE = re.compile(r"\\\*(?=[^*\n]*[A-Za-z])(?P<text>[^*\s](?:[^*\n]*?[^*\s])?)\\\*")
HAND_BULLET_RE = re.compile(r"^(?P<indent>\s*)\\\* ", re.MULTILINE)
HAND_CODE_RE = re.compile(r"\\`(?P<text>[^`\n]+?)\\`")
HAND_LINK_RE = re.compile(r"\\\[(?P<text>[^\]\n]*?)\\\]\((?P<url>[^)\s]+)\)")
CODE_ESCAPE_RE = re.compile(r"\\([!-/:-@\[-`{-~])")
# Emphasis the source opened and never closed. Anchored to a line start, bullet,
# or another delimiter so it cannot strip a literal asterisk mid-word.
ABANDONED_EM_RE = re.compile(r"(?P<pre>^|[-(#.] |[(*_])(?:\\\*){1,2}(?=\S)", re.MULTILINE)
STRAY_STAR_LINE_RE = re.compile(r"^\\\*\\?$\n?", re.MULTILINE)
BANG_RE = re.compile(r"\\!(?!\[)")
GT_RE = re.compile(r"(?<=[^\n])\\>")
QUOTE_LINE_RE = re.compile(r"^\\> ?", re.MULTILINE)


def _parse_export(text: str) -> tuple[dict[str, str], str]:
    meta: dict[str, str] = {}
    for line in text.splitlines():
        match = META_RE.match(line)
        if not match:
            break
        meta[match["key"].strip()] = match["value"].rstrip("\\").strip()
    html = HTML_RE.search(text)
    return meta, html["html"] if html else ""


def _to_utc(stamp: str) -> datetime:
    moment = datetime.fromisoformat(stamp)
    return moment if moment.tzinfo else moment.replace(tzinfo=EXPORT_TZ)


def _extract_images(html: str) -> tuple[str, list[tuple[str, bytes]]]:
    images: list[tuple[str, bytes]] = []

    def replace(match: re.Match[str]) -> str:
        ext = {"image/heic": "heic", "image/jpeg": "jpg", "image/png": "png"}.get(match["mime"], "bin")
        images.append((f"image-{len(images) + 1}.{ext}", base64.b64decode(match["data"])))
        return f"<p>ximgplaceholderx{len(images) - 1}x</p>"

    return IMG_RE.sub(replace, html), images


def _to_djot(html: str) -> str:
    pandoc = shutil.which("pandoc")
    if not pandoc:
        msg = "pandoc is required to convert Apple Notes HTML"
        raise RuntimeError(msg)

    html = BARE_ENTITY_RE.sub(r"&\1;", html)
    while (stripped := EMPTY_TAG_RE.sub("", html)) != html:
        html = stripped
    html = re.sub(r"<div>\s*<br\s*/?>\s*</div>", "", html)
    html = html.replace("<div>", "<p>").replace("</div>", "</p>")
    proc = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [pandoc, "-f", "html", "-t", "djot", "--wrap=none"],
        input=html,
        text=True,
        capture_output=True,
        check=True,
    )
    return proc.stdout


def _restore_markdown(djot: str) -> str:
    djot = HAND_RULE_RE.sub("---", djot)
    djot = HAND_STRONG_RE.sub(lambda m: f"\x00{m['text']}\x00", djot)
    djot = HAND_EM_RE.sub(lambda m: f"_{m['text']}_", djot)
    djot = djot.replace("\x00", "*")
    djot = HAND_BULLET_RE.sub(lambda m: f"{m['indent']}- ", djot)
    while (stripped := ABANDONED_EM_RE.sub(operator.itemgetter("pre"), djot)) != djot:
        djot = stripped
    djot = STRAY_STAR_LINE_RE.sub("", djot)
    djot = HAND_CODE_RE.sub(lambda m: "`" + CODE_ESCAPE_RE.sub(r"\1", m["text"]) + "`", djot)
    return HAND_LINK_RE.sub(lambda m: f"[{m['text']}]({m['url']})", djot)


def _clean(djot: str, title: str) -> str:
    djot = ATTR_RE.sub("", djot)
    djot = djot.replace("\\:", ":").replace("\\_", "_")
    djot = NOISY_ESCAPE_RE.sub(r"\1", djot)
    djot = _restore_markdown(djot)
    djot = BANG_RE.sub("!", djot)
    djot = QUOTE_LINE_RE.sub("> ", djot)
    djot = GT_RE.sub(">", djot)
    djot = TRAILING_BREAK_RE.sub("", djot)
    djot = EMPTY_UNDERLINE_RE.sub("", djot)
    djot = UNDERLINE_RE.sub(operator.itemgetter("text"), djot)
    djot = BARE_URL_RE.sub(lambda m: f"<{m.group(0)}>", djot)
    djot = EMPTY_HEADING_RE.sub("\n", djot)
    djot = re.sub(r"\n{3,}", "\n\n", djot).strip()
    if not djot.startswith("# "):
        djot = f"# {title}\n\n{djot}"
    return djot + "\n"


def _frontmatter(meta: dict[str, str]) -> str:
    fields = {
        "source": "apple-notes",
        "source-folder": meta.get("folder", ""),
        "source-id": meta.get("id", "").rsplit("/", 1)[-1],
        "modified": canonical_stem(_to_utc(meta["modification_date"])).replace("_", ":"),
    }
    return "---\n" + "".join(f"{k}: {v}\n" for k, v in fields.items() if v) + "---\n\n"


async def _convert(text: str, yak_dir: Path) -> tuple[str, str, dict[str, str]]:
    meta, html = _parse_export(text)
    html, images = _extract_images(html)
    stem = canonical_stem(_to_utc(meta["creation_date"]))
    title = meta.get("name", stem).lstrip("#* ").strip().rstrip("*").strip() or stem

    snippets = []
    for filename, data in images:
        result = await process_upload(yak_dir, f"{CATEGORY}/{stem}.dj", filename, data)
        snippets.append(result.snippet)

    body = _clean(_to_djot(html), title)
    body = PLACEHOLDER_RE.sub(lambda m: snippets[int(m["index"])], body)
    return stem, _frontmatter(meta) + body, meta


async def _already_imported(dest: Path) -> dict[str, str]:
    found = {}
    async for path in dest.glob("*.dj"):
        if match := SOURCE_ID_RE.search(await path.read_text()):
            found[match["id"]] = path.name
    return found


async def main(src: Path) -> None:
    """Convert every export in `src` into the vault, leaving imported notes alone.

    Notes are matched by `source-id`, never by filename: the same note exports
    under a different name from a machine in another timezone. A note edited in
    the vault since its import is therefore never overwritten.
    """
    yak_dir = await Path(os.getenv("YAK_SHEARS_DIR", "~/Sync/yak-shears")).expanduser()
    dest = yak_dir / CATEGORY
    await dest.mkdir(parents=True, exist_ok=True)
    existing = await _already_imported(dest)

    written: dict[str, str] = {}
    skipped: list[str] = []
    collisions: list[str] = []
    async for note in src.glob("*.dj"):
        stem, content, meta = await _convert(await note.read_text(), yak_dir)
        source_id = meta.get("id", "").rsplit("/", 1)[-1]
        if prior := existing.get(source_id):
            skipped.append(f"{prior}: {meta.get('name')!r}")
        elif stem in written:
            collisions.append(f"{stem}: {written[stem]!r} vs {meta.get('name')!r}")
        else:
            written[stem] = meta.get("name", "")
            await (dest / f"{stem}.dj").write_text(content)

    log(f"wrote {len(written)} notes to {dest}")
    for line in sorted(skipped):
        log(f"SKIP already imported {line}")
    for line in collisions:
        log(f"COLLISION {line}")


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1])))
