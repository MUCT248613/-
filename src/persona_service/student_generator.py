"""
Student Generator - Complete 4-Layer Pipeline
L1 → L2 → L3 → L4 → Final Student Archive with Uniqueness Guarantee

Reference: 档案设计文档 §1.4
"""
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import asdict
import json
import time
from datetime import datetime, timedelta

from persona_service import UniquenessGuarantor
from persona_service.identity_seed import (
    IdentitySeedGenerator, Layer1SkeletonGenerator, IdentitySeed
)
from persona_service.layers_3_4 import Layer3DerivationEngine, Layer4CoherenceEngine


class StudentGenerator:
    """
    Complete student generation pipeline
    
    四层管线：
    L1: 随机骨架采样 (deterministic, from posterior)
    L2: LLM 身份种子 (creative, high temp)
    L3: 规则派生 + LLM 叙事 (hybrid)
    L4: 指纹校验去重 (deterministic)
    """
    
    def __init__(self, posterior_dist: Dict = None, llm_func: Callable = None):
        """
        Args:
            posterior_dist: Calibrated BKT posterior distribution
            llm_func: Function to call LLM (mock-able for testing)
        """
        self.posterior_dist = posterior_dist or {
            "p_know": {"mu": 0.3, "sigma": 0.15},
            "p_learn": {"mu": 0.25, "sigma": 0.08}
        }
        self.llm_func = llm_func or self._mock_llm
        self.uniqueness_guarantor = UniquenessGuarantor()
    
    def _mock_llm(self, prompt: str, temperature: float = 0.9) -> str:
        """Mock LLM for testing (returns dummy JSON)"""
        # Simulate LLM response with dummy identity seeds
        return json.dumps({
            "name": "张明宇",
            "birth_place": "浙江省金华市武义县",
            "family_structure_type": "完整家庭",
            "core_personality_seed": "内向但执着，擅长独立思考",
            "unique_life_seed": "八岁时因为一次数学竞赛获奖经历，产生了对数学的热情，成为学习的主要驱动力。"
        })
    
    def generate_student(self, student_id: str, seed: int = None) -> Tuple[Dict, str]:
        """
        Generate a single student through 4-layer pipeline
        
        Args:
            student_id: Unique ID for this student
            seed: Random seed for reproducibility
            
        Returns:
            (student_archive_dict, status_message)
        """
        import numpy as np
        if seed is not None:
            np.random.seed(seed)
        
        # Layer 1: Sample skeleton from posterior
        skeleton = Layer1SkeletonGenerator.sample_skeleton(self.posterior_dist)
        
        # Layer 2: LLM generate identity seed
        identity_seed_prompt = IdentitySeedGenerator.get_identity_seed_prompt(
            skeleton, batch_size=1
        )
        llm_response = self.llm_func(identity_seed_prompt, temperature=1.0)
        identity_seeds = IdentitySeedGenerator.parse_llm_output(llm_response)
        
        if not identity_seeds:
            return None, "llm_parse_failed"
        
        identity_seed = identity_seeds[0]
        
        # Layer 3: Derive numerical fields + LLM narrative
        numerical_fields = Layer3DerivationEngine.derive_numerical_fields(
            skeleton, asdict(identity_seed)
        )
        
        narrative_prompt = Layer3DerivationEngine.get_narrative_continuation_prompt(
            asdict(identity_seed), numerical_fields
        )
        narrative_response = self.llm_func(narrative_prompt, temperature=0.7)
        narrative_fields = Layer3DerivationEngine.parse_narrative_output(narrative_response)
        
        # Assemble student archive
        student_archive = {
            "student_id": student_id,
            "name": identity_seed.name,
            "birth_date": (datetime.now() - timedelta(days=365*14)).isoformat(),
            "birth_place": identity_seed.birth_place,
            "grade": 8,
            "family_structure": identity_seed.family_structure_type,
            "personality_tags": [identity_seed.core_personality_seed],
            "interests": narrative_fields.get("interests", []),
            "achievement_score": numerical_fields["achievement_score"],
            "study_habits_score": numerical_fields["study_habits_score"],
            "self_efficacy": numerical_fields["self_efficacy"],
            "family_investment_hours_weekly": numerical_fields["family_investment_hours_weekly"],
            "motivation_level": numerical_fields["motivation_level"],
            "time_allocation": narrative_fields.get("time_allocation", {
                "school": 0.45, "homework": 0.20, "self_study": 0.10, "recreation": 0.25
            }),
            "key_life_event": narrative_fields.get("key_life_event", ""),
            "teacher_interaction": narrative_fields.get("teacher_interaction_style", ""),
            
            # Simulation vector (for cognitive engine)
            "simulation_vector": {
                "p_know": skeleton["p_know"],
                "p_learn": skeleton["p_learn"],
                "p_slip": 0.1,
                "p_guess": 0.1,
                "misconception_type": skeleton.get("misconception_type", "代数"),
                "motivation": numerical_fields["motivation_level"],
                "self_efficacy": numerical_fields["self_efficacy"]
            },
            
            # Sensitive fields (S-level)
            "sensitive_data": {
                "health_status": "正常",
                "family_structure_detail": "两亲俱在，无特殊情况",
                "tutoring_cost_yearly": 5000 + int(np.random.normal(0, 2000))
            },
            
            # LLM traceability
            "llm_generated_fields": {
                "name": True,
                "birth_place": True,
                "family_structure_type": True,
                "personality_tags": True,
                "interests": True,
                "key_life_event": True,
                "time_allocation": True
            },
            
            "created_at": int(time.time() * 1000)
        }
        
        # Layer 4: Coherence validation + Uniqueness guarantee
        coherence_checks = Layer4CoherenceEngine.validate_coherence(student_archive)
        student_archive = Layer4CoherenceEngine.repair_inconsistencies(student_archive)
        
        # Uniqueness check (L4)
        unique_student, uniqueness_status = self.uniqueness_guarantor.ensure_unique(
            student_archive,
            regenerator_func=lambda: self.generate_student(student_id, seed)
        )
        
        if uniqueness_status != "unique_accepted":
            return unique_student, f"uniqueness_warning: {uniqueness_status}"
        
        return unique_student, "success"
    
    def generate_batch(self, n: int, start_id: str = "S", base_seed: int = 42) -> List[Dict]:
        """
        Generate batch of students
        
        Args:
            n: Number of students
            start_id: ID prefix (e.g., "S001", "S002", ...)
            base_seed: Random seed for reproducibility
            
        Returns:
            List of student archives
        """
        import numpy as np
        students = []
        
        for i in range(n):
            student_id = f"{start_id}{i+1:04d}"
            seed = base_seed + i
            
            student, status = self.generate_student(student_id, seed)
            if student:
                students.append(student)
                if (i + 1) % 10 == 0:
                    print(f"Generated {i+1}/{n} students...")
            else:
                print(f"Failed to generate {student_id}: {status}")
        
        return students


if __name__ == "__main__":
    # Test: Generate 5 sample students
    generator = StudentGenerator()
    students = generator.generate_batch(5, start_id="DEMO")
    
    print(f"\nGenerated {len(students)} students:")
    for s in students:
        print(f"  - {s['student_id']}: {s['name']} (成绩: {s['achievement_score']:.1f})")
    
    # Save to JSON for inspection
    with open("sample_students.json", "w", encoding="utf-8") as f:
        json.dump(students, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to sample_students.json")
