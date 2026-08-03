"""
Teacher and Parent Generators
T-Model and P-Model parameter generation with LLM narrative (optional)
"""
from typing import Dict, List, Tuple, Optional
import json
import time
import numpy as np
from datetime import datetime

from ..llm import get_client
from .family_background import (
    sample_education, sample_occupation, EDUCATION_SUPPORT_BASE,
)


def _llm_narrative(prompt: str, temperature: float = 0.7,
                   max_tokens: int = 300) -> Optional[str]:
    """Generate a short narrative via the real Qwen model when available.

    Returns None when offline (no API key configured in the frontend settings
    page) so persona generation stays deterministic and network-free for
    demos/tests. When live, the teacher/parent persona gains an LLM-authored
    narrative field, extending the v5.0 "LLM 深度参与画像生成" beyond students
    (C1 比赛硬性).
    """
    client = get_client()
    if not client.is_live:
        return None
    try:
        text = client.call(prompt, temperature=temperature, max_tokens=max_tokens)
        return (text or "").strip() or None
    except Exception:
        return None


class TeacherGenerator:
    """
    Teacher persona generation (T-Model)
    
    Key parameters:
    - fidelity: How well does teacher implement interventions? (0-1)
    - style_match: Style compatibility with student (0-1)
    - experience_curve: Experience level decay curve
    - teaching_style: Specific teaching approach
    """
    
    @staticmethod
    def generate_teacher(teacher_id: str, experience_years: int = 10, 
                        seed: int = None) -> Dict:
        """
        Generate a teacher persona
        
        Args:
            teacher_id: Unique teacher ID
            experience_years: Years of teaching experience
            seed: For reproducibility
            
        Returns:
            Teacher archive dict
        """
        if seed is not None:
            np.random.seed(seed)
        
        # Core T-Model parameters
        fidelity = min(1.0, 0.5 + experience_years * 0.03 + np.random.normal(0, 0.15))
        fidelity = float(np.clip(fidelity, 0.3, 0.95))
        
        # Teaching style distribution (样本内的风格)
        style_types = ["自主支持型", "控制型", "放任型", "均衡型"]
        style = np.random.choice(style_types)
        
        # Subject area
        subject = np.random.choice(["数学", "英语", "语文", "物理", "化学"])
        
        # Experience-based competency
        experience_level = min(1.0, experience_years / 20)
        
        teacher_archive = {
            "teacher_id": teacher_id,
            "name": f"教师_{teacher_id}",
            "subject": subject,
            "experience_years": experience_years,
            
            # T-Model parameters (simulation_vector)
            "simulation_vector": {
                "fidelity": fidelity,
                "style_match_base": 0.5 + np.random.normal(0, 0.2),  # Varies by student
                "experience_level": float(experience_level),
                "fatigue_susceptibility": np.random.uniform(0.1, 0.5),
                "motivational_quality": np.random.uniform(0.4, 0.9),
                "error_detection_rate": 0.7 + 0.2 * experience_level
            },
            
            # Narrative fields (optional, for demo)
            "teaching_style": style,
            "classroom_management": ["结构化", "温暖", "严谨", "灵活"][
                np.random.randint(0, 4)
            ],
            
            "created_at": int(time.time() * 1000)
        }
        
        # LLM narrative enrichment (only when a real Qwen backend is available)
        philosophy = _llm_narrative(
            f"用一句话描述一位{subject}教师（教龄{experience_years}年，"
            f"教学风格{style}）的教学理念，避免套话。"
        )
        if philosophy:
            teacher_archive["teaching_philosophy"] = philosophy
            teacher_archive["llm_generated_fields"] = {"teaching_philosophy": True}
        
        return teacher_archive
    
    @staticmethod
    def generate_batch(n: int, start_id: str = "T", base_seed: int = 42) -> List[Dict]:
        """Generate batch of teachers"""
        teachers = []
        for i in range(n):
            teacher_id = f"{start_id}{i+1:04d}"
            experience = np.random.randint(1, 30)
            teacher = TeacherGenerator.generate_teacher(
                teacher_id, 
                experience_years=experience,
                seed=base_seed + i
            )
            teachers.append(teacher)
        return teachers


