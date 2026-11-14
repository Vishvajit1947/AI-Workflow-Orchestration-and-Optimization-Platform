"""
Minimal Markdown reader shared by the PDF and TXT exporters.

It turns stage output into a small block model (headings, paragraphs, lists, tables,
code, quotes, rules) with inline spans (bold, italic, code, strikethrough, links), so
each exporter can render it without leaking Markdown syntax. It covers the subset LLM
output uses (CommonMark + GFM tables); anything it does not recognise stays as text.
Parsing never fails on malformed Markdown and never modifies its input.
"""
import re
from dataclasses import dataclass, field, replace
from typing import Optional, Union

from backend.app.artifacts.limits import MAX_EXPORT_CHARS


class ExportError(Exception):
    """A document could not be exported; the original text output is unaffected."""


# ---------- model ----------

@dataclass(frozen=True)
class Span:
    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False
    strike: bool = False
    href: Optional[str] = None


@dataclass
class Heading:
    level: int
    spans: list[Span]


@dataclass
class Paragraph:
    spans: list[Span]


@dataclass
class ListItem:
    marker: str      # "•" for bullets, "3." for ordered items
    depth: int
    spans: list[Span]


@dataclass
class ListBlock:
    items: list[ListItem]


@dataclass
class Table:
    header: list[list[Span]]
    rows: list[list[list[Span]]]
    align: list[str]  # "left" | "center" | "right" per column


@dataclass
class CodeBlock:
    code: str
    language: Optional[str] = None


@dataclass
class Quote:
    blocks: list["Block"] = field(default_factory=list)


@dataclass
class Rule:
    pass


Block = Union[Heading, Paragraph, ListBlock, Table, CodeBlock, Quote, Rule]


# ---------- source preparation ----------

# Control characters other than tab/newline cannot appear in PDF text or a clean TXT file
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def prepare_source(markdown: object, title: Optional[str] = None) -> tuple[str, Optional[str]]:
    """Validate export input; returns (normalized text, cleaned title). Raises ExportError."""
    if not isinstance(markdown, str):
        raise ExportError("Nothing to export: the output is not text")
    if len(markdown) > MAX_EXPORT_CHARS:
        raise ExportError(f"Output is too large to export ({len(markdown):,} > {MAX_EXPORT_CHARS:,} characters)")
    text = _CONTROL.sub("", markdown.replace("\r\n", "\n").replace("\r", "\n"))
    if not text.strip():
        raise ExportError("Nothing to export: the output is empty")
    clean_title = None
    if isinstance(title, str):
        clean_title = " ".join(_CONTROL.sub("", title).split())[:200] or None
    return text, clean_title


# ---------- inline ----------

_PUNCT = set("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")
_LINK = re.compile(r"\[([^\]\n]*)\]\(\s*<?([^)\s>]*)>?(?:\s+\"[^\"\n]*\")?\s*\)")
_AUTOLINK = re.compile(r"<((?:https?://|mailto:)[^>\s]+)>")
_SAFE_URL = re.compile(r"^(?:https?://|mailto:)", re.IGNORECASE)


def _safe_href(url: str) -> Optional[str]:
    """Only absolute http(s)/mailto links are kept; anything else is shown as plain text."""
    return url if _SAFE_URL.match(url) else None


def _run_length(text: str, i: int, char: str) -> int:
    n = 0
    while i + n < len(text) and text[i + n] == char:
        n += 1
    return n


def _find_closing(text: str, start: int, char: str, length: int) -> int:
    """Index of a closing delimiter run of exactly `length` chars, or -1."""
    j = start
    while True:
        j = text.find(char * length, j)
        if j < 0:
            return -1
        run = _run_length(text, j, char)
        if run == length and not text[j - 1].isspace():
            if char != "_" or j + run >= len(text) or not text[j + run].isalnum():
                return j
        j += run


