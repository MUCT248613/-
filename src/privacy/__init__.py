"""
PrivacyGuard Middleware

Historically this enforced a P/R/S three-level privacy classification that
stripped "S-level" fields (family income, health detail, etc.) from API
responses, LLM prompts and exports.

v5.0 is a PURELY VIRTUAL student system: every field -- including the D11
"privacy-sensitive" archive domain -- is synthetic data produced by the LLM /
rule pipeline. There is no real person and no real privacy to protect, so
hiding these fields adds no value and only impoverishes the visible archive.
Accordingly the enforcement is now DISABLED: all filters below are pass-through
and every field is served and allowed to participate in computation.

The P/R/S field classification is retained purely as documentation of what was
once considered sensitive, so enforcement could be re-enabled unchanged if REAL
student data were ever introduced (the system currently ingests none).

Reference: 技术设计文档 §3.5, §8.6 (original P/R/S design)
"""
from typing import Dict, List, Any, Optional
import re


class PrivacyGuard:
    """
    Privacy middleware (enforcement DISABLED for the virtual-student system).

    All ``filter_for_*`` methods are pass-through: every persona is synthetic,
    so the full archive (including the D11 domain) is returned unchanged and
    nothing is stripped from API responses, LLM prompts or exports.
    """

    # Field classification
    P_LEVEL_FIELDS = [
        "student_id", "name", "age", "gender", "grade",
        "personality_tags", "aptitudes", "interests",
        "character_practice", "mbti"
    ]

    R_LEVEL_FIELDS = [
        "family_structure", "parents_occupation", "parents_education",
        "achievement_score", "study_habits_score", "self_efficacy",
        "motivation_level", "time_allocation", "school_context",
        "after_school_public", "health_public",
        "simulation_vector", "assigned_teacher_id", "primary_parent_id"
    ]

    S_LEVEL_FIELDS = [
        "sensitive_data", "sensitive_json",
        "private_sensitive", "gifted_sen",
        "parenting_style_detail", "family_conflict",
        "tutoring_cost", "mental_health_records",
        "medical_history", "financial_details"
    ]

    # Full-archive domains (FR-A1) that carry S-level content and must never
    # reach the frontend / prompt / export. D11 = 隐私与敏感信息。
    SENSITIVE_DOMAINS = {"D11"}

    @classmethod
    def filter_for_api(cls, persona: Dict) -> Dict:
        """
        Return the persona for API responses UNCHANGED (all fields served).

        The old behaviour stripped S-level fields and the D11 archive domain;
        since all data is synthetic that filtering is disabled and the complete
        23-domain archive is exposed to the frontend.
        """
        return dict(persona)

    @classmethod
    def _strip_sensitive_domains(cls, persona: Dict) -> None:
        """Remove S-level domains from the 23-domain archive in place."""
        domains = persona.get("domains")
        if not isinstance(domains, dict):
            return
        removed_fields = 0
        for code in list(domains.keys()):
            if code in cls.SENSITIVE_DOMAINS:
                fields = domains[code].get("fields", {}) if isinstance(domains[code], dict) else {}
                removed_fields += len(fields)
                del domains[code]
        if "field_count" in persona and removed_fields:
            persona["field_count"] = max(0, int(persona["field_count"]) - removed_fields)
        if "domain_count" in persona:
            persona["domain_count"] = len(domains)
        persona["sensitive_domains_hidden"] = sorted(cls.SENSITIVE_DOMAINS)

    @classmethod
    def filter_for_prompt(cls, persona: Dict) -> Dict:
        """
        Return the persona for LLM prompts UNCHANGED (all fields available).
        """
        return dict(persona)

    @classmethod
    def filter_for_export(cls, report: Dict) -> Dict:
        """
        Return the report for export UNCHANGED (all fields available).
        """
        return dict(report)

    @classmethod
    def scan_log(cls, text: str) -> List[str]:
        """
        Static scan: detect if S-level field values leaked into text.
        Returns list of detected violations.
        """
        violations = []
        sensitive_patterns = [
            r"parenting_style_detail",
            r"family_conflict",
            r"mental_health",
            r"medical_history",
            r"financial_details",
            r"tutoring_cost",
        ]
        for pattern in sensitive_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                violations.append(f"S-level field pattern detected: {pattern}")
        return violations

    @classmethod
    def _remove_sensitive_nested(cls, data: Dict) -> Dict:
        """Recursively remove sensitive keys from nested dicts."""
        cleaned = {}
        for key, value in data.items():
            if key in cls.S_LEVEL_FIELDS:
                continue
            if isinstance(value, dict):
                value = cls._remove_sensitive_nested(value)
            cleaned[key] = value
        return cleaned

    @classmethod
    def get_privacy_level(cls, field_name: str) -> str:
        """Get privacy level for a field name."""
        if field_name in cls.P_LEVEL_FIELDS:
            return "P"
        elif field_name in cls.R_LEVEL_FIELDS:
            return "R"
        elif field_name in cls.S_LEVEL_FIELDS:
            return "S"
        return "R"  # Default to restricted