class ParentGenerator:
    """
    Parent persona generation (P-Model)
    
    Key parameters:
    - parenting_style: Autonomy support vs Control vs Indulgence
    - involvement_level: How involved in child's learning (0-1)
    - expectations_pressure: Realistic vs Unrealistic expectations
    - educational_background: Parent education level
    """
    
    # Parenting style effects on learning (documented in literature)
    PARENTING_STYLE_EFFECTS = {
        "自主支持型": {"multiplier": 0.2, "description": "鼓励独立思考，支持自主选择"},
        "内容讲解型": {"multiplier": 0.05, "description": "主要提供学习辅导和讲解"},
        "控制监督型": {"multiplier": -0.05, "description": "严格要求和监督，可能产生压力"},
        "代劳型": {"multiplier": -0.1, "description": "过度帮助，阻碍独立能力发展"},
    }
    
    @staticmethod
    def generate_parent(parent_id: str, student_id: str, ses_level: str = "中等",
                       seed: int = None, family_info: Optional[Dict] = None) -> Dict:
        """
        Generate a parent persona
        
        Args:
            parent_id: Parent ID
            student_id: Associated student ID
            ses_level: Socioeconomic status ("低", "中等", "高")
            seed: For reproducibility
            family_info: Optional D2 family-background fields (统一口径). When
                provided (e.g. ``family_info_from_archive(student["domains"])``),
                the parent's education / occupation are linked to the student's
                own D2 father/mother fields by ``relation`` so the parent persona
                and the student archive can never disagree.
        """
        if seed is not None:
            np.random.seed(seed)
        
        # When linked to a student archive, the archive's SES wins so involvement
        # and the fallback distributions stay consistent with D2.
        if family_info and family_info.get("ses_level"):
            ses_level = family_info["ses_level"]
        
        # Parenting style distribution
        style_choice = np.random.choice(list(ParentGenerator.PARENTING_STYLE_EFFECTS.keys()))
        style_effect = ParentGenerator.PARENTING_STYLE_EFFECTS[style_choice]
        
        relation = np.random.choice(["父亲", "母亲"])
        
        # Involvement level correlated with family SES.
        if ses_level == "高":
            involvement = np.random.uniform(0.6, 0.95)
        elif ses_level == "中等":
            involvement = np.random.uniform(0.3, 0.7)
        else:
            involvement = np.random.uniform(0.1, 0.5)
        
        # Education / occupation: linked to the student's D2 fields by relation
        # (统一口径) when available; otherwise fall back to the shared SES
        # distributions so standalone generation still uses one 口径.
        if family_info and relation == "父亲":
            education = family_info.get("father_education")
            occupation = family_info.get("father_occupation")
        elif family_info and relation == "母亲":
            education = family_info.get("mother_education")
            occupation = family_info.get("mother_occupation")
        else:
            education, occupation = None, None
        if not education:
            education = sample_education(ses_level, np.random)
        if not occupation:
            occupation = sample_occupation(ses_level, np.random)
        
        # Expectations (can be realistic or unrealistic)
        expectations_level = np.random.uniform(0.3, 1.0)
        
        # Profile fields surfaced by the 家长档案 UI (FR-F7). Each is derived from
        # the P-Model parameters above so the displayed data is coherent rather
        # than independent noise: better-educated / more-involved parents give
        # more homework support and daily interaction; warmth tracks style.
        homework_support = float(np.clip(
            EDUCATION_SUPPORT_BASE.get(education, 0.4) * 0.55 + involvement * 0.45
            + np.random.normal(0, 0.08), 0.0, 1.0))
        daily_interaction_hours = float(np.clip(
            0.5 + involvement * 3.0 + np.random.normal(0, 0.4), 0.2, 5.0))
        style_warmth = {"自主支持型": 0.80, "内容讲解型": 0.65,
                        "控制监督型": 0.50, "代劳型": 0.60}
        emotional_warmth = float(np.clip(
            style_warmth.get(style_choice, 0.6) + np.random.normal(0, 0.12),
            0.1, 1.0))
        style_monitoring = {"自主支持型": 0.50, "内容讲解型": 0.60,
                            "控制监督型": 0.85, "代劳型": 0.70}
        monitoring = float(np.clip(
            style_monitoring.get(style_choice, 0.5) + np.random.normal(0, 0.10),
            0.0, 1.0))
        educational_quality = float(np.random.uniform(0.3, 0.9))
        support_quality = float(np.clip(
            educational_quality * 0.5 + homework_support * 0.5
            + np.random.normal(0, 0.08), 0.0, 1.0))
        
        parent_archive = {
            "parent_id": parent_id,
            "student_id": student_id,
            "relation": relation,
            "education_level": education,
            "occupation_category": occupation,
            "daily_interaction_hours": round(daily_interaction_hours, 1),
            "homework_support_level": round(homework_support, 3),
            "emotional_warmth": round(emotional_warmth, 3),
            
            # P-Model parameters (simulation_vector)
            "simulation_vector": {
                "parenting_style": style_choice,
                "parenting_effect_multiplier": float(style_effect["multiplier"]),
                "involvement_level": float(involvement),
                "expectations_pressure": float(expectations_level),
                "educational_quality": educational_quality,
                "consistency": float(np.random.uniform(0.4, 0.9)),
                # Display fields consumed by the 家长档案 page (FR-F7).
                "support_quality": round(support_quality, 3),
                "monitoring": round(monitoring, 3),
                "expectation_level": round(float(expectations_level), 3)
            },
            
            # Narrative fields
            "parenting_description": style_effect["description"],
            "family_expectations": "高期望" if expectations_level > 0.7 else "适度期望",
            "tutoring_investment": f"{int(involvement * 100)}% 参与程度",
            
            "created_at": int(time.time() * 1000)
        }
        
        # LLM narrative enrichment (only when a real Qwen backend is available)
        narrative = _llm_narrative(
            f"用一句话描述一位{parent_archive['relation']}（学历{education}，"
            f"教养方式{style_choice}）的家庭教育观念，避免套话。"
        )
        if narrative:
            parent_archive["parenting_narrative"] = narrative
            parent_archive["llm_generated_fields"] = {"parenting_narrative": True}
        
        return parent_archive
    
    @staticmethod
    def generate_batch_for_students(n_parents: int, n_students: int,
                                   start_id: str = "P", base_seed: int = 42) -> List[Dict]:
        """
        Generate parents for students (each student gets 1-2 parents)
        
        Args:
            n_parents: Total parents to generate
            n_students: Number of students to associate with
            
        Returns:
            List of parent archives
        """
        rng = np.random.RandomState(base_seed)

        # How many parents each student gets: mostly 2, a few 1 (single-parent
        # families). A dedicated RandomState drives these batch-level decisions
        # so the output is reproducible and independent of the per-parent
        # reseeding that generate_parent performs internally.
        counts = [2 if rng.random() > 0.15 else 1 for _ in range(n_students)]

        # Reconcile with the requested total so exactly n_parents are returned
        # whenever n_students <= n_parents <= 2 * n_students.
        total = sum(counts)
        grow = 0
        while total < n_parents and grow < 2 * n_students:
            idx = grow % n_students
            if counts[idx] < 2:
                counts[idx] += 1
                total += 1
            grow += 1
        shrink = n_students - 1
        while total > n_parents and shrink >= 0:
            if counts[shrink] > 1:
                counts[shrink] -= 1
                total -= 1
            shrink -= 1

        parents = []
        parent_count = 0
        for student_idx in range(n_students):
            for _ in range(counts[student_idx]):
                if parent_count >= n_parents:
                    break
                parent_id = f"{start_id}{parent_count+1:04d}"
                student_id = f"S{student_idx+1:04d}"
                ses_level = rng.choice(["低", "中等", "高"])
                parent = ParentGenerator.generate_parent(
                    parent_id,
                    student_id,
                    ses_level=ses_level,
                    seed=base_seed + parent_count
                )
                parents.append(parent)
                parent_count += 1

        return parents[:n_parents]


