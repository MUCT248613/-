"""Markdown -> DOCX converter (python-docx based).

Converts the project's design documents from Markdown to Word without any
external toolchain (no pandoc). It supports the Markdown subset used by the
requirements / technical design docs:

    # / ## / ### headings
    pipe tables (| a | b | with a |---| separator row)
    bullet lists (- item) and numbered lists (1. item)
    fenced code blocks (```python / ```sql / ```yaml / ```)
    blockquotes (> text)
    horizontal rules (---)
    inline **bold**, `code` and LaTeX math \\( ... \\) / \\[ ... \\]

Chinese text is rendered through an East-Asian font (Microsoft YaHei) so the
generated Word files display correctly.

Usage:
    python scripts/md_to_docx.py                 # convert the two design docs
    python scripts/md_to_docx.py in.md out.docx  # convert a single file
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

# --------------------------------------------------------------------------- #
# Fonts / sizes
# --------------------------------------------------------------------------- #
LATIN_FONT = "Calibri"
CJK_FONT = "微软雅黑"          # East-Asian font for Chinese characters
MONO_FONT = "Consolas"        # code / inline code
MATH_FONT = "Cambria Math"    # LaTeX math (rendered as readable text)
BODY_SIZE = 10.5              # 五号, standard Chinese body size
HEADING_SIZES = {1: 18, 2: 14, 3: 12, 4: 11}
HEADING_COLOR = RGBColor(0x1F, 0x37, 0x64)

# Inline tokeniser: **bold** | `code` | \(inline math\)
TOKEN_RE = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\\\(.+?\\\))")


# --------------------------------------------------------------------------- #
# Low-level styling helpers
# --------------------------------------------------------------------------- #
def set_run_font(run, name=LATIN_FONT, east_asia=CJK_FONT, size=None,
                 bold=None, italic=None, color=None):
    """Set a run's font, making sure the East-Asian font is applied so Chinese
    characters render with the intended typeface."""
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), name)
    rfonts.set(qn("w:hAnsi"), name)
    rfonts.set(qn("w:eastAsia"), east_asia)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic
    if color is not None:
        run.font.color.rgb = color


def _shade(element_pr, fill):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    element_pr.append(shd)


def shade_paragraph(paragraph, fill="F5F5F5"):
    _shade(paragraph._p.get_or_add_pPr(), fill)


def shade_run(run, fill="F0F0F0"):
    _shade(run._element.get_or_add_rPr(), fill)


def shade_cell(cell, fill):
    _shade(cell._tc.get_or_add_tcPr(), fill)


def add_bottom_border(paragraph, color="AAAAAA", sz="6"):
    ppr = paragraph._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), sz)
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), color)
    pbdr.append(bottom)
    ppr.append(pbdr)


def add_left_border(paragraph, color="BFBFBF", sz="18"):
    ppr = paragraph._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    left = OxmlElement("w:left")
    left.set(qn("w:val"), "single")
    left.set(qn("w:sz"), sz)
    left.set(qn("w:space"), "8")
    left.set(qn("w:color"), color)
    pbdr.append(left)
    ppr.append(pbdr)


def set_table_full_width(table):
    table.autofit = True
    tbl_w = OxmlElement("w:tblW")
    tbl_w.set(qn("w:w"), "5000")   # 5000 fiftieths-of-a-percent = 100%
    tbl_w.set(qn("w:type"), "pct")
    table._tbl.tblPr.append(tbl_w)


# --------------------------------------------------------------------------- #
# Inline content (bold / code / inline math)
# --------------------------------------------------------------------------- #
def add_inline(paragraph, text, base_size=BODY_SIZE, bold=False):
    """Add runs to a paragraph, interpreting inline Markdown markers.

    ``bold`` propagates into nested tokens so that constructs such as
    ``**`config/x.yaml`**`` (inline code wrapped in bold) render correctly.
    """
    pos = 0
    for match in TOKEN_RE.finditer(text):
        if match.start() > pos:
            _plain_run(paragraph, text[pos:match.start()], base_size, bold)
        token = match.group(0)
        if token.startswith("**"):
            # recurse so nested `code` / math inside bold is handled
            add_inline(paragraph, token[2:-2], base_size, bold=True)
        elif token.startswith("`"):
            run = paragraph.add_run(token[1:-1])
            set_run_font(run, name=MONO_FONT, east_asia=CJK_FONT,
                         size=base_size - 0.5, bold=bold)
            shade_run(run)
        elif token.startswith("\\("):
            run = paragraph.add_run(token[2:-2])
            set_run_font(run, name=MATH_FONT, east_asia=CJK_FONT,
                         size=base_size, italic=True, bold=bold)
        pos = match.end()
    if pos < len(text):
        _plain_run(paragraph, text[pos:], base_size, bold)


def _plain_run(paragraph, text, base_size, bold=False):
    run = paragraph.add_run(text)
    set_run_font(run, size=base_size, bold=bold)


# --------------------------------------------------------------------------- #
# Block builders
# --------------------------------------------------------------------------- #
def add_heading(doc, text, level):
    style = f"Heading {level}" if level <= 4 else "Heading 4"
    paragraph = doc.add_paragraph(style=style)
    if level == 1:
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run(text)
    set_run_font(run, name=LATIN_FONT, east_asia=CJK_FONT,
                 size=HEADING_SIZES.get(level, 11), bold=True,
                 color=HEADING_COLOR)


def add_paragraph(doc, text):
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(6)
    paragraph.paragraph_format.line_spacing = 1.15
    add_inline(paragraph, text)


def add_bullet(doc, text):
    paragraph = doc.add_paragraph(style="List Bullet")
    paragraph.paragraph_format.space_after = Pt(2)
    add_inline(paragraph, text)


def add_number(doc, text):
    paragraph = doc.add_paragraph(style="List Number")
    paragraph.paragraph_format.space_after = Pt(2)
    add_inline(paragraph, text)


def add_blockquote(doc, text):
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.left_indent = Inches(0.25)
    paragraph.paragraph_format.space_before = Pt(4)
    paragraph.paragraph_format.space_after = Pt(6)
    add_left_border(paragraph)
    add_inline(paragraph, text)


def add_hr(doc):
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(6)
    paragraph.paragraph_format.space_after = Pt(6)
    add_bottom_border(paragraph)


def add_block_math(doc, text):
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(6)
    paragraph.paragraph_format.space_after = Pt(6)
    run = paragraph.add_run(text)
    set_run_font(run, name=MATH_FONT, east_asia=CJK_FONT, size=11, italic=True)


def add_code_block(doc, code_lines):
    for line in code_lines:
        paragraph = doc.add_paragraph()
        pf = paragraph.paragraph_format
        pf.space_before = Pt(0)
        pf.space_after = Pt(0)
        pf.line_spacing = 1.0
        pf.left_indent = Inches(0.1)
        shade_paragraph(paragraph)
        text = line.rstrip("\n")
        run = paragraph.add_run(text if text else " ")
        set_run_font(run, name=MONO_FONT, east_asia=CJK_FONT, size=8.5)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def _split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


def _fill_cell(cell, text, bold=False, fill=None, size=9.5):
    if fill:
        shade_cell(cell, fill)
    paragraph = cell.paragraphs[0]
    paragraph.paragraph_format.space_before = Pt(2)
    paragraph.paragraph_format.space_after = Pt(2)
    if bold:
        run = paragraph.add_run(text)
        set_run_font(run, size=size, bold=True)
    else:
        add_inline(paragraph, text, base_size=size)


def add_table(doc, table_lines):
    rows = [_split_row(line) for line in table_lines]
    header = rows[0]
    body = rows[2:]                      # rows[1] is the |---| separator
    n_cols = len(header)

    table = doc.add_table(rows=1, cols=n_cols)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_full_width(table)

    for j, cell_text in enumerate(header):
        _fill_cell(table.rows[0].cells[j], cell_text, bold=True, fill="D9E2F3")

    for row in body:
        cells = table.add_row().cells
        for j in range(n_cols):
            _fill_cell(cells[j], row[j] if j < len(row) else "")

    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(2)


# --------------------------------------------------------------------------- #
# Markdown parser
# --------------------------------------------------------------------------- #
_SEP_RE = re.compile(r"^\s*\|?[\s:\-|]+\|?\s*$")


def parse(doc, lines):
    i = 0
    n = len(lines)
    while i < n:
        stripped = lines[i].strip()

        if not stripped:
            i += 1
            continue

        # fenced code block
        if stripped.startswith("```"):
            i += 1
            code_lines = []
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1                       # skip closing fence
            add_code_block(doc, code_lines)
            continue

        # block math \[ ... \]
        if stripped == "\\[":
            i += 1
            math_lines = []
            while i < n and lines[i].strip() != "\\]":
                math_lines.append(lines[i].strip())
                i += 1
            i += 1                       # skip closing \]
            add_block_math(doc, " ".join(m for m in math_lines if m))
            continue

        # heading
        heading = re.match(r"^(#{1,6})\s+(.*)", stripped)
        if heading:
            add_heading(doc, heading.group(2).strip(), len(heading.group(1)))
            i += 1
            continue

        # horizontal rule
        if re.match(r"^-{3,}$", stripped) or re.match(r"^\*{3,}$", stripped):
            add_hr(doc)
            i += 1
            continue

        # table (header row followed by a separator row)
        if (stripped.startswith("|") and i + 1 < n
                and _SEP_RE.match(lines[i + 1]) and "-" in lines[i + 1]):
            table_lines = []
            while i < n and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            add_table(doc, table_lines)
            continue

        # blockquote
        if stripped.startswith(">"):
            quote_lines = []
            while i < n and lines[i].strip().startswith(">"):
                quote_lines.append(re.sub(r"^>\s?", "", lines[i].strip()))
                i += 1
            add_blockquote(doc, " ".join(quote_lines))
            continue

        # bullet list
        if re.match(r"^[-*+]\s+", stripped):
            while i < n and re.match(r"^\s*[-*+]\s+", lines[i]):
                item = re.sub(r"^\s*[-*+]\s+", "", lines[i]).strip()
                add_bullet(doc, item)
                i += 1
            continue

        # numbered list
        if re.match(r"^\d+\.\s+", stripped):
            while i < n and re.match(r"^\s*\d+\.\s+", lines[i]):
                item = re.sub(r"^\s*\d+\.\s+", "", lines[i]).strip()
                add_number(doc, item)
                i += 1
            continue

        # plain paragraph (merge consecutive plain lines)
        para_lines = []
        while i < n:
            s = lines[i].strip()
            if not s:
                break
            if (s.startswith("```") or s.startswith("|") or s.startswith(">")
                    or s == "\\[" or re.match(r"^#{1,6}\s+", s)
                    or re.match(r"^-{3,}$", s) or re.match(r"^\*{3,}$", s)
                    or re.match(r"^[-*+]\s+", s)
                    or re.match(r"^\d+\.\s+", s)):
                break
            para_lines.append(s)
            i += 1
        add_paragraph(doc, " ".join(para_lines))


# --------------------------------------------------------------------------- #
# Document assembly
# --------------------------------------------------------------------------- #
def configure_styles(doc):
    normal = doc.styles["Normal"]
    normal.font.name = LATIN_FONT
    normal.font.size = Pt(BODY_SIZE)
    rpr = normal.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), LATIN_FONT)
    rfonts.set(qn("w:hAnsi"), LATIN_FONT)
    rfonts.set(qn("w:eastAsia"), CJK_FONT)


def _first_title(lines):
    for line in lines:
        match = re.match(r"^#\s+(.*)", line.strip())
        if match:
            return match.group(1).strip()
    return ""


def convert(md_path, docx_path):
    md_path = Path(md_path)
    text = md_path.read_text(encoding="utf-8")
    lines = text.split("\n")

    doc = Document()
    configure_styles(doc)
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    parse(doc, lines)

    doc.core_properties.title = _first_title(lines)
    doc.core_properties.author = "VirtualStudent Sandbox Team"

    doc.save(docx_path)
    print(f"[ok] {md_path.name} -> {Path(docx_path).name}")


def main(argv):
    root = Path(__file__).resolve().parent.parent
    if len(argv) == 3:
        convert(argv[1], argv[2])
        return
    # default: the three v6.0 deliverable documents
    pairs = [
        (root / "需求说明文档-虚拟学生试验台-v6.0.md",
         root / "需求说明文档-虚拟学生试验台-v6.0.docx"),
        (root / "技术设计文档-虚拟学生试验台-v6.0.md",
         root / "技术设计文档-虚拟学生试验台-v6.0.docx"),
        (root / "虚拟学生全方位档案设计文档-v6.0.md",
         root / "虚拟学生全方位档案设计文档-v6.0.docx"),
    ]
    for md, docx in pairs:
        convert(md, docx)


if __name__ == "__main__":
    main(sys.argv)
