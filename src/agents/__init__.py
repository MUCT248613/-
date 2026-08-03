"""
VirtualStudent Sandbox v5.0 - Language Agents

Implements §3.1 agent roles:
  - LanguageAgent: generates student answer text / error explanations.
    CRITICAL guardrail: it NEVER decides correctness — that is determined
    by the CognitiveEngine (BKT). The LLM only renders the already-decided
    outcome as natural language.
  - PersonaView: structured profile injection (§8.2).
    All persona fields are synthetic, so the full profile is available to the
    prompt (no privacy filtering in the virtual-student system).

Teacher/parent language generation (§8.5) is an optional P2 enhancement;
the main pipeline uses deterministic T-Model/P-Model instead.

Reference: 技术设计文档 §3.1, §3.4, §8.2, §8.5, §8.6
"""
from typing import Dict, List, Optional, Any

from ..llm import get_client
from ..privacy import PrivacyGuard


class PersonaView:
    """
    Structured persona injection for LLM prompts (§8.2).

    A curated subset of fields is injected to keep the prompt compact; since
    every field is synthetic there is no privacy filtering (PrivacyGuard is a
    pass-through in the virtual-student system).
    """
    
    # Fields injected into the prompt (kept compact for token budget)
    VIEW_FIELDS = [
        "name", "grade", "mbti", "interests", "self_efficacy",
        "study_habits", "learning_style", "motivation_level",
        "personality_tags", "aptitudes",
    ]
    
    @classmethod
    def build(cls, persona: Dict) -> str:
        """
        Build a compact profile string for prompt injection.
        """
        safe = PrivacyGuard.filter_for_prompt(persona)
        
        parts = []
        for field in cls.VIEW_FIELDS:
            if field in safe and safe[field] is not None:
                parts.append(f"{field}={safe[field]}")
        
        header = "[LEARNER PROFILE]"
        return f"{header}\n" + "; ".join(parts)


class LanguageAgent:
    """
    Generates natural-language renderings of already-decided cognitive
    outcomes. Does NOT determine correctness.
    """
    
    def __init__(self, llm_client=None):
        self.llm = llm_client or get_client()
        self.privacy = PrivacyGuard()
    
    def generate_answer_text(self, persona: Dict, item: Dict,
                             is_correct: bool, p_correct: float) -> str:
        """
        Generate the text of a student's answer.
        
        Args:
            persona: Student persona (will be privacy-filtered)
            item: The question/item dict
            is_correct: ALREADY DECIDED by CognitiveEngine
            p_correct: The model's P(correct) for calibration of wording
        
        Returns:
            Natural-language answer text
        """
        profile = PersonaView.build(persona)
        prompt = (
            f"{profile}\n\n"
            f"题目：{item.get('content', item.get('question', '一道数学题'))}\n"
            f"该学生{'答对' if is_correct else '答错'}了这道题（模型概率 {p_correct:.2f}）。\n"
            f"请以该学生的口吻写出他/她的作答过程（2-3 句）。"
            f"注意：结果已确定，你只需呈现，不得改变对错。"
        )
        
        if self.llm.is_live:
            return self.llm.call(prompt, temperature=0.7, max_tokens=200)
        
        # Deterministic offline rendering
        return self._mock_answer(persona, is_correct, p_correct)
    
    def generate_error_explanation(self, persona: Dict, item: Dict,
                                   error_type: str = "misconception") -> str:
        """
        Generate an explanation of WHY the student made an error
        (post-hoc narrative, not a correctness decision).
        """
        profile = PersonaView.build(persona)
        prompt = (
            f"{profile}\n\n"
            f"题目：{item.get('content', '一道题目')}\n"
            f"错误类型：{error_type}\n"
            f"请解释该学生产生此错误的可能认知原因（1-2 句，基于其画像）。"
        )
        
        if self.llm.is_live:
            return self.llm.call(prompt, temperature=0.6, max_tokens=150)
        
        explanations = {
            "misconception": "对该知识点的核心概念存在误解，将相似规则混淆使用。",
            "careless": "解题过程仓促，在计算环节出现疏忽。",
            "knowledge_gap": "前置知识掌握不牢，导致无法正确推进解题。",
            "fatigue": "因疲劳导致注意力下降，审题不仔细。",
        }
        return explanations.get(error_type, "对该知识点的理解尚不牢固。")
    
    def _mock_answer(self, persona: Dict, is_correct: bool, p_correct: float) -> str:
        """Deterministic offline answer rendering."""
        name = persona.get("name", "该学生")
        if is_correct:
            if p_correct > 0.8:
                return f"{name}快速审题后，熟练地运用公式，几步便得出正确答案。"
            return f"{name}思考了片刻，尝试了一种方法，验证后确认答案正确。"
        else:
            if p_correct < 0.3:
                return f"{name}看着题目有些茫然，尝试套用公式但方向有误，答案不正确。"
            return f"{name}解题到一半发现思路卡住，最终给出的答案有偏差。"


class TeacherLanguageAgent:
    """
    Optional (§8.5 P2): generates teacher classroom explanation text.
    The main pipeline uses the deterministic T-Model; this is an enhancement.
    """
    
    def __init__(self, llm_client=None):
        self.llm = llm_client or get_client()
    
    def generate_explanation(self, teacher: Dict, item: Dict,
                             student_need: str = "concept") -> str:
        """Generate a teacher's explanation adapted to their style."""
        style = teacher.get("teaching_style", "均衡型")
        subject = teacher.get("subject", "数学")
        
        if self.llm.is_live:
            safe = PrivacyGuard.filter_for_prompt(teacher)
            prompt = (
                f"教师风格：{style}，学科：{subject}\n"
                f"请针对学生的'{student_need}'需求，写一段课堂讲解（2-3 句）。"
            )
            return self.llm.call(prompt, temperature=0.7, max_tokens=200)
        
        style_openings = {
            "自主支持型": "大家先自己想想这个问题，我来引导一下思路——",
            "控制型": "注意看，这道题必须按步骤来：",
            "放任型": "这题大家可以自由尝试，我给个参考方向：",
            "均衡型": "我们一起来分析这道题的关键点：",
        }
        opening = style_openings.get(style, style_openings["均衡型"])
        return f"{opening}抓住{subject}的核心概念，问题就能迎刃而解。"


def build_persona_view(persona: Dict) -> str:
    """Convenience wrapper for PersonaView.build()."""
    return PersonaView.build(persona)
