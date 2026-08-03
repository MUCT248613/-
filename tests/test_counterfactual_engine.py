"""
Unit tests for the Counterfactual Experiment Engine (技术设计文档 §4.8).

These tests lock in the business-logic guarantee that EVERY named modification
actually changes the simulated trajectory. A previous defect left several
modifications as silent no-ops (the demo state lacked the L-Model fields the
engine mutates, and the simulation ignored homework / network effects), so the
baseline and modified branches were identical. This suite fails if any
modification regresses to a zero-effect no-op.

Run:
    python -m pytest tests/test_counterfactual_engine.py -q
"""
import copy
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.l_model.counterfactual import (
    CounterfactualEngine,
    SimulationState,
    Trajectory,
)


def build_state(n: int = 20, seed: int = 42) -> SimulationState:
    """Build a SimulationState populated with every L-Model field the engine
    mutates, so each named modification has something to act on."""
    rng = np.random.RandomState(seed)
    students = {}
    for i in range(n):
        sid = f"S{i:05d}"
        students[sid] = {
            "student_id": sid,
            "achievement_score": float(np.clip(rng.normal(60, 12), 0, 100)),
            "motivation": float(np.clip(rng.normal(0.5, 0.15), 0, 1)),
            "parent_support": float(np.clip(rng.normal(0.5, 0.15), 0, 0.9)),
            "shadow_hours": float(np.clip(rng.normal(3.0, 1.2), 0.5, 8)),
            "tutoring_hours": float(np.clip(rng.normal(1.5, 1.0), 0, 6)),
            "romance_enabled": True,
            "homework_load": float(np.clip(rng.normal(1.0, 0.2), 0.4, 2.0)),
            "fatigue": float(np.clip(rng.normal(40, 8), 0, 100)),
            "stress": float(np.clip(rng.normal(45, 10), 0, 100)),
            "emotion": float(np.clip(rng.normal(55, 8), 0, 100)),
        }

    # A small social network so `switch_class` has edges to reshuffle.
    edges = []
    ids = list(students)
    erng = np.random.RandomState(seed + 1)
    for _ in range(n * 2):
        a, b = erng.choice(n, 2, replace=False)
        edges.append({
            "source": ids[int(a)],
            "target": ids[int(b)],
            "weight": float(erng.uniform(0.3, 0.9)),
        })

    return SimulationState(students=students, network_edges=edges, seed=seed)


ALL_MODS = [
    "remove_shadow_edu",
    "increase_parental_support",
    "forbid_romance",
    "switch_class",
    "add_tutoring",
    "reduce_homework",
]


@pytest.mark.parametrize("modification", ALL_MODS)
def test_each_modification_has_real_effect(modification):
    """Every named modification must change the cohort trajectory.

    Guards against the no-op regression where baseline == modified exactly.
    """
    engine = CounterfactualEngine()
    state = build_state()

    record = engine.create_run(
        baseline_state=state,
        modification={modification: True},
        days=30,
        seed=42,
    )
    cmp = record["comparison_json"]

    base = np.array(cmp["trajectory_baseline"])
    mod = np.array(cmp["trajectory_modified"])

    assert len(base) == 30 and len(mod) == 30, "trajectory length mismatch"
    # The two branches must NOT be identical -> the modification did something.
    assert not np.allclose(base, mod), (
        f"modification '{modification}' had ZERO effect "
        f"(baseline == modified); the intervention is a silent no-op"
    )
    assert cmp["baseline_mean"] != cmp["modified_mean"], (
        f"modification '{modification}' produced identical means"
    )


def test_determinism_same_seed():
    """Same seed + same modification => identical trajectories (reproducible)."""
    engine = CounterfactualEngine()

    r1 = engine.create_run(build_state(), {"add_tutoring": True}, days=20, seed=7)
    r2 = engine.create_run(build_state(), {"add_tutoring": True}, days=20, seed=7)

    assert r1["comparison_json"]["trajectory_modified"] == \
        r2["comparison_json"]["trajectory_modified"]
    assert r1["comparison_json"]["trajectory_baseline"] == \
        r2["comparison_json"]["trajectory_baseline"]


def test_identical_origin_guarantee():
    """Branching must not mutate the caller's baseline state (deep clone)."""
    engine = CounterfactualEngine()
    state = build_state()
    snapshot = copy.deepcopy(state.students)

    engine.create_run(state, {"remove_shadow_edu": True}, days=10, seed=42)

    # The original state must be untouched after branching.
    assert state.students == snapshot, "branching mutated the baseline state"


def test_direction_of_effects():
    """Sanity-check the causal direction of well-understood interventions."""
    engine = CounterfactualEngine()

    # Adding tutoring hours should raise cohort achievement.
    up = engine.create_run(build_state(), {"add_tutoring": True}, days=30, seed=42)
    assert up["comparison_json"]["modified_mean"] > \
        up["comparison_json"]["baseline_mean"], "add_tutoring should increase achievement"

    # Removing shadow education should lower cohort achievement.
    down = engine.create_run(build_state(), {"remove_shadow_edu": True}, days=30, seed=42)
    assert down["comparison_json"]["modified_mean"] < \
        down["comparison_json"]["baseline_mean"], "remove_shadow_edu should decrease achievement"


def test_comparison_output_shape():
    """The comparison dict must carry the fields the API / DB table expect."""
    engine = CounterfactualEngine()
    record = engine.create_run(build_state(), {"reduce_homework": True}, days=15, seed=42)

    cmp = record["comparison_json"]
    for key in ("baseline_mean", "modified_mean", "effect_size_g", "ci_95",
                "trajectory_baseline", "trajectory_modified"):
        assert key in cmp, f"missing comparison field: {key}"

    assert isinstance(cmp["ci_95"], list) and len(cmp["ci_95"]) == 2
    assert cmp["ci_95"][0] <= cmp["ci_95"][1], "CI bounds inverted"
    assert record["cf_id"].startswith("CF_")


def test_get_run_roundtrip():
    """Created runs must be retrievable by cf_id."""
    engine = CounterfactualEngine()
    record = engine.create_run(build_state(), {"forbid_romance": True}, days=10, seed=42)
    fetched = engine.get_run(record["cf_id"])
    assert fetched is not None
    assert fetched["cf_id"] == record["cf_id"]
    assert engine.get_run("CF_DOES_NOT_EXIST") is None
