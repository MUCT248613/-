"""
Full 23-Domain Student Archive Builder (FR-A1)

Generates the comprehensive 23-domain / 210+ field persona archive specified in
《虚拟学生全方位档案设计文档》§2B. All fields are derived deterministically from
a small set of coherent latent traits (Big Five, SES index, BKT p_know/p_learn,
motivation, self-efficacy) so that cross-domain consistency holds (e.g. high
conscientiousness ↔ good study habits ↔ higher achievement).

The builder is pure-python + numpy (seeded) so it stays offline-safe; qualitative
narrative fields can optionally be enriched by the LLM layer upstream.

Reference: 档案设计文档 §2B (D1–D23), 需求说明文档 §6 FR-A1
"""
from __future__ import annotations

from typing import Dict, List, Optional
import numpy as np

from .family_background import sample_education, sample_occupation


# Domain metadata: (code, chinese label, field count) — mirrors 档案设计文档 §2B.
DOMAIN_SPECS: List[Dict] = [
    {"code": "D1", "label": "身份与学籍", "fields": 9},
    {"code": "D2", "label": "家庭与成长背景", "fields": 9},
    {"code": "D3", "label": "人格与心理特质", "fields": 8},
    {"code": "D4", "label": "能力与天赋", "fields": 9},
    {"code": "D5", "label": "学业档案", "fields": 8},
    {"code": "D6", "label": "身心健康", "fields": 8},
    {"code": "D7", "label": "品德与社会实践", "fields": 8},
    {"code": "D8", "label": "兴趣与生活方式", "fields": 6},
    {"code": "D9", "label": "关系与经历", "fields": 5},
    {"code": "D10", "label": "家庭深度结构与照护史", "fields": 12},
    {"code": "D11", "label": "隐私与敏感信息", "fields": 14},
    {"code": "D12", "label": "同伴、亚文化与数字生活", "fields": 13},
    {"code": "D13", "label": "隐性心理特质", "fields": 13},
    {"code": "D14", "label": "发展阶段与年龄效应", "fields": 7},
    {"code": "D15", "label": "认知与学习过程画像", "fields": 13},
    {"code": "D16", "label": "学校与课堂情境", "fields": 11},
    {"code": "D17", "label": "特殊才能与特殊教育需求", "fields": 8},
    {"code": "D18", "label": "课外学习生态", "fields": 13},
    {"code": "D19", "label": "家庭生活与作息", "fields": 12},
    {"code": "D20", "label": "家长角色连接点", "fields": 3},
    {"code": "D21", "label": "恋爱与亲密关系", "fields": 10},
    {"code": "D22", "label": "同伴社会网络", "fields": 11},
    {"code": "D23", "label": "成长关键事件与生命历程", "fields": 9},
]