class CoherenceValidator:
    """
    Validate coherence across student-teacher-parent relationships
    """
    
    @staticmethod
    def validate(students: List[Dict], teachers: List[Dict], 
                 parents: List[Dict]) -> Dict[str, int]:
        """
        Check data integrity
        """
        issues = {
            "orphaned_students": 0,
            "orphaned_parents": 0,
            "orphaned_teachers": 0,
            "duplicate_ids": 0
        }
        
        student_ids = set(s["student_id"] for s in students)
        parent_student_ids = set(p["student_id"] for p in parents)
        
        # Find orphaned students (no parents)
        issues["orphaned_students"] = len(student_ids - parent_student_ids)
        
        # Find orphaned parents (no students)
        issues["orphaned_parents"] = len(parent_student_ids - student_ids)
        
        return issues


if __name__ == "__main__":
    # Test
    teachers = TeacherGenerator.generate_batch(5, start_id="T")
    parents = ParentGenerator.generate_batch_for_students(10, 5, start_id="P")
    
    print(f"Generated {len(teachers)} teachers")
    print(f"Generated {len(parents)} parents")
    
    for t in teachers[:3]:
        print(f"  - {t['teacher_id']}: {t['subject']} (fidelity={t['simulation_vector']['fidelity']:.2f})")
