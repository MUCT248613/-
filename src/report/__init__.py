"""
VirtualStudent Sandbox v5.0 - Report Module (M7 + M8)

M7 报告卡 (Report Card): assembles a structured run report from calibration,
simulation, gap, and ranking results.

M8 《科学假设与研究计划》生成器 (Scientific Hypothesis & Research Plan
Generator): drafts a research plan from the top-ranked interventions.
Uses the LLM for narrative polish, but ALL numbers and citations are
injected from verified results (guardrail: never fabricate numbers or
references).

Reference: 技术设计文档 §5 M7, §5 M8, §3.1 (ReportWriter role)
"""
from typing import Dict, List, Optional, Any

from ..llm import get_client


class ReportWriter:
    """
    M7: Assemble a structured report card for a simulation run.
    """
    
    def __init__(self):
        self.llm = get_client()
    
    def build_report(self, run_summary: Dict, calibration: Dict,
                     effect_sizes: List[Dict], gap_records: List[Dict],
                     ranked: List[Dict]) -> Dict[str, Any]:
        """
        Build the full report card.
        
        Returns a structured dict (JSON-serializable) with all sections.
        """
        report = {
            "title": "虚拟学生试验台运行报告",
            "run_id": run_summary.get("run_id"),
            "overview": {
                "n_students": run_summary.get("n_students", 0),
                "n_teachers": run_summary.get("n_teachers", 0),
                "n_parents": run_summary.get("n_parents", 0),
                "sim_days": run_summary.get("sim_days", 0),
                "seed": run_summary.get("seed"),
            },
            "calibration": {
                "cognitive_distance": calibration.get("distance"),
                "persona_distribution": calibration.get("persona", {}),
            },
            "effect_sizes": effect_sizes,
            "gap_analysis": {
                "records": gap_records,
                "n_high_distortion": sum(
                    1 for g in gap_records if g.get("distortion_category") != "none"),
            },
            "priority_ranking": ranked[:10],
            "privacy_note": "本报告基于全量虚拟仿真数据生成，所有字段均为合成数据，无真实学生隐私。",
        }
        return report
    
    def render_markdown(self, report: Dict) -> str:
        """Render the report card as Markdown (for export)."""
        lines = [f"# {report['title']}", ""]
        ov = report["overview"]
        lines.append(f"- 运行 ID: {report['run_id']}")
        lines.append(f"- 学生数: {ov['n_students']} | 教师数: {ov['n_teachers']} "
                     f"| 家长数: {ov['n_parents']} | 模拟天数: {ov['sim_days']}")
        lines.append("")
        
        lines.append("## 效应量汇总")
        for es in report["effect_sizes"][:10]:
            lines.append(f"- {es.get('intervention_id', '?')} @ {es.get('scene', '?')}: "
                         f"g = {es.get('hedges_g', 0):.3f} "
                         f"[{es.get('ci_lower', 0):.3f}, {es.get('ci_upper', 0):.3f}]")
        lines.append("")
        
        lines.append("## 优先干预（Top 5）")
        for r in report["priority_ranking"][:5]:
            flag = " [失真区]" if r.get("in_distorted_region") else ""
            lines.append(f"{r['rank']}. {r['intervention_id']} "
                         f"(score={r['priority_score']:.3f}){flag}")
        lines.append("")
        
        lines.append(f"> {report['privacy_note']}")
        return "\n".join(lines)


