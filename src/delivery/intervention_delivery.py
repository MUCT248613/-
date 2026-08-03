"""
W4: Intervention Delivery System
5-channel intervention delivery with virtual effect size calculation

Reference: 需求说明文档 §2.3, 技术设计文档 §5.1
"""
from typing import Dict, List, Tuple, Optional, Union
from dataclasses import dataclass
from enum import Enum
import os
import numpy as np
from scipy import stats as scipy_stats


class InterventionChannel(Enum):
    """5-channel intervention delivery"""
    DIRECT = "direct"  # Direct manipulation on student
    TEACHER_MEDIATED = "teacher_mediated"  # Through T-Model
    PARENT_MEDIATED = "parent_mediated"  # Through P-Model
    SHADOW_EDU_MEDIATED = "shadow_edu_mediated"  # Through tutoring
    SELF_STUDY_MEDIATED = "self_study_mediated"  # Self-paced materials


class InterventionType(Enum):
    """Types of interventions"""
    COGNITIVE_SUPPORT = "cognitive_support"  # Help understanding
    MOTIVATIONAL_BOOST = "motivational_boost"  # Confidence/goal-setting
    TIME_MANAGEMENT = "time_management"  # Organization/planning
    STRESS_REDUCTION = "stress_reduction"  # Relaxation/coping
    SOCIAL_SUPPORT = "social_support"  # Peer/family support
    # FR-S1: four evidence-based learning interventions (I1–I4)
    WORKED_EXAMPLES = "worked_examples"        # I1 样例学习
    SPACED_PRACTICE = "spaced_practice"        # I2 间隔练习
    FEEDBACK = "feedback"                       # I3 即时反馈
    RETRIEVAL_PRACTICE = "retrieval_practice"  # I4 检索练习


def _type_key(intervention_type: Union["InterventionType", str]) -> str:
    """Normalise an InterventionType or raw string to a hashable string key."""
    if isinstance(intervention_type, InterventionType):
        return intervention_type.value
    return str(intervention_type)


def load_intervention_catalog(
        config_path: Optional[str] = None) -> Dict[str, Dict]:
    """Load the YAML-declared intervention catalog (FR-S1: 新增干预不改代码).

    Returns a dict keyed by intervention id (e.g. ``I1_worked_examples``). Each
    entry carries ``type`` (string key), effect sizes, ``target_scene`` routing
    and ``default_channel``. A missing file or missing ``yaml`` dependency
    degrades gracefully to an empty catalog so the engine still runs on its
    built-in defaults.
    """
    try:
        import yaml
    except ImportError:
        return {}
    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "config",
            "intervention_delivery.yaml")
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return {}
    return data.get("interventions", {}) or {}


@dataclass
class Intervention:
    """Single intervention instance"""
    intervention_id: str
    student_id: str
    intervention_type: InterventionType
    channel: InterventionChannel
    
    day_started: int
    duration_days: int
    intensity: float  # 0-1, strength of intervention
    
    # Expected effect (set by theory)
    expected_effect_on_achievement: float
    expected_effect_on_motivation: float
    
    # Tracking
    is_active: bool = True
    adherence_rate: float = 1.0  # 0-1, how well executed
    
    def is_active_on_day(self, day: int) -> bool:
        """Check if intervention is active on a given day"""
        return self.is_active and (self.day_started <= day < self.day_started + self.duration_days)


