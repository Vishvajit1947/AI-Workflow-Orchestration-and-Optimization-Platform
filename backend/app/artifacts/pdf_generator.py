"""
PDF export of stage output, built with reportlab.

The Markdown is parsed into blocks (document.py) and laid out as real PDF elements:
title, headings, paragraphs with emphasis, lists, tables (header repeated across pages),
wrapped monospace code blocks, margins and page numbers. All text is XML-escaped before
reportlab's paragraph markup sees it, so model output cannot inject markup.

Fonts: a Unicode TTF from the OS is used when present (DejaVu on Linux, Arial/Consolas on
Windows); otherwise reportlab's bundled Vera (sans) and built-in Courier (code), which
cover Western European text. Characters the chosen font cannot draw are printed as "?"
instead of disappearing; the TXT export keeps them.

Raises ExportError (only) when the PDF cannot be produced; the source is never modified.
"""
import io
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional
from xml.sax.saxutils import escape

from backend.app.artifacts.document import (
    Block, CodeBlock, ExportError, Heading, ListBlock, Paragraph, Quote, Rule, Span, Table,
    document_blocks, plain_text, prepare_source,
)

try:
    import reportlab
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFError, TTFont
    from reportlab.platypus import (
        HRFlowable, Indenter, KeepTogether, Preformatted, SimpleDocTemplate, Spacer,
        Table as RLTable, TableStyle,
    )
    from reportlab.platypus import Paragraph as RLParagraph
    from reportlab.lib.fonts import addMapping
    _REPORTLAB_ERROR: Optional[ImportError] = None
except ImportError as e:  # the app still starts; only PDF export is unavailable
    _REPORTLAB_ERROR = e

MARGIN_CM = 2.0
BODY_SIZE = 10.5
CODE_SIZE = 8.5
CONTINUATION = "» "  # prefix for wrapped code lines (Latin-1, so every font has it)

_TEXT = "#1a1a1a"
_MUTED = "#666666"
_LINK = "#1f5fbf"
_RULE = "#c8c8c8"
_CODE_BG = "#f3f3f3"
_TABLE_HEADER_BG = "#ececec"

# (regular, bold, italic, bold italic) file names, best first
_SANS_CANDIDATES = [
    ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans-Oblique.ttf", "DejaVuSans-BoldOblique.ttf"),
    ("arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf"),
    ("Arial.ttf", "Arial Bold.ttf", "Arial Italic.ttf", "Arial Bold Italic.ttf"),
]
_MONO_CANDIDATES = [
    ("DejaVuSansMono.ttf", "DejaVuSansMono-Bold.ttf", "DejaVuSansMono-Oblique.ttf", "DejaVuSansMono-BoldOblique.ttf"),
    ("consola.ttf", "consolab.ttf", "consolai.ttf", "consolaz.ttf"),
    ("cour.ttf", "courbd.ttf", "couri.ttf", "courbi.ttf"),
]


def _font_dirs() -> list[str]:
    dirs = []
    if os.environ.get("WINDIR"):
        dirs.append(os.path.join(os.environ["WINDIR"], "Fonts"))
    dirs += [
        "/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu", "/usr/share/fonts/TTF",
        "/Library/Fonts", "/System/Library/Fonts/Supplemental",
    ]
    return [d for d in dirs if os.path.isdir(d)]


@dataclass(frozen=True)
class FontSet:
    sans: str
    mono: str
    sans_glyphs: Optional[frozenset]   # code points the sans font can draw; None = built-in font
    mono_glyphs: Optional[frozenset]

    def cover(self, text: str, mono: bool = False) -> str:
        """Replace characters the font cannot draw with '?' (tabs and newlines are kept)."""
        glyphs = self.mono_glyphs if mono else self.sans_glyphs
        out = []
        for c in text:
            if c in "\n\t" or (ord(c) in glyphs if glyphs is not None else _in_cp1252(c)):
                out.append(c)
            else:
                out.append("?")
        return "".join(out)


def _in_cp1252(c: str) -> bool:
    try:
        c.encode("cp1252")
        return True
    except UnicodeEncodeError:
        return False


def _register_family(name: str, paths: tuple[str, str, str, str]) -> frozenset:
    """Register a TTF family under `name`; returns its code-point coverage."""
    variants = [name, f"{name}-Bold", f"{name}-Italic", f"{name}-BoldItalic"]
    for variant, path in zip(variants, paths):
        pdfmetrics.registerFont(TTFont(variant, path))
    for (bold, italic), variant in zip([(0, 0), (1, 0), (0, 1), (1, 1)], variants):
        addMapping(name, bold, italic, variant)
    return frozenset(pdfmetrics.getFont(name).face.charToGlyph)


