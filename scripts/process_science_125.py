"""Extract and process the 125 Science/SJTU questions reproducibly.

The booklet is laid out as two columns, so plain PDF text extraction can
interleave headings and body text.  This script uses the heading font metadata
to recover question titles, then emits a transparent offline batch record.
It deliberately does not claim live Qwen calls, external literature retrieval,
or scientific validation; those fields remain explicit review gates.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pdfplumber


QUESTION_STARTS = (
    "what ", "why ", "how ", "can ", "could ", "will ", "is ", "are ",
    "does ", "do ", "where ", "which ", "when ", "would ", "should ",
    "might ", "who ", "and of course",
)

CATEGORIES = [
    "Mathematical Sciences", "Chemistry", "Medicine & Health", "Biology",
    "Astronomy", "Physics", "Engineering & Materials Science",
    "Information Science", "Neuroscience", "Ecology", "Energy Science",
    "Artificial Intelligence",
]


def _line_key(word: Dict) -> Tuple[float, int]:
    """Group words by baseline and booklet column."""
    # The content columns are separated at x ~= 282 on the 612pt page.
    # The right column starts at 281.6pt, so using 315 would merge headings
    # from both columns when they share a baseline.
    col = 0 if float(word["x0"]) < 280 else 1
    return (round(float(word["top"]), 1), col)


def _heading_lines(page) -> List[Tuple[float, int, str]]:
    words = page.extract_words(extra_attrs=["fontname", "size"])
    grouped: Dict[Tuple[float, int], List[Dict]] = defaultdict(list)
    for word in words:
        size = float(word.get("size", 0))
        font = str(word.get("fontname", ""))
        # Question headings are MyriadPro-Bold at 12pt in the booklet.
        if 11.5 <= size <= 12.5 and "Bold" in font:
            grouped[_line_key(word)].append(word)
    lines = []
    for (top, col), group in grouped.items():
        text = " ".join(w["text"] for w in sorted(group, key=lambda w: w["x0"]))
        lines.append((top, col, re.sub(r"\s+", " ", text).strip()))
    return sorted(lines, key=lambda x: (x[1], x[0]))


def _looks_like_question(text: str) -> bool:
    lower = text.lower()
    return lower.startswith(QUESTION_STARTS)


def extract_questions(pdf_path: Path) -> List[Dict]:
    """Recover question titles and source pages from the two-column PDF."""
    recovered: List[Dict] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        # Pages 7-42 contain the numbered question section; the first pages
        # are introductions and the final pages are university information.
        for page_number, page in enumerate(pdf.pages, start=1):
            if page_number < 7 or page_number > 42:
                continue
            lines = _heading_lines(page)
            # The PDF's text columns begin at x=36 and x=281.6.  A long
            # heading may place the tail of its first line in the right
            # column at the same y-coordinate (the next physical line then
            # returns to the left column).  Join that tail before the normal
            # per-column pass, but only when the right fragment is not itself
            # a new question heading.
            merged = []
            consumed_cross = set()
            for idx, (top, col, text) in enumerate(lines):
                if idx in consumed_cross:
                    continue
                if col == 0 and "?" not in text:
                    for jdx, (top2, col2, text2) in enumerate(lines):
                        if jdx == idx or jdx in consumed_cross or col2 != 1:
                            continue
                        if abs(float(top2) - float(top)) <= 1.5 and not _looks_like_question(text2):
                            text = f"{text} {text2}".strip()
                            consumed_cross.add(jdx)
                            break
                merged.append((top, col, text))
            lines = merged
            unfinished: List[Dict] = []
            consumed = set()
            # Normal case: each column flows top-to-bottom and wrapped heading
            # lines stay in the same column.
            for col in (0, 1):
                col_lines = [(top, text) for top, c, text in lines if c == col]
                pending: List[str] = []
                start_top = None
                for line_index, (top, text) in enumerate(col_lines):
                    begins = _looks_like_question(text)
                    if not pending:
                        if not begins:
                            continue
                        pending = [text]
                        start_top = top
                    elif begins and "?" not in " ".join(pending):
                        # The previous title may continue in the other column
                        # at the same vertical position.
                        unfinished.append({"parts": pending[:], "top": start_top, "column": col})
                        pending = [text]
                        start_top = top
                    else:
                        pending.append(text)
                    joined = " ".join(pending)
                    if "?" in joined:
                        recovered.append({
                            "title": joined.split("?", 1)[0].strip() + "?",
                            "source_page": page_number,
                            "column": col,
                            "top": start_top,
                        })
                        pending = []
                        start_top = None
                if pending:
                    unfinished.append({"parts": pending[:], "top": start_top, "column": col})

            # Exceptional case: a long heading can wrap from the left column
            # into a right-column line at the same y-coordinate. Attach an
            # orphan line such as ``solved?`` to the matching unfinished title.
            for item in unfinished:
                candidate = None
                for idx, (top, col, text) in enumerate(lines):
                    if idx in consumed or col == item["column"]:
                        continue
                    if "?" in text and abs(float(top) - float(item["top"])) <= 2.0 and not _looks_like_question(text):
                        candidate = (idx, text)
                        break
                parts = item["parts"][:]
                if candidate:
                    consumed.add(candidate[0])
                    parts.append(candidate[1])
                recovered.append({
                    "title": " ".join(parts).split("?", 1)[0].strip() + "?",
                    "source_page": page_number,
                    "column": item["column"],
                    "top": item["top"],
                })
    # Preserve booklet reading order: page, vertical position, left column first.
    recovered.sort(key=lambda x: (x["source_page"], x["top"], x["column"]))
    # Remove exact duplicates caused by repeated running headers, if any.
    unique: List[Dict] = []
    seen = set()
    for item in recovered:
        key = (item["title"], item["source_page"], item["column"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    if len(unique) != 125:
        for i, item in enumerate(unique, start=1):
            print(f"{i:03d} p{item['source_page']} c{item['column']} {item['title']}")
        raise RuntimeError(
            f"Expected 125 question headings, recovered {len(unique)}. "
            "Inspect PDF font extraction before using the batch output."
        )
    for i, item in enumerate(unique, start=1):
        item["question_id"] = f"SCI-{i:03d}"
    return unique


def infer_category(page_text: str) -> str:
    # Prefer the first category heading that appears in the page text.
    for category in CATEGORIES:
        if category in page_text:
            return category
    return "跨学科"


def _domain_plan(category: str) -> Dict[str, str]:
    plans = {
        "Mathematical Sciences": ("定理/模型推导、反例检验与可复算计算", "符号推导、数值实验、公开数据或形式化证明"),
        "Chemistry": ("分子/材料机制与可重复实验条件", "光谱、反应动力学、材料表征和对照实验"),
        "Medicine & Health": ("机制—风险因素—临床结局的因果链", "系统综述、队列/病例对照研究、前瞻性临床验证"),
        "Biology": ("遗传、生态或生理机制的可检验关系", "多组学/成像、模型生物实验和独立重复"),
        "Astronomy": ("观测量、物理模型与不确定度", "多波段观测、数值模拟和独立观测复核"),
        "Physics": ("理论预测与实验可观测量", "精密测量、重复实验和理论/数值交叉验证"),
        "Engineering & Materials Science": ("设计变量、性能指标与工程约束", "原型测试、寿命/安全测试和基准方案比较"),
        "Information Science": ("算法假设、数据分布与系统性能", "公开基准、留出集、消融实验和可复现代码"),
        "Neuroscience": ("神经机制、行为指标与个体差异", "神经影像/电生理、行为实验和预注册分析"),
        "Ecology": ("生态过程、环境扰动与系统响应", "长期监测、遥感/实地调查和情景模型"),
        "Energy Science": ("能量转换/储存机制与系统成本", "效率、循环寿命、全生命周期和安全性测试"),
        "Artificial Intelligence": ("能力边界、任务定义与人机协同机制", "基准评测、对照模型、压力测试和人工审查"),
    }
    focus, method = plans.get("跨学科", ("问题中的关键机制和可观测结果", "公开资料、对照实验和独立复核")) if category == "跨学科" else plans[category]
    return {"focus": focus, "method": method}


def build_record(item: Dict, category: str, source_file: str) -> Dict:
    plan = _domain_plan(category)
    title = item["title"]
    return {
        "question_id": item["question_id"],
        "question": title,
        "domain": category,
        "source": {
            "file": source_file,
            "page": item["source_page"],
            "publisher": "Science/AAAS 与上海交通大学",
            "edition": "125 Questions: Exploration and Discovery (2021)",
        },
        "round_1": {
            "understanding": f"将“{title}”拆解为研究对象、关键机制、可观测结果和适用边界。",
            "knowledge_integration": "仅整合该题在原PDF中的题干及说明文字；未把说明文字当作已验证结论。",
            "candidate_hypothesis": f"候选假设：在明确边界条件下，{plan['focus']}能够对该问题给出可重复的机制解释。",
            "evidence_status": "source_context_only",
            "verification_plan": plan["method"],
            "research_plan": "先建立可复算基线，再进行对照/消融或独立重复；结果需报告效应、不确定度和失败条件。",
        },
        "round_2": {
            "change": "补充可证伪指标、对照条件和失败留档字段；未进行外部文献检索或真人实验。",
            "score": {"specificity": 0.6, "reproducibility": 0.6, "evidence_completeness": 0.2},
            "human_review": "required",
        },
        "execution": {
            "mode": "offline_deterministic_fallback",
            "live_qwen_called": False,
            "external_literature_retrieved": False,
            "real_experiment_completed": False,
            "status": "draft_requires_review",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, default=Path("sjtu-booklet.pdf"))
    parser.add_argument("--output", type=Path, default=Path("data/science_125_batch.json"))
    args = parser.parse_args()
    questions = extract_questions(args.pdf)
    page_text = {}
    with pdfplumber.open(str(args.pdf)) as pdf:
        for page_number in sorted({q["source_page"] for q in questions}):
            page_text[page_number] = pdf.pages[page_number - 1].extract_text() or ""
    records = [
        build_record(q, infer_category(page_text[q["source_page"]]), args.pdf.name)
        for q in questions
    ]
    payload = {
        "schema_version": "science-125-batch-v1",
        "created_at": "2026-08-25",
        "source": {
            "file": args.pdf.name,
            "question_count": 125,
            "extraction": "pdfplumber heading-font extraction",
        },
        "summary": {
            "total": 125,
            "processed": len(records),
            "completed_live_scientific_validation": 0,
            "requires_human_review": len(records),
        },
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False))
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
