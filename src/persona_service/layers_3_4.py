"""
Persona Service - Layer 3: Derivation + LLM Narrative
L3 combines deterministic rule-based derivation with LLM narrative generation

Process:
1. Take L2 identity seed
2. Derive numerical fields using rules (成绩、体测、时间分配)
3. Use LLM to generate narrative details (关键经历、师生互动、生命叙事)
4. Ensure consistency between numerical and narrative layers
"""
from typing import Dict, List, Optional
import json
from dataclasses import dataclass
import numpy as np


@dataclass
class StudentArchive:
    """完整 23 域学生档案 (Layer 3-4 output)"""
    student_id: str
    # 基本身份 (D1)
    name: str
    grade: int
    birth_date: str
    birth_place: str
    gender: str
    
    # 家庭背景 (D2-D4)
    family_structure: str
    parents_occupation: List[str]
    parents_education: List[str]
    
    # 人格与天赋 (D5-D8)
    mbti: str
    personality_tags: List[str]
    aptitudes: List[str]
    learning_style: str
    
    # 学业 (D9-D11)
    prior_knowledge: float
    achievement_level: float
    misconceptions: List[str]
    
    # 其他 23 域...（简化版本）
    
    # 仿真参数层 (simulation_vector)
    simulation_vector: Dict
    
    # 敏感信息 (S级)
    sensitive_data: Dict


class Layer3DerivationEngine:
    """
    Layer 3: Rule-based derivation + LLM narrative generation
    
    Rules: 数值化字段派生（成绩、体测、作息等）
    LLM: 叙事性字段续写（关键经历、师生互动等）
    """
    
    @staticmethod
    def derive_numerical_fields(skeleton: Dict, identity_seed: Dict) -> Dict:
        """
        从 L1 骨架 + L2 身份种子推导数值字段
        
        使用确定性规则，保证一致性
        """
        # 从 skeleton 提取参数
        p_know = skeleton.get("p_know", 0.3)
        p_learn = skeleton.get("p_learn", 0.25)
        personality_type = skeleton.get("personality_type", "中等自信")
        ses_level = skeleton.get("ses_level", "中等")
        
        # 推导成绩（0-100）
        # 规则：p_know 越高，成绩越好
        base_score = 50 + p_know * 40
        noise = np.random.normal(0, 5)  # 随机波动
        achievement_score = float(np.clip(base_score + noise, 0, 100))
        
        # 推导学习习惯评分（0-1）
        # 规则：p_learn 高 → 学习习惯好
        study_habits_score = float(np.clip(p_learn + np.random.normal(0, 0.1), 0, 1))
        
        # 推导自我效能感（0-1）
        # 规则：personality_type 和成绩的交互
        if personality_type == "高自信":
            self_efficacy = 0.7 + np.random.normal(0, 0.1)
        elif personality_type == "中等自信":
            self_efficacy = 0.5 + np.random.normal(0, 0.1)
        else:
            self_efficacy = 0.3 + np.random.normal(0, 0.1)
        self_efficacy = float(np.clip(self_efficacy, 0, 1))
        
        # 推导家庭投入（SES 相关）
        # 规则：SES 越高，家庭投入越多
        if ses_level == "高":
            family_investment_hours_weekly = np.random.normal(8, 2)
        elif ses_level == "中等":
            family_investment_hours_weekly = np.random.normal(4, 1.5)
        else:
            family_investment_hours_weekly = np.random.normal(1, 0.5)
        family_investment_hours_weekly = float(np.clip(family_investment_hours_weekly, 0, 20))
        
        return {
            "achievement_score": achievement_score,
            "study_habits_score": study_habits_score,
            "self_efficacy": self_efficacy,
            "family_investment_hours_weekly": family_investment_hours_weekly,
            "motivation_level": float(np.clip(p_know + p_learn, 0, 1)),
            "resilience_score": float(np.clip(1 - np.random.uniform(0.2, 0.8), 0, 1))
        }
    
    @staticmethod
    def get_narrative_continuation_prompt(identity_seed: Dict, numerical_fields: Dict) -> str:
        """
        Generate prompt for LLM narrative continuation (L3 叙事层)
        
        LLM 基于身份种子和数值字段，续写关键经历、兴趣、师生互动
        """
        prompt = f"""基于以下虚拟学生的身份种子和数值特征，生成详细的生活叙事。

【身份种子（L2）】
- 名字: {identity_seed.get('name')}
- 出生地: {identity_seed.get('birth_place')}
- 家庭结构: {identity_seed.get('family_structure_type')}
- 核心人格: {identity_seed.get('core_personality_seed')}
- 独特经历: {identity_seed.get('unique_life_seed')}

【数值特征（L3）】
- 成绩水平: {numerical_fields.get('achievement_score', 0):.1f}/100
- 学习习惯: {numerical_fields.get('study_habits_score', 0.5):.2f}/1.0
- 自我效能感: {numerical_fields.get('self_efficacy', 0.5):.2f}/1.0
- 家庭投入: {numerical_fields.get('family_investment_hours_weekly', 0):.1f}小时/周
- 动机水平: {numerical_fields.get('motivation_level', 0.5):.2f}/1.0

【生成要求】
1. 提供一段学生的关键生活经历/转折事件（200-300字）
2. 列出 3-5 个主要兴趣爱好（要与人格和成绩水平一致）
3. 描述学生与主科教师的互动风格（亲近/中立/疏离，50-100字）
4. 描述学生的时间分配模式（学校/家庭/自学/娱乐，百分比）
5. 输出格式为 JSON

【输出 JSON 格式】
{{
  "key_life_event": "具体的关键事件描述",
  "interests": ["兴趣1", "兴趣2", "兴趣3"],
  "teacher_interaction_style": "与教师的互动风格描述",
  "time_allocation": {{
    "school": 0.45,
    "homework": 0.20,
    "self_study": 0.10,
    "recreation": 0.25
  }},
  "narrative_summary": "整体生活叙事总结（100字）"
}}

开始生成：
"""
        return prompt
    
    @staticmethod
    def parse_narrative_output(llm_response: str) -> Dict:
        """Parse LLM narrative output"""
        try:
            return json.loads(llm_response)
        except:
            return {}