def _first_family(name: str, candidates: list[tuple[str, ...]], extra_dirs: list[str]) -> Optional[frozenset]:
    for directory in _font_dirs() + extra_dirs:
        for files in candidates:
            paths = tuple(os.path.join(directory, f) for f in files)
            if all(os.path.isfile(p) for p in paths):
                try:
                    return _register_family(name, paths)
                except (TTFError, OSError, ValueError):
                    continue  # unreadable or unsupported font file: try the next one
    return None


@lru_cache(maxsize=1)
def get_fonts() -> FontSet:
    """Best available fonts, registered once per process."""
    sans_glyphs = _first_family("ArtifactSans", _SANS_CANDIDATES, [])
    if sans_glyphs is None:
        bundled = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
        sans_glyphs = _first_family("ArtifactSans", [("Vera.ttf", "VeraBd.ttf", "VeraIt.ttf", "VeraBI.ttf")],
                                    [bundled])
    sans = "ArtifactSans" if sans_glyphs is not None else "Helvetica"
    mono_glyphs = _first_family("ArtifactMono", _MONO_CANDIDATES, [])
    mono = "ArtifactMono" if mono_glyphs is not None else "Courier"
    return FontSet(sans=sans, mono=mono, sans_glyphs=sans_glyphs, mono_glyphs=mono_glyphs)


# ---------- styles ----------

class _Styles:
    def __init__(self, fonts: FontSet):
        base = dict(fontName=fonts.sans, textColor=colors.HexColor(_TEXT))
        self.title = ParagraphStyle("title", **base, fontSize=22, leading=27, spaceAfter=6)
        self.headings = {
            level: ParagraphStyle(f"h{level}", **base, fontSize=size, leading=size * 1.3,
                                  spaceBefore=space, spaceAfter=4, keepWithNext=1)
            for level, size, space in [(1, 18, 14), (2, 15, 12), (3, 13, 10), (4, 11.5, 8), (5, 11, 8), (6, 10.5, 8)]
        }
        self.body = ParagraphStyle("body", **base, fontSize=BODY_SIZE, leading=15, spaceAfter=7)
        self.label = ParagraphStyle("label", fontName=fonts.sans, fontSize=7.5, leading=9,
                                    textColor=colors.HexColor(_MUTED), spaceBefore=4, spaceAfter=1, keepWithNext=1)
        self.code = ParagraphStyle("code", fontName=fonts.mono, fontSize=CODE_SIZE, leading=11,
                                   textColor=colors.HexColor(_TEXT), backColor=colors.HexColor(_CODE_BG),
                                   borderPadding=(5, 6, 5, 6), leftIndent=6, rightIndent=6,
                                   spaceBefore=4, spaceAfter=12)
        cell = dict(**base, fontSize=9, leading=12)
        self.cells = {a: ParagraphStyle(f"cell-{a}", **cell, alignment=al)
                      for a, al in [("left", TA_LEFT), ("center", TA_CENTER), ("right", TA_RIGHT)]}
        self._list_cache: dict[int, ParagraphStyle] = {}
        self._base = base

    def list_item(self, depth: int) -> ParagraphStyle:
        if depth not in self._list_cache:
            indent = 20 + 16 * depth
            self._list_cache[depth] = ParagraphStyle(
                f"li{depth}", **self._base, fontSize=BODY_SIZE, leading=15, leftIndent=indent,
                bulletIndent=indent - 16, bulletFontName=self._base["fontName"], spaceAfter=2)
        return self._list_cache[depth]


# ---------- markup ----------

def _attr(value: str) -> str:
    return escape(value, {'"': "&quot;"})


def _markup(spans: list[Span], fonts: FontSet) -> str:
    """reportlab paragraph markup; every piece of text is escaped first."""
    parts = []
    for s in spans:
        text = escape(fonts.cover(s.text, mono=s.code))
        if s.code:
            text = f'<font face="{fonts.mono}" size="{BODY_SIZE - 1}">{text}</font>'
        if s.strike:
            text = f"<strike>{text}</strike>"
        if s.italic:
            text = f"<i>{text}</i>"
        if s.bold:
            text = f"<b>{text}</b>"
        if s.href:
            text = f'<a href="{_attr(s.href)}" color="{_LINK}"><u>{text}</u></a>'
        parts.append(text)
    return "".join(parts)


# ---------- flowables ----------

