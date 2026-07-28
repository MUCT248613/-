"""
Teacher and Parent Generators
T-Model and P-Model parameter generation with LLM narrative (optional)
"""
from typing import Dict, List, Tuple
import json
import time
import numpy as np
from datetime import datetime


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
                       seed: int = None) -> Dict:
        """
        Generate a parent persona
        
        Args:
            parent_id: Parent ID
            student_id: Associated student ID
            ses_level: Socioeconomic status ("低", "中等", "高")
            seed: For reproducibility
        """
        if seed is not None:
            np.random.seed(seed)
        
        # Parenting style distribution
        style_choice = np.random.choice(list(ParentGenerator.PARENTING_STYLE_EFFECTS.keys()))
        style_effect = ParentGenerator.PARENTING_STYLE_EFFECTS[style_choice]
        
        # Involvement level (inversely related to SES in some populations)
        if ses_level == "高":
            involvement = np.random.uniform(0.6, 0.95)
            education = np.random.choice(["大专", "本科", "研究生"])
        elif ses_level == "中等":
            involvement = np.random.uniform(0.3, 0.7)
            education = np.random.choice(["高中", "大专", "本科"])
        else:
            involvement = np.random.uniform(0.1, 0.5)
            education = np.random.choice(["初中", "高中"])
        
        # Expectations (can be realistic or unrealistic)
        expectations_level = np.random.uniform(0.3, 1.0)
        
        parent_archive = {
            "parent_id": parent_id,
            "student_id": student_id,
            "relation": np.random.choice(["父亲", "母亲"]),
            "education_level": education,
            
            # P-Model parameters (simulation_vector)
            "simulation_vector": {
                "parenting_style": style_choice,
                "parenting_effect_multiplier": float(style_effect["multiplier"]),
                "involvement_level": float(involvement),
                "expectations_pressure": float(expectations_level),
                "educational_quality": float(np.random.uniform(0.3, 0.9)),
                "consistency": float(np.random.uniform(0.4, 0.9))
            },
            
            # Narrative fields
            "parenting_description": style_effect["description"],
            "family_expectations": "高期望" if expectations_level > 0.7 else "适度期望",
            "tutoring_investment": f"{int(involvement * 100)}% 参与程度",
            
            "created_at": int(time.time() * 1000)
        }
        
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
        parents = []
        parent_count = 0
        
        for student_idx in range(n_students):
            # Most students get 2 parents, some get 1 (single parent family)
            n_for_this_student = 2 if np.random.random() > 0.15 else 1
            
            for parent_idx in range(n_for_this_student):
                if parent_count >= n_parents:
                    break
                
                parent_id = f"{start_id}{parent_count+1:04d}"
                student_id = f"S{student_idx+1:04d}"
                ses_level = np.random.choice(["低", "中等", "高"])
                
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
