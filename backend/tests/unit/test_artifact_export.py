"""Unit tests for PDF/TXT export of stage output (in memory only; no files are written)."""
import re

import pytest
from reportlab.platypus import Paragraph as RLParagraph, Preformatted, Table as RLTable

from backend.app.artifacts import document, pdf_generator
from backend.app.artifacts.document import (
    CodeBlock, ExportError, Heading, ListBlock, Paragraph, Quote, Rule, Span, Table,
    document_blocks, parse_blocks, parse_inline, plain_text, prepare_source,
)
from backend.app.artifacts.pdf_generator import FontSet, build_story, get_fonts, render_pdf
from backend.app.artifacts.txt_generator import WIDTH, render_txt, render_txt_bytes

FENCE = "```"

SAMPLE = f"""# Binary Trees

A **binary tree** is a *hierarchical* structure; use `insert()` to add nodes.
See [the guide](https://example.com/trees?a=1&b=2).

## Operations

1. Insert
2. Search
   - recursive
   - iterative
3. Delete

| Operation | Average | Worst |
|:----------|:-------:|------:|
| Search    | O(log n) | O(n) |
| Insert    | O(log n) | O(n) |

{FENCE}python
def insert(node, value):
    if node is None:
        return Node(value)
{FENCE}

> **Tip:** keep the tree balanced.

---

Done.
"""