class HypothesisGenerator:
    """
    M8: Generate a 《科学假设与研究计划》 from top-ranked interventions.
    
    Guardrails:
      - Numbers come ONLY from the provided effect_sizes / gap_records.
      - No fabricated citations; references section lists only the
        intervention IDs and their computed statistics.
      - LLM is used only for narrative structure (optional, offline-safe).
    """
    
    PLAN_SECTIONS = [
        "研究背景", "研究假设", "实验设计", "样本与功效",
        "测量指标", "统计分析计划", "伦理与风险", "预期贡献",
    ]
    
    def __init__(self):
        self.llm = get_client()
    
    def generate(self, ranked: List[Dict], effect_sizes: List[Dict],
                 gap_records: List[Dict], n_students: int = 500) -> Dict[str, Any]:
        """
        Generate a structured research plan.
        
        Args:
            ranked: Priority-ranked interventions (from M6)
            effect_sizes: Virtual effect size records (from M4)
            gap_records: Gap analysis records (from M5)
            n_students: Planned real-trial sample size
        
        Returns:
            {"sections": {section: text}, "hypotheses": [...], "references": [...]}
        """
        top = ranked[:3] if ranked else []
        
        hypotheses = self._build_hypotheses(top, effect_sizes)
        sections = self._build_sections(top, effect_sizes, gap_records, n_students)
        references = self._build_references(top, effect_sizes)
        
        plan = {
            "title": "科学假设与研究计划",
            "sections": sections,
            "hypotheses": hypotheses,
            "references": references,
            "generated_from": {
                "n_ranked": len(ranked),
                "n_effect_sizes": len(effect_sizes),
            },
        }
        
        # Optional LLM narrative polish (offline-safe)
        plan["narrative"] = self._llm_polish(plan)
        return plan
    
    def _build_hypotheses(self, top: List[Dict], effect_sizes: List[Dict]) -> List[Dict]:
        """Build falsifiable hypotheses grounded in the virtual effect sizes.

        FR-R6: hypotheses carry explicit ``role`` (teacher/parent/scene/student)
        and ``scene`` fields, and additionally include multi-role hypotheses
        (教师/家长/场景) such as “自主支持型教师能否抵消叛逆期动机低谷”。
        """
        hypotheses = []
        es_by_id = {es.get("intervention_id"): es for es in effect_sizes}
        
        for i, r in enumerate(top, 1):
            intv_id = r["intervention_id"]
            es = es_by_id.get(intv_id, {})
            g = es.get("hedges_g", r.get("breakdown", {}).get("effect_size", 0))
            scene = es.get("scene") or r.get("scene") or "school"
            role = self._role_from_channel(r.get("channel") or es.get("channel"))
            
            hypotheses.append({
                "id": f"H{i}",
                "statement": (
                    f"与对照组相比，接受「{intv_id}」干预的学生在学业成就上将有显著提升"
                    f"（虚拟效应量 g = {g:.3f}）。"
                ),
                "predicted_effect": float(g),
                "intervention_id": intv_id,
                "role": role,
                "scene": scene,
                "falsifiable": True,
            })
        
        # FR-R6: multi-role hypotheses (teacher / parent / scene)
        hypotheses.extend(self._build_role_hypotheses(top, effect_sizes))
        return hypotheses

    @staticmethod
    def _role_from_channel(channel: Optional[str]) -> str:
        """Map a delivery channel to the mediating role for hypothesis tagging."""
        mapping = {
            "teacher_mediated": "teacher",
            "parent_mediated": "parent",
            "shadow_edu_mediated": "shadow_edu",
            "self_study_mediated": "self_study",
            "direct": "student",
        }
        return mapping.get(channel or "", "student")

    def _build_role_hypotheses(self, top: List[Dict],
                               effect_sizes: List[Dict]) -> List[Dict]:
        """FR-R6: generate teacher / parent / scene differentiated hypotheses.

        All effect magnitudes are anchored on the provided virtual effect sizes
        (never fabricated); each hypothesis is tagged with role + scene.
        """
        role_hypotheses: List[Dict] = []
        if not top:
            return role_hypotheses
        
        es_by_id = {es.get("intervention_id"): es for es in effect_sizes}
        anchor = top[0]
        anchor_id = anchor["intervention_id"]
        anchor_g = float(es_by_id.get(anchor_id, {}).get(
            "hedges_g", anchor.get("breakdown", {}).get("effect_size", 0)))
        base_id = len(top) + 1
        
        # Teacher-role hypothesis (T-Model)
        role_hypotheses.append({
            "id": f"H{base_id}",
            "statement": (
                f"自主支持型教师（T-Model 高保真度）传递的「{anchor_id}」干预，"
                f"能够抵消学生叛逆期（D14）的动机低谷，其虚拟效应量不低于"
                f" g = {anchor_g:.3f}。"
            ),
            "predicted_effect": anchor_g,
            "intervention_id": anchor_id,
            "role": "teacher",
            "scene": "school",
            "falsifiable": True,
        })
        # Parent-role hypothesis (P-Model)
        role_hypotheses.append({
            "id": f"H{base_id + 1}",
            "statement": (
                f"在控制型家长子群中，将家长参与方式（P-Model）调整为自主支持型后，"
                f"「{anchor_id}」干预的家庭场景效应量将显著高于维持控制型时（虚拟模拟）。"
            ),
            "predicted_effect": anchor_g,
            "intervention_id": anchor_id,
            "role": "parent",
            "scene": "home",
            "falsifiable": True,
        })
        # Scene-comparison hypothesis
        role_hypotheses.append({
            "id": f"H{base_id + 2}",
            "statement": (
                f"同一干预「{anchor_id}」在学校场景与自学场景下的虚拟效应量存在显著差异，"
                f"学校场景因教师中介而效应量更高（场景×干预交互项）。"
            ),
            "predicted_effect": anchor_g,
            "intervention_id": anchor_id,
            "role": "scene_comparison",
            "scene": "school_vs_self_study",
            "falsifiable": True,
        })
        return role_hypotheses
    
    def _build_sections(self, top, effect_sizes, gap_records, n_students) -> Dict[str, str]:
        """Fill each plan section with grounded content."""
        top_names = ", ".join(r["intervention_id"] for r in top) or "（无候选干预）"
        n_distorted = sum(1 for g in gap_records if g.get("distortion_category") != "none")
        
        # Power analysis approximation: detect g=0.3 with 80% power needs ~175/group
        min_g = min((es.get("hedges_g", 0.3) for es in effect_sizes), default=0.3)
        per_group = max(50, int(175 * (0.3 / max(abs(min_g), 0.05)) ** 2))
        
        return {
            "研究背景": (
                f"基于虚拟学生试验台的多主体模拟，我们对 {len(effect_sizes)} 个干预×场景组合"
                f"进行了反事实效应估计，筛选出优先级最高的干预：{top_names}。"
            ),
            "研究假设": "见 hypotheses 字段（每条均可证伪，效应量来自虚拟模拟）。",
            "实验设计": (
                f"采用随机对照试验（RCT），将学生随机分配至干预组与对照组，"
                f"干预周期 8-12 周，前后测设计。"
            ),
            "样本与功效": (
                f"计划招募 {n_students} 名学生。按最小虚拟效应量 g={min_g:.2f}、"
                f"统计功效 80%、alpha=0.05 估算，每组约需 {per_group} 人。"
            ),
            "测量指标": (
                "主要结局：学业成就标准化测试；次要结局：学习动机、自我效能、"
                "疲劳与压力水平（均来自 L-Model 状态曲线对应量表）。"
            ),
            "统计分析计划": (
                "主分析采用协方差分析（ANCOVA）控制基线，报告 Hedges' g 及 95% CI；"
                "亚组分析按性别/年级/家庭结构分层，警惕高失真子群（见差距分析）。"
            ),
            "伦理与风险": (
                f"差距分析发现 {n_distorted} 个指标存在模拟失真，相关结论需在真实试验中"
                "谨慎验证；所有学生数据经 PrivacyGuard P/R/S 分级保护。"
            ),
            "预期贡献": (
                "为教育干预提供低成本、可扩展的虚拟预筛证据，减少无效干预进入"
                "真实试验的比例，节约研究经费与伦理成本。"
            ),
        }
    
    def _build_references(self, top, effect_sizes) -> List[Dict]:
        """
        References = the virtual evidence itself (NO fabricated citations).
        """
        refs = []
        es_by_id = {es.get("intervention_id"): es for es in effect_sizes}
        for r in top:
            intv_id = r["intervention_id"]
            es = es_by_id.get(intv_id, {})
            refs.append({
                "type": "virtual_experiment",
                "intervention_id": intv_id,
                "hedges_g": es.get("hedges_g"),
                "ci_95": [es.get("ci_lower"), es.get("ci_upper")],
                "note": "虚拟模拟效应量（非真实文献）",
            })
        return refs
    
    def _llm_polish(self, plan: Dict) -> str:
        """Optional LLM narrative summary (offline-safe)."""
        summary = (
            f"本研究计划基于虚拟模拟筛选出 {len(plan['hypotheses'])} 个待验证假设，"
            f"对应 {len(plan['references'])} 项虚拟证据。所有数值均来自模拟结果，"
            f"未引用任何未经核实的外部文献。"
        )
        if self.llm.is_live:
            try:
                prompt = (
                    "请为以下研究计划撰写一段 150 字以内的摘要（不得编造数字或文献）：\n"
                    + str(plan["sections"].get("研究背景", ""))
                )
                return self.llm.call(prompt, temperature=0.5, max_tokens=300)
            except Exception:
                return summary
        return summary


def build_report(run_summary, calibration, effect_sizes, gap_records, ranked) -> Dict:
    """Convenience wrapper for M7 report building."""
    return ReportWriter().build_report(run_summary, calibration, effect_sizes,
                                       gap_records, ranked)


def generate_research_plan(ranked, effect_sizes, gap_records, n_students=500) -> Dict:
    """Convenience wrapper for M8 hypothesis/research-plan generation."""
    return HypothesisGenerator().generate(ranked, effect_sizes, gap_records, n_students)