def parse_inline(text: str, style: Optional[Span] = None) -> list[Span]:
    """Inline Markdown to styled spans; unmatched delimiters stay as literal text."""
    base = style or Span("")
    spans: list[Span] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            spans.append(replace(base, text="".join(buffer)))
            buffer.clear()

    i = 0
    while i < len(text):
        c = text[i]
        if c == "\\" and i + 1 < len(text) and text[i + 1] in _PUNCT:
            buffer.append(text[i + 1])
            i += 2
            continue
        if c == "`":
            run = _run_length(text, i, "`")
            j = i + run
            while True:
                j = text.find("`" * run, j)
                if j < 0 or _run_length(text, j, "`") == run:
                    break
                j += _run_length(text, j, "`")
            if j >= 0:
                content = text[i + run:j]
                if len(content) > 1 and content[0] == content[-1] == " " and content.strip():
                    content = content[1:-1]
                flush()
                spans.append(replace(base, text=content, code=True))
                i = j + run
            else:
                buffer.append("`" * run)
                i += run
            continue
        if c == "[" or (c == "!" and text.startswith("![", i)):
            m = _LINK.match(text, i + (1 if c == "!" else 0))
            if m:
                flush()
                label, url = m.group(1), m.group(2)
                if c == "!":  # image → its alt text
                    spans.extend(parse_inline(label or "image", base))
                else:
                    spans.extend(parse_inline(label or url, replace(base, href=_safe_href(url))))
                i = m.end()
                continue
        if c == "<":
            m = _AUTOLINK.match(text, i)
            if m:
                flush()
                spans.append(replace(base, text=m.group(1), href=m.group(1)))
                i = m.end()
                continue
        if c in "*_~":
            run = _run_length(text, i, c)
            length = min(run, 3) if c != "~" else 2
            opens = (
                run >= length and (c != "~" or run == 2)
                and i + run < len(text) and not text[i + run].isspace()
                and (c != "_" or i == 0 or not text[i - 1].isalnum())
            )
            if opens:
                j = _find_closing(text, i + length, c, length)
                if j > i + length:
                    flush()
                    if c == "~":
                        inner = replace(base, strike=True)
                    else:
                        inner = replace(base, bold=base.bold or length >= 2, italic=base.italic or length != 2)
                    spans.extend(parse_inline(text[i + length:j], inner))
                    i = j + length
                    continue
            buffer.append(c * run)
            i += run
            continue
        buffer.append(c)
        i += 1
    flush()
    return [s for s in spans if s.text]


def plain_text(spans: list[Span]) -> str:
    return "".join(s.text for s in spans)


# ---------- blocks ----------

_ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$")
_FENCE = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")
_RULE = re.compile(r"^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")
_LIST = re.compile(r"^([ \t]*)([-*+]|\d{1,9}[.)])(?:[ \t]+(.*))?$")
_QUOTE = re.compile(r"^ {0,3}>[ ]?(.*)$")
_TABLE_DELIM = re.compile(r"^[ \t]*\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$")