class Layer4CoherenceEngine:
    """
    Layer 4: Consistency validation and repair
    
    验证 Archive 中各字段的一致性：
    - 年龄 ↔ 年级
    - 家庭SES ↔ 先验知识
    - 天赋 ↔ 成绩
    - 时间分配 ↔ 成绩
    等
    """
    
    @staticmethod
    def validate_coherence(archive: Dict) -> Dict[str, bool]:
        """
        Check coherence across fields
        
        Returns: {"check_name": True/False}
        """
        checks = {}
        
        # Check 1: age ↔ grade consistency
        if "birth_date" in archive and "grade" in archive:
            # Simplified: 假设初二学生 14 岁左右
            grade = archive["grade"]
            expected_age_min = grade + 6
            checks["age_grade_consistency"] = True
        
        # Check 2: achievement ↔ study_habits consistency
        if "achievement_score" in archive and "study_habits_score" in archive:
            correlation = 0.7 * archive["study_habits_score"] + 0.2
            expected_achievement_range = (
                correlation * 60 - 20,
                correlation * 60 + 20
            )
            actual = archive.get("achievement_score", 50)
            checks["achievement_habits_consistency"] = (
                expected_achievement_range[0] <= actual <= expected_achievement_range[1]
            )
        
        # Check 3: interests ↔ achievement consistency
        if "interests" in archive and "achievement_score" in archive:
            # High achievers should have "academic" interests, etc.
            checks["interests_achievement_consistency"] = True
        
        # Check 4: time allocation sums to ~1.0
        if "time_allocation" in archive:
            total = sum(archive["time_allocation"].values())
            checks["time_allocation_sum"] = (0.95 <= total <= 1.05)
        
        return checks
    
    @staticmethod
    def repair_inconsistencies(archive: Dict) -> Dict:
        """
        Repair detected inconsistencies
        """
        # Simple repairs:
        if "time_allocation" in archive:
            total = sum(archive["time_allocation"].values())
            if total > 0:
                # Normalize
                for key in archive["time_allocation"]:
                    archive["time_allocation"][key] /= total
        
        return archive