def page_count(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page(?![s\w])", pdf))


def assert_valid_pdf(pdf: bytes) -> None:
    assert isinstance(pdf, bytes) and len(pdf) > 500
    assert pdf.startswith(b"%PDF-")
    assert pdf.rstrip().endswith(b"%%EOF")
    assert page_count(pdf) >= 1


# ---------- input preparation ----------

class TestPrepareSource:
    @pytest.mark.parametrize("value", [None, 42, b"bytes", ["a"]])
    def test_non_text_is_rejected(self, value):
        with pytest.raises(ExportError, match="not text"):
            prepare_source(value)

    @pytest.mark.parametrize("value", ["", "   ", "\n\n\t", "\x00\x01"])
    def test_empty_is_rejected(self, value):
        with pytest.raises(ExportError, match="empty"):
            prepare_source(value)

    def test_oversized_is_rejected(self, monkeypatch):
        monkeypatch.setattr(document, "MAX_EXPORT_CHARS", 10)
        with pytest.raises(ExportError, match="too large"):
            prepare_source("x" * 11)

    def test_normalizes_line_endings_and_strips_control_characters(self):
        text, title = prepare_source("a\r\nb\rc\x00d\x1be\tf", "  My\x07  Title \n")
        assert text == "a\nb\ncde\tf"
        assert title == "My Title"

    def test_blank_title_becomes_none(self):
        assert prepare_source("x", "   ")[1] is None
        assert prepare_source("x", None)[1] is None


# ---------- Markdown reader ----------

class TestInline:
    def test_emphasis_code_and_strike(self):
        spans = parse_inline("a **b** *c* ***d*** `e*f` ~~g~~ __h__ _i_")
        styled = {s.text: s for s in spans}
        assert styled["b"].bold and not styled["b"].italic
        assert styled["c"].italic and not styled["c"].bold
        assert styled["d"].bold and styled["d"].italic
        assert styled["e*f"].code
        assert styled["g"].strike
        assert styled["h"].bold and styled["i"].italic
        assert plain_text(spans) == "a b c d e*f g h i"

    def test_nested_emphasis(self):
        spans = parse_inline("**bold *both* bold**")
        assert [(s.text, s.bold, s.italic) for s in spans] == [
            ("bold ", True, False), ("both", True, True), (" bold", True, False),
        ]

    @pytest.mark.parametrize("text", [
        "snake_case_name", "2 * 3 * 4", "a ** b", "unclosed **bold", "x_1 = y_2", "~not strike~",
    ])
    def test_literal_delimiters_are_kept(self, text):
        spans = parse_inline(text)
        assert plain_text(spans) == text
        assert not any(s.bold or s.italic or s.strike for s in spans)

    def test_snake_case_is_not_italic(self):
        assert not any(s.italic for s in parse_inline("call my_func_name now"))

    def test_escapes(self):
        assert plain_text(parse_inline(r"\*not italic\* \`x\` \\")) == "*not italic* `x` \\"

    def test_links_images_and_autolinks(self):
        spans = parse_inline("[docs](https://a.io/x) ![diagram](img.png) <https://b.io> [bad](javascript:alert(1))")
        assert spans[0] == Span("docs", href="https://a.io/x")
        assert "diagram" in plain_text(spans) and "img.png" not in plain_text(spans)
        assert any(s.href == "https://b.io" for s in spans)
        bad = [s for s in spans if s.text.startswith("bad")]
        assert bad and bad[0].href is None  # unsafe scheme is shown as text only

    def test_multi_backtick_code_span(self):
        (span,) = parse_inline("``a `b` c``")
        assert span.code and span.text == "a `b` c"


class TestBlocks:
    def test_sample_structure(self):
        kinds = [type(b).__name__ for b in parse_blocks(SAMPLE)]
        assert kinds == ["Heading", "Paragraph", "Heading", "ListBlock", "Table", "CodeBlock", "Quote", "Rule", "Paragraph"]

    def test_headings(self):
        blocks = parse_blocks("# One\n## Two ##\n###### Six\n#hashtag\n# C#")
        assert [(b.level, plain_text(b.spans)) for b in blocks if isinstance(b, Heading)] == [
            (1, "One"), (2, "Two"), (6, "Six"), (1, "C#"),
        ]
        assert any(isinstance(b, Paragraph) and plain_text(b.spans) == "#hashtag" for b in blocks)

    def test_ordered_lists_are_renumbered_and_nested(self):
        (lst,) = parse_blocks("1. a\n1. b\n   - x\n   - y\n1. c")
        assert [(i.marker, i.depth, plain_text(i.spans)) for i in lst.items] == [
            ("1.", 0, "a"), ("2.", 0, "b"), ("•", 1, "x"), ("•", 1, "y"), ("3.", 0, "c"),
        ]

    def test_list_start_number_and_continuation_lines(self):
        (lst,) = parse_blocks("3. first line\n   continues here\n4. second")
        assert [(i.marker, plain_text(i.spans)) for i in lst.items] == [
            ("3.", "first line continues here"), ("4.", "second"),
        ]

    def test_code_fence_inside_list_is_kept_as_code(self):
        blocks = parse_blocks(f"1. Install:\n   {FENCE}bash\n   pip install x\n   {FENCE}\n2. Run")
        kinds = [type(b).__name__ for b in blocks]
        assert "CodeBlock" in kinds
        code = next(b for b in blocks if isinstance(b, CodeBlock))
        assert code.language == "bash" and code.code == "pip install x"

    def test_table_alignment_escaped_pipes_and_ragged_rows(self):
        (table,) = parse_blocks("| A | B | C |\n|:--|:-:|--:|\n| `x|y` | a\\|b | 1 |\n| only |\n| 1 | 2 | 3 | 4 |")
        assert table.align == ["left", "center", "right"]
        rows = [[plain_text(c) for c in r] for r in table.rows]
        assert rows[0] == ["x|y", "a|b", "1"]
        assert rows[1] == ["only", "", ""]
        assert rows[2] == ["1", "2", "3 | 4"]  # extra cells are kept, not dropped

    def test_pipe_text_without_delimiter_row_is_a_paragraph(self):
        (block,) = parse_blocks("a | b\nc | d")
        assert isinstance(block, Paragraph)

    def test_code_block_keeps_indentation_and_unclosed_runs_to_end(self):
        (code,) = parse_blocks("~~~js\nif (x) {\n    y();\n}\n")
        assert code.language == "js" and code.code == "if (x) {\n    y();\n}\n"
        (code,) = parse_blocks(f"{FENCE}\n  a\n\tb")
        assert code.code == "  a\n\tb" and code.language is None

    def test_quote_contains_blocks(self):
        (quote,) = parse_blocks("> # Title\n> - item\n> text")
        assert isinstance(quote, Quote)
        assert [type(b).__name__ for b in quote.blocks] == ["Heading", "ListBlock"]

    def test_rules(self):
        assert all(isinstance(b, Rule) for b in parse_blocks("---\n\n***\n\n_ _ _"))

    def test_leading_h1_matching_title_is_not_repeated(self):
        assert isinstance(document_blocks("# Binary Trees\n\ntext", "binary trees")[0], Paragraph)
        assert isinstance(document_blocks("# Other\n\ntext", "Binary Trees")[0], Heading)

    @pytest.mark.parametrize("text", [
        "**", "`", "[", "](", "| |", "|---|", "> ", "1.", "-", "```", "~~~", "#", "<", "\\", "*_*_*_", "[a](",
        "| a |\n|---|\n|", "1. \n   \n", "\t\t\t", "````\n```\n", "<https://", "![](",
    ])
    def test_malformed_markdown_never_raises(self, text):
        parse_blocks(text)


# ---------- TXT ----------

class TestTxt:
    def test_removes_markdown_syntax_and_keeps_structure(self):
        txt = render_txt(SAMPLE, "Binary Trees")
        assert txt.startswith("============\nBinary Trees\n============\n")
        assert txt.count("Binary Trees") == 1  # duplicate leading H1 dropped
        assert "Operations\n----------" in txt
        for syntax in ("**", "`", "## ", "](", "|:--", "~~~", FENCE):
            assert syntax not in txt
        assert "the guide (https://example.com/trees?a=1&b=2)" in " ".join(txt.split())  # prose is wrapped
        assert "1. Insert\n2. Search\n  - recursive\n  - iterative\n3. Delete" in txt
        assert "> Tip: keep the tree balanced." in txt
        assert "-" * 40 in txt

    def test_table_is_aligned(self):
        txt = render_txt(SAMPLE)
        assert "Operation | Average  | Worst" in txt
        assert "----------+----------+------" in txt
        assert "Search    | O(log n) |  O(n)" in txt

    def test_wide_table_becomes_records(self):
        long = "word " * 30
        txt = render_txt(f"| Name | Description |\n|---|---|\n| a | {long} |")
        assert "Row 1\n  Name: a\n  Description: word word" in txt

    def test_code_keeps_content_and_relative_indentation(self):
        txt = render_txt(SAMPLE)
        assert "    def insert(node, value):\n        if node is None:\n            return Node(value)" in txt

    def test_prose_is_wrapped_but_long_words_are_not_broken(self):
        url = "https://example.com/" + "a" * 120
        txt = render_txt(("lorem ipsum " * 30) + url)
        lines = txt.splitlines()
        assert all(len(line) <= WIDTH for line in lines if url not in line)
        assert any(url in line for line in lines)

    def test_utf8_bytes_preserve_all_characters(self):
        text = "Unicode: café €100 “q” — Ω Привет 漢字 ✓ 😀"
        data = render_txt_bytes(text)
        assert not data.startswith(b"\xef\xbb\xbf")  # no BOM
        assert data.decode("utf-8") == text + "\n"

    def test_markup_like_text_is_kept_verbatim(self):
        assert "<b>x</b> &amp; </para>" in render_txt("<b>x</b> &amp; </para>")

    def test_plain_line_endings_and_trailing_newline(self):
        txt = render_txt("a\r\n\r\nb  \r\n")
        assert "\r" not in txt and txt == "a\n\nb\n"

    @pytest.mark.parametrize("value", ["", "  \n ", None, 3])
    def test_empty_or_invalid_input_raises_export_error(self, value):
        with pytest.raises(ExportError):
            render_txt(value)

    def test_source_is_not_modified(self):
        source = str(SAMPLE)
        render_txt(source, "T")
        assert source == SAMPLE


# ---------- PDF ----------

def story_for(markdown: str, title=None):
    fonts = get_fonts()
    text, title = prepare_source(markdown, title)
    return build_story(document_blocks(text, title), title, fonts, 480)


class TestPdfStory:
    def test_maps_blocks_to_pdf_elements(self):
        story = story_for(SAMPLE, "Binary Trees")
        paragraphs = [f for f in story if isinstance(f, RLParagraph)]
        styles = [p.style.name for p in paragraphs]
        assert "h2" in styles and "body" in styles and "li0" in styles and "li1" in styles
        assert "h1" not in styles  # the H1 repeating the title is not printed twice
        tables = [f for f in story if isinstance(f, RLTable)]
        assert len(tables) == 1 and len(tables[0]._cellvalues) == 3
        code = [f for f in story if isinstance(f, Preformatted)]
        assert len(code) == 1
        code_text = "\n".join(line[1] if isinstance(line, tuple) else str(line) for line in code[0].lines)
        assert "def insert(node, value):" in code_text and "        return Node(value)" in code_text

    def test_emphasis_and_links_become_markup_not_markdown(self):
        story = story_for("A **b** *c* `d` [e](https://x.io/?a=1&b=2)")
        markup = story[0].text
        assert "<b>b</b>" in markup and "<i>c</i>" in markup
        assert 'href="https://x.io/?a=1&amp;b=2"' in markup
        assert "**" not in markup and "`" not in markup

    def test_markup_in_model_output_is_escaped(self):
        story = story_for('<font name="x">bold</font> </para> & <a href="javascript:x">y</a>')
        markup = story[0].text
        assert "&lt;font name=" in markup and "&lt;/para&gt;" in markup and "&amp;" in markup
        assert "<font name" not in markup and "javascript" not in re.findall(r'href="([^"]*)"', markup)


class TestFontCoverage:
    def test_cover_with_glyph_set(self):
        fonts = FontSet(sans="S", mono="M", sans_glyphs=frozenset(map(ord, "abc ")), mono_glyphs=None)
        assert fonts.cover("ab xyz\n\tc") == "ab ???\n\tc"

    def test_cover_with_builtin_font_uses_cp1252(self):
        fonts = FontSet(sans="S", mono="Courier", sans_glyphs=None, mono_glyphs=None)
        assert fonts.cover("café €5 Ω 漢", mono=True) == "café €5 ? ?"

    def test_active_fonts_keep_western_text(self):
        fonts = get_fonts()
        assert fonts.cover("café naïve €100 “q” —") == "café naïve €100 “q” —"
        assert fonts.cover("😀") == "?"  # no candidate font has emoji


class TestPdf:
    def test_basic_pdf_is_valid(self):
        assert_valid_pdf(render_pdf("Hello **world**"))

    def test_full_sample_is_valid(self):
        pdf = render_pdf(SAMPLE, "Binary Trees")
        assert_valid_pdf(pdf)
        assert b"/Title" in pdf

    def test_long_content_spans_multiple_pages(self):
        sections = "\n\n".join(f"## Section {n}\n\n" + ("Paragraph text. " * 60) for n in range(30))
        pdf = render_pdf(sections, "Long")
        assert_valid_pdf(pdf)
        assert page_count(pdf) >= 5

    def test_code_block_longer_than_a_page_splits_across_pages(self):
        code = "\n".join(f"line_{n} = {n}  # {'x' * 150}" for n in range(300))
        pdf = render_pdf(f"{FENCE}python\n{code}\n{FENCE}")
        assert_valid_pdf(pdf)
        assert page_count(pdf) >= 3

    def test_table_with_many_rows_and_a_huge_cell(self):
        rows = "\n".join(f"| {n} | {'long text ' * 8} |" for n in range(120))
        huge = "| big | " + ("word " * 1500) + "|"
        pdf = render_pdf(f"| # | Text |\n|---|---|\n{rows}\n{huge}")
        assert_valid_pdf(pdf)
        assert page_count(pdf) >= 3

    def test_many_columns_and_long_unbreakable_words(self):
        header = "|" + "|".join(f" c{n} " for n in range(12)) + "|"
        delim = "|" + "|".join("---" for _ in range(12)) + "|"
        row = "|" + "|".join(" " + "x" * 80 + " " for _ in range(12)) + "|"
        assert_valid_pdf(render_pdf(f"{header}\n{delim}\n{row}\n\n" + "y" * 3000))

    def test_unicode_and_special_characters(self):
        text = "café €100 “q” — Ω Привет 漢字 ✓ 😀 <b>&amp;</b> \\ % $ { } ( ) /Type /Page"
        pdf = render_pdf(f"# {text}\n\n{text}\n\n{FENCE}\n{text}\n{FENCE}", title=text)
        assert_valid_pdf(pdf)
        assert page_count(pdf) == 1  # the literal "/Type /Page" text does not create pages

    def test_deeply_nested_and_mixed_content(self):
        md = "\n".join("  " * d + f"- level {d}" for d in range(12)) + "\n\n> > > nested quote\n> ```\n> code\n> ```"
        assert_valid_pdf(render_pdf(md))

    @pytest.mark.parametrize("value", ["", "   \n", None, 7])
    def test_empty_or_invalid_input_raises_export_error(self, value):
        with pytest.raises(ExportError):
            render_pdf(value)

    def test_layout_failure_becomes_export_error(self, monkeypatch):
        def broken_build(self, *args, **kwargs):
            raise ValueError("layout exploded")
        monkeypatch.setattr(pdf_generator.SimpleDocTemplate, "build", broken_build)
        with pytest.raises(ExportError, match="PDF generation failed: layout exploded") as info:
            render_pdf(SAMPLE)
        assert isinstance(info.value.__cause__, ValueError)

    def test_missing_reportlab_becomes_export_error(self, monkeypatch):
        monkeypatch.setattr(pdf_generator, "_REPORTLAB_ERROR", ImportError("No module named 'reportlab'"))
        with pytest.raises(ExportError, match="unavailable"):
            render_pdf(SAMPLE)

    def test_source_is_not_modified(self):
        source = str(SAMPLE)
        render_pdf(source, "T")
        assert source == SAMPLE