class InterventionDeliveryEngine:
    """
    Manages intervention delivery through 5 channels
    
    Key mechanisms:
    - Channel-specific efficacy multipliers
    - Mediation through teachers/parents
    - Cumulative and interference effects
    """
    
    # Channel efficacy multipliers (base effect = 1.0)
    CHANNEL_EFFICACY = {
        InterventionChannel.DIRECT: 1.0,  # Direct has baseline efficacy
        InterventionChannel.TEACHER_MEDIATED: 0.7,  # Teacher may not execute perfectly (fidelity)
        InterventionChannel.PARENT_MEDIATED: 0.5,  # Parent involvement variable
        InterventionChannel.SHADOW_EDU_MEDIATED: 0.8,  # Tutor professional
        InterventionChannel.SELF_STUDY_MEDIATED: 0.4  # Lowest - requires self-discipline
    }
    
    # Type-specific effects on achievement and motivation
    TYPE_EFFECTS = {
        InterventionType.COGNITIVE_SUPPORT: {
            "achievement": 5.0,
            "motivation": 1.0
        },
        InterventionType.MOTIVATIONAL_BOOST: {
            "achievement": 2.0,
            "motivation": 0.15
        },
        InterventionType.TIME_MANAGEMENT: {
            "achievement": 3.0,
            "motivation": 0.05
        },
        # Sleep-hygiene / stress-reduction improves focus and working memory,
        # with a modest but reliable achievement effect (meta-analytic g~0.25).
        # The base effect must clear the simulation's background noise floor or
        # the weakest arm's estimate hovers around zero.
        InterventionType.STRESS_REDUCTION: {
            "achievement": 3.0,
            "motivation": 0.1
        },
        # Parental involvement has a well-established effect (meta-analytic
        # g~0.3-0.5); expressed here on the 0-100 achievement scale.
        InterventionType.SOCIAL_SUPPORT: {
            "achievement": 3.5,
            "motivation": 0.12
        },
        # FR-S1 I1–I4: effect sizes approximate learning-science meta-analyses
        # (worked-examples g≈0.35, spaced g≈0.50, feedback g≈0.55, retrieval g≈0.50)
        # expressed on the engine's 0–100 achievement / 0–1 motivation scales.
        InterventionType.WORKED_EXAMPLES: {
            "achievement": 4.0,
            "motivation": 0.05
        },
        InterventionType.SPACED_PRACTICE: {
            "achievement": 5.5,
            "motivation": 0.06
        },
        InterventionType.FEEDBACK: {
            "achievement": 6.0,
            "motivation": 0.10
        },
        InterventionType.RETRIEVAL_PRACTICE: {
            "achievement": 5.8,
            "motivation": 0.07
        }
    }
    
    def __init__(self, catalog_path: Optional[str] = None,
                 load_catalog: bool = True):
        self.interventions: Dict[str, Intervention] = {}
        self.intervention_history: List[Intervention] = []
        # YAML-declared interventions (FR-S1): keyed by string type, merged over
        # the built-in TYPE_EFFECTS so new interventions need no code change.
        self.custom_effects: Dict[str, Dict] = {}
        self.catalog: Dict[str, Dict] = {}
        if load_catalog:
            self.load_catalog(catalog_path)

    def load_catalog(self, config_path: Optional[str] = None) -> Dict[str, Dict]:
        """Load and register YAML-declared interventions (FR-S1).

        Each catalog entry's ``effect_achievement``/``effect_motivation`` are
        registered into ``custom_effects`` under its ``type`` string so that
        ``assign_intervention(..., intervention_type="<type>")`` works for
        interventions that exist only in YAML.
        """
        self.catalog = load_intervention_catalog(config_path)
        for _id, spec in self.catalog.items():
            type_str = spec.get("type") or _id
            self.custom_effects[type_str] = {
                "achievement": float(spec.get("effect_achievement", 0.0)),
                "motivation": float(spec.get("effect_motivation", 0.0)),
            }
        return self.catalog

    def _effect_for(self, intervention_type: Union[InterventionType, str]) -> Dict:
        """Resolve effect sizes for an enum or YAML-declared string type."""
        if isinstance(intervention_type, InterventionType):
            return self.TYPE_EFFECTS.get(intervention_type, {})
        # String type: prefer YAML catalog, then any built-in with same value.
        if intervention_type in self.custom_effects:
            return self.custom_effects[intervention_type]
        for enum_type, effects in self.TYPE_EFFECTS.items():
            if enum_type.value == intervention_type:
                return effects
        return {}
    
    def assign_intervention(self, student_id: str, intervention_type: Union[InterventionType, str],
                           channel: InterventionChannel, day_started: int,
                           duration_days: int = 30, intensity: float = 0.8) -> str:
        """
        Assign an intervention to a student
        
        Args:
            student_id: Student ID
            intervention_type: Type of intervention (enum or YAML-declared string)
            channel: Delivery channel
            day_started: When intervention starts
            duration_days: How long it lasts
            intensity: Strength (0-1)
        
        Returns:
            Intervention ID
        """
        type_str = _type_key(intervention_type)
        int_id = f"{student_id}_{type_str}_{channel.value}_{day_started}"
        
        # Get base effect from type (built-in enum or YAML catalog)
        type_effect = self._effect_for(intervention_type)
        
        intervention = Intervention(
            intervention_id=int_id,
            student_id=student_id,
            intervention_type=intervention_type,
            channel=channel,
            day_started=day_started,
            duration_days=duration_days,
            intensity=intensity,
            expected_effect_on_achievement=type_effect.get("achievement", 0),
            expected_effect_on_motivation=type_effect.get("motivation", 0)
        )
        
        self.interventions[int_id] = intervention
        self.intervention_history.append(intervention)
        return int_id
    
    def compute_intervention_effect(self, intervention: Intervention, day: int,
                                   mediator_quality: float = 1.0) -> Dict[str, float]:
        """
        Compute actual intervention effect on a given day
        
        Args:
            intervention: Intervention instance
            day: Current simulation day
            mediator_quality: Quality of mediator (T-Model fidelity, P-Model involvement, etc.)
        
        Returns:
            Dict of {attribute: effect_value}
        """
        
        if not intervention.is_active_on_day(day):
            return {
                "achievement_delta": 0.0,
                "motivation_delta": 0.0
            }
        
        # Get channel efficacy
        channel_efficacy = self.CHANNEL_EFFICACY.get(intervention.channel, 0.5)
        
        # Apply mediator quality if applicable
        if intervention.channel != InterventionChannel.DIRECT:
            channel_efficacy *= mediator_quality
        
        # Compute effect with adherence
        ach_delta = (intervention.expected_effect_on_achievement * 
                    intervention.intensity * 
                    channel_efficacy * 
                    intervention.adherence_rate)
        
        mot_delta = (intervention.expected_effect_on_motivation * 
                    intervention.intensity * 
                    channel_efficacy * 
                    intervention.adherence_rate)
        
        return {
            "achievement_delta": ach_delta,
            "motivation_delta": mot_delta
        }
    
    def apply_interventions_to_student(self, student: Dict, day: int,
                                      teachers: Dict = None, parents: Dict = None) -> Dict:
        """
        Apply all active interventions to a student
        
        Args:
            student: Student profile dict
            day: Current simulation day
            teachers: Dict of teacher profiles for mediation quality
            parents: Dict of parent profiles for mediation quality
        
        Returns:
            Updated student dict
        """
        teachers = teachers or {}
        parents = parents or {}
        
        total_ach_delta = 0.0
        total_mot_delta = 0.0
        
        # Get all interventions for this student
        student_interventions = [i for i in self.intervention_history 
                                if i.student_id == student.get("student_id")]
        
        for intervention in student_interventions:
            if not intervention.is_active_on_day(day):
                continue
            
            # Get mediator quality
            mediator_quality = 1.0
            
            if intervention.channel == InterventionChannel.TEACHER_MEDIATED:
                # Get assigned teacher's fidelity
                teacher_id = student.get("assigned_teacher_id")
                if teacher_id and teacher_id in teachers:
                    mediator_quality = teachers[teacher_id].get(
                        "simulation_vector", {}).get("fidelity", 0.7)
            
            elif intervention.channel == InterventionChannel.PARENT_MEDIATED:
                # Get parent's involvement level
                parent_id = student.get("primary_parent_id")
                if parent_id and parent_id in parents:
                    mediator_quality = parents[parent_id].get(
                        "simulation_vector", {}).get("involvement_level", 0.5)
            
            # Compute effect
            effect = self.compute_intervention_effect(intervention, day, mediator_quality)
            total_ach_delta += effect["achievement_delta"]
            total_mot_delta += effect["motivation_delta"]
        
        # Apply to student
        if "achievement_score" not in student:
            student["achievement_score"] = 50
        student["achievement_score"] = np.clip(
            student["achievement_score"] + total_ach_delta,
            0, 100
        )
        
        if "motivation" not in student:
            student["motivation"] = 0.5
        student["motivation"] = np.clip(
            student["motivation"] + total_mot_delta,
            0, 1
        )
        
        return student
    
    def set_adherence(self, intervention_id: str, adherence_rate: float) -> None:
        """Update adherence rate for an intervention"""
        if intervention_id in self.interventions:
            self.interventions[intervention_id].adherence_rate = np.clip(adherence_rate, 0, 1)
    
    def get_active_interventions(self, student_id: str, day: int) -> List[Intervention]:
        """Get active interventions for a student on a given day"""
        student_interventions = [i for i in self.intervention_history 
                                if i.student_id == student_id]
        return [i for i in student_interventions if i.is_active_on_day(day)]


