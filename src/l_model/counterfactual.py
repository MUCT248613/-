"""
VirtualStudent Sandbox v5.0 - Counterfactual Engine

Implements §4.8 反事实实验引擎 (Counterfactual Experiment Engine).

Core idea: from an IDENTICAL starting state, run two branches —
a baseline and a modified variant — using a FIXED random seed so that
the only difference between the two trajectories is the modification
itself. This enables "what-if" questions such as:
  - "如果家长选择引导而非压制" (if parents guided rather than suppressed)
  - "如果禁止恋爱" (if romance were forbidden)
  - "如果换班" (if the student switched classes)

Reference: 技术设计文档 §4.8, §5 M4, §6 counterfactual_runs table
"""
import copy
import uuid
from typing import Callable, Dict, List, Tuple, Any, Optional

import numpy as np


class SimulationState:
    """
    A snapshot of the full simulation state at a point in time.
    Deep-copyable so that branches diverge from an identical origin.
    """
    
    def __init__(self, students: Dict[str, Dict], day: int = 0,
                 network_edges: Optional[List[Dict]] = None,
                 relationships: Optional[List[Dict]] = None,
                 seed: int = 42):
        self.students = students          # student_id -> state dict
        self.day = day
        self.network_edges = network_edges or []
        self.relationships = relationships or []
        self.seed = seed
    
    def clone(self) -> "SimulationState":
        """Deep copy for branching"""
        return SimulationState(
            students=copy.deepcopy(self.students),
            day=self.day,
            network_edges=copy.deepcopy(self.network_edges),
            relationships=copy.deepcopy(self.relationships),
            seed=self.seed,
        )


class Trajectory:
    """A single simulation trajectory (sequence of daily states)."""
    
    def __init__(self, state: SimulationState):
        self.student_id = None
        self.days: List[int] = []
        self.achievement: List[float] = []
        self.motivation: List[float] = []
        self.fatigue: List[float] = []
        self.stress: List[float] = []
        self.emotion: List[float] = []
    
    @classmethod
    def from_states(cls, student_id: str, daily_states: List[Dict]) -> "Trajectory":
        """Build a trajectory from a list of daily state dicts"""
        traj = cls(None)
        traj.student_id = student_id
        for i, s in enumerate(daily_states):
            traj.days.append(i)
            traj.achievement.append(float(s.get("achievement_score", 0.0)))
            traj.motivation.append(float(s.get("motivation", 0.0)))
            traj.fatigue.append(float(s.get("fatigue", 0.0)))
            traj.stress.append(float(s.get("stress", 0.0)))
            traj.emotion.append(float(s.get("emotion", 0.0)))
        return traj

    @classmethod
    def from_cohort(cls, label: str, daily_by_student: Dict[str, List[Dict]]) -> "Trajectory":
        """
        Build a cohort-averaged trajectory (mean across all students per day).

        Using the cohort mean (average treatment effect) instead of a single
        representative student makes the baseline-vs-modified comparison robust:
        a modification shows up as long as it affects any subset of students,
        rather than depending on the arbitrary first student's circumstances.
        """
        traj = cls(None)
        traj.student_id = label
        if not daily_by_student:
            return traj
        sids = list(daily_by_student.keys())
        n_days = min(len(daily_by_student[s]) for s in sids)
        metric_keys = [
            ("achievement", "achievement_score"),
            ("motivation", "motivation"),
            ("fatigue", "fatigue"),
            ("stress", "stress"),
            ("emotion", "emotion"),
        ]
        for d in range(n_days):
            traj.days.append(d)
            for attr, key in metric_keys:
                vals = [float(daily_by_student[s][d].get(key, 0.0)) for s in sids]
                getattr(traj, attr).append(float(np.mean(vals)))
        return traj
    
    def mean(self, metric: str = "achievement") -> float:
        values = getattr(self, metric, [])
        return float(np.mean(values)) if values else 0.0