class FullArchiveBuilder:
    """Build a coherent 23-domain archive from latent traits."""

    def __init__(self, skeleton: Dict, identity_seed: Dict,
                 numerical_fields: Dict, seed: int = 42):
        self.skeleton = skeleton or {}
        self.identity_seed = identity_seed or {}
        self.numerical = numerical_fields or {}
        self.rng = np.random.RandomState(seed)
        self.latents = self._derive_latents()

    # ------------------------------------------------------------------ #
    # Latent trait derivation (single source of truth for coherence)
    # ------------------------------------------------------------------ #
    def _derive_latents(self) -> Dict:
        r = self.rng
        p_know = float(self.skeleton.get("p_know", 0.3))
        p_learn = float(self.skeleton.get("p_learn", 0.25))
        ses_level = self.skeleton.get("ses_level", "中等")
        ses_index = {"低": 0.25, "中等": 0.55, "高": 0.82}.get(ses_level, 0.55)
        ses_index = float(np.clip(ses_index + r.normal(0, 0.08), 0.05, 0.98))

        achievement = float(self.numerical.get("achievement_score",
                                               50 + p_know * 40))
        motivation = float(self.numerical.get("motivation_level",
                                              np.clip(p_know + p_learn, 0, 1)))
        self_efficacy = float(self.numerical.get("self_efficacy", 0.5))
        study_habits = float(self.numerical.get("study_habits_score", 0.5))

        # Big Five (0–1), loosely coupled to achievement/personality.
        personality_type = self.skeleton.get("personality_type", "中等自信")
        extra_base = {"自信": 0.68, "中等自信": 0.5, "低自信": 0.35}.get(personality_type, 0.5)
        big5 = {
            "openness": float(np.clip(0.45 + p_know * 0.3 + r.normal(0, 0.12), 0, 1)),
            "conscientiousness": float(np.clip(study_habits * 0.7 + 0.2 + r.normal(0, 0.1), 0, 1)),
            "extraversion": float(np.clip(extra_base + r.normal(0, 0.12), 0, 1)),
            "agreeableness": float(np.clip(0.55 + r.normal(0, 0.13), 0, 1)),
            "neuroticism": float(np.clip(0.5 - self_efficacy * 0.3 + r.normal(0, 0.12), 0, 1)),
        }
        return {
            "p_know": p_know, "p_learn": p_learn, "ses_index": ses_index,
            "ses_level": ses_level, "achievement": achievement,
            "motivation": motivation, "self_efficacy": self_efficacy,
            "study_habits": study_habits, "big5": big5,
        }

    def _f(self, lo: float, hi: float, ndigits: int = 2) -> float:
        return float(round(self.rng.uniform(lo, hi), ndigits))

    def _pick(self, options: List) -> object:
        return options[int(self.rng.randint(0, len(options)))]

    # ------------------------------------------------------------------ #
    # Domain builders
    # ------------------------------------------------------------------ #
    def _d1_identity(self) -> Dict:
        L = self.latents
        return {
            "name": self.identity_seed.get("name", ""),
            # Gender flows from the identity seed (resolved in generate_student)
            # so it matches the name; only fall back to a random draw when the
            # seed carries no gender (e.g. a direct build_full_archive call).
            "gender": self.identity_seed.get("gender") or self._pick(["男", "女"]),
            "birth_date": "2012-0%d-%02d" % (int(self.rng.randint(1, 9)), int(self.rng.randint(1, 28))),
            "birth_place": self.identity_seed.get("birth_place", ""),
            "grade": 8,
            "class_id": "C%02d" % int(self.rng.randint(1, 12)),
            "student_status": "在读",
            "nationality": "中国",
            "household_registration": self._pick(["城镇", "农村"]),
        }

    def _d2_family_background(self) -> Dict:
        L = self.latents
        ses = L["ses_level"]
        return {
            "family_structure": self.identity_seed.get("family_structure_type", "完整家庭"),
            "ses_level": ses,
            "ses_index": round(L["ses_index"], 3),
            # 父母学历/职业与家长画像(P-Model)共用同一套 SES 条件分布（统一口径）；
            # 家长档案页的 education_level / occupation_category 由这里联动生成。
            "father_occupation": sample_occupation(ses, self.rng),
            "mother_occupation": sample_occupation(ses, self.rng),
            "father_education": sample_education(ses, self.rng),
            "mother_education": sample_education(ses, self.rng),
            "only_child": bool(self.rng.random() < 0.6),
            "household_income_band": self._pick(["偏低", "中等", "中上", "较高"]) if L["ses_index"] > 0.5 else self._pick(["偏低", "中等"]),
        }

    def _d3_personality(self) -> Dict:
        b = self.latents["big5"]
        return {
            "big5_openness": round(b["openness"], 3),
            "big5_conscientiousness": round(b["conscientiousness"], 3),
            "big5_extraversion": round(b["extraversion"], 3),
            "big5_agreeableness": round(b["agreeableness"], 3),
            "big5_neuroticism": round(b["neuroticism"], 3),
            "mbti": self._pick(["INTJ", "INFP", "ENTP", "ISFJ", "ESTJ", "ENFJ", "ISTP", "ESFP"]),
            "personality_tags": [self.identity_seed.get("core_personality_seed", "中等自信")],
            "temperament": self._pick(["多血质", "胆汁质", "粘液质", "抑郁质"]),
        }

    def _d4_ability(self) -> Dict:
        L = self.latents
        return {
            "logical_mathematical": round(np.clip(L["p_know"] + self._f(-0.1, 0.1), 0, 1), 3),
            "verbal_linguistic": round(self._f(0.3, 0.9), 3),
            "spatial": round(self._f(0.3, 0.9), 3),
            "musical": round(self._f(0.2, 0.8), 3),
            "bodily_kinesthetic": round(self._f(0.3, 0.8), 3),
            "interpersonal": round(np.clip(L["big5"]["extraversion"] + self._f(-0.1, 0.1), 0, 1), 3),
            "intrapersonal": round(self._f(0.3, 0.9), 3),
            "naturalistic": round(self._f(0.2, 0.7), 3),
            "gifted_domain": self._pick(["无明显特长", "数学", "语言", "艺术", "体育", "科学"]),
        }

    def _d5_academic(self) -> Dict:
        L = self.latents
        base = L["achievement"]
        return {
            "overall_achievement": round(base, 1),
            "chinese_score": round(np.clip(base + self._f(-8, 8), 0, 100), 1),
            "math_score": round(np.clip(base + (L["p_know"] - 0.5) * 20 + self._f(-6, 6), 0, 100), 1),
            "english_score": round(np.clip(base + self._f(-10, 10), 0, 100), 1),
            "science_score": round(np.clip(base + self._f(-8, 8), 0, 100), 1),
            "class_rank_percentile": round(np.clip(1 - base / 100 + self._f(-0.05, 0.05), 0, 1), 3),
            "academic_trend": self._pick(["上升", "平稳", "波动", "下滑"]),
            "main_misconception": self.skeleton.get("misconception_type", "代数"),
        }

    def _d6_health(self) -> Dict:
        L = self.latents
        return {
            "physical_fitness_score": round(self._f(60, 95), 1),
            "bmi_category": self._pick(["偏瘦", "正常", "正常", "超重"]),
            "vision_status": self._pick(["正常", "轻度近视", "中度近视"]),
            "sleep_quality": round(np.clip(0.7 - L["big5"]["neuroticism"] * 0.3 + self._f(-0.1, 0.1), 0, 1), 3),
            "chronic_fatigue": round(np.clip(0.3 + L["big5"]["neuroticism"] * 0.3 + self._f(-0.1, 0.1), 0, 1), 3),
            "mental_health_index": round(np.clip(0.75 - L["big5"]["neuroticism"] * 0.4 + self._f(-0.1, 0.1), 0, 1), 3),
            "exercise_frequency_weekly": int(self.rng.randint(0, 6)),
            "self_rated_health": self._pick(["很好", "较好", "一般"]),
        }

    def _d7_moral_social(self) -> Dict:
        return {
            "moral_rating": self._pick(["优秀", "良好", "良好", "合格"]),
            "volunteer_hours_year": int(self.rng.randint(0, 30)),
            "political_status": self._pick(["少先队员", "共青团员"]),
            "social_practice_count": int(self.rng.randint(0, 6)),
            "leadership_role": self._pick(["无", "课代表", "小组长", "班长", "学生会干事"]),
            "rule_compliance": round(self._f(0.5, 0.98), 3),
            "civic_awareness": round(self._f(0.4, 0.9), 3),
            "community_engagement": round(self._f(0.2, 0.8), 3),
        }

    def _d8_interests(self) -> Dict:
        return {
            "interests": self.identity_seed.get("interests", []) or ["阅读", "运动"],
            "hobby_depth": round(self._f(0.3, 0.9), 3),
            "art_literacy": round(self._f(0.2, 0.8), 3),
            "club_participation": self._pick(["无", "文学社", "机器人社", "篮球队", "合唱团", "辩论队"]),
            "screen_leisure_hours_daily": round(self._f(0.5, 4.0), 1),
            "lifestyle_regularity": round(self._f(0.3, 0.9), 3),
        }

    def _d9_relations_experience(self) -> Dict:
        return {
            "key_life_event": self.identity_seed.get("unique_life_seed", ""),
            "teacher_interaction_style": self._pick(["亲近", "中立", "疏离"]),
            "classroom_positions_held": self._pick(["无", "课代表", "班长"]),
            "notable_achievement": self._pick(["无", "学科竞赛获奖", "文体比赛获奖", "优秀学生干部"]),
            "turning_point_event": self._pick(["转学", "家庭变故", "一次重要考试", "结识良师"]),
        }

    def _d10_family_deep(self) -> Dict:
        L = self.latents
        return {
            "primary_caregiver": self._pick(["母亲", "父亲", "祖辈", "父母共同"]),
            "caregiver_warmth": round(self._f(0.3, 0.95), 3),
            "caregiver_control": round(self._f(0.2, 0.9), 3),
            "family_cohesion": round(np.clip(0.5 + L["ses_index"] * 0.2 + self._f(-0.15, 0.15), 0, 1), 3),
            "family_conflict_level": round(np.clip(0.4 - L["ses_index"] * 0.2 + self._f(-0.1, 0.15), 0, 1), 3),
            "parental_marital_quality": round(self._f(0.3, 0.95), 3),
            "economic_stress": round(np.clip(0.7 - L["ses_index"] * 0.5 + self._f(-0.1, 0.1), 0, 1), 3),
            "cultural_capital": round(np.clip(L["ses_index"] * 0.6 + self._f(0, 0.3), 0, 1), 3),
            "home_learning_environment": round(np.clip(L["ses_index"] * 0.5 + self._f(0.1, 0.4), 0, 1), 3),
            "siblings_count": int(self.rng.randint(0, 3)),
            "birth_order": self._pick(["独生", "长子/长女", "次子/次女", "幼子/幼女"]),
            "intergenerational_education_gap": round(self._f(-0.3, 0.5), 3),
        }

    def _d11_privacy_sensitive(self) -> Dict:
        # S-level fields: generated but MUST be filtered before frontend/export.
        return {
            "chronic_condition": self._pick(["无", "无", "无", "哮喘", "过敏体质"]),
            "adhd_indicator": round(self._f(0.0, 0.4), 3),
            "anxiety_indicator": round(self._f(0.0, 0.6), 3),
            "depression_indicator": round(self._f(0.0, 0.5), 3),
            "absenteeism_days_year": int(self.rng.randint(0, 12)),
            "medication_history": self._pick(["无", "无", "无", "有"]),
            "family_income_detail": int(self.rng.randint(30000, 200000)),
            "parent_health_issue": self._pick(["无", "无", "有"]),
            "economic_hardship_flag": bool(self.rng.random() < 0.15),
            "psychological_counseling_history": self._pick(["无", "无", "无", "有"]),
            "sleep_disorder_flag": bool(self.rng.random() < 0.1),
            "substance_exposure": self._pick(["无", "无", "无", "无"]),
            "self_harm_risk_flag": False,
            "disability_flag": self._pick(["无", "无", "无", "无"]),
        }

    def _d12_peers_digital(self) -> Dict:
        return {
            "peer_group_quality": round(self._f(0.3, 0.9), 3),
            "close_friends_count": int(self.rng.randint(1, 7)),
            "peer_academic_norm": round(self._f(0.3, 0.85), 3),
            "deviant_peer_exposure": round(self._f(0.0, 0.4), 3),
            "subculture_affiliation": self._pick(["无", "动漫", "电竞", "饭圈", "运动", "音乐"]),
            "idol_worship_intensity": round(self._f(0.0, 0.7), 3),
            "gaming_hours_weekly": round(self._f(0.0, 14.0), 1),
            "short_video_hours_daily": round(self._f(0.0, 3.0), 1),
            "social_media_platforms": self._pick([["QQ"], ["QQ", "微信"], ["微信", "B站"], ["QQ", "抖音"]]),
            "online_social_activity": round(self._f(0.2, 0.9), 3),
            "cyberbullying_exposure": round(self._f(0.0, 0.2), 3),
            "device_ownership": self._pick(["仅家长手机", "共用平板", "自有手机", "自有手机+电脑"]),
            "digital_literacy": round(self._f(0.3, 0.9), 3),
        }

    def _d13_hidden_psych(self) -> Dict:
        L = self.latents
        return {
            "intrinsic_motivation": round(np.clip(L["motivation"] * 0.7 + self._f(0, 0.2), 0, 1), 3),
            "extrinsic_motivation": round(self._f(0.3, 0.9), 3),
            "autonomy_need": round(self._f(0.3, 0.9), 3),
            "competence_need": round(np.clip(L["self_efficacy"] + self._f(-0.1, 0.1), 0, 1), 3),
            "relatedness_need": round(self._f(0.3, 0.9), 3),
            "resilience_adversity_quotient": round(np.clip(0.5 + L["self_efficacy"] * 0.3 + self._f(-0.15, 0.15), 0, 1), 3),
            "self_drive_index": round(np.clip(L["motivation"] * 0.6 + L["study_habits"] * 0.3 + self._f(-0.1, 0.1), 0, 1), 3),
            "goal_orientation": self._pick(["掌握导向", "成绩导向", "回避导向"]),
            "attribution_style": self._pick(["努力归因", "能力归因", "运气归因", "任务归因"]),
            "metacognitive_calibration": round(self._f(-0.5, 0.5), 3),
            "self_regulation": round(np.clip(L["study_habits"] * 0.7 + self._f(0, 0.2), 0, 1), 3),
            "growth_mindset": round(self._f(0.3, 0.95), 3),
            "academic_burnout": round(np.clip(0.5 - L["motivation"] * 0.3 + self._f(-0.1, 0.15), 0, 1), 3),
        }

    def _d14_development(self) -> Dict:
        return {
            "age": 14,
            "pubertal_stage": self._pick(["青春期中期", "青春期早期", "青春期中后期"]),
            "rebelliousness": round(self._f(0.2, 0.8), 3),
            "identity_exploration": round(self._f(0.3, 0.8), 3),
            "school_transition_stress": round(self._f(0.1, 0.6), 3),
            "autonomy_development": round(self._f(0.3, 0.85), 3),
            "age_norm_pressure": round(self._f(0.2, 0.7), 3),
        }

    def _d15_cognitive_process(self) -> Dict:
        L = self.latents
        return {
            "cognitive_style_field": round(self._f(0.2, 0.8), 3),
            "impulsivity_vs_reflection": round(self._f(0.2, 0.8), 3),
            "strategy_elaboration": round(self._f(0.2, 0.9), 3),
            "strategy_organization": round(np.clip(L["study_habits"] + self._f(-0.1, 0.1), 0, 1), 3),
            "strategy_rehearsal": round(self._f(0.3, 0.9), 3),
            "strategy_retrieval_self_testing": round(self._f(0.2, 0.9), 3),
            "working_memory_capacity": round(self._f(0.3, 0.95), 3),
            "processing_speed": round(self._f(0.3, 0.9), 3),
            "error_careless_slip_rate": round(self._f(0.05, 0.4), 3),
            "error_misconception_rate": round(np.clip(0.5 - L["p_know"] * 0.4 + self._f(-0.1, 0.1), 0, 1), 3),
            "error_knowledge_gap_rate": round(np.clip(0.5 - L["p_know"] * 0.4 + self._f(-0.1, 0.1), 0, 1), 3),
            "transfer_ability": round(self._f(0.2, 0.85), 3),
            "help_seeking_tendency": round(self._f(0.2, 0.8), 3),
        }

    def _d16_school_context(self) -> Dict:
        return {
            "school_tier": self._pick(["县城中学", "市区普通中学", "市区重点中学", "乡镇中学"]),
            "class_climate_cohesion": round(self._f(0.3, 0.9), 3),
            "class_climate_competition": round(self._f(0.2, 0.9), 3),
            "class_climate_support": round(self._f(0.3, 0.9), 3),
            "teacher_support_perceived": round(self._f(0.3, 0.9), 3),
            "classroom_autonomy_space": round(self._f(0.2, 0.8), 3),
            "peer_competition_intensity": round(self._f(0.2, 0.9), 3),
            "school_resources_index": round(self._f(0.3, 0.9), 3),
            "class_size": int(self.rng.randint(35, 60)),
            "boarding_status": self._pick(["走读", "走读", "住校"]),
            "commute_minutes": int(self.rng.randint(5, 60)),
        }

    def _d17_special_needs(self) -> Dict:
        return {
            "gifted_flag": bool(self.rng.random() < 0.08),
            "learning_disability_flag": bool(self.rng.random() < 0.05),
            "twice_exceptional_flag": bool(self.rng.random() < 0.02),
            "sen_category": self._pick(["无", "无", "无", "无", "学习困难", "情绪行为"]),
            "accommodation_needed": self._pick(["无", "无", "无", "延长考试时间", "座位调整"]),
            "talent_development_track": self._pick(["无", "学科竞赛", "艺术特长", "体育特长", "科创"]),
            "enrichment_participation": round(self._f(0.0, 0.7), 3),
            "individualized_plan_flag": bool(self.rng.random() < 0.05),
        }

    def _d18_shadow_edu(self) -> Dict:
        L = self.latents
        base_hours = 2 + L["ses_index"] * 6
        return {
            "shadow_edu_hours_weekly": round(float(np.clip(base_hours + self._f(-2, 3), 0, 15)), 1),
            "tutoring_subjects": self._pick([["数学"], ["数学", "英语"], ["英语"], ["数学", "物理"], []]),
            "tutoring_format": self._pick(["无", "大班", "小班", "一对一", "线上"]),
            "tutoring_quality": round(self._f(0.3, 0.9), 3),
            "shadow_edu_cost_yearly": int(self.rng.randint(0, 40000)),
            "self_study_hours_weekly": round(self._f(1, 12), 1),
            "self_study_effectiveness": round(np.clip(L["study_habits"] + self._f(-0.1, 0.1), 0, 1), 3),
            "online_learning_platforms": self._pick([["无"], ["学而思网校"], ["B站学习区"], ["国家中小学智慧教育平台"]]),
            "parent_academic_involvement": round(self._f(0.2, 0.9), 3),
            "homework_hours_daily": round(self._f(0.5, 3.5), 1),
            "academic_overload_flag": bool(self.rng.random() < 0.25),
            "shadow_edu_dependency": round(self._f(0.1, 0.7), 3),
            "weekend_study_load": round(self._f(0, 10), 1),
        }

    def _d19_daily_routine(self) -> Dict:
        return {
            "weekday_wake_time": self._pick(["06:00", "06:30", "07:00"]),
            "weekday_sleep_time": self._pick(["22:00", "22:30", "23:00", "23:30"]),
            "sleep_duration_hours": round(self._f(6.5, 9.0), 1),
            "breakfast_regularity": round(self._f(0.4, 1.0), 3),
            "after_school_structure": round(self._f(0.2, 0.9), 3),
            "family_dinner_frequency_weekly": int(self.rng.randint(2, 8)),
            "weekend_screen_hours": round(self._f(1, 8), 1),
            "physical_activity_hours_weekly": round(self._f(0, 8), 1),
            "part_time_or_chores": self._pick(["无", "少量家务", "较多家务"]),
            "daily_routine_stability": round(self._f(0.3, 0.95), 3),
            "morningness_eveningness": round(self._f(0.2, 0.8), 3),
            "leisure_reading_hours_weekly": round(self._f(0, 6), 1),
        }

    def _d20_parent_link(self) -> Dict:
        return {
            "primary_parent_id": None,  # filled by pipeline
            "parent_relation_quality": round(self._f(0.3, 0.95), 3),
            "parent_involvement_perceived": round(self._f(0.2, 0.9), 3),
        }

    def _d21_romance(self) -> Dict:
        return {
            "romance_status": self._pick(["无", "无", "无", "暧昧", "恋爱中"]),
            "romance_intensity": round(self._f(0.0, 0.7), 3),
            "romance_time_investment_weekly": round(self._f(0, 8), 1),
            "romance_emotional_impact": round(self._f(-0.3, 0.5), 3),
            "romance_academic_interference": round(self._f(0.0, 0.5), 3),
            "parent_awareness": self._pick(["不知情", "知情默许", "知情反对", "支持"]),
            "peer_norm_romance": round(self._f(0.1, 0.6), 3),
            "emotional_maturity": round(self._f(0.3, 0.9), 3),
            "attachment_style": self._pick(["安全型", "焦虑型", "回避型"]),
            "breakup_history": bool(self.rng.random() < 0.15),
        }

    def _d22_social_network(self) -> Dict:
        return {
            "network_size": int(self.rng.randint(3, 20)),
            "network_density": round(self._f(0.1, 0.6), 3),
            "centrality_degree": round(self._f(0.1, 0.9), 3),
            "betweenness_centrality": round(self._f(0.0, 0.5), 3),
            "clique_membership": self._pick(["核心成员", "普通成员", "边缘", "孤立"]),
            "peer_influence_susceptibility": round(self._f(0.2, 0.9), 3),
            "friendship_stability": round(self._f(0.3, 0.95), 3),
            "cross_gender_friendships": int(self.rng.randint(0, 6)),
            "mentor_relationship": self._pick(["无", "有"]),
            "social_support_perceived": round(self._f(0.3, 0.95), 3),
            "loneliness_index": round(self._f(0.0, 0.6), 3),
        }

    def _d23_life_events(self) -> Dict:
        return {
            "recent_positive_events": self._pick([["无"], ["获奖"], ["交到好朋友"], ["成绩进步"]]),
            "recent_negative_events": self._pick([["无"], ["无"], ["考试失利"], ["与朋友冲突"], ["家庭争吵"]]),
            "event_stress_load": round(self._f(0.0, 0.7), 3),
            "turning_point_count": int(self.rng.randint(0, 4)),
            "family_change_event": self._pick(["无", "无", "搬家", "父母工作变动", "二胎"]),
            "academic_milestone": self._pick(["无", "升入重点班", "竞赛入围"]),
            "health_event": self._pick(["无", "无", "一次生病请假"]),
            "event_recovery_capacity": round(self._f(0.3, 0.9), 3),
            "life_satisfaction": round(self._f(0.4, 0.95), 3),
        }

    # ------------------------------------------------------------------ #
    # Assembly
    # ------------------------------------------------------------------ #
    _BUILDERS = {
        "D1": _d1_identity, "D2": _d2_family_background, "D3": _d3_personality,
        "D4": _d4_ability, "D5": _d5_academic, "D6": _d6_health,
        "D7": _d7_moral_social, "D8": _d8_interests, "D9": _d9_relations_experience,
        "D10": _d10_family_deep, "D11": _d11_privacy_sensitive,
        "D12": _d12_peers_digital, "D13": _d13_hidden_psych, "D14": _d14_development,
        "D15": _d15_cognitive_process, "D16": _d16_school_context,
        "D17": _d17_special_needs, "D18": _d18_shadow_edu, "D19": _d19_daily_routine,
        "D20": _d20_parent_link, "D21": _d21_romance, "D22": _d22_social_network,
        "D23": _d23_life_events,
    }

    # S-level domains that must be filtered before frontend/export.
    SENSITIVE_DOMAINS = {"D11"}

    def build(self) -> Dict:
        """Return {"domains": {...}, "field_count": int, "domain_count": int}."""
        domains: Dict[str, Dict] = {}
        field_count = 0
        for spec in DOMAIN_SPECS:
            code = spec["code"]
            builder = self._BUILDERS[code]
            data = builder(self)
            domains[code] = {"label": spec["label"], "fields": data}
            field_count += len(data)
        return {
            "domains": domains,
            "field_count": field_count,
            "domain_count": len(domains),
            "sensitive_domains": sorted(self.SENSITIVE_DOMAINS),
        }


def build_full_archive(skeleton: Dict, identity_seed: Dict,
                       numerical_fields: Dict, seed: int = 42) -> Dict:
    """Convenience wrapper around :class:`FullArchiveBuilder`."""
    return FullArchiveBuilder(skeleton, identity_seed, numerical_fields,
                              seed=seed).build()