def _split_row(line: str) -> list[str]:
    """Cells of a GFM table row; `\\|` and pipes inside code spans do not split."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    cells, current, in_code, i = [], [], False, 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            current.append("|")
            i += 2
            continue
        if c == "`":
            in_code = not in_code
        if c == "|" and not in_code:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(c)
        i += 1
    cells.append("".join(current).strip())
    return cells


def _is_table_start(lines: list[str], i: int) -> bool:
    if i + 1 >= len(lines) or "|" not in lines[i]:
        return False
    delim = lines[i + 1]
    if not _TABLE_DELIM.match(delim) or ("|" not in delim and len(_split_row(lines[i])) > 1):
        return False
    return len(_split_row(lines[i])) == len(_split_row(delim))


def _starts_block(lines: list[str], i: int) -> bool:
    line = lines[i]
    return bool(
        _ATX.match(line) or _FENCE.match(line) or _RULE.match(line) or _QUOTE.match(line)
        or _LIST.match(line) or _is_table_start(lines, i)
    )


def _parse_table(lines: list[str], i: int) -> tuple[Table, int]:
    header = _split_row(lines[i])
    align = []
    for cell in _split_row(lines[i + 1]):
        left, right = cell.startswith(":"), cell.endswith(":")
        align.append("center" if left and right else "right" if right else "left")
    width = len(header)
    rows: list[list[list[Span]]] = []
    i += 2
    while i < len(lines) and lines[i].strip() and "|" in lines[i]:
        cells = _split_row(lines[i])
        if len(cells) > width:  # keep extra cells' text instead of dropping it
            cells = cells[:width - 1] + [" | ".join(cells[width - 1:])]
        cells += [""] * (width - len(cells))
        rows.append([parse_inline(c) for c in cells])
        i += 1
    return Table(header=[parse_inline(c) for c in header], rows=rows, align=align), i


def _parse_fence(lines: list[str], i: int) -> tuple[CodeBlock, int]:
    m = _FENCE.match(lines[i])
    indent, fence, info = len(m.group(1)), m.group(2), m.group(3).strip()
    closing = re.compile(rf"^ {{0,3}}{re.escape(fence[0])}{{{len(fence)},}}[ \t]*$")
    body = []
    i += 1
    while i < len(lines) and not closing.match(lines[i]):
        line = lines[i]
        strip = min(indent, len(line) - len(line.lstrip(" ")))
        body.append(line[strip:])
        i += 1
    language = info.split()[0] if info else None
    return CodeBlock(code="\n".join(body), language=language), i + 1  # unclosed: runs to the end


def _parse_list(lines: list[str], i: int) -> tuple[ListBlock, int]:
    items: list[ListItem] = []
    texts: list[list[str]] = []
    indents: list[int] = []          # indent of each open nesting level
    numbers: dict[int, int] = {}     # depth -> next number for ordered lists
    while i < len(lines):
        line = lines[i]
        m = _LIST.match(line)
        if m and not _RULE.match(line):
            indent = len(m.group(1).expandtabs(4))
            while indents and indent < indents[-1]:
                indents.pop()
            if not indents or indent > indents[-1]:
                indents.append(indent)
            depth = len(indents) - 1
            for deeper in [d for d in numbers if d > depth]:
                del numbers[deeper]
            marker = m.group(2)
            if marker[0].isdigit():
                n = numbers.get(depth, int(marker[:-1]))
                numbers[depth] = n + 1
                marker = f"{n}."
            else:
                numbers.pop(depth, None)
                marker = "•"
            items.append(ListItem(marker=marker, depth=depth, spans=[]))
            texts.append([m.group(3) or ""])
            i += 1
        elif not line.strip():
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            nxt = lines[j] if j < len(lines) else ""
            if (_LIST.match(nxt) and not _RULE.match(nxt)) or (nxt[:1] in (" ", "\t") and not _FENCE.match(nxt)):
                i = j
                continue
            break
        elif line[:1] in (" ", "\t") and not _FENCE.match(line) and not _QUOTE.match(line):
            texts[-1].append(line.strip())  # indented continuation of the last item
            i += 1
        elif not _starts_block(lines, i) and line[:1] not in (" ", "\t"):
            texts[-1].append(line.strip())  # lazy continuation
            i += 1
        else:
            break
    for item, parts in zip(items, texts):
        item.spans = parse_inline(" ".join(p for p in parts if p))
    return ListBlock(items=items), i


def parse_blocks(text: str) -> list[Block]:
    """Block structure of a Markdown document."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[Block] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if _FENCE.match(line) and not (line.lstrip().startswith("`") and "`" in _FENCE.match(line).group(3)):
            block, i = _parse_fence(lines, i)
            blocks.append(block)
            continue
        if m := _ATX.match(line):
            blocks.append(Heading(level=len(m.group(1)), spans=parse_inline(m.group(2) or "")))
            i += 1
            continue
        if _RULE.match(line):
            blocks.append(Rule())
            i += 1
            continue
        if _is_table_start(lines, i):
            block, i = _parse_table(lines, i)
            blocks.append(block)
            continue
        if _QUOTE.match(line):
            inner = []
            while i < len(lines) and (q := _QUOTE.match(lines[i])):
                inner.append(q.group(1))
                i += 1
            blocks.append(Quote(blocks=parse_blocks("\n".join(inner))))
            continue
        if _LIST.match(line):
            block, i = _parse_list(lines, i)
            blocks.append(block)
            continue
        paragraph = [line.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not _starts_block(lines, i):
            paragraph.append(lines[i].strip())
            i += 1
        blocks.append(Paragraph(spans=parse_inline(" ".join(paragraph))))
    return blocks


def document_blocks(text: str, title: Optional[str]) -> list[Block]:
    """Blocks to export; a leading H1 that repeats the title is dropped to avoid printing it twice."""
    blocks = parse_blocks(text)
    if (title and blocks and isinstance(blocks[0], Heading) and blocks[0].level == 1
            and plain_text(blocks[0].spans).strip().lower() == title.strip().lower()):
        blocks = blocks[1:]
    return blocks
