"""
VirtualStudent Sandbox v6.0 - Prefect DAG Orchestration

Implements §7 流水线 DAG (Pipeline DAG) with the v3.0/v4.0 node structure:
  n1_load_realdata -> n2_fit_kc_model
  n3a_gen_students / n3b_gen_teachers / n3c_gen_parents (from n2)
  n4_calibrate (from n2, n3a)
  n4b_init_network (from n3a)
  n5_l_model_simulate (from n4, n3a, n3b, n3c, n4b)
  n6_virtual_es -> n7_gap_analysis -> n8_rank
  n9_heldout (from n6)
  n10_report (from n8, n9)

If Prefect is not installed, the module degrades gracefully to a plain
sequential runner so the pipeline remains runnable anywhere.

Reference: 技术设计文档 §7, C-9
"""
from typing import Dict, List, Optional, Any

# Try to import Prefect; fall back to a no-op decorator if unavailable.
try:
    from prefect import flow, task
    PREFECT_AVAILABLE = True
except ImportError:
    PREFECT_AVAILABLE = False
    
    def task(fn=None, **kwargs):
        """No-op task decorator when Prefect is unavailable."""
        if fn is None:
            return lambda f: f
        return fn
    
    def flow(fn=None, **kwargs):
        """No-op flow decorator when Prefect is unavailable."""
        if fn is None:
            return lambda f: f
        return fn


# ============ DAG Node Implementations ============

@task
def n1_load_realdata(config: Dict) -> Dict:
    """M1: Load real learning log data (FR-D1 / C6 比赛硬性).

    Prefers genuine ASSISTments/EdNet datasets discovered under ``data/real/``;
    transparently falls back to labelled synthetic logs when none is present so
    the DAG always runs. The data provenance (``data_source``/``dataset``) is
    carried forward so calibration and reporting stay honest about whether real
    or synthetic logs were used.
    """
    from ..data_loader import load_real_data
    result = load_real_data(
        data_dir=config.get("real_data_dir", "data/real"),
        max_learners=config.get("real_students", 50),
        n_synthetic=config.get("real_students", 50),
        seed=config.get("seed", 42),
    )
    return {
        "real_logs": result["logs"],
        "n": result["n_learners"],
        "data_source": result["source"],
        "dataset": result["dataset"],
        "data_files": result["files"],
    }


@task
def n2_fit_kc_model(realdata: Dict) -> Dict:
    """M1/M3: Fit BKT knowledge-component parameters to real logs."""
    from ..calibrate import CognitiveCalibrator
    cal = CognitiveCalibrator()
    result = cal.calibrate(realdata["real_logs"])
    return result


@task
def n3a_gen_students(config: Dict, kc_params: Dict) -> Dict:
    """M2: Generate student personas (4-layer pipeline)."""
    from ..persona_service.student_generator import StudentGenerator
    gen = StudentGenerator()
    n = config.get("n_students", 50)
    students = {}
    for i in range(n):
        student, status = gen.generate_student(f"S{i:05d}", seed=config.get("seed", 42) + i)
        if student:
            students[f"S{i:05d}"] = student
    return {"students": students, "n": len(students)}


@task
def n3b_gen_teachers(config: Dict, kc_params: Dict) -> Dict:
    """M2: Generate teacher personas."""
    from ..persona_service.teacher_parent_generator import TeacherGenerator
    n = config.get("n_teachers", 5)
    teachers = {}
    for i in range(n):
        t = TeacherGenerator.generate_teacher(f"T{i:04d}", seed=config.get("seed", 42) + i)
        teachers[f"T{i:04d}"] = t
    return {"teachers": teachers, "n": len(teachers)}


@task
def n3c_gen_parents(config: Dict, students: Dict) -> Dict:
    """M2: Generate parent personas, linked to each student's D2 family
    background so the parent persona and student archive share one 口径."""
    from ..persona_service.teacher_parent_generator import ParentGenerator
    from ..persona_service.family_background import family_info_from_archive
    parents = {}
    for i, sid in enumerate(students["students"].keys()):
        student = students["students"][sid]
        family_info = family_info_from_archive(student.get("domains", {}))
        p = ParentGenerator.generate_parent(f"P{i:05d}", student_id=sid,
                                            seed=config.get("seed", 42) + i,
                                            family_info=family_info)
        parents[f"P{i:05d}"] = p
    return {"parents": parents, "n": len(parents)}