class VirtualEffectSizeCalculator:
    """
    Calculate Hedges' g effect sizes from simulation data
    
    Reference: Cohen (1988), Hedges & Olkin (1985)
    """
    
    @staticmethod
    def compute_hedges_g(control_data: np.ndarray, treatment_data: np.ndarray) -> Tuple[float, float, float]:
        """
        Compute Hedges' g effect size with confidence interval
        
        Args:
            control_data: Achievement scores for control group (no intervention)
            treatment_data: Achievement scores for treatment group (intervention)
        
        Returns:
            (effect_size_g, ci_lower, ci_upper)
        """
        n_c = len(control_data)
        n_t = len(treatment_data)
        
        if n_c < 2 or n_t < 2:
            return 0.0, 0.0, 0.0
        
        # Means
        m_c = np.mean(control_data)
        m_t = np.mean(treatment_data)
        
        # Standard deviations
        sd_c = np.std(control_data, ddof=1)
        sd_t = np.std(treatment_data, ddof=1)
        
        # Pooled standard deviation
        sp = np.sqrt(((n_c - 1) * sd_c**2 + (n_t - 1) * sd_t**2) / (n_c + n_t - 2))
        
        if sp == 0:
            return 0.0, 0.0, 0.0
        
        # Cohen's d
        cohens_d = (m_t - m_c) / sp
        
        # Hedges' g (correction for small sample sizes)
        J = 1 - (3 / (4 * (n_c + n_t - 2) - 1))
        hedges_g = J * cohens_d
        
        # Standard error of Hedges' g (correct formula)
        # SE_g = sqrt((n_c + n_t)/(n_c * n_t) + g^2 / (2*(n_c + n_t - 2)))
        df = n_c + n_t - 2
        se_g = np.sqrt((n_c + n_t) / (n_c * n_t) + hedges_g**2 / (2 * df))
        
        # 95% CI using t-distribution
        t_crit = scipy_stats.t.ppf(0.975, df)
        
        ci_lower = hedges_g - t_crit * se_g
        ci_upper = hedges_g + t_crit * se_g
        
        return float(hedges_g), float(ci_lower), float(ci_upper)
    
    @staticmethod
    def compute_nnt(effect_size: float, control_success_rate: float) -> float:
        """
        Number Needed to Treat (NNT)
        
        Args:
            effect_size: Hedges' g or Cohen's d
            control_success_rate: Success rate in control group (0-1)
        
        Returns:
            NNT (lower is better)
        """
        # Convert d to probability difference using normal CDF
        if control_success_rate <= 0 or control_success_rate >= 1:
            return float('inf')
        
        # Effect size to improvement in success rate
        treatment_success_prob = scipy_stats.norm.cdf(effect_size / 2)
        
        if treatment_success_prob <= control_success_rate:
            return float('inf')
        
        improvement = treatment_success_prob - control_success_rate
        if improvement == 0:
            return float('inf')
        
        nnt = 1 / improvement
        return max(1, nnt)


