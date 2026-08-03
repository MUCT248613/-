"""
VirtualStudent Sandbox v5.0 - Coherence Engine

Implements the persona 一致性引擎 (Coherence Engine) referenced in §5 M2
(pipeline_stages includes validate_repair) and the archive design doc.

Ensures a generated persona is INTERNALLY CONSISTENT — i.e. its fields do
not contradict each other. Examples of incoherence:
  - A "留守家庭" (left-behind) child whose parents_occupation says both
    parents work at home.
  - A student with very low aptitude but recorded as a "竞赛保送" achiever.
  - MBTI "I" (introvert) but core_personality says "极度外向社交达人".

The engine runs a set of rule-based checks, scores overall coherence, and
can auto-repair simple violations (or flag for regeneration).

Reference: 技术设计文档 §5 M2 (coherence_engine.py), C-1
"""
from typing import Dict, List, Tuple, Optional


class CoherenceViolation:
    """A single coherence rule violation."""
    
    def __init__(self, rule: str, severity: str, message: str,
                 fields: List[str]):
        self.rule = rule
        self.severity = severity  # "error" | "warning"
        self.message = message
        self.fields = fields
    
    def to_dict(self) -> Dict:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "fields": self.fields,
        }


class CoherenceEngine:
    """
    Rule-based persona coherence validation and repair.
    """
    
    # Coherence score threshold below which a persona needs regeneration
    MIN_COHERENCE = 0.7
    
    def __init__(self, max_retry: int = 5):
        self.max_retry = max_retry
    
    def validate(self, persona: Dict) -> Tuple[float, List[CoherenceViolation]]:
        """
        Run all coherence checks on a persona.
        
        Returns:
            (coherence_score in [0,1], list of violations)
        """
        violations = []
        violations.extend(self._check_family_structure(persona))
        violations.extend(self._check_aptitude_achievement(persona))
        violations.extend(self._check_personality_mbti(persona))
        violations.extend(self._check_shadow_education(persona))
        violations.extend(self._check_age_grade(persona))
        
        # Score: errors weigh more than warnings
        n_error = sum(1 for v in violations if v.severity == "error")
        n_warning = sum(1 for v in violations if v.severity == "warning")
        score = max(0.0, 1.0 - 0.25 * n_error - 0.08 * n_warning)
        
        return score, violations
    
    def is_coherent(self, persona: Dict) -> bool:
        """Quick check: is this persona above the coherence threshold?"""
        score, _ = self.validate(persona)
        return score >= self.MIN_COHERENCE
    
    def repair(self, persona: Dict) -> Tuple[Dict, List[str]]:
        """
        Attempt to auto-repair simple violations in place.
        
        Returns:
            (repaired_persona, list of repairs applied)
        """
        persona = dict(persona)
        repairs = []
        
        # Repair: left-behind child must not have both parents at home
        if persona.get("family_structure") == "留守":
            occ = persona.get("parents_occupation", "")
            if "在家" in str(occ) and "外出" not in str(occ):
                persona["parents_occupation"] = "父母外出务工，由祖辈照料"
                repairs.append("corrected parents_occupation for 留守家庭")
        
        # Repair: age-grade mismatch -> adjust grade
        age = persona.get("age")
        grade = persona.get("grade")
        if age is not None and grade is not None:
            expected_grade = age - 6
            if abs(grade - expected_grade) > 2:
                persona["grade"] = max(1, expected_grade)
                repairs.append(f"adjusted grade to {persona['grade']} for age {age}")
        
        # Repair: extreme aptitude-achievement contradiction -> soften achievement
        apt = persona.get("aptitude_score", 0.5)
        ach = persona.get("achievement_level", "")
        if isinstance(apt, (int, float)) and apt < 0.3 and "保送" in str(ach):
            persona["achievement_level"] = "中等"
            repairs.append("softened achievement_level to match aptitude")
        
        return persona, repairs
    
    def validate_and_repair(self, persona: Dict) -> Tuple[Dict, Dict]:
        """
        Full validate -> repair -> re-validate cycle.
        
        Returns:
            (final_persona, report dict)
        """
        score_before, violations = self.validate(persona)
        repaired, repairs = self.repair(persona)
        score_after, remaining = self.validate(repaired)
        
        return repaired, {
            "score_before": score_before,
            "score_after": score_after,
            "repairs_applied": repairs,
            "remaining_violations": [v.to_dict() for v in remaining],
            "coherent": score_after >= self.MIN_COHERENCE,
        }
    
    # ============ Individual rule checks ============
    
    def _check_family_structure(self, persona: Dict) -> List[CoherenceViolation]:
        violations = []
        fs = persona.get("family_structure")
        occ = str(persona.get("parents_occupation", ""))
        
        if fs == "留守" and occ and "外出" not in occ and "务工" not in occ \
           and "在家" in occ:
            violations.append(CoherenceViolation(
                rule="family_structure_vs_occupation",
                severity="error",
                message="留守家庭但父母职业显示均在家，存在矛盾",
                fields=["family_structure", "parents_occupation"],
            ))
        
        if fs == "单亲" and "父母双方" in occ:
            violations.append(CoherenceViolation(
                rule="family_structure_vs_occupation",
                severity="warning",
                message="单亲家庭但职业描述提及父母双方",
                fields=["family_structure", "parents_occupation"],
            ))
        return violations
    
    def _check_aptitude_achievement(self, persona: Dict) -> List[CoherenceViolation]:
        violations = []
        apt = persona.get("aptitude_score")
        ach = str(persona.get("achievement_level", ""))
        
        if isinstance(apt, (int, float)) and apt < 0.3 and ("保送" in ach or "顶尖" in ach):
            violations.append(CoherenceViolation(
                rule="aptitude_vs_achievement",
                severity="error",
                message=f"天赋分 {apt:.2f} 偏低但成就描述为 {ach}，矛盾",
                fields=["aptitude_score", "achievement_level"],
            ))
        return violations
    
    def _check_personality_mbti(self, persona: Dict) -> List[CoherenceViolation]:
        violations = []
        mbti = str(persona.get("mbti", ""))
        core = str(persona.get("core_personality", ""))
        
        if mbti.startswith("I") and ("极度外向" in core or "社交达人" in core):
            violations.append(CoherenceViolation(
                rule="mbti_vs_personality",
                severity="warning",
                message=f"MBTI 为内向({mbti})但人格描述极度外向",
                fields=["mbti", "core_personality"],
            ))
        if mbti.startswith("E") and ("极度内向" in core or "回避社交" in core):
            violations.append(CoherenceViolation(
                rule="mbti_vs_personality",
                severity="warning",
                message=f"MBTI 为外向({mbti})但人格描述极度内向",
                fields=["mbti", "core_personality"],
            ))
        return violations
    
    def _check_shadow_education(self, persona: Dict) -> List[CoherenceViolation]:
        violations = []
        hours = persona.get("shadow_education_hours")
        cost = persona.get("tutoring_cost")
        
        if isinstance(hours, (int, float)) and hours > 0 and \
           isinstance(cost, (int, float)) and cost == 0:
            violations.append(CoherenceViolation(
                rule="shadow_edu_hours_vs_cost",
                severity="warning",
                message=f"补习时长 {hours}h 但费用为 0，需核实",
                fields=["shadow_education_hours", "tutoring_cost"],
            ))
        return violations
    
    def _check_age_grade(self, persona: Dict) -> List[CoherenceViolation]:
        violations = []
        age = persona.get("age")
        grade = persona.get("grade")
        
        if age is not None and grade is not None:
            expected = age - 6
            if abs(grade - expected) > 2:
                violations.append(CoherenceViolation(
                    rule="age_vs_grade",
                    severity="error",
                    message=f"年龄 {age} 与年级 {grade} 不匹配（预期约 {expected}）",
                    fields=["age", "grade"],
                ))
        return violations


def check_coherence(persona: Dict) -> Tuple[float, List[Dict]]:
    """Convenience wrapper returning (score, violations as dicts)."""
    score, violations = CoherenceEngine().validate(persona)
    return score, [v.to_dict() for v in violations]
