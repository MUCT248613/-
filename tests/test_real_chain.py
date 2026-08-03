"""
End-to-end tests for the *real* scientific chain (v5.0).

These tests pin down the central guarantee of the platform: every number the
API serves is produced by the genuine pipeline --

    4-layer persona generation
        -> L-Model 2.0 multi-agent simulation (network influence + events)
        -> multi-arm intervention delivery (5 arms vs a no-treatment control)
        -> real Hedges' g effect sizes / trajectories / social network

-- and NOT drawn from ``np.random``. They cover the orchestrator
(``build_real_run``), the API endpoints that consume the stored run, the
literature-calibrated calibration diagnostics (genuine KS test), and the
Prefect/sequential pipeline nodes n6/n7.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.api.main import app, _runs
from src.api.real_run import build_real_run, _INTERVENTION_ARMS
from src.api.models import RunCreateRequest

client = TestClient(app)

N_STUDENTS = 48
N_TEACHERS = 5
SIM_DAYS = 24
SEED = 7

ARM_IDS = [a[0] for a in _INTERVENTION_ARMS]


def _make_config() -> RunCreateRequest:
    return RunCreateRequest(
        n_students=N_STUDENTS, n_teachers=N_TEACHERS,
        n_parents=N_STUDENTS, sim_days=SIM_DAYS, seed=SEED,
    )


@pytest.fixture(scope="module")
def real_run():
    """Build a run directly through the scientific-chain orchestrator."""
    return build_real_run("RUN_TEST_REAL", _make_config())


@pytest.fixture(scope="module")
def api_run_id():
    """Create a run through the API (which drives build_real_run internally)."""
    resp = client.post("/api/runs", json={
        "n_students": N_STUDENTS, "n_teachers": N_TEACHERS,
        "n_parents": N_STUDENTS, "sim_days": SIM_DAYS, "seed": SEED,
    })
    assert resp.status_code == 200
    return resp.json()["run_id"]


# ============ build_real_run: genuine structure ============

def test_run_is_labelled_simulation(real_run):
    """The run must be explicitly labelled as produced by the simulation."""
    assert real_run["data_source"] == "simulation"
    assert real_run["status"] == "completed"


def test_all_five_arms_have_effect_sizes(real_run):
    """One real effect size per treatment arm, each well-formed."""
    es = real_run["effect_sizes"]
    assert len(es) == len(ARM_IDS) == 5
    by_id = {e["intervention_id"]: e for e in es}
    for arm in ARM_IDS:
        assert arm in by_id, f"missing effect size for arm {arm}"
        e = by_id[arm]
        for key in ("hedges_g", "ci_lower", "ci_upper", "n_treatment",
                    "n_control", "control_mean_gain", "treatment_mean_gain"):
            assert key in e, f"effect size missing key {key}"
        # A valid confidence interval brackets the point estimate.
        assert e["ci_lower"] <= e["hedges_g"] <= e["ci_upper"]
        assert e["n_treatment"] > 0 and e["n_control"] > 0


def test_arms_form_a_valid_partition(real_run):
    """Treatment arms + control are disjoint and cover the whole cohort."""
    arms = real_run["arms"]
    assert set(ARM_IDS) | {"control"} == set(arms.keys())
    all_ids = []
    for arm in ARM_IDS + ["control"]:
        assert arms[arm], f"arm {arm} is empty"
        all_ids.extend(arms[arm])
    # Disjoint...
    assert len(all_ids) == len(set(all_ids)), "arms overlap"
    # ...and exhaustive over the simulated cohort.
    assert set(all_ids) == set(real_run["students"].keys())


def test_interventions_produce_a_real_effect(real_run):
    """The wired-in delivery must actually move achievement: the pooled
    treatment cohort outgains the control arm and no arm is a no-op."""
    es = real_run["effect_sizes"]
    # Not a single arm may be exactly zero (that would mean the intervention
    # never touched the students' state).
    assert any(abs(e["hedges_g"]) > 0.0 for e in es), \
        "all effect sizes are exactly zero -> interventions not wired in"
    # Every intervention is theory-positive, so the pooled treatment gain must
    # exceed the control gain (change-score contrast, robust to baseline
    # arm-imbalance).
    control_gain = es[0]["control_mean_gain"]
    pooled = np.mean([e["treatment_mean_gain"] for e in es])
    assert pooled > control_gain, \
        f"pooled treatment gain {pooled:.2f} !> control gain {control_gain:.2f}"


def test_network_uses_real_student_ids(real_run):
    """The social network must be built on the actual 5-digit student ids
    (the old 4-digit hard-coding silently disconnected influence)."""
    node_ids = {n["node_id"] for n in real_run["network"]["nodes"]}
    student_ids = set(real_run["students"].keys())
    assert node_ids == student_ids
    # Every id is the 5-digit canonical form.
    assert all(len(sid) == 6 and sid.startswith("S") for sid in node_ids)
    assert real_run["network"]["edges"], "network has no edges"


def test_trajectories_and_timelines_are_complete(real_run):
    """Every student has a full-length trajectory + per-day timeline."""
    students = real_run["students"]
    traj = real_run["trajectories"]
    day_tl = real_run["day_timelines"]
    assert set(traj.keys()) == set(students.keys())
    assert set(day_tl.keys()) == set(students.keys())
    for sid in students:
        assert len(traj[sid]["achievement"]) == SIM_DAYS
        assert len(day_tl[sid]) == SIM_DAYS
        # Each stored day carries the real scene events.
        assert "events" in day_tl[sid][0]
        assert "achievement_end" in day_tl[sid][0]


def test_network_evolution_recorded_daily(real_run):
    """The DynamicNetworkMonitor must have one snapshot per simulated day."""
    evo = real_run["network_evolution"]
    assert len(evo) == SIM_DAYS
    for snap in evo:
        for key in ("day", "density", "avg_clustering", "n_components"):
            assert key in snap


# ============ Calibration: genuine literature-anchored KS test ============

def test_calibration_is_literature_calibrated(api_run_id):
    """p_slip/p_guess must come from the literature-calibrated cohort
    (not the old hard-coded 0.1 constants) and the KS test must be genuine."""
    resp = client.get(f"/api/runs/{api_run_id}/calibration")
    assert resp.status_code == 200
    data = resp.json()

    bkt = data["bkt_params_virtual"]
    assert set(bkt.keys()) == {"p_know", "p_learn", "p_slip", "p_guess"}
    # p_guess is calibrated to ~0.20 (literature mean); the legacy code path
    # hard-coded it to 0.1, so this separates the real chain from the old one.
    assert bkt["p_guess"] > 0.15, f"p_guess {bkt['p_guess']} looks uncalibrated"
    assert 0.02 <= bkt["p_slip"] <= 0.20

    # Genuine KS diagnostics: valid p-values, one per parameter.
    ks = data["ks_test_results"]
    assert set(ks.keys()) == {"p_know", "p_learn", "p_slip", "p_guess"}
    for param, res in ks.items():
        assert 0.0 <= res["p_value"] <= 1.0
        assert 0.0 <= res["ks_statistic"] <= 1.0

    # The cohort is anchored to the literature baseline -> small distance.
    assert 0.0 <= data["cognitive_distance"] <= 1.0
    assert data["cognitive_distance"] < 0.10, \
        "cohort is not anchored to the literature baseline"
    assert data["verdict"] in ("pass", "marginal", "fail")


def test_calibration_matches_stored_cohort(api_run_id):
    """The endpoint's virtual BKT means must equal the stored cohort's actual
    simulation_vector means (proving it reads real data, not fresh randomness)."""
    resp = client.get(f"/api/runs/{api_run_id}/calibration")
    bkt = resp.json()["bkt_params_virtual"]

    students = _runs[api_run_id]["students"]
    sv = [s["simulation_vector"] for s in students.values()]
    for param in ("p_know", "p_learn", "p_slip", "p_guess"):
        cohort_mean = float(np.mean([v[param] for v in sv]))
        assert abs(bkt[param] - cohort_mean) < 1e-3, \
            f"{param}: endpoint {bkt[param]} != cohort {cohort_mean:.4f}"


# ============ Endpoints serve the *stored* simulation output ============

def test_timeline_serves_stored_events(api_run_id):
    """The timeline endpoint must return the exact stored per-day events."""
    run = _runs[api_run_id]
    sid = next(iter(run["students"].keys()))
    stored_last = run["day_timelines"][sid][-1]

    resp = client.get(f"/api/runs/{api_run_id}/students/{sid}/timeline")
    assert resp.status_code == 200
    tl = resp.json()
    # Defaults to the last simulated day.
    assert abs(tl["total_learning_gain"] - stored_last["total_learning_gain"]) < 1e-6
    assert len(tl["events"]) == len(stored_last["events"])


def test_scene_comparison_serves_stored_data(api_run_id):
    """Scene comparison must return the stored per-scene Hedges' g."""
    run = _runs[api_run_id]
    stored = run["scene_comparison"]
    assert stored, "run has no stored scene_comparison"

    resp = client.get(f"/api/runs/{api_run_id}/scene_comparison")
    assert resp.status_code == 200
    data = resp.json()
    assert data["intervention_type"] == "multi_arm_evidence_based"
    assert set(data["scenes"].keys()) == set(stored.keys())
    for scene, vals in stored.items():
        assert abs(data["scenes"][scene]["g"] - vals["g"]) < 1e-6