class InterventionComparator:
    """
    Compare intervention effects across channels and types
    """
    
    def __init__(self, simulation_results: Dict):
        """
        Args:
            simulation_results: Dict with 'trajectories' key from LifeTimeEngineV2
        """
        self.results = simulation_results
    
    def compare_channels(self, intervention_results: Dict) -> Dict:
        """
        Compare effect sizes across channels
        
        Args:
            intervention_results: Dict with interventions assigned
        
        Returns:
            Comparison table by channel
        """
        comparison = {}
        
        for channel in InterventionChannel:
            comparison[channel.value] = {
                "n_students": 0,
                "avg_effect_size": 0.0,
                "avg_achievement_gain": 0.0
            }
        
        return comparison
    
    def compute_scenario_comparison(self, scenario_name: str, 
                                   final_achievements: np.ndarray) -> Dict:
        """
        Compare achievement distribution across scenarios
        
        Args:
            scenario_name: Name of this scenario
            final_achievements: Array of final achievement scores
        
        Returns:
            Scenario statistics
        """
        return {
            "scenario": scenario_name,
            "n": len(final_achievements),
            "mean": np.mean(final_achievements),
            "std": np.std(final_achievements),
            "median": np.median(final_achievements),
            "min": np.min(final_achievements),
            "max": np.max(final_achievements),
            "q25": np.percentile(final_achievements, 25),
            "q75": np.percentile(final_achievements, 75)
        }