def _table(block: Table, styles: _Styles, fonts: FontSet, width: float) -> "RLTable":
    columns = len(block.header)
    header = [RLParagraph(f"<b>{_markup(c, fonts)}</b>", styles.cells[block.align[k]])
              for k, c in enumerate(block.header)]
    rows = [[RLParagraph(_markup(c, fonts), styles.cells[block.align[k]]) for k, c in enumerate(row)]
            for row in block.rows]
    # Column widths follow content length, within limits, scaled to the frame
    weights = []
    for k in range(columns):
        longest = max([len(plain_text(block.header[k]))] + [len(plain_text(r[k])) for r in block.rows])
        weights.append(min(max(longest, 6), 60))
    total = sum(weights)
    widths = [width * w / total for w in weights]
    table = RLTable([header] + rows, colWidths=widths, repeatRows=1, splitInRow=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(_RULE)),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(_TABLE_HEADER_BG)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _code(block: CodeBlock, styles: _Styles, fonts: FontSet, width: float) -> list:
    flowables = []
    if block.language:
        flowables.append(RLParagraph(escape(fonts.cover(block.language)), styles.label))
    code = fonts.cover(block.code.expandtabs(4), mono=True) or " "
    inner = width - styles.code.leftIndent - styles.code.rightIndent
    chars = max(20, int(inner / pdfmetrics.stringWidth("M", fonts.mono, CODE_SIZE)) - len(CONTINUATION))
    flowables.append(Preformatted(code, styles.code, maxLineLength=chars, newLineChars=CONTINUATION))
    return flowables


def _flowables(blocks: list[Block], styles: _Styles, fonts: FontSet, width: float) -> list:
    story: list = []
    for block in blocks:
        if isinstance(block, Heading):
            story.append(RLParagraph(_markup(block.spans, fonts), styles.headings[block.level]))
        elif isinstance(block, Paragraph):
            story.append(RLParagraph(_markup(block.spans, fonts), styles.body))
        elif isinstance(block, ListBlock):
            for item in block.items:
                story.append(RLParagraph(_markup(item.spans, fonts), styles.list_item(item.depth),
                                         bulletText=fonts.cover(item.marker)))
            story.append(Spacer(1, 6))
        elif isinstance(block, Table):
            story.append(_table(block, styles, fonts, width))
            story.append(Spacer(1, 10))
        elif isinstance(block, CodeBlock):
            story.extend(_code(block, styles, fonts, width))
        elif isinstance(block, Quote):
            indent = 16
            story.append(Indenter(left=indent))
            story.extend(_flowables(block.blocks, styles, fonts, width - indent))
            story.append(Indenter(left=-indent))
        elif isinstance(block, Rule):
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor(_RULE),
                                    spaceBefore=6, spaceAfter=10))
    return story


def build_story(blocks: list[Block], title: Optional[str], fonts: FontSet, width: float) -> list:
    """All flowables for a document (exposed for tests)."""
    styles = _Styles(fonts)
    story: list = []
    if title:
        story.append(KeepTogether([
            RLParagraph(escape(fonts.cover(title)), styles.title),
            HRFlowable(width="100%", thickness=1, color=colors.HexColor(_RULE), spaceBefore=2, spaceAfter=12),
        ]))
    story.extend(_flowables(blocks, styles, fonts, width))
    return story


def render_pdf(markdown: str, title: Optional[str] = None) -> bytes:
    """
    PDF bytes for a Markdown document.

    Raises ExportError for empty, non-text or oversized input, when reportlab is not
    installed, or when layout fails. Nothing else is affected by a failure.
    """
    text, title = prepare_source(markdown, title)
    if _REPORTLAB_ERROR is not None:
        raise ExportError(f"PDF export is unavailable: {_REPORTLAB_ERROR}")
    blocks = document_blocks(text, title)
    buffer = io.BytesIO()
    try:
        fonts = get_fonts()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            leftMargin=MARGIN_CM * cm, rightMargin=MARGIN_CM * cm,
            topMargin=MARGIN_CM * cm, bottomMargin=MARGIN_CM * cm,
            title=title or "Document", author="AI Orchestrator", creator="AI Orchestrator",
        )
        footer_title = fonts.cover(title or "")[:90]

        def footer(canvas, document) -> None:
            canvas.saveState()
            canvas.setFont(fonts.sans, 8)
            canvas.setFillColor(colors.HexColor(_MUTED))
            y = MARGIN_CM * cm / 2
            if footer_title:
                canvas.drawString(document.leftMargin, y, footer_title)
            canvas.drawRightString(document.pagesize[0] - document.rightMargin, y, f"Page {document.page}")
            canvas.restoreState()

        story = build_story(blocks, title, fonts, doc.width)
        doc.build(story, onFirstPage=footer, onLaterPages=footer)
    except Exception as e:
        # Scoped to PDF layout only: reportlab signals failures with many exception types
        # (LayoutError, ValueError, ...). Callers get one controlled error with the cause attached.
        raise ExportError(f"PDF generation failed: {e}") from e
    return buffer.getvalue()
