from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt


ROOT = Path(r"D:\Desktop\-")
SOURCE = ROOT / "提交pdf初稿-规范版.docx"
OUTPUT = ROOT / "提交pdf初稿-最终交付版.docx"


def set_cell_text(cell, text: str, size: float = 8.2, bold: bool = False) -> None:
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.left_indent = Pt(0)
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.0
    if p.runs:
        p.runs[0].text = text
        for r in p.runs[1:]:
            r.text = ""
    else:
        p.add_run(text)
    for r in p.runs:
        r.font.name = "Microsoft YaHei"
        r._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        r.font.size = Pt(size)
        r.bold = bold
    for extra in cell.paragraphs[1:]:
        extra.text = ""


def insert_body_note_after(doc, table, text: str) -> None:
    """Replace a callout table with an ordinary, compact body paragraph."""
    p = doc.add_paragraph()
    p.style = "Normal"
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.left_indent = Pt(0)
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.0
    r = p.add_run(text)
    r.font.name = "Microsoft YaHei"
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    r.font.size = Pt(8.8)
    table._tbl.addnext(p._p)


def main() -> None:
    doc = Document(str(SOURCE))

    # Remove empty body paragraphs that contain no text, drawing, page break,
    # or section marker. They are spacing artifacts from the source template;
    # heading spacing and explicit page breaks provide the intended layout.
    body = doc.element.body
    for p in list(body.findall(qn("w:p"))):
        text = "".join(p.itertext()).strip()
        has_drawing = bool(p.xpath('.//wp:inline | .//wp:anchor'))
        has_break = bool(p.xpath('.//w:br | .//w:lastRenderedPageBreak'))
        if not text and not has_drawing and not has_break:
            body.remove(p)
    # Empty trailing rows are template artifacts. Keep image-only table 0.
    for idx, table in enumerate(doc.tables):
        if idx == 0:
            continue
        while len(table.rows) > 1:
            row = table.rows[-1]
            has_text = any(c.text.strip() for c in row.cells)
            has_drawing = any(c._tc.xpath('.//wp:inline | .//wp:anchor') for c in row.cells)
            if has_text or has_drawing:
                break
            table._tbl.remove(row._tr)

    # Architecture table: complete every downstream relationship.
    if len(doc.tables) > 6:
        architecture = doc.tables[6]
        values = ["进入证据组织", "进入候选假设生成", "进入仿真验证与筛选", "进入研究计划生成", "进入人在回路反馈", "进入专家反馈与下一轮配置"]
        for row, value in zip(architecture.rows[1:], values):
            if len(row.cells) >= 5:
                set_cell_text(row.cells[4], value)
        if len(architecture.rows) >= 7:
            set_cell_text(architecture.rows[6].cells[1], "M8、HITL、版本比较")
            set_cell_text(architecture.rows[6].cells[2], "研究计划和下一轮配置")
            set_cell_text(architecture.rows[6].cells[3], "报告层")

    # Qwen/tool collaboration row: complete the value cell.
    if len(doc.tables) > 7 and len(doc.tables[7].rows) >= 7:
        set_cell_text(doc.tables[7].rows[-1].cells[1], "检索提供来源与版本；代码工具执行仿真、统计和导出；Qwen 仅组织语言并引用工具结果。")

    # Complete rows that contain a meaningful label but were left blank by the
    # original template. Values are derived from the surrounding section text.
    fills = {
        1: {6: ["标注为候选假设，保留不确定性和真人验证边界。", "候选/虚拟结果不得写作已证实科学结论。"]},
        8: {
            2: ["文献/数据字段、参数和约束", "形成证据清单", "进入候选假设生成"],
            3: ["来源等级、校准距离、缺失字段和冲突证据", "形成知识缺口", "标记证据冲突与不确定性"],
            4: ["将缺口改写为干预、样本、指标和预测", "形成候选假设", "进入实验配置"],
            5: ["对象、变量、证据缺口和约束", "可运行问题定义", "进入仿真与研究计划"],
        },
        9: {
            5: ["唯一性、字段完整性、指标与预测检查", "去重并保留淘汰原因"],
            6: ["候选假设 schema 与字段清单", "字段齐全、可执行、可追溯"],
        },
        10: {
            6: ["表达、变量、干预和预测是否重复", "去重并记录保留理由"],
            7: ["综合效应量、稳健性和人工反馈", "GO/CONDITIONAL/NO-GO 仅作预筛建议"],
        },
        11: {6: ["预先定义扩大样本、补证或停止自动升级的条件", "对应停止条件/补证方案"]},
        12: {
            2: ["限制结论强度，不冒充真人实验结果", "保留低置信状态"],
            3: ["降级、淘汰或扩大 seed，交由研究者决定", "记录失败原因与人工判断"],
        },
        14: {6: ["争议、缺失字段、CI/seed/样本量敏感性和待补证项", "提交前由研究者确认"]},
        20: {6: ["方向性结果", "增加失真和隐私提示", "不把模拟写成真人结论", "提交前复核"]},
        23: {5: ["重复运行成本与结果稳定性", "缓存、sidecar 和敏感性分析", "记录性能与稳健性摘要", "保留运行 ID 和版本"]},
    }
    for table_idx, row_map in fills.items():
        if table_idx >= len(doc.tables):
            continue
        table = doc.tables[table_idx]
        for row_idx, values in row_map.items():
            if row_idx >= len(table.rows):
                continue
            row = table.rows[row_idx]
            for offset, value in enumerate(values, start=1):
                if offset < len(row.cells) and not row.cells[offset].text.strip():
                    set_cell_text(row.cells[offset], value)

    # Remove duplicate terminal rows that repeat an existing label but contain
    # no data (H-03, sequence 3, duplicate uncertainty/optional-video rows).
    for table_idx, label in ((15, "H-03"), (16, "3"), (25, "可选演示视频")):
        if table_idx < len(doc.tables) and len(doc.tables[table_idx].rows) > 2:
            last = doc.tables[table_idx].rows[-1]
            if last.cells[0].text.strip() == label and all(not c.text.strip() for c in last.cells[1:]):
                doc.tables[table_idx]._tbl.remove(last._tr)

    # The failure-handling table's fourth column is the downstream impact;
    # its two middle rows were blank in the source template.
    if len(doc.tables) > 12 and len(doc.tables[12].columns) >= 4:
        set_cell_text(doc.tables[12].rows[2].cells[3], "降低结论强度，保留待补证状态。")
        set_cell_text(doc.tables[12].rows[3].cells[3], "降级、淘汰或扩大 seed，并记录人工判断。")

    # Replace all single-cell gray callouts with concise ordinary prose, then
    # remove the framed tables. Process in reverse index order.
    callouts = {
        22: "对照范围说明：本文仅呈现团队已完成的对照与反馈；v5→v6 内容属于工程改进记录，不包装为真人科学实验。",
        19: "逐题记录原则：每个回答对应一条实际科学问题；证据不足、失败或需人工判断的题目保留状态，不用模板文本填充为成功。",
        17: "案例迭代原则：代表性案例应保留第一轮结果、反馈来源、调整配置和第二轮结果；仅有工程迭代时，明确标为工程反馈。",
        13: "125 题测试状态：官方全量测试尚未完成；本文件仅呈现已实现能力和代表性案例，未运行题目不计为成功。",
        5: "评价原则：同时检查证据可追溯、假设可检验、输入输出可复现、隐私可控和计划可执行；结论保留不确定性和真人验证边界。",
        3: "证据管理原则：所有来源记录名称、版本、许可证和用途；合成数据与真实数据分栏，Qwen 生成文本不作为事实证据。",
    }
    for idx in sorted(callouts, reverse=True):
        if idx < len(doc.tables) and len(doc.tables[idx].rows) == 1 and len(doc.tables[idx].columns) == 1:
            table = doc.tables[idx]
            insert_body_note_after(doc, table, callouts[idx])
            table._tbl.getparent().remove(table._tbl)

    # Replace column-description placeholders with row-specific consequences.
    # Table indices are evaluated before the callout tables are removed.
    # These tables remain after removal as the row-specific tables are kept.
    target_table = next((t for t in doc.tables if t.rows and t.rows[0].cells[0].text.strip() == "步骤" and len(t.columns) == 4), None)
    if target_table:
        values = [
            "形成可运行问题定义，明确对象、干预和结果变量",
            "形成证据清单并绑定来源",
            "标记证据冲突与不确定性",
            "将知识缺口转为可检验假设与实验配置",
            "进入仿真与研究计划",
        ]
        for row, value in zip(target_table.rows[1:], values):
            set_cell_text(row.cells[3], value)

    failure_table = next((t for t in doc.tables if t.rows and t.rows[0].cells[0].text.strip() == "失败类型"), None)
    if failure_table and len(failure_table.rows) > 1:
        set_cell_text(failure_table.rows[1].cells[3], "保留候选并要求补证或修改，影响后续假设/计划版本。")

    # All body cells left-aligned, with zero indent; header rows centered and bold.
    for table in doc.tables:
        for ri, row in enumerate(table.rows):
            for cell in row.cells:
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                for p in cell.paragraphs:
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if ri == 0 else WD_ALIGN_PARAGRAPH.LEFT
                    p.paragraph_format.left_indent = Pt(0)
                    p.paragraph_format.first_line_indent = Pt(0)
                    p.paragraph_format.space_before = Pt(0)
                    p.paragraph_format.space_after = Pt(0)
                    p.paragraph_format.line_spacing = 1.0
                    for r in p.runs:
                        r.font.name = "Microsoft YaHei"
                        r._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
                        r.font.size = Pt(8.2)
                        if ri == 0:
                            r.bold = True

    doc.core_properties.title = "虚拟学生试验台 v6.0 技术方案（表格规范版）"
    doc.core_properties.comments = "修复表格空尾行、缺失单元格、缩进和正文对齐；保留图片与正文内容。"
    doc.save(str(OUTPUT))
    check = Document(str(OUTPUT))
    print(f"wrote {OUTPUT}; tables={len(check.tables)} images={len(check.inline_shapes)}")
    print("rows", [len(t.rows) for t in check.tables])


if __name__ == "__main__":
    main()
