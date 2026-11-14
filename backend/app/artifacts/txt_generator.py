"""
Plain-text export of stage output.

Markdown syntax is removed while structure stays readable in a basic editor: underlined
headings, indented lists, aligned tables and indented code. Output is UTF-8 with "\n"
line endings. Raises ExportError (only) for unusable input; the source is never modified.
"""
import textwrap
import unicodedata
from typing import Optional

from backend.app.artifacts.document import (
    Block, CodeBlock, Heading, ListBlock, Paragraph, Quote, Rule, Span, Table,
    document_blocks, prepare_source,
)

WIDTH = 80             # prose is wrapped to this many columns
MAX_TABLE_WIDTH = 100  # wider tables are written one record per row instead of a grid
_UNDERLINES = {1: "=", 2: "-", 3: "~"}


def _inline(spans: list[Span]) -> str:
    """Span text with links written as 'label (url)'."""
    out: list[str] = []
    i = 0
    while i < len(spans):
        href = spans[i].href
        if not href:
            out.append(spans[i].text)
            i += 1
            continue
        j = i
        while j < len(spans) and spans[j].href == href:
            j += 1
        label = "".join(s.text for s in spans[i:j])
        out.append(label if label == href else f"{label} ({href})")
        i = j
    return "".join(out)


def _width(text: str) -> int:
    """Display columns: wide East Asian characters take 2, combining marks 0."""
    return sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in "WF" else 1
               for c in text)


def _pad(text: str, width: int, align: str) -> str:
    gap = width - _width(text)
    if align == "right":
        return " " * gap + text
    if align == "center":
        return " " * (gap // 2) + text + " " * (gap - gap // 2)
    return text + " " * gap


def _wrap(text: str, first: str = "", rest: str = "") -> str:
    return textwrap.fill(" ".join(text.split()), width=WIDTH, initial_indent=first, subsequent_indent=rest,
                         break_long_words=False, break_on_hyphens=False) or first.rstrip()


def _table(table: Table) -> str:
    header = [_inline(c) for c in table.header]
    rows = [[_inline(c) for c in row] for row in table.rows]
    widths = [max([_width(header[k])] + [_width(r[k]) for r in rows]) for k in range(len(header))]
    if sum(widths) + 3 * (len(widths) - 1) > MAX_TABLE_WIDTH:
        records = []
        for n, row in enumerate(rows, 1):
            lines = [f"Row {n}"] + [_wrap(f"{h}: {v}", "  ", "    ") for h, v in zip(header, row)]
            records.append("\n".join(lines))
        return "\n\n".join(records) if records else " | ".join(header)
    line = lambda cells: " | ".join(_pad(c, w, a) for c, w, a in zip(cells, widths, table.align))
    out = [line(header), "-+-".join("-" * w for w in widths)]
    out += [line(r) for r in rows]
    return "\n".join(out)


def _block(block: Block) -> str:
    if isinstance(block, Heading):
        text = " ".join(_inline(block.spans).split())
        char = _UNDERLINES.get(block.level)
        return f"{text}\n{char * min(max(_width(text), 3), WIDTH)}" if char else text
    if isinstance(block, Paragraph):
        return _wrap(_inline(block.spans))
    if isinstance(block, ListBlock):
        lines = []
        for item in block.items:
            indent = "  " * item.depth
            marker = "-" if item.marker == "•" else item.marker
            lines.append(_wrap(_inline(item.spans), f"{indent}{marker} ", indent + " " * (len(marker) + 1)))
        return "\n".join(lines)
    if isinstance(block, Table):
        return _table(block)
    if isinstance(block, CodeBlock):
        return "\n".join(("    " + line) if line.strip() else "" for line in block.code.split("\n"))
    if isinstance(block, Quote):
        inner = "\n\n".join(_block(b) for b in block.blocks)
        return "\n".join(f"> {line}" if line else ">" for line in inner.split("\n"))
    if isinstance(block, Rule):
        return "-" * 40
    return ""


def render_txt(markdown: str, title: Optional[str] = None) -> str:
    """Plain text for a Markdown document. Raises ExportError for empty, non-text or oversized input."""
    text, title = prepare_source(markdown, title)
    parts = []
    if title:
        bar = "=" * min(max(_width(title), 3), WIDTH)
        parts.append(f"{bar}\n{title}\n{bar}")
    parts += [p for p in (_block(b) for b in document_blocks(text, title)) if p]
    body = "\n\n".join(parts)
    return "\n".join(line.rstrip() for line in body.split("\n")).strip("\n") + "\n"


def render_txt_bytes(markdown: str, title: Optional[str] = None) -> bytes:
    """render_txt encoded as UTF-8 (no byte-order mark)."""
    return render_txt(markdown, title).encode("utf-8")
