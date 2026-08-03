"""
Shared family-background distributions -- single source of truth (统一口径).

Both the student archive (D2 家庭与成长背景) and the parent persona (P-Model)
draw parent education / occupation from these SES-conditioned distributions,
and the parent persona is linked back to the student's own D2 fields, so the
two views of the same family can never disagree. This keeps downstream
statistics (家长学历子群切片、家长档案页) consistent with each student's archive.

Reference: 档案设计文档 §2B (D2 / D20), 需求说明文档 FR-F7
"""
from typing import Dict, Optional

import numpy as np  # noqa: F401  (re-exported for callers that sample via rng)

# Canonical parent education tiers (统一口径), lowest -> highest. Explicit
# 硕士/博士 tiers replace the old catch-all "研究生".
EDUCATION_TIERS = ["初中", "高中", "大专", "本科", "硕士", "博士"]

# SES-conditioned education distributions (probabilities sum to 1 per SES).
EDUCATION_BY_SES = {
    "高":   (["大专", "本科", "硕士", "博士"], [0.15, 0.35, 0.32, 0.18]),
    "中等": (["高中", "大专", "本科", "硕士"], [0.30, 0.30, 0.30, 0.10]),
    "低":   (["初中", "高中", "大专"],        [0.45, 0.40, 0.15]),
}

# SES-conditioned occupation categories (gender-neutral; shared by the D2
# father / mother fields and the parent persona so the 口径 stays unified).
OCCUPATION_BY_SES = {
    "高":   ["公务员", "企业管理者", "医生", "高校教师", "工程师", "律师"],
    "中等": ["企业职员", "个体经营者", "技术工人", "中小学教师", "服务业人员"],
    "低":   ["产业工人", "务农", "服务业人员", "自由职业", "无固定职业"],
}

# Homework-support ability implied by each education tier (P-Model derivation).
EDUCATION_SUPPORT_BASE = {"初中": 0.25, "高中": 0.40, "大专": 0.50,
                          "本科": 0.65, "硕士": 0.80, "博士": 0.85}


def sample_education(ses_level: str, rng) -> str:
    """Sample a parent education tier conditioned on family SES.

    ``rng`` may be the global ``np.random`` module or a ``RandomState`` instance
    (both expose ``choice``).
    """
    options, probs = EDUCATION_BY_SES.get(ses_level, EDUCATION_BY_SES["中等"])
    return str(rng.choice(options, p=probs))


def sample_occupation(ses_level: str, rng) -> str:
    """Sample a parent occupation category conditioned on family SES."""
    options = OCCUPATION_BY_SES.get(ses_level, OCCUPATION_BY_SES["中等"])
    return str(rng.choice(options))


def family_info_from_archive(domains: Optional[Dict]) -> Dict:
    """Extract the D2 family-background fields from a student archive so a parent
    persona can be linked to them (统一口径).

    Archive domains are keyed by code (``D2`` = 家庭与成长背景) with a nested
    ``fields`` dict. Returns ses_level + father/mother education & occupation,
    suitable for ``ParentGenerator.generate_parent(family_info=...)``; missing
    fields become None so the generator falls back to SES sampling.
    """
    fam: Dict = {}
    if isinstance(domains, dict):
        d2 = domains.get("D2")
        if isinstance(d2, dict):
            fields = d2.get("fields")
            if isinstance(fields, dict):
                fam = fields
    return {
        "ses_level": str(fam.get("ses_level", "中等")),
        "father_education": fam.get("father_education"),
        "mother_education": fam.get("mother_education"),
        "father_occupation": fam.get("father_occupation"),
        "mother_occupation": fam.get("mother_occupation"),
    }