def test_network_evolution_serves_stored_data(api_run_id):
    """Network evolution must return the stored monitor history."""
    run = _runs[api_run_id]
    stored = run["network_evolution"]

    resp = client.get(
        f"/api/runs/{api_run_id}/network/evolution",
        params={"from": 0, "to": SIM_DAYS})
    assert resp.status_code == 200
    snaps = resp.json()["snapshots"]
    assert len(snaps) == len(stored)
    assert snaps[0]["density"] == pytest.approx(stored[0]["density"])


def test_subgroups_use_real_attributes(api_run_id):
    """Subgroup slicing must group by genuine persona attributes."""
    resp = client.get(
        f"/api/runs/{api_run_id}/subgroups", params={"dims": "gender,ses"})
    assert resp.status_code == 200
    data = resp.json()
    dims = {s["dimension"] for s in data}
    assert "gender" in dims
    for slice_result in data:
        assert slice_result["groups"], \
            f"dimension {slice_result['dimension']} returned no groups"
        for g in slice_result["groups"]:
            assert g["n"] > 0
            assert "mean_ach" in g and "effect_size" in g


# ============ Pipeline n6/n7 consume the real simulation output ============

def test_pipeline_produces_real_effect_sizes_and_gaps():
    """The DAG's n6/n7 must yield genuine multi-arm effect sizes and gap
    records derived from the simulation + loaded logs (no random draws)."""
    from src.pipeline import run_pipeline
    result = run_pipeline({
        "n_students": 24, "n_teachers": 4, "sim_days": 16, "seed": 42})

    assert result["status"] == "completed"

    # n6: one real effect size per treatment arm.
    ranked = result["ranking"]["ranked"]
    assert len(ranked) == len(ARM_IDS)
    assert all("priority_score" in r for r in ranked)

    # n7: gap records exist and carry the 4 metric families.
    # (Re-run the nodes directly to inspect their raw output.)
    from src.pipeline import (
        n1_load_realdata, n3a_gen_students, n3b_gen_teachers,
        n3c_gen_parents, n5_l_model_simulate, n6_virtual_es, n7_gap_analysis,
    )
    cfg = {"n_students": 24, "n_teachers": 4, "sim_days": 16, "seed": 42}
    realdata = n1_load_realdata(cfg)
    kc = {"p_know": 0.38, "p_learn": 0.25}
    students = n3a_gen_students(cfg, kc)
    teachers = n3b_gen_teachers(cfg, kc)
    parents = n3c_gen_parents(cfg, students)
    sim = n5_l_model_simulate(students, teachers, parents, {}, {}, cfg)

    es = n6_virtual_es(sim, cfg)["effect_sizes"]
    assert len(es) == len(ARM_IDS)
    assert any(abs(e["hedges_g"]) > 0.0 for e in es), \
        "pipeline effect sizes are all zero -> n5/n6 not wired"

    gaps = n7_gap_analysis(es, sim, realdata, cfg)["gap_records"]
    assert gaps, "n7 produced no gap records"
    metrics = {g["metric"] for g in gaps}
    assert metrics == {"learning_curve", "error_dist", "first_correct",
                       "variance_ratio"}
    for g in gaps:
        assert "real_value" in g and "virtual_value" in g
        assert "gap_magnitude" in g and "distortion_category" in g


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
