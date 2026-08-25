from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_ROW_HEIGHT_RULE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


ROOT = Path(r"D:\Desktop\-")
SOURCE = ROOT / "提交pdf初稿-优化版.docx"
OUTPUT = ROOT / "提交pdf初稿-最终版.docx"


def set_run_font(run, size: float, bold: bool, color: str | None = None) -> None:
    run.font.name = "Microsoft YaHei"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def set_paragraph_text(paragraph, text: str, style: str | None = None) -> None:
    if style:
        paragraph.style = style
    if paragraph.runs:
        paragraph.runs[0].text = text
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.add_run(text)


def set_cell_text(cell, text: str, *, size: float = 8.2, bold: bool = False,
                  color: str | None = None, align: WD_ALIGN_PARAGRAPH = WD_ALIGN_PARAGRAPH.LEFT) -> None:
    if not cell.paragraphs:
        cell.text = text
    p = cell.paragraphs[0]
    p.alignment = align
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.0
    if p.runs:
        p.runs[0].text = text
        for run in p.runs[1:]:
            run.text = ""
    else:
        p.add_run(text)
    for run in p.runs:
        set_run_font(run, size, bold, color)
    for extra in cell.paragraphs[1:]:
        set_paragraph_text(extra, "")


def shade_cell(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def mark_header_row(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)
    row.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
    row.height = Cm(0.45)
    for cell in row.cells:
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        shade_cell(cell, "D9E5F2")


def add_header(table, labels: list[str]) -> None:
    if len(table.columns) != len(labels) or len(table.rows) < 1:
        return
    # Insert one compact header row before the existing content rows.
    row = table.add_row()
    table._tbl.remove(row._tr)
    table._tbl.insert(0, row._tr)
    for cell, label in zip(row.cells, labels):
        set_cell_text(cell, label, size=8.2, bold=True, color="1F2937", align=WD_ALIGN_PARAGRAPH.CENTER)
    mark_header_row(row)


def normalize_tables(doc: Document) -> None:
    headers = {
        1: ["字段", "内容"],
        2: ["环节", "采用方法", "输出/判断"],
        3: ["证据来源", "用途", "当前状态", "使用边界"],
        5: ["模块", "方法/工具", "关注问题", "输出"],
        7: ["模块", "输入/处理", "输出", "系统层级", "衔接关系"],
        8: ["Qwen 使用项", "具体做法"],
        9: ["步骤", "输入/依据", "输出", "作用"],
        10: ["步骤", "生成方式", "质量约束"],
        11: ["筛选维度", "判断标准", "证据/决策"],
        12: ["计划环节", "具体做法", "对应字段"],
        13: ["失败类型", "系统反馈", "处理动作", "后续影响"],
        15: ["评价维度", "评价重点"],
        16: ["编号", "候选假设", "案例证据", "真人验证设计", "状态"],
        17: ["序号", "验证要素", "判断问题"],
        19: ["反馈阶段", "主要内容", "评价依据", "结果用途"],
        21: ["迭代对象", "第一轮", "第二轮调整", "修订结果", "证据/依据"],
        22: ["交付对象", "已有证据", "待补内容", "影响/边界", "置信度", "记录方式"],
        24: ["问题类型", "表现", "处理方法", "留档"],
        25: ["状态", "当前表现", "触发条件", "回退/处理"],
        26: ["交付项", "状态/说明"],
    }
    for idx, labels in headers.items():
        if idx < len(doc.tables):
            add_header(doc.tables[idx], labels)
    # Shorten the registration form labels so the core claim fits on P1 and
    # the table can be scanned without template boilerplate.
    if len(doc.tables) > 1 and len(doc.tables[1].rows) >= 7:
        short_labels = [
            "报名作品名",
            "最终作品名",
            "参赛选题",
            "作品简介",
            "Qwen/AI 说明",
            "视频/附件",
        ]
        for row, label in zip(doc.tables[1].rows[1:], short_labels):
            set_cell_text(row.cells[0], label, size=7.8, bold=False)

    # Remove empty trailing rows introduced by the template. A row containing
    # an image or any non-whitespace text is never considered empty.
    for idx, table in enumerate(doc.tables):
        if idx == 0:  # the image-only team-information table
            continue
        while len(table.rows) > 1:
            last = table.rows[-1]
            has_text = any(cell.text.strip() for cell in last.cells)
            has_drawing = any(cell._tc.xpath('.//wp:inline | .//wp:anchor') for cell in last.cells)
            if has_text or has_drawing:
                break
            table._tbl.remove(last._tr)

    # Fill the relationships column of the architecture table. These rows
    # are downstream contracts, not optional decoration.
    if len(doc.tables) > 6:
        architecture = doc.tables[6]
        links = [
            "进入证据组织",
            "进入候选假设生成",
            "进入仿真验证与筛选",
            "进入研究计划生成",
            "进入人在回路反馈",
        ]
        for row, value in zip(architecture.rows[1:], links):
            if len(row.cells) >= 5:
                set_cell_text(row.cells[4], value, size=8.2, bold=False)

    # Complete the final Qwen/tool collaboration row instead of leaving a
    # label with an empty value cell.
    if len(doc.tables) > 7 and len(doc.tables[7].rows) >= 7:
        set_cell_text(doc.tables[7].rows[-1].cells[1],
                      "检索提供来源与版本；代码工具执行仿真、统计和导出；Qwen 仅组织语言并引用工具结果。",
                      size=8.2, bold=False)
    # Tables containing a single note are deliberately kept as callouts, not
    # forced into artificial two-column tables.
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                for p in cell.paragraphs:
                    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                    p.paragraph_format.left_indent = Pt(0)
                    p.paragraph_format.first_line_indent = Pt(0)
                    p.paragraph_format.space_before = Pt(0)
                    p.paragraph_format.space_after = Pt(0)
                    p.paragraph_format.line_spacing = 1.0
                    for run in p.runs:
                        set_run_font(run, 8.2, bool(run.bold), None)
    # Re-apply centered alignment only to header rows after body normalization.
    for table in doc.tables:
        if table.rows:
            for cell in table.rows[0].cells:
                for p in cell.paragraphs:
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER


def normalize_headings(doc: Document) -> None:
    for p in doc.paragraphs:
        if p.style.name == "Heading 1":
            p.paragraph_format.keep_with_next = True
            p.paragraph_format.space_before = Pt(5)
            p.paragraph_format.space_after = Pt(3)
            for run in p.runs:
                set_run_font(run, 14, True, "2E74B5")
        elif p.style.name == "Heading 2":
            p.paragraph_format.keep_with_next = True
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after = Pt(1.5)
            for run in p.runs:
                set_run_font(run, 11.5, True, "2E74B5")
        elif p.style.name == "Heading 3":
            p.paragraph_format.keep_with_next = True
            for run in p.runs:
                set_run_font(run, 10.5, True, "1F4D78")

    # Front matter is not a section heading, but it should have one consistent
    # title treatment instead of inheriting arbitrary template direct-formatting.
    front = {
        0: (12, True, "1F4D78"),
        1: (17, True, "2E74B5"),
        2: (8.5, False, "666666"),
    }
    for idx, (size, bold, color) in front.items():
        if idx >= len(doc.paragraphs):
            continue
        p = doc.paragraphs[idx]
        for run in p.runs:
            set_run_font(run, size, bold, color)
        p.paragraph_format.space_after = Pt(2)


def repair_misclassified_content(doc: Document) -> None:
    # These paragraphs were previously populated while retaining Heading 2.
    # Split each into a short section label followed by ordinary body text.
    repairs = {
        116: ("第一轮实际结果", "第一轮固定 seed 结果：I1 g=0.309、I2 g=0.414、I3 g=0.551、I4 g=0.331、I5 g=0.263；5 个 95% CI 均跨零。系统因此保留“家长/教师中介和场景差异值得真人验证”的候选假设，暂不输出 GO 结论。"),
        118: ("研究计划输出", "目标为比较不同干预在学校与家庭场景的成绩增益和学习动机；采用分层随机对照设计，主指标为增益分数与 Hedges' g，报告 95% CI、子群和稳健性；真人阶段需预注册、补充真实日志校准，并以 CI、伦理审查和依从性作为停止/升级条件。"),
        144: ("固定 seed 代表性案例结果", "100 名学生、90 天、5 个干预臂；g 范围 0.263–0.551，所有 95% CI 跨零。详细输入、模型、分组、效应量和解释见提交材料_代表性案例_20260821.json。"),
        151: ("最终交付内容", "源代码（src/、frontend/、config/、tests/）、README 运行说明、技术/需求/画像设计文档、固定 seed 案例 JSON、测试记录和可选演示脚本；Qwen 实时调用日志、盖章报名表截图与 125 题全量结果需由团队补入最终提交包。"),
    }
    for idx, (heading, body) in repairs.items():
        if idx >= len(doc.paragraphs):
            continue
        p = doc.paragraphs[idx]
        set_paragraph_text(p, heading, "Heading 2")
        # The next paragraph is intentionally blank in the source template.
        if idx + 1 < len(doc.paragraphs):
            set_paragraph_text(doc.paragraphs[idx + 1], body, "Normal")


def normalize_page_layout(doc: Document) -> None:
    for section in doc.sections:
        section.top_margin = Cm(1.55)
        section.bottom_margin = Cm(1.55)
        section.left_margin = Cm(1.75)
        section.right_margin = Cm(1.75)
        # The source template stores its explanatory "使用说明" in the
        # first-page header. It is an instruction to the author, not part of
        # the submitted technical proposal, so remove it from every header
        # variant while retaining the footer page numbers.
        for header in (section.header, section.first_page_header, section.even_page_header):
            for p in header.paragraphs:
                set_paragraph_text(p, "")
            # The template's first-page note is stored in a text box rather
            # than a normal paragraph, so clear the header XML content too.
            for child in list(header._element):
                header._element.remove(child)
    normal = doc.styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    normal.font.size = Pt(9.5)
    normal.paragraph_format.line_spacing = 1.02
    normal.paragraph_format.space_after = Pt(1.5)
    for p in doc.paragraphs:
        if p.style.name in {"Normal", "List Bullet"}:
            p.paragraph_format.line_spacing = 1.02
            p.paragraph_format.space_after = Pt(1.5)


def main() -> None:
    doc = Document(str(SOURCE))
    before_images = len(doc.inline_shapes)
    if len(doc.paragraphs) > 13:
        set_paragraph_text(doc.paragraphs[4], "团队/成员信息（补入盖章报名表截图）", "Heading 2")
        set_paragraph_text(doc.paragraphs[13], "限制：真实数据、Qwen 实时凭证和 125 题全量证据待补；模拟结果不替代真人 RCT。", "List Bullet")
    repair_misclassified_content(doc)
    normalize_headings(doc)
    normalize_tables(doc)
    normalize_page_layout(doc)
    # P1 already ends exactly at the page boundary after the compacted
    # registration block; keeping the template's extra break before P2 would
    # create a blank page. Let P2 flow onto the next page naturally.
    if len(doc.paragraphs) > 18:
        doc.paragraphs[18].paragraph_format.page_break_before = False
    # Keep both user-supplied screenshots, but prevent the two-column image
    # block from forcing P1 onto an extra physical page. Preserve aspect ratio.
    for shape in doc.inline_shapes:
        ratio = shape.height / shape.width if shape.width else 1.4
        shape.width = Cm(5.0)
        shape.height = int(shape.width * ratio)
    doc.core_properties.title = "虚拟学生试验台 v6.0 技术方案（最终排版版）"
    doc.core_properties.comments = "统一标题层级与表头；保留用户已插入的图片和内容。"
    doc.save(str(OUTPUT))
    after = Document(str(OUTPUT))
    print(f"wrote {OUTPUT}")
    print(f"images {before_images}->{len(after.inline_shapes)} tables={len(after.tables)} paragraphs={len(after.paragraphs)}")


if __name__ == "__main__":
    main()
