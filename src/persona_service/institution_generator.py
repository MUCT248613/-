"""
VirtualStudent Sandbox v6.0 - Institution Generator

Implements §5 M2 generate_institutions() (v6.0 baseline) and the `institutions`
table (§6).

Institution types: school / class / shadow_edu_provider.
Each institution carries an I1-I2 profile:
  - I1 机构特色 (institution character): type, resources, culture
  - I2 氛围/风格 (climate/style): teaching climate, management style

Like other personas, institutions get an LLM-generated "特色签名"
(character signature) plus an identity_fingerprint for uniqueness.

Reference: 技术设计文档 §5 M2, §6 institutions table, C-20
"""
from typing import Dict, List, Optional, Tuple

import hashlib
import json
import numpy as np

from . import UniquenessGuarantor


class InstitutionGenerator:
    """
    Generate institution personas (schools, classes, shadow-edu providers).
    """
    
    INSTITUTION_TYPES = ["school", "class", "shadow_edu_provider"]
    
    SCHOOL_CULTURES = ["学术导向", "全面发展", "纪律严明", "宽松自由", "艺体特色"]
    SHADOW_STYLES = ["应试强化型", "兴趣拓展型", "一对一辅导", "小班精品", "线上远程"]
    CLASS_CLIMATES = ["高凝聚高竞争", "高凝聚低竞争", "低凝聚高竞争", "均衡发展型"]
    
    def __init__(self, llm_func=None):
        self.llm_func = llm_func
        self.uniqueness_guarantor = UniquenessGuarantor()
    
    def generate_institution(self, institution_id: str,
                             institution_type: str = "school",
                             seed: int = None) -> Tuple[Dict, str]:
        """
        Generate a single institution persona.
        
        Args:
            institution_id: Unique ID
            institution_type: school / class / shadow_edu_provider
            seed: For reproducibility
        
        Returns:
            (institution_archive, status)
        """
        if institution_type not in self.INSTITUTION_TYPES:
            return {}, f"invalid_type:{institution_type}"
        
        if seed is not None:
            np.random.seed(seed)
        
        # I1: institution character
        if institution_type == "school":
            profile = self._school_profile()
        elif institution_type == "class":
            profile = self._class_profile()
        else:
            profile = self._shadow_profile()
        
        # L2: LLM character signature (with deterministic fallback)
        signature = self._generate_signature(institution_id, institution_type, profile)
        
        archive = {
            "institution_id": institution_id,
            "type": institution_type,
            "archive_json": profile,
            "character_signature": signature,
            "identity_fingerprint": self._fingerprint(institution_id, institution_type, profile),
            "llm_generated_fields": {"character_signature": self.llm_func is not None},
            "seed": seed,
        }
        
        return archive, "ok"
    
    def generate_institutions(self, n: int, institution_type: str = "school",
                              seed: int = 42) -> List[Dict]:
        """Generate a batch of institutions."""
        institutions = []
        for i in range(n):
            inst_id = f"{institution_type[:3].upper()}_{i:04d}"
            archive, status = self.generate_institution(
                inst_id, institution_type, seed=seed + i)
            if status == "ok":
                institutions.append(archive)
        return institutions
    
    def _school_profile(self) -> Dict:
        """I1/I2 profile for a school."""
        return {
            "school_type": np.random.choice(["公办重点", "公办普通", "民办", "乡镇中学"]),
            "culture": np.random.choice(self.SCHOOL_CULTURES),
            "resource_level": float(np.clip(np.random.beta(5, 2), 0.1, 1.0)),
            "student_teacher_ratio": int(np.random.randint(10, 45)),
            "academic_pressure": float(np.clip(np.random.beta(3, 3), 0, 1)),
        }
    
    def _class_profile(self) -> Dict:
        """I1/I2 profile for a class."""
        return {
            "climate": np.random.choice(self.CLASS_CLIMATES),
            "cohesion": float(np.clip(np.random.beta(4, 2), 0, 1)),
            "competition_level": float(np.clip(np.random.beta(2, 2), 0, 1)),
            "peer_support": float(np.clip(np.random.beta(4, 3), 0, 1)),
            "student_count": int(np.random.randint(25, 55)),
        }
    
    def _shadow_profile(self) -> Dict:
        """I1/I2 profile for a shadow-education provider."""
        return {
            "style": np.random.choice(self.SHADOW_STYLES),
            "quality": float(np.clip(np.random.beta(4, 2), 0.1, 1.0)),
            "hourly_cost_yuan": float(np.random.randint(50, 500)),
            "focus": np.random.choice(["提分", "竞赛", "兴趣", "补差"]),
            "teacher_quality": float(np.clip(np.random.beta(4, 2), 0.1, 1.0)),
        }
    
    def _generate_signature(self, institution_id: str,
                            institution_type: str, profile: Dict) -> str:
        """LLM-generated character signature with deterministic fallback."""
        if self.llm_func is not None:
            try:
                prompt = (
                    f"为以下{institution_type}生成一句独特的机构特色签名（30字内）：\n"
                    f"{json.dumps(profile, ensure_ascii=False)}"
                )
                result = self.llm_func(prompt, 0.8)
                if result and not result.startswith("[MOCK_LLM"):
                    return result.strip()[:60]
            except Exception:
                pass
        
        # Deterministic fallback signature
        h = int(hashlib.md5(institution_id.encode()).hexdigest()[:8], 16)
        traits = ["历史悠久", "锐意进取", "以人为本", "追求卓越", "兼容并包", "务实创新"]
        return f"{traits[h % len(traits)]}的{institution_type}#{h % 997}"
    
    def _fingerprint(self, institution_id: str, institution_type: str,
                     profile: Dict) -> str:
        """Identity fingerprint for uniqueness guarantee."""
        canonical = json.dumps(
            {"id": institution_id, "type": institution_type, **profile},
            sort_keys=True, ensure_ascii=False, default=str,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]
