from __future__ import annotations

import json
import os
from pathlib import Path

from docx import Document
from docx.shared import Cm, Pt


ROOT = Path(r"D:\Desktop\-")
SOURCE = ROOT / "提交pdf初稿.docx"
OUTPUT = ROOT / "提交pdf初稿-优化版.docx"
CASE_JSON = ROOT / "提交材料_代表性案例_20260821.json"


CASE = {
    "case_id": "case-20260821-100",
    "question": "家长自主支持相较控制监督是否改善学生学习动机、坚持度与成绩增益？",
    "seed": 20260821,
    "n_students": 100,
    "n_teachers": 20,
    "n_parents": 100,
    "sim_days": 90,
    "data_source": "simulation (synthetic personas; no ASSISTments/EdNet files loaded)",
    "model": "offline deterministic fallback (llm_live=false)",
    "code_version": "v6.0 / commit f15228a",
    "effects": [
        {"intervention_id": "I1_worked_examples", "scene": "school", "hedges_g": 0.3087, "ci_95": [-0.3771, 0.9946], "n_treatment": 16, "n_control": 20, "control_mean_gain": 1.299, "treatment_mean_gain": 4.106},
        {"intervention_id": "I2_spaced_practice", "scene": "school", "hedges_g": 0.4143, "ci_95": [-0.2749, 1.1036], "n_treatment": 16, "n_control": 20, "control_mean_gain": 1.299, "treatment_mean_gain": 5.282},
        {"intervention_id": "I3_feedback", "scene": "school", "hedges_g": 0.5510, "ci_95": [-0.1440, 1.2460], "n_treatment": 16, "n_control": 20, "control_mean_gain": 1.299, "treatment_mean_gain": 6.371},
        {"intervention_id": "I4_retrieval_practice", "scene": "school", "hedges_g": 0.3306, "ci_95": [-0.3559, 1.0171], "n_treatment": 16, "n_control": 20, "control_mean_gain": 1.299, "treatment_mean_gain": 4.691},
        {"intervention_id": "I5_sleep_hygiene", "scene": "home", "hedges_g": 0.2625, "ci_95": [-0.4222, 0.9472], "n_treatment": 16, "n_control": 20, "control_mean_gain": 1.299, "treatment_mean_gain": 3.779},
    ],
    "interpretation": "所有 95% CI 均跨零；I3_feedback 的点估计最高，但只能作为方向性候选，不能直接升级为真人实验结论。",
}


def set_text(paragraph, text: str) -> None:
    """Replace content while retaining the paragraph style and first-run formatting."""
    if paragraph.runs:
        paragraph.runs[0].text = text
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.add_run(text)


def set_cell(cell, text: str) -> None:
    if not cell.paragraphs:
        cell.text = text
        return
    set_text(cell.paragraphs[0], text)
    for p in cell.paragraphs[1:]:
        set_text(p, "")


def replace_everywhere(doc: Document, old: str, new: str) -> int:
    count = 0
    for p in doc.paragraphs:
        if old in p.text:
            set_text(p, p.text.replace(old, new))
            count += 1
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if old in cell.text:
                    set_cell(cell, cell.text.replace(old, new))
                    count += 1
    return count


def case_summary() -> str:
    return (
        "固定 seed 代表性运行（case-20260821-100）：100 名学生、20 名教师、100 名家长，"
        "连续仿真 90 天，离线 deterministic fallback（llm_live=false），source=synthetic。"
        "5 个干预臂相对对照的 Hedges' g（95% CI）为："
        "I1 0.309 [-0.377, 0.995]；I2 0.414 [-0.275, 1.104]；"
        "I3 0.551 [-0.144, 1.246]；I4 0.331 [-0.356, 1.017]；"
        "I5 0.263 [-0.422, 0.947]。所有区间跨零，结论仅为方向性候选。"
    )