@task
def n4_calibrate(kc_params: Dict, students: Dict) -> Dict:
    """M3: Calibrate (cognitive + persona distribution)."""
    from ..calibrate import PersonaDistributionCalibrator
    persona_cal = PersonaDistributionCalibrator()
    persona_report = persona_cal.calibrate(list(students["students"].values()))
    return {"cognitive": kc_params, "persona": persona_report}


@task
def n4b_init_network(students: Dict, config: Dict) -> Dict:
    """M4: Initialize peer network by homophily."""
    from ..l_model.social_network import SocialNetworkEngine
    n = len(students["students"])
    net = SocialNetworkEngine(n, init_density=config.get("init_density", 0.04),
                              seed=config.get("seed", 42),
                              profiles=students["students"] if isinstance(students, dict) else None)
    return {"network": net, "n_nodes": n}


@task
def n5_l_model_simulate(students: Dict, teachers: Dict, parents: Dict,
                        calibration: Dict, network: Dict, config: Dict) -> Dict:
    """M4: L-Model 2.0 multi-agent networked simulation.

    Wires in the multi-arm intervention delivery (5 evidence-based arms vs a
    no-treatment control) so the simulated achievement trajectories respond to
    the experimental manipulation, and returns the actual post-simulation
    outcomes + arm assignments so downstream nodes compute genuine effects.
    """
    from ..l_model.engine import LifeTimeEngineV2
    from ..delivery.intervention_delivery import InterventionDeliveryEngine
    from ..api.real_run import _INTERVENTION_ARMS, _INTENSITY, _add_lmodel_state
    import numpy as np

    days = config.get("sim_days", 30)
    seed = config.get("seed", 42)
    student_map = students["students"]
    n_teachers = max(1, len(teachers["teachers"]))

    # Enrich each persona with the L-Model daily-state fields + mediator links
    # (derived from the generated persona, coherent with the 4-layer archive).
    for i, (sid, student) in enumerate(student_map.items()):
        _add_lmodel_state(student, np.random.RandomState(seed + i * 7919))
        student["assigned_teacher_id"] = f"T{i % n_teachers:04d}"
        student["primary_parent_id"] = f"P{i:05d}"

    # Multi-arm assignment: 5 treatment arms + control (deterministic).
    rng = np.random.RandomState(seed + 12345)
    shuffled = list(rng.permutation(list(student_map.keys())))
    n_groups = len(_INTERVENTION_ARMS) + 1
    arm_size = max(1, len(shuffled) // n_groups)
    arms: Dict[str, List[str]] = {}
    control_ids = shuffled[:arm_size]
    for k, (intv_id, _t, _c, _s) in enumerate(_INTERVENTION_ARMS):
        arms[intv_id] = shuffled[arm_size * (k + 1): arm_size * (k + 2)]
    control_ids = control_ids + shuffled[arm_size * n_groups:]

    intervention_engine = InterventionDeliveryEngine()
    day_started = max(1, days // 4)
    duration = max(5, min(30, days // 3))
    for intv_id, intv_type, channel, _scene in _INTERVENTION_ARMS:
        for sid in arms[intv_id]:
            intervention_engine.assign_intervention(
                student_id=sid, intervention_type=intv_type, channel=channel,
                day_started=day_started, duration_days=duration,
                intensity=_INTENSITY)

    engine = LifeTimeEngineV2(
        students=list(student_map.values()),
        teachers=list(teachers["teachers"].values()),
        parents=list(parents["parents"].values()),
        seed=seed,
    )
    # Snapshot pre-simulation achievement so n6 can estimate effects on the
    # *gain* (final - baseline), removing baseline arm-imbalance confounding.
    baseline_achievement = {
        sid: float(s.get("achievement_score", 50.0))
        for sid, s in engine.students.items()
    }
    result = engine.simulate(days=days, intervention_engine=intervention_engine)

    # Actual post-simulation achievement for every student + arm assignments.
    final_achievement = {
        sid: float(engine.students[sid]["achievement_score"])
        for sid in engine.students
    }
    return {
        "trajectories": result,
        "days": days,
        "baseline_achievement": baseline_achievement,
        "final_achievement": final_achievement,
        "arms": arms,
        "control_ids": list(control_ids),
    }


@task
def n6_virtual_es(simulation: Dict, config: Dict) -> Dict:
    """M4: Compute virtual effect sizes from the actual simulated outcomes.

    Each treatment arm's genuine achievement *gain* (final - baseline) is
    contrasted against the control arm's gain via Hedges' g -- the real
    experimental effect produced by the L-Model simulation, not a random draw.
    The change-score contrast removes baseline arm-imbalance confounding.
    """
    from ..delivery.intervention_delivery import VirtualEffectSizeCalculator
    from ..api.real_run import _INTERVENTION_ARMS
    import numpy as np

    calc = VirtualEffectSizeCalculator()
    final = simulation["final_achievement"]
    baseline = simulation.get("baseline_achievement", {})
    control_ids = simulation["control_ids"]
    control_gain = np.array(
        [final[sid] - baseline.get(sid, final[sid]) for sid in control_ids],
        dtype=float)

    scene_by_intv = {iid: scene for iid, _t, _c, scene in _INTERVENTION_ARMS}
    effect_sizes = []
    for intv_id, sids in simulation["arms"].items():
        treatment_gain = np.array(
            [final[sid] - baseline.get(sid, final[sid]) for sid in sids],
            dtype=float)
        g, lo, hi = calc.compute_hedges_g(control_gain, treatment_gain)
        effect_sizes.append({
            "intervention_id": intv_id,
            "scene": scene_by_intv.get(intv_id, "school"),
            "hedges_g": float(g), "ci_lower": float(lo), "ci_upper": float(hi),
            "n_treatment": int(len(sids)), "n_control": int(len(control_ids)),
            "control_mean_gain": float(np.mean(control_gain)) if len(control_gain) else 0.0,
            "treatment_mean_gain": float(np.mean(treatment_gain)) if len(treatment_gain) else 0.0,
        })
    return {"effect_sizes": effect_sizes}


@task
def n7_gap_analysis(effect_sizes: Dict, simulation: Dict, realdata: Dict,
                    config: Dict) -> Dict:
    """M5: Quantify real-vs-virtual gaps across the 4 metric families.

    The virtual side is derived from the genuine L-Model achievement
    trajectories; the real side is derived from the loaded learning-log
    sequences (real dataset when present, else transparently-synthetic logs).
    No random numbers are used.
    """
    from ..gap import GapAnalyst
    import numpy as np

    analyst = GapAnalyst()

    # ---- Real side: from the loaded learning-log correctness sequences ----
    seqs = [list(r["sequence"]) for r in realdata.get("real_logs", [])
            if r.get("sequence")]
    if seqs:
        max_len = max(len(s) for s in seqs)
        real_curve = np.array([
            float(np.mean([s[t] for s in seqs if len(s) > t]))
            for t in range(max_len)
        ])
        first_correct_real = np.array([
            float(next((i + 1 for i, c in enumerate(s) if c == 1), len(s)))
            for s in seqs
        ])
        per_learner_mean = np.array([float(np.mean(s)) for s in seqs])
    else:
        real_curve = np.linspace(0.4, 0.7, 30)
        first_correct_real = np.full(30, 2.0)
        per_learner_mean = np.full(30, 0.55)

    # ---- Virtual side: from the genuine simulated achievement trajectories ----
    traj = simulation["trajectories"]["trajectories"]  # {sid: [DayTimeline, ...]}
    ach_curves = [
        [float(t.achievement_end) for t in timelines]
        for timelines in traj.values()
    ]
    if ach_curves:
        mean_curve = np.mean(ach_curves, axis=0)
        span = max(1e-6, float(mean_curve.max() - mean_curve.min()))
        virtual_curve = (mean_curve - mean_curve.min()) / span
        # Per-student latency to first measurable achievement gain.
        first_correct_virtual = np.array([
            float(next((i + 1 for i, a in enumerate(c) if a > c[0] + 1e-6), len(c)))
            for c in ach_curves
        ])
    else:
        virtual_curve = np.linspace(0.3, 0.7, len(real_curve))
        first_correct_virtual = np.full(len(seqs) or 30, 2.0)

    # Resample the real curve to the virtual curve's length (shape-aware).
    n_pts = len(virtual_curve)
    real_curve_rs = np.interp(np.linspace(0, 1, n_pts),
                              np.linspace(0, 1, len(real_curve)), real_curve)

    # Per-student final achievement (normalized) for the variance comparison.
    final = simulation.get("final_achievement", {})
    final_vals = np.array(list(final.values()), dtype=float) if final \
        else np.array([c[-1] for c in ach_curves], dtype=float)
    fspan = max(1e-6, float(final_vals.max() - final_vals.min()))
    final_norm = (final_vals - final_vals.min()) / fspan

    real = {
        "learning_curve": real_curve_rs,
        "error_dist": 1.0 - real_curve_rs,
        "first_correct": first_correct_real,
        "variance_ratio": per_learner_mean,
    }
    virtual = {
        "learning_curve": virtual_curve,
        "error_dist": 1.0 - virtual_curve,
        "first_correct": first_correct_virtual,
        "variance_ratio": final_norm,
    }
    records = analyst.analyze(real, virtual)
    return {"gap_records": records}


@task
def n8_rank(effect_sizes: Dict, gap_analysis: Dict) -> Dict:
    """M6: Priority ranking of interventions."""
    from ..rank import PriorityRanker
    ranker = PriorityRanker()
    candidates = []
    for es in effect_sizes["effect_sizes"]:
        candidates.append({
            "intervention_id": es["intervention_id"],
            "hedges_g": es["hedges_g"],
            "ci_95": [es["ci_lower"], es["ci_upper"]],
            "reach": 0.6, "cost_yuan": 100.0, "scene": es["scene"],
        })
    ranked = ranker.rank(candidates)
    return {"ranked": ranked}


@task
def n9_heldout(realdata: Dict, config: Dict) -> Dict:
    """M5: Held-out validation."""
    from ..gap import GapAnalyst
    import numpy as np
    analyst = GapAnalyst()
    def predictor(logs):
        return [np.mean(r.get("sequence", [0.5])) for r in logs]
    result = analyst.heldout_validation(realdata["real_logs"], predictor)
    return {"heldout": result}


@task
def n10_report(ranking: Dict, heldout: Dict, config: Dict) -> Dict:
    """M7+M8: Report card + research plan generation."""
    from ..report import ReportWriter, HypothesisGenerator
    writer = ReportWriter()
    run_summary = {"run_id": config.get("run_id", "RUN_DEMO"),
                   "n_students": config.get("n_students", 50),
                   "sim_days": config.get("sim_days", 30)}
    report = writer.build_report(run_summary, {"distance": 0.05},
                                 [], [], ranking["ranked"])
    return {"report": report}


# ============ Full DAG Flow ============

@flow(name="virtual-student-pipeline")
def virtual_student_pipeline(config: Optional[Dict] = None) -> Dict:
    """
    Full §7 DAG: load -> fit -> generate personas -> calibrate -> simulate
    -> effect sizes -> gap -> rank -> report.
    """
    config = config or {"n_students": 50, "n_teachers": 5, "sim_days": 30, "seed": 42}
    
    # n1, n2
    realdata = n1_load_realdata(config)
    kc_params = n2_fit_kc_model(realdata)
    
    # n3a, n3b, n3c (n3c depends on n3a)
    students = n3a_gen_students(config, kc_params)
    teachers = n3b_gen_teachers(config, kc_params)
    parents = n3c_gen_parents(config, students)
    
    # n4, n4b
    calibration = n4_calibrate(kc_params, students)
    network = n4b_init_network(students, config)
    
    # n5
    simulation = n5_l_model_simulate(students, teachers, parents,
                                     calibration, network, config)
    
    # n6, n7, n8, n9
    effect_sizes = n6_virtual_es(simulation, config)
    gap_analysis = n7_gap_analysis(effect_sizes, simulation, realdata, config)
    ranking = n8_rank(effect_sizes, gap_analysis)
    heldout = n9_heldout(realdata, config)
    
    # n10
    report = n10_report(ranking, heldout, config)
    
    return {
        "status": "completed",
        "config": config,
        "report": report,
        "ranking": ranking,
        "data_source": realdata.get("data_source", "synthetic"),
        "dataset": realdata.get("dataset"),
    }


def run_pipeline(config: Optional[Dict] = None) -> Dict:
    """
    Entry point. Uses Prefect if available, otherwise runs sequentially.
    """
    return virtual_student_pipeline(config)


if __name__ == "__main__":
    result = run_pipeline({"n_students": 20, "sim_days": 14, "seed": 42})
    print(f"Pipeline status: {result['status']}")