class CounterfactualEngine:
    """
    反事实轨迹分流引擎 (Counterfactual Trajectory Branching Engine).
    
    Guarantees:
      1. Identical starting point (deep-copied state)
      2. Fixed seed (both branches use the same RNG stream)
      3. Single-variable divergence (only the modification differs)
    """
    
    # Supported modification types and their default effects
    MODIFICATION_EFFECTS = {
        "remove_shadow_edu": {"shadow_hours_multiplier": 0.0},
        "increase_parental_support": {"parent_support_delta": 0.3},
        "forbid_romance": {"romance_enabled": False},
        "switch_class": {"class_switch": True},
        "add_tutoring": {"tutoring_hours_delta": 3.0},
        "reduce_homework": {"homework_multiplier": 0.5},
    }
    
    def __init__(self, max_branches: int = 5):
        self.max_branches = max_branches
        self._branches: Dict[str, Dict] = {}
    
    def branch(self, baseline_state: SimulationState,
               modification: Callable[[SimulationState], SimulationState],
               days: int, seed: int = 42) -> Tuple[Trajectory, Trajectory]:
        """
        Run baseline and modified branches from the same origin.
        
        Args:
            baseline_state: Starting simulation state (will be cloned)
            modification: Function that mutates a cloned state
            days: Number of days to simulate
            seed: Fixed random seed for reproducibility
        
        Returns:
            (baseline_trajectory, modified_trajectory)
        """
        # Clone so both branches start from an identical origin
        base_state = baseline_state.clone()
        mod_state = baseline_state.clone()
        
        # Apply the modification ONLY to the modified branch
        mod_state = modification(mod_state)
        
        # Simulate both with the same seed
        base_daily = self._simulate_branch(base_state, days, seed)
        mod_daily = self._simulate_branch(mod_state, days, seed)
        
        # Compare cohort-averaged trajectories (average treatment effect) so the
        # result is robust rather than dependent on a single arbitrary student.
        base_traj = Trajectory.from_cohort("cohort", base_daily)
        mod_traj = Trajectory.from_cohort("cohort", mod_daily)
        
        return base_traj, mod_traj
    
    def branch_by_name(self, baseline_state: SimulationState,
                       modification_name: str, days: int,
                       seed: int = 42) -> Tuple[Trajectory, Trajectory]:
        """Branch using a named, predefined modification."""
        def modifier(state: SimulationState) -> SimulationState:
            return self.apply_named_modification(state, modification_name)
        return self.branch(baseline_state, modifier, days, seed)
    
    def apply_named_modification(self, state: SimulationState,
                                 name: str) -> SimulationState:
        """Apply a predefined modification by name to a state."""
        effects = self.MODIFICATION_EFFECTS.get(name, {})
        
        for sid, student in state.students.items():
            if "shadow_hours_multiplier" in effects:
                student["shadow_hours"] = (
                    student.get("shadow_hours", 0.0) * effects["shadow_hours_multiplier"]
                )
            if "parent_support_delta" in effects:
                student["parent_support"] = min(
                    1.0, student.get("parent_support", 0.5) + effects["parent_support_delta"]
                )
            if "romance_enabled" in effects and not effects["romance_enabled"]:
                student["romance_enabled"] = False
            if "tutoring_hours_delta" in effects:
                student["tutoring_hours"] = (
                    student.get("tutoring_hours", 0.0) + effects["tutoring_hours_delta"]
                )
            if "homework_multiplier" in effects:
                student["homework_load"] = (
                    student.get("homework_load", 1.0) * effects["homework_multiplier"]
                )
        
        # Class switch: reshuffle network edges
        if effects.get("class_switch"):
            rng = np.random.RandomState(state.seed)
            for edge in state.network_edges:
                if rng.random() < 0.5:
                    edge["weight"] = float(rng.uniform(0.1, 0.5))
        
        return state
    
    def _simulate_branch(self, state: SimulationState, days: int,
                         seed: int) -> Dict[str, List[Dict]]:
        """
        Lightweight deterministic simulation of a branch.
        Returns student_id -> list of daily state dicts.
        """
        rng = np.random.RandomState(seed)
        daily: Dict[str, List[Dict]] = {sid: [] for sid in state.students}
        
        # Local mutable copy of student states
        current = {sid: dict(s) for sid, s in state.students.items()}
        
        # Per-student peer support derived from the social network (mean weight
        # of incident edges). This lets the `switch_class` modification — which
        # reshuffles network edge weights — actually influence the trajectory.
        peer_sum = {sid: 0.0 for sid in current}
        peer_cnt = {sid: 0 for sid in current}
        for e in state.network_edges:
            w = float(e.get("weight", 0.0))
            for key in ("source", "target"):
                node = e.get(key)
                if node in peer_sum:
                    peer_sum[node] += w
                    peer_cnt[node] += 1
        peer_support = {
            sid: (peer_sum[sid] / peer_cnt[sid] if peer_cnt[sid] else 0.0)
            for sid in current
        }
        
        for day in range(days):
            for sid, s in current.items():
                ach = float(s.get("achievement_score", 50.0))
                mot = float(s.get("motivation", 0.5))
                support = float(s.get("parent_support", 0.5))
                shadow = float(s.get("shadow_hours", 0.0))
                tutoring = float(s.get("tutoring_hours", 0.0))
                homework = float(s.get("homework_load", 1.0))
                romance_off = not s.get("romance_enabled", True)
                
                # Daily gain model: base growth + modifiers + noise
                gain = 0.10
                gain += mot * 0.15
                gain += support * 0.10
                gain += min(shadow, 6.0) * 0.02
                gain += min(tutoring, 6.0) * 0.03
                gain += min(homework, 2.0) * 0.05       # homework practice effect
                gain += peer_support[sid] * 0.10        # peer/network effect
                if romance_off:
                    gain += 0.05  # time reallocated to study
                
                ach = min(100.0, ach + gain + rng.normal(0, 0.5))
                fatigue = float(np.clip(
                    s.get("fatigue", 30.0) + rng.uniform(0, 5)
                    - shadow * 0.5 + homework * 1.5, 0, 100))
                stress = float(np.clip(
                    s.get("stress", 30.0) + rng.uniform(-2, 4), 0, 100))
                emotion = float(np.clip(
                    s.get("emotion", 55.0) + rng.uniform(-3, 3), 0, 100))
                
                s.update({
                    "achievement_score": ach,
                    "fatigue": fatigue,
                    "stress": stress,
                    "emotion": emotion,
                })
                
                daily[sid].append({
                    "achievement_score": ach,
                    "motivation": mot,
                    "fatigue": fatigue,
                    "stress": stress,
                    "emotion": emotion,
                })
        
        return daily
    
    def compare(self, base_traj: Trajectory, mod_traj: Trajectory,
                metric: str = "achievement") -> Dict[str, Any]:
        """
        Compare two trajectories and compute effect size.
        
        Returns a comparison dict suitable for the API / counterfactual_runs table.
        """
        from ..delivery.intervention_delivery import VirtualEffectSizeCalculator
        
        base_vals = np.array(getattr(base_traj, metric, []))
        mod_vals = np.array(getattr(mod_traj, metric, []))
        
        if len(base_vals) == 0 or len(mod_vals) == 0:
            return {"effect_size_g": 0.0, "ci_95": [0.0, 0.0]}
        
        g, ci_low, ci_up = VirtualEffectSizeCalculator.compute_hedges_g(base_vals, mod_vals)
        
        return {
            "baseline_mean": float(np.mean(base_vals)),
            "modified_mean": float(np.mean(mod_vals)),
            "effect_size_g": float(g),
            "ci_95": [float(ci_low), float(ci_up)],
            "trajectory_baseline": base_vals.tolist(),
            "trajectory_modified": mod_vals.tolist(),
        }
    
    def create_run(self, baseline_state: SimulationState,
                   modification: Any, days: int, seed: int = 42) -> Dict[str, Any]:
        """
        High-level API: create a full counterfactual run record.
        
        Args:
            modification: Either a callable OR a dict of named modifications
                          (e.g. {"remove_shadow_edu": True})
        
        Returns:
            A counterfactual_runs record dict (cf_id, modification, comparison).
        """
        cf_id = f"CF_{uuid.uuid4().hex[:8].upper()}"
        
        # Normalize modification to a callable
        if callable(modification):
            mod_fn = modification
            mod_desc = {"custom": True}
        elif isinstance(modification, dict):
            mod_desc = modification
            # Build a combined modifier from named flags
            names = [k for k, v in modification.items() if v]
            def mod_fn(state, _names=names):
                for n in _names:
                    state = self.apply_named_modification(state, n)
                return state
        else:
            mod_fn = lambda s: s
            mod_desc = {"none": True}
        
        base_traj, mod_traj = self.branch(baseline_state, mod_fn, days, seed)
        comparison = self.compare(base_traj, mod_traj)
        
        record = {
            "cf_id": cf_id,
            "base_run_id": None,
            "branch_run_id": None,
            "modification_json": mod_desc,
            "comparison_json": comparison,
        }
        self._branches[cf_id] = record
        return record
    
    def get_run(self, cf_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a stored counterfactual run record."""
        return self._branches.get(cf_id)
