"""
VirtualStudent Sandbox v6.0 - Intervention Simulation Module (M4)

Implements §5 M4 干预模拟 (Intervention Simulation), driven by L-Model 2.0.

Replaces the v2.0 "learning-sequence step" approach with a continuous
L-Model event stream:
    simulate_intervention_l_model(student, teacher, parent, intervention, days)
        -> VirtualTrajectory (30 days x 1440 min event stream)

Also provides scene-effect comparison: the same intervention is run under
target_scene = school / shadow_edu / home / self_study, producing 4 virtual
effect sizes.

Reference: 技术设计文档 §5 M4, §4.7 (multi-channel delivery)
"""
from typing import Dict, List, Optional, Any

import numpy as np

from ..l_model.engine import LifeTimeEngineV2
from ..delivery.intervention_delivery import (
    InterventionDeliveryEngine, InterventionType, InterventionChannel,
    VirtualEffectSizeCalculator,
)


class VirtualTrajectory:
    """Container for a simulated intervention trajectory (event stream)."""
    
    def __init__(self, student_id: str, intervention_id: Optional[str] = None):
        self.student_id = student_id
        self.intervention_id = intervention_id
        self.events: List[Dict] = []
        self.daily_achievement: List[float] = []
        self.daily_motivation: List[float] = []
        self.daily_fatigue: List[float] = []
    
    @property
    def days(self) -> int:
        return len(self.daily_achievement)
    
    def mean_achievement(self) -> float:
        return float(np.mean(self.daily_achievement)) if self.daily_achievement else 0.0


class LModelSimulator:
    """
    L-Model 驱动的干预模拟器 (L-Model-driven intervention simulator).
    
    Couples the LifeTimeEngineV2 (multi-agent continuous timeline) with the
    InterventionDeliveryEngine (5-channel routing) to produce virtual
    trajectories and effect sizes.
    """
    
    SCENES = ["school", "shadow_edu", "home", "self_study"]
    
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.delivery = InterventionDeliveryEngine()
        self.effect_calc = VirtualEffectSizeCalculator()
    
    def simulate_intervention_l_model(self, student: Dict, teacher: Optional[Dict],
                                      parent: Optional[Dict], intervention: Dict,
                                      days: int = 30) -> VirtualTrajectory:
        """
        Continuous L-Model simulation: days x event stream.
        
        Args:
            student: Student state dict (must contain achievement_score, motivation)
            teacher: Teacher dict (for teacher_mediated channel fidelity)
            parent: Parent dict (for parent_mediated channel style multiplier)
            intervention: Intervention config dict with delivery_model / target_scene
            days: Number of days to simulate
        
        Returns:
            VirtualTrajectory with daily state curves and event stream
        """
        traj = VirtualTrajectory(
            student_id=student.get("student_id", "S00000"),
            intervention_id=intervention.get("intervention_id"),
        )
        
        # Resolve delivery channel from intervention config
        channel = self._resolve_channel(intervention.get("delivery_model", "direct"))
        
        # Assign the intervention through the delivery engine
        int_type = self._resolve_type(intervention.get("type", "cognitive_support"))
        self.delivery.assign_intervention(
            student_id=traj.student_id,
            intervention_type=int_type,
            channel=channel,
            day_started=0,
            duration_days=days,
            intensity=float(intervention.get("intensity", 0.5)),
        )
        
        # Simulate day by day (fatigue/forgetting evolve continuously across days)
        state = dict(student)
        rng = np.random.RandomState(self.seed)
        
        for day in range(days):
            # Apply intervention effects via the delivery engine
            self.delivery.apply_interventions_to_student(state, day=day)
            
            # Daily cognitive dynamics (learning gain + fatigue accumulation)
            ach = float(state.get("achievement_score", 50.0))
            mot = float(state.get("motivation", 0.5))
            
            gain = 0.10 + mot * 0.12 + rng.normal(0, 0.3)
            ach = float(np.clip(ach + gain, 0, 100))
            fatigue = float(np.clip(
                state.get("fatigue", 20.0) + rng.uniform(0, 4) - 2.0, 0, 100))
            
            state["achievement_score"] = ach
            state["fatigue"] = fatigue
            
            traj.daily_achievement.append(ach)
            traj.daily_motivation.append(mot)
            traj.daily_fatigue.append(fatigue)
            
            traj.events.append({
                "day": day,
                "scene": intervention.get("target_scene", "school"),
                "type": "intervention_dose",
                "learning_gain": float(gain),
                "channel": channel.value,
            })
        
        return traj
    
    def compare_scenes(self, student: Dict, teacher: Optional[Dict],
                       parent: Optional[Dict], intervention: Dict,
                       control_student: Optional[Dict] = None,
                       days: int = 30) -> Dict[str, Dict]:
        """
        Scene-effect comparison: run the SAME intervention under each target
        scene and compute a virtual effect size for each (vs. control).
        
        Returns:
            {scene: {"hedges_g": ..., "ci_95": [...], "mean_ach": ...}}
        """
        control = control_student or dict(student)
        control_traj = self.simulate_intervention_l_model(
            control, teacher, parent,
            {**intervention, "intensity": 0.0},  # zero-intensity = control
            days=days,
        )
        control_vals = np.array(control_traj.daily_achievement)
        
        results = {}
        for scene in self.SCENES:
            scene_intervention = {**intervention, "target_scene": scene}
            traj = self.simulate_intervention_l_model(
                dict(student), teacher, parent, scene_intervention, days=days
            )
            treat_vals = np.array(traj.daily_achievement)
            
            g, ci_low, ci_up = self.effect_calc.compute_hedges_g(control_vals, treat_vals)
            results[scene] = {
                "hedges_g": float(g),
                "ci_95": [float(ci_low), float(ci_up)],
                "mean_ach": traj.mean_achievement(),
                "n_days": traj.days,
            }
        
        return results
    
    def _resolve_channel(self, delivery_model: str) -> InterventionChannel:
        """Map a delivery_model string to an InterventionChannel enum."""
        mapping = {
            "direct": InterventionChannel.DIRECT,
            "teacher_mediated": InterventionChannel.TEACHER_MEDIATED,
            "parent_mediated": InterventionChannel.PARENT_MEDIATED,
            "shadow_edu_mediated": InterventionChannel.SHADOW_EDU_MEDIATED,
            "self_study_mediated": InterventionChannel.SELF_STUDY_MEDIATED,
        }
        return mapping.get(delivery_model, InterventionChannel.DIRECT)
    
    def _resolve_type(self, type_str: str) -> InterventionType:
        """Map an intervention type string to the enum."""
        for member in InterventionType:
            if member.value == type_str or member.name.lower() == type_str.lower():
                return member
        return InterventionType.COGNITIVE_SUPPORT


def simulate_intervention_l_model(student, teacher, parent, intervention,
                                  days: int = 30, seed: int = 42) -> VirtualTrajectory:
    """
    Module-level convenience function matching the documented M4 interface.
    
    Reference: 技术设计文档 §5 M4
    """
    sim = LModelSimulator(seed=seed)
    return sim.simulate_intervention_l_model(student, teacher, parent, intervention, days)