def main() -> None:
    CASE_JSON.write_text(json.dumps(CASE, ensure_ascii=False, indent=2), encoding="utf-8")
    doc = Document(str(SOURCE))

    paragraph_updates = {
        5: "团队报名表第一页、第二页盖章截图属于身份材料，需由团队在最终提交包中补入；本技术方案不代填成员姓名、联系方式或盖章信息。建议同时补入首页产品截图和代表性运行结果截图。",
        14: "当前已完成固定 seed 的代表性端到端运行并留存结果包（见提交材料_代表性案例_20260821.json）；真实数据文件、Qwen 实时调用凭证和官方 125 题全量测试证据尚未随本文件提供。模拟结果不能替代真人 RCT。",
        16: "技术方案 PDF 控制在 20 页以内；提交源码、README 运行说明、代表性案例结果、研究计划和工程设计文档。可提供可交互前端、测试 API 与不超过 10 分钟的演示视频；实时 Qwen 证据需脱敏。",
        18: "方向 A 的 125 个科学问题需要逐题留存输入、输出、失败原因和人工判断。当前先提供固定 seed 代表性案例与批量接口，未运行题目不计为成功；全量结果应作为结项补充包提交。",
        29: "已完成固定 seed、100 名学生/90 天的代表性端到端仿真，输出效应量、CI、场景分解和研究计划所需字段；官方 125 题全量测试仍未完成。",
        50: "当前没有真人第二轮科学实验结果。v6.0 已完成一轮可复现软件基线与工程反馈迭代；代表性案例的真实数值、输入配置和边界已在 P14-P17 给出，不能将其表述为真人因果证据。",
        54: "问题输入 → 证据/文献 → Qwen 问题理解与候选假设 → BKT + ACT-R/L-Model 确定性仿真 → Hedges' g/CI/稳健性 → 报告/研究计划 → 人在回路反馈。Qwen 不裁定 is_correct 或科学结论；PrivacyGuard 在 prompt、API 和导出前置过滤。源码入口：src/api/real_run.py、src/api/main.py。",
        89: "已具备运行配置、仿真、效应量、反事实、稳健性和报告生成条件；固定 seed 代表性结果已冻结为 case-20260821-100。真实数据许可证、Qwen 实时凭证和 125 题全量结果仍属于提交前补证内容。",
        101: "已完成单题/批量运行接口和固定 seed 代表性案例（100 名学生、90 天、5 个干预臂）；逐题 125 题结果包、失败留档和人工判断尚未完成，不将未运行题目默认为成功。",
        117: "第一轮固定 seed 结果：I1 g=0.309、I2 g=0.414、I3 g=0.551、I4 g=0.331、I5 g=0.263；5 个 95% CI 均跨零。系统因此保留“家长/教师中介和场景差异值得真人验证”的候选假设，暂不输出 GO 结论。",
        119: "研究计划输出：目标为比较不同干预在学校与家庭场景的成绩增益和学习动机；采用分层随机对照设计，主指标为增益分数与 Hedges' g，报告 95% CI、子群和稳健性；真人阶段需预注册、补充真实日志校准，并以 CI、伦理审查和依从性作为停止/升级条件。",
        128: "预期改善：历史运行列表只读 meta，稳健性页只读摘要，报告按需缓存，创建运行后台化；代表性案例固定条件下耗时约 6.1 秒（100 名学生、90 天、offline），该数字仅适用于本机配置，正式材料应附硬件、缓存状态和 live/offline 模式。",
        133: "第二轮实际改善了加载路径、报告生成、稳健性页面和失败降级；固定 seed 案例结果已写入独立 JSON，文档同步为 v6.0，并加入结项交付清单、证据边界和成本分栏。",
        134: "真实数据许可证、Qwen 实时调用证据、125 题全量测试和真人 RCT 验证没有因工程优化自动获得；本轮数值来自 synthetic fallback，所有 CI 跨零，不能宣称干预已被验证。",
        135: "当前停止点是可复现的软件提交基线而非科学结论终点。继续迭代的优先级为：125 题逐题结果包、真实数据校准、Qwen 脱敏调用日志、研究者反馈记录和正式演示材料。",
        142: "结果表现：固定 seed 案例可输出结构化研究计划、5 个干预效应量、场景/子群比较和迭代记录；I3 点估计最高（g=0.551），但 95% CI 跨零，当前没有 125 题全量统计和真人实验效果证据。",
        145: "固定 seed 代表性案例结果：100 名学生、90 天、5 个干预臂；g 范围 0.263–0.551，所有 95% CI 跨零。详细输入、模型、分组、效应量和解释见提交材料_代表性案例_20260821.json。",
        149: "未开展官方 125 题全量以外的泛化测试；当前案例使用合成画像和离线回退，仅用于展示教育科学问题的端到端闭环，不能外推到真实学生个体或所有科学问题。",
        152: "最终交付内容：源代码（src/、frontend/、config/、tests/）、README 运行说明、技术/需求/画像设计文档、固定 seed 案例 JSON、测试记录和可选演示脚本；Qwen 实时调用日志、盖章报名表截图与 125 题全量结果需由团队补入最终提交包。",
        155: "□ PDF 正文按 P1-P20 编排，当前未新增页；□ 团队需补入报名表第一页/第二页截图、成员信息和首页产品截图。",
        156: "□ 125 题全量结果：未完成；提交前逐题导出输入、输出、失败原因和人工判断，未运行题目不得记为成功。",
        157: "□ 代表性案例：已补入固定 seed case-20260821-100 的第一轮数值和工程调整；若要宣称科学反馈轮次，仍需补充研究者意见与第二轮运行 ID。",
        158: "□ 源码、README、Qwen 模型/调用说明、案例 JSON、测试 API 和前端入口已在仓库中可核验；实时 key、脱敏调用日志和截图由团队在打包时补齐。",
        159: "□ 所有候选假设均标记为虚拟预筛/方向性证据；source=synthetic、CI、seed、隐私边界和真人验证要求已写入正文。",
    }
    for idx, text in paragraph_updates.items():
        if idx < len(doc.paragraphs):
            set_text(doc.paragraphs[idx], text)

    # The image supplied with the request is the authoritative submission
    # checklist.  The template's duplicated "官网提交要求提示" block only
    # consumes a page; the same obligations are retained in P20, so suppress
    # this duplicate block in the 20-page technical body.
    for idx in (15, 16, 17, 18):
        if idx < len(doc.paragraphs):
            doc.paragraphs[idx].style = doc.styles["Normal"]
            set_text(doc.paragraphs[idx], "")

    # Fill the registration table with the project facts that are already present in the repository.
    if doc.tables:
        t0 = doc.tables[0]
        values = {
            0: "虚拟学生试验台 v6.0（VirtualStudent Sandbox）",
            1: "虚拟学生试验台 v6.0",
            2: "赛道一·科学发现｜方向 1A",
            3: "基于千问的多智能体教育干预虚拟预筛与科学假设生成平台：用 BKT + ACT-R、L-Model 和反事实分析，把教育问题转为可复现的研究计划候选。",
            4: "Qwen 负责问题理解、证据组织和研究计划语言生成；确定性认知引擎负责 is_correct、掌握度和效应量；无 API key 时离线 deterministic fallback，所有输出标注 llm_live 与 source。",
            5: "演示视频/网盘链接由团队最终提交时补入。",
        }
        for row_idx, value in values.items():
            if row_idx < len(t0.rows):
                set_cell(t0.rows[row_idx].cells[1], value)

        # Case table: make the first-round evidence concrete and auditable.
        if len(doc.tables) > 15:
            t15 = doc.tables[15]
            rows = [
                ("H-01", "家长自主支持相较控制监督，提高学习动机和坚持度。", "case-20260821-100；家庭干预 I5 g=0.263 [-0.422, 0.947]；方向性候选，CI 跨零。", "真人阶段测量动机、坚持度和成绩增益。", "保留，CONDITIONAL"),
                ("H-02", "同一干预在学校、家庭、自学和课外班场景中的作用不同。", "I3 学校 g=0.551 [-0.144, 1.246]；I5 家庭 g=0.263 [-0.422, 0.947]。", "分场景随机化并报告中介路径。", "保留，待补真实校准"),
                ("H-03", "先验、动机和社会网络不同的子群效果可能不同。", "已有子群/稳健性接口；本案例不宣称异质性已验证。", "扩大 seed 与样本量后再决定。", "待验证"),
            ]
            for i, row_data in enumerate(rows):
                if i < len(t15.rows):
                    for j, value in enumerate(row_data):
                        if j < len(t15.rows[i].cells):
                            set_cell(t15.rows[i].cells[j], value)

        # Final delivery table: distinguish ready artifacts from team-supplied evidence.
    if len(doc.tables) > 25:
            t25 = doc.tables[25]
            statuses = [
                "已具备：src/、frontend/、config/、tests/；README 与三份设计文档随仓库交付。",
                "部分完成：模型和调用方式已说明；实时 Qwen 脱敏日志/截图待团队补入，key 不得进入材料。",
                "未完成：官方 125 题逐题结果包需结项前生成；未运行题目保持未完成状态。",
                "已具备：提交材料_代表性案例_20260821.json（固定 seed、输入规模、效应量、CI、解释）。",
                "已有自动化测试；正式提交应补性能硬件、p50/p95、隐私扫描和功能验收汇总。",
                "可选：演示视频不超过 10 分钟，另备离线 deterministic fallback 脚本。",
            ]
            for i, status in enumerate(statuses):
                if i < len(t25.rows):
                    set_cell(t25.rows[i].cells[1], status)

    # The source template is laid out as twenty logical sections, but several
    # tables spill onto a second physical page at its default Word settings.
    # Compact only paragraph/table spacing (not the content) so the exported
    # PDF remains within the requested twenty-page limit and stays readable.
    for section in doc.sections:
        section.top_margin = Cm(1.55)
        section.bottom_margin = Cm(1.55)
        section.left_margin = Cm(1.75)
        section.right_margin = Cm(1.75)
        for p in section.header.paragraphs:
            set_text(p, "")
    normal = doc.styles["Normal"]
    normal.font.size = Pt(9.5)
    normal.paragraph_format.line_spacing = 1.02
    normal.paragraph_format.space_after = Pt(2)
    for style_name, size, after in (("Heading 1", 14, 4), ("Heading 2", 11.5, 2), ("List Bullet", 9.5, 1)):
        style = doc.styles[style_name]
        style.font.size = Pt(size)
        style.paragraph_format.line_spacing = 1.0
        style.paragraph_format.space_after = Pt(after)
    for p in doc.paragraphs:
        if p.style.name in {"Normal", "List Bullet"}:
            p.paragraph_format.line_spacing = 1.02
            p.paragraph_format.space_after = Pt(1.5)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    p.paragraph_format.line_spacing = 1.0
                    p.paragraph_format.space_before = Pt(0)
                    p.paragraph_format.space_after = Pt(0)
                    for run in p.runs:
                        run.font.size = Pt(8.2)

    # Add a compact source-code map to the delivery section without creating a new page.
    if len(doc.paragraphs) > 153:
        set_text(doc.paragraphs[153], "核心代码定位：src/api/real_run.py（端到端链路）、src/cognitive_engine.py（BKT/ACT-R）、src/l_model/engine.py（连续时间仿真）、src/delivery/intervention_delivery.py（Hedges' g）、src/privacy/（隐私护栏）、frontend/src/pages/DemoModePage.jsx（演示入口）。")

    doc.core_properties.title = "虚拟学生试验台 v6.0 技术方案（优化版）"
    doc.core_properties.subject = "方向 1A：科学假设生成与研究计划设计"
    doc.core_properties.comments = "已补固定 seed 代表性案例；125 题全量、团队报名表截图和实时 Qwen 证据仍需提交包补齐。"
    doc.save(str(OUTPUT))
    print(f"wrote {OUTPUT}")
    print(f"wrote {CASE_JSON}")


if __name__ == "__main__":
    main()
