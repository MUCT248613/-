"""
PrivacyGuard Middleware

Enforces the P/R/S three-level privacy classification required by FR-A8 (P0):
S-level fields and the D11 (隐私与敏感信息) archive domain are stripped at
the code level from API responses, LLM prompts and exports.

Every persona in this system is synthetic, but enforcement stays ENABLED:
FR-A8 is a P0 acceptance requirement (T-P10), the guard is the single barrier
that keeps real calibration data safe the moment any is ever introduced, and
the platform's responsible-AI design demands it by default.

Reference: 技术设计文档 §3.5, §8.6; 需求说明文档 FR-A8
"""
from typing import Dict, List, Any, Optional
import re


class PrivacyGuard:
    """
    Privacy middleware (FR-A8 enforcement ENABLED).

    All ``filter_for_*`` methods return a sanitized deep copy with S-level
    fields and sensitive archive domains removed; inputs are never mutated.
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
        Return the persona for API responses with S-level content stripped.

        Removes the D11 archive domain and every S-level field (recursively),
        then adjusts domain/field counters so the response stays consistent.
        The input persona is never mutated.
        """
        return cls._sanitize(persona)

    @classmethod
    def _sanitize(cls, data: Dict) -> Dict:
        """Return a deep copy of ``data`` without S-level fields/domains."""
        cleaned = cls._remove_sensitive_nested(dict(data))
        cls._strip_sensitive_domains(cleaned)
        return cleaned

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
        Return the persona for LLM prompts with S-level content stripped
        (FR-A8: S-level fields never enter prompts).
        """
        return cls._sanitize(persona)

    @classmethod
    def filter_for_export(cls, report: Dict) -> Dict:
        """
        Return the export payload with S-level content stripped
        (FR-A8: S-level fields never enter exports).
        """
        return cls._sanitize(report)

    @classmethod
    def scan_log(cls, text: str) -> List[str]:
        """
        Static scan: detect if S-level field values leaked into text.
        Returns list of detected violations.
        """
        violations = []
        # Word-boundary patterns: match the exact S-level field names without
        # false-positives on legitimate look-alikes (family_conflict_level,
        # mental_health_index, ...).
        sensitive_patterns = [
            r"\bparenting_style_detail\b",
            r"\bfamily_conflict\b",
            r"\bmental_health_records\b",
            r"\bmedical_history\b",
            r"\bfinancial_details\b",
            r"\btutoring_cost\b",
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
