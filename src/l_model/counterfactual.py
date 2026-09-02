"""
VirtualStudent Sandbox v6.0 - Counterfactual Engine

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


def _builtin_modification_effects() -> Dict[str, Dict]:
    return {
        "remove_shadow_edu": {"shadow_hours_multiplier": 0.0},
        "increase_parental_support": {"parent_support_delta": 0.3},
        "forbid_romance": {"romance_enabled": False},
        "switch_class": {"class_switch": True},
        "add_tutoring": {"tutoring_hours_delta": 3.0},
        "reduce_homework": {"homework_multiplier": 0.5},
    }


def _load_modification_effects() -> Dict[str, Dict]:
    """YAML-first counterfactual table; built-ins are the fallback and are
    merged under YAML-declared entries (single source of truth: config)."""
    effects = _builtin_modification_effects()
    try:
        from ..delivery.intervention_delivery import load_counterfactual_catalog
        for spec in load_counterfactual_catalog():
            key = spec.get("key")
            if key and isinstance(spec.get("effects"), dict):
                effects[key] = spec["effects"]
    except Exception:
        pass
    return effects


class CounterfactualEngine:
    """
    反事实轨迹分流引擎 (Counterfactual Trajectory Branching Engine).
    
    Guarantees:
      1. Identical starting point (deep-copied state)
      2. Fixed seed (both branches use the same RNG stream)
      3. Single-variable divergence (only the modification differs)
    """
    
    # Supported modification types and their default effects (YAML-first,
    # see _load_modification_effects; config/intervention_delivery.yaml is
    # the single source of truth).
    MODIFICATION_EFFECTS = _load_modification_effects()
    # Hard bounds keep researcher inputs in a plausible simulation range.
    CUSTOM_EFFECT_BOUNDS = {
        "achievement_rate_delta": (-0.2, 0.2),
        "motivation_delta": (-0.3, 0.3),
        "parent_support_delta": (-0.5, 0.5),
        "shadow_hours_multiplier": (0.0, 1.5),
        "tutoring_hours_delta": (-3.0, 4.0),
        "homework_multiplier": (0.5, 1.5),
        "fatigue_delta": (-20.0, 20.0),
        "stress_delta": (-20.0, 20.0),
        "emotion_delta": (-20.0, 20.0),
        "romance_enabled": (0.0, 1.0),
        "class_switch": (0.0, 1.0),
    }
    
    def __init__(self, max_branches: int = 5):
        self.max_branches = max_branches
        self._branches: Dict[str, Dict] = {}

    @classmethod
    def normalize_custom_effects(cls, effects: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clamp researcher inputs before they alter a state."""
        normalized = {}
        for key, value in (effects or {}).items():
            if key not in cls.CUSTOM_EFFECT_BOUNDS:
                raise ValueError(f"不支持的反事实变量: {key}")
            if key in ("romance_enabled", "class_switch"):
                normalized[key] = bool(value)
                continue
            try:
                number = float(value)
            except (TypeError, ValueError):
                raise ValueError(f"反事实变量 {key} 必须是数字")
            if not np.isfinite(number):
                raise ValueError(f"反事实变量 {key} 必须是有限数值")
            low, high = cls.CUSTOM_EFFECT_BOUNDS[key]
            normalized[key] = float(np.clip(number, low, high))
        return normalized

    @staticmethod
    def _apply_effects_to_student(student: Dict[str, Any], effects: Dict[str, Any]) -> None:
        """Apply bounded state changes shared by named and custom branches."""
        # Keep a persistent, interpretable daily treatment channel in addition
        # to the changed latent state. Without this, one-time wellbeing edits
        # are washed out by the daily random drift before they can affect
        # learning, making otherwise meaningful interventions look like no-ops.
        daily_bonus = float(student.get("_cf_daily_bonus", 0.0))
        if "shadow_hours_multiplier" in effects:
            old_hours = float(student.get("shadow_hours", 0.0))
            new_hours = float(np.clip(
                old_hours * effects["shadow_hours_multiplier"], 0, 8))
            student["shadow_hours"] = new_hours
            daily_bonus += (new_hours - old_hours) * 0.015
        if "parent_support_delta" in effects:
            support_delta = float(effects["parent_support_delta"])
            student["parent_support"] = float(np.clip(
                student.get("parent_support", 0.5) + support_delta, 0, 1))
            daily_bonus += support_delta * 0.10
        if "romance_enabled" in effects:
            student["romance_enabled"] = bool(effects["romance_enabled"])
        if "tutoring_hours_delta" in effects:
            tutoring_delta = float(effects["tutoring_hours_delta"])
            student["tutoring_hours"] = float(np.clip(
                student.get("tutoring_hours", 0.0) + tutoring_delta, 0, 8))
            daily_bonus += tutoring_delta * 0.012
        if "homework_multiplier" in effects:
            old_homework = float(student.get("homework_load", 1.0))
            new_homework = float(np.clip(
                old_homework * effects["homework_multiplier"], 0.3, 2.0))
            student["homework_load"] = new_homework
            daily_bonus += (new_homework - old_homework) * 0.04
        # This is a rate applied on each simulated day, not a one-time score jump.
        if "achievement_rate_delta" in effects:
            student["_cf_achievement_rate_delta"] = float(effects["achievement_rate_delta"])
        # Backward compatibility for persisted experiments using the old key.
        if "achievement_delta" in effects:
            student["_cf_achievement_rate_delta"] = float(np.clip(effects["achievement_delta"], -0.2, 0.2))
        if "motivation_delta" in effects:
            motivation_delta = float(effects["motivation_delta"])
            student["motivation"] = float(np.clip(
                student.get("motivation", 0.5) + motivation_delta, 0, 1))
            daily_bonus += motivation_delta * 0.20
        for state_key in ("fatigue", "stress", "emotion"):
            delta_key = f"{state_key}_delta"
            if delta_key in effects:
                state_delta = float(effects[delta_key])
                student[state_key] = float(np.clip(
                    student.get(state_key, 0.0) + state_delta, 0, 100))
                # Lower fatigue/stress and higher emotion improve effective
                # learning over the whole branch, not just on day one.
                direction = -1.0 if state_key in ("fatigue", "stress") else 1.0
                scale = {"fatigue": 0.003, "stress": 0.002, "emotion": 0.002}[state_key]
                daily_bonus += direction * state_delta * scale
        student["_cf_daily_bonus"] = float(np.clip(daily_bonus, -0.25, 0.25))
    
    def _branch_daily(self, baseline_state: SimulationState,
                      modification: Callable[[SimulationState], SimulationState],
                      days: int, seed: int = 42) -> Tuple[Dict[str, List[Dict]], Dict[str, List[Dict]]]:
        """Run both cloned branches once and retain per-student daily states."""
        base_state = baseline_state.clone()
        mod_state = modification(baseline_state.clone())
        return (
            self._simulate_branch(base_state, days, seed),
            self._simulate_branch(mod_state, days, seed),
        )

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
        base_daily, mod_daily = self._branch_daily(baseline_state, modification, days, seed)
        
        # Compare cohort-averaged trajectories (average treatment effect) so the
        # result is robust rather than dependent on a single arbitrary student.
        base_traj = Trajectory.from_cohort("cohort", base_daily)
        mod_traj = Trajectory.from_cohort("cohort", mod_daily)
        
        return base_traj, mod_traj

    def branch_for_student(self, baseline_state: SimulationState,
                           modification: Callable[[SimulationState], SimulationState],
                           days: int, seed: int, student_id: str) -> Tuple[Trajectory, Trajectory]:
        """Return baseline/modified trajectories for one student only."""
        if student_id not in baseline_state.students:
            raise ValueError(f"学生 {student_id} 不存在")
        base_daily, mod_daily = self._branch_daily(baseline_state, modification, days, seed)
        return (
            Trajectory.from_states(student_id, base_daily[student_id]),
            Trajectory.from_states(student_id, mod_daily[student_id]),
        )
    
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
        
        for student in state.students.values():
            self._apply_effects_to_student(student, effects)
        
        # Class switch: reshuffle network edges
        if effects.get("class_switch"):
            rng = np.random.RandomState(state.seed)
            for edge in state.network_edges:
                if rng.random() < 0.5:
                    edge["weight"] = float(rng.uniform(0.1, 0.5))
        
        return state
    
    def apply_custom_effects(self, state, effects):
        """Apply researcher-supplied counterfactual effects."""
        effects = self.normalize_custom_effects(effects)
        for student in state.students.values():
            self._apply_effects_to_student(student, effects)
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
                fatigue = float(s.get("fatigue", 30.0))
                stress = float(s.get("stress", 30.0))
                emotion = float(s.get("emotion", 55.0))
                
                # Daily gain model: base growth + modifiers + noise
                gain = 0.10
                gain += mot * 0.15
                gain += support * 0.10
                gain += min(shadow, 6.0) * 0.02
                gain += min(tutoring, 6.0) * 0.03
                gain += min(homework, 2.0) * 0.05       # homework practice effect
                gain += peer_support[sid] * 0.10        # peer/network effect
                # Wellbeing variables are part of the causal path as well:
                # lower fatigue/stress and higher emotion should translate
                # into a modest but measurable learning-gain difference.
                gain += (emotion - 50.0) * 0.001
                gain -= stress * 0.0005
                gain -= fatigue * 0.0003
                gain += float(s.get("_cf_achievement_rate_delta", 0.0))
                # Learning has diminishing returns near the 0-100 ceiling;
                # use the same headroom to scale signal and noise.
                headroom = float(np.clip((100.0 - ach) / 40.0, 0.08, 1.0))
                # Heterogeneous response: students with more motivation and
                # headroom can realize more of the same intervention dose.
                self_efficacy = float((s.get("simulation_vector") or {}).get("self_efficacy", 0.5))
                responsiveness = float(np.clip(
                    0.65 + mot * 0.45 + self_efficacy * 0.20 + headroom * 0.20,
                    0.65, 1.35))
                gain += float(s.get("_cf_daily_bonus", 0.0)) * responsiveness
                if romance_off:
                    gain += 0.05  # time reallocated to study

                # Scale both signal and noise by remaining headroom so a
                # tutoring change cannot jump a student straight to 100.
                ach = float(np.clip(
                    ach + gain * headroom + rng.normal(0, 0.35 * headroom + 0.04),
                    0, 100))
                fatigue = float(np.clip(
                    fatigue + rng.uniform(0, 5)
                    - shadow * 0.5 + homework * 1.5, 0, 100))
                stress = float(np.clip(
                    stress + rng.uniform(-2, 4), 0, 100))
                emotion = float(np.clip(
                    emotion + rng.uniform(-3, 3), 0, 100))
                
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
        
        # ANCOVA-adjusted effect size using early trajectory as baseline covariate
        ancova_g, ancova_ci_lo, ancova_ci_hi, ancova_diff = 0.0, 0.0, 0.0, 0.0
        try:
            n_pts = min(len(base_vals), len(mod_vals))
            if n_pts >= 6:
                split = max(1, n_pts // 3)
                base_pre = base_vals[:split]
                base_post = base_vals[split:]
                mod_pre = mod_vals[:split]
                mod_post = mod_vals[split:]
                from ..delivery.intervention_delivery import VirtualEffectSizeCalculator
                ancova_g, ancova_ci_lo, ancova_ci_hi, ancova_diff = (
                    VirtualEffectSizeCalculator.compute_ancova_g(
                        base_pre, base_post, mod_pre, mod_post))
        except Exception:
            pass

        return {
            "baseline_mean": float(np.mean(base_vals)),
            "modified_mean": float(np.mean(mod_vals)),
            "baseline_final": float(base_vals[-1]),
            "modified_final": float(mod_vals[-1]),
            "final_delta": float(mod_vals[-1] - base_vals[-1]),
            "average_delta": float(np.mean(mod_vals) - np.mean(base_vals)),
            "effect_size_g": float(g),
            "ci_95": [float(ci_low), float(ci_up)],
            "trajectory_baseline": base_vals.tolist(),
            "trajectory_modified": mod_vals.tolist(),
            "ancova_g": float(ancova_g),
            "ancova_ci_95": [float(ancova_ci_lo), float(ancova_ci_hi)],
            "ancova_adjusted_diff": float(ancova_diff),
        }
    
    def create_run(self, baseline_state: SimulationState,
                   modification: Any, days: int, seed: int = 42,
                   custom_effects: Optional[Dict[str, Any]] = None,
                   student_id: Optional[str] = None) -> Dict[str, Any]:
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
        if custom_effects:
            normalized_effects = self.normalize_custom_effects(custom_effects)
            mod_desc = {"custom_effects": normalized_effects}
            def mod_fn(state, _eff=normalized_effects):
                return self.apply_custom_effects(state, _eff)
        elif callable(modification):
            mod_fn = modification
            mod_desc = {"custom": True}
        elif isinstance(modification, dict):
            mod_desc = modification
            names = [k for k, v in modification.items() if v]
            def mod_fn(state, _names=names):
                for n in _names:
                    state = self.apply_named_modification(state, n)
                return state
        else:
            mod_fn = lambda s: s
            mod_desc = {"none": True}
        
        base_daily, mod_daily = self._branch_daily(baseline_state, mod_fn, days, seed)
        if student_id:
            if student_id not in baseline_state.students:
                raise ValueError(f"学生 {student_id} 不存在")
            base_traj = Trajectory.from_states(student_id, base_daily[student_id])
            mod_traj = Trajectory.from_states(student_id, mod_daily[student_id])
        else:
            base_traj = Trajectory.from_cohort("cohort", base_daily)
            mod_traj = Trajectory.from_cohort("cohort", mod_daily)
        comparison = self.compare(base_traj, mod_traj)
        comparison["scope"] = "student" if student_id else "cohort"
        comparison["student_id"] = student_id
        
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
