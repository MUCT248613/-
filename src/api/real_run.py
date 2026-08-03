"""
Real end-to-end simulation runner (v5.0 scientific chain).

This module replaces the old ``np.random`` demo generator with the genuine
pipeline, so every number the API serves is produced by the actual scientific
chain rather than drawn from a random number generator:

    4-layer persona generation (L1 skeleton -> L2 LLM identity seed ->
    L3 derivation + narrative -> L4 coherence/uniqueness)
        -> L-Model 2.0 multi-agent simulation (social network influence +
           event engine + relationship state machine)
        -> multi-arm intervention delivery (5 evidence-based interventions,
           each routed through a distinct delivery channel) vs a no-treatment
           control arm
        -> *real* Hedges' g effect sizes (treatment vs control final
           achievement), real trajectories, real social network.

The resulting run dict is stored under the same keys the API endpoints already
consume (``students`` / ``teachers`` / ``parents`` / ``network`` /
``trajectories``), plus new keys carrying the genuine evidence
(``effect_sizes`` / ``day_timelines`` / ``network_evolution`` /
``scene_comparison`` / ``arms``).
"""
from dataclasses import asdict
from datetime import datetime
from typing import Dict, List

import numpy as np

from src.persona_service.student_generator import StudentGenerator
from src.persona_service.teacher_parent_generator import (
    TeacherGenerator, ParentGenerator,
)
from src.persona_service.family_background import family_info_from_archive
from src.l_model.engine import LifeTimeEngineV2
from src.delivery.intervention_delivery import (
    InterventionDeliveryEngine, InterventionType, InterventionChannel,
    VirtualEffectSizeCalculator,
)
from src.calibrate.literature_reference import get_reference_params


# Multi-arm experimental design. Each evidence-based intervention is delivered
# through a distinct channel (exercising the 5-channel delivery system) and is
# attributed to its target scene for the scene-comparison analysis.
#   (intervention_id, InterventionType, InterventionChannel, scene)
_INTERVENTION_ARMS = [
    ("cognitive_support", InterventionType.COGNITIVE_SUPPORT,
     InterventionChannel.TEACHER_MEDIATED, "school"),
    ("autonomy_teaching", InterventionType.MOTIVATIONAL_BOOST,
     InterventionChannel.TEACHER_MEDIATED, "school"),
    ("parent_involvement", InterventionType.SOCIAL_SUPPORT,
     InterventionChannel.PARENT_MEDIATED, "home"),
    ("shadow_edu_reduction", InterventionType.TIME_MANAGEMENT,
     InterventionChannel.SHADOW_EDU_MEDIATED, "shadow_edu"),
    ("sleep_schedule", InterventionType.STRESS_REDUCTION,
     InterventionChannel.SELF_STUDY_MEDIATED, "self_study"),
]

# Intervention intensity. Together with each channel's efficacy and mediator
# quality this yields total effects of roughly 2.5-10 achievement points over
# the treatment window -- large enough to be the dominant signal in the
# treatment-vs-control contrast, while the (realistic, modest) peer-network
# drift stays in the background. The result is a stable, plausible Hedges' g
# gradient rather than estimates swamped by network noise.
_INTENSITY = 0.40


def _add_lmodel_state(student: Dict, rng: np.random.RandomState) -> Dict:
    """Attach the daily-state fields the L-Model engine, intervention delivery
    and counterfactual engine expect, deriving them from the generated persona
    so they are coherent with the 4-layer archive (not independent noise)."""
    motivation = float(student.get("motivation_level", 0.5))
    student["motivation"] = motivation
    student.setdefault("age", 14)
    student.setdefault("gender", "M" if rng.random() < 0.5 else "F")
    student["grade"] = "Grade 8"
    # Calibrate the slip/guess rates to the literature baseline with realistic
    # per-student variation (instead of a hard-coded constant), so the cohort's
    # full BKT profile matches published values and the calibration diagnostics
    # operate on genuine distributions.
    sv = student.setdefault("simulation_vector", {})
    sv["p_slip"] = float(np.clip(rng.normal(0.10, 0.03), 0.02, 0.30))
    sv["p_guess"] = float(np.clip(rng.normal(0.20, 0.05), 0.05, 0.45))
    # Peer susceptibility is kept modest so the social-network influence stays
    # a realistic background drift (~a few points over the run) instead of
    # swamping the experimental intervention effect in the treatment-vs-control
    # contrast (a strong convergence force produces large, seed-dependent drift
    # that can even invert the estimated effect sizes).
    student["susceptibility"] = float(np.clip(rng.normal(0.03, 0.015), 0.005, 0.10))
    student["parent_support"] = float(np.clip(rng.normal(0.55, 0.15), 0, 1))
    student["shadow_hours"] = float(np.clip(rng.normal(3.0, 1.5), 0, 8))
    student["tutoring_hours"] = float(np.clip(rng.normal(1.5, 1.2), 0, 6))
    student["romance_enabled"] = bool(rng.random() < 0.85)
    student["homework_load"] = float(np.clip(rng.normal(1.0, 0.2), 0.3, 2.0))
    student["fatigue"] = float(np.clip(rng.normal(40, 10), 0, 100))
    student["stress"] = float(np.clip(rng.normal(45, 12), 0, 100))
    student["emotion"] = float(np.clip(rng.normal(55, 10), 0, 100))
    return student


def _generate_personas(config, progress_callback=None) -> (Dict, Dict, Dict):
    """Generate the full cohort through the real persona pipelines.

    Students are sampled from a literature-calibrated BKT posterior so the
    cohort's cognitive parameters are anchored to published baselines.

    ``progress_callback`` (optional) is invoked as ``callback(fraction, msg)``
    with ``fraction`` in ``[0, 1]`` covering the whole persona stage (student
    generation dominates; teachers/parents are fast and reported at the end).
    """
    seed = config.seed or 42
    n_students = config.n_students
    n_teachers = config.n_teachers

    def report(frac, msg):
        if progress_callback is not None:
            progress_callback(frac, msg)

    # Literature-calibrated posterior for the L1 skeleton sampler.
    ref = get_reference_params()
    posterior = {
        "p_know": {"mu": float(ref["p_know"]), "sigma": 0.12},
        "p_learn": {"mu": float(ref["p_learn"]), "sigma": 0.07},
    }
    student_gen = StudentGenerator(posterior_dist=posterior)

    # Generate the whole cohort. In live mode this batches the L2 identity
    # seeds and L3 narratives (~8 students per LLM call), cutting a 100-student
    # cohort from 200+ sequential LLM calls to ~26; offline it falls back to the
    # per-student pipeline (instant mock calls, byte-for-byte reproducible).
    # Student generation is the dominant cost, so it owns [0, 0.85] of the
    # persona-stage progress budget.
    def _student_cb(frac, msg):
        report(0.85 * frac, msg)

    cohort = student_gen.generate_cohort(
        n_students, base_seed=seed, id_prefix="S",
        progress_callback=_student_cb)
    students: Dict[str, Dict] = {}
    for sid, student in cohort.items():
        # The numeric index embedded in the id (S00007 -> 7) drives the same
        # rng / teacher / parent assignments as the old per-student loop.
        i = int(sid[len("S"):])
        rng = np.random.RandomState(seed + i * 7919)
        student = _add_lmodel_state(student, rng)
        student["assigned_teacher_id"] = f"T{i % n_teachers:04d}"
        student["primary_parent_id"] = f"P{i:05d}"
        students[sid] = student

    teachers: Dict[str, Dict] = {}
    for i in range(n_teachers):
        tid = f"T{i:04d}"
        teachers[tid] = TeacherGenerator.generate_teacher(
            tid, experience_years=int(np.random.RandomState(seed + i).randint(3, 28)),
            seed=seed + i,
        )
    report(0.92, f"已生成 {n_teachers} 名教师画像")

    # One primary parent per student so parent-mediated delivery always has a
    # real mediator. The parent persona is linked to the student's own D2 family
    # background (统一口径): education / occupation mirror the D2 father/mother
    # fields by relation, so the 家长档案页 and the student archive never disagree.
    parents: Dict[str, Dict] = {}
    for i, sid in enumerate(students.keys()):
        pid = f"P{i:05d}"
        domains = students[sid].get("domains", {})
        family_info = family_info_from_archive(domains)
        parent = ParentGenerator.generate_parent(pid, student_id=sid,
                                                 seed=seed + i,
                                                 family_info=family_info)
        parent["child_id"] = sid
        parent.setdefault("name", f"家长_{pid}")
        parent["involvement_style"] = parent.get("simulation_vector", {}).get(
            "parenting_style", "自主支持型")
        parents[pid] = parent
        # Fill the D20 家长角色连接点 foreign key (left None by the archive builder)
        # and link the student's perceived parental involvement to the parent's
        # actual involvement_level (联动, deterministic) so the two views agree.
        d20 = (domains.get("D20") or {}).get("fields") if isinstance(domains, dict) else None
        if isinstance(d20, dict):
            d20["primary_parent_id"] = pid
            inv = parent.get("simulation_vector", {}).get("involvement_level")
            if inv is not None:
                d20_rng = np.random.RandomState(seed + i * 104729 + 7)
                d20["parent_involvement_perceived"] = round(
                    float(np.clip(float(inv) + d20_rng.normal(0, 0.08), 0.0, 1.0)), 3)
    report(1.0, f"已生成 {len(parents)} 名家长画像")

    return students, teachers, parents


def _assign_arms(students: Dict, config) -> (InterventionDeliveryEngine, Dict, List):
    """Split the cohort into 5 treatment arms + a control arm and assign the
    corresponding intervention to each treatment student."""
    seed = config.seed or 42
    sim_days = config.sim_days
    rng = np.random.RandomState(seed + 12345)
    ids = list(students.keys())
    shuffled = list(rng.permutation(ids))

    n_groups = len(_INTERVENTION_ARMS) + 1
    arm_size = max(1, len(shuffled) // n_groups)

    arms: Dict[str, List[str]] = {}
    control_ids = shuffled[:arm_size]
    for k, (intv_id, _t, _c, _s) in enumerate(_INTERVENTION_ARMS):
        arms[intv_id] = shuffled[arm_size * (k + 1): arm_size * (k + 2)]
    # Any remainder joins the control arm.
    control_ids = control_ids + shuffled[arm_size * n_groups:]

    engine = InterventionDeliveryEngine()
    day_started = max(1, sim_days // 4)
    duration = max(5, min(30, sim_days // 3))
    for intv_id, intv_type, channel, _scene in _INTERVENTION_ARMS:
        for sid in arms[intv_id]:
            engine.assign_intervention(
                student_id=sid,
                intervention_type=intv_type,
                channel=channel,
                day_started=day_started,
                duration_days=duration,
                intensity=_INTENSITY,
            )
    return engine, arms, control_ids


def _trajectories_from_sim(sim_result: Dict) -> (Dict, Dict):
    """Convert the engine's DayTimeline objects into (a) the numeric state
    curves consumed by the life-course endpoint and (b) serializable per-day
    timelines consumed by the timeline endpoint."""
    trajectories: Dict[str, Dict] = {}
    day_timelines: Dict[str, List] = {}
    for sid, timelines in sim_result["trajectories"].items():
        trajectories[sid] = {
            "achievement": [round(float(t.achievement_end), 2) for t in timelines],
            "motivation": [round(float(t.motivation_end), 3) for t in timelines],
            "fatigue": [round(float(t.fatigue_end), 2) for t in timelines],
            "stress": [round(float(t.stress_end), 2) for t in timelines],
            "emotion": [round(float(t.emotion_end), 2) for t in timelines],
        }
        day_timelines[sid] = [
            {
                "sim_date": t.sim_date,
                "events": [asdict(e) for e in t.events],
                "total_learning_gain": float(t.total_learning_gain),
                "fatigue_end": float(t.fatigue_end),
                "stress_end": float(t.stress_end),
                "emotion_end": float(t.emotion_end),
                "achievement_end": float(t.achievement_end),
                "motivation_end": float(t.motivation_end),
            }
            for t in timelines
        ]
    return trajectories, day_timelines


def build_real_run(run_id: str, config, progress_callback=None) -> Dict:
    """Orchestrate the genuine end-to-end simulation for one run.

    Returns a run dict shaped for the in-memory ``_runs`` store.

    ``progress_callback`` (optional) is invoked as
    ``callback(percent, stage, message)`` with ``percent`` in ``[0, 100]`` so
    the API layer can surface a live progress bar while the run is built.
    Percent budget: personas 1-50, arm assignment ~51, simulation 52-90,
    effect sizes / trajectories / network 91-100.
    """
    seed = config.seed or 42
    sim_days = config.sim_days

    def report(percent, stage, message):
        if progress_callback is not None:
            progress_callback(int(percent), stage, message)

    # 1. Real personas (4-layer student pipeline + T-Model + P-Model).
    report(1, "persona", "准备生成学生画像…")

    def _persona_cb(frac, msg):
        report(1 + frac * 49, "persona", msg)  # 1 -> 50

    students, teachers, parents = _generate_personas(
        config, progress_callback=_persona_cb)

    # 2. Multi-arm intervention assignment (treatment vs control).
    report(51, "arms", "划分实验组与对照组…")
    intervention_engine, arms, control_ids = _assign_arms(students, config)

    # 3. L-Model 2.0 multi-agent simulation with intervention delivery wired in.
    report(52, "simulate", "启动多智能体仿真…")
    engine = LifeTimeEngineV2(
        students=list(students.values()),
        teachers=list(teachers.values()),
        parents=list(parents.values()),
        seed=seed,
    )
    # Snapshot the pre-simulation achievement of every student so effects can
    # be estimated on the *gain* (final - baseline). Random arm assignment
    # leaves residual baseline imbalance (up to several points with ~10
    # students per arm); comparing raw final scores would confound the
    # intervention effect with that imbalance and make small-arm estimates
    # flip sign across seeds. A change-score (pretest-posttest) contrast is
    # the standard way to isolate the experimental manipulation.
    baseline_ach = {
        sid: float(s.get("achievement_score", 50.0))
        for sid, s in engine.students.items()
    }

    def _sim_cb(day, days):
        report(52 + (day / max(1, days)) * 38, "simulate",
               f"模拟第 {day + 1}/{days} 天")  # 52 -> 90

    sim_result = engine.simulate(days=sim_days,
                                 intervention_engine=intervention_engine,
                                 progress_callback=_sim_cb)

    # 4. Real effect sizes: each treatment arm vs the control arm, from the
    #    actual simulated achievement *gain* (Hedges' g with 95% CI).
    report(91, "effects", "计算真实效应量（Hedges' g）…")
    calc = VirtualEffectSizeCalculator()
    control_gain = np.array(
        [engine.students[sid]["achievement_score"] - baseline_ach[sid]
         for sid in control_ids],
        dtype=float)
    effect_sizes = []
    for intv_id, _t, _c, scene in _INTERVENTION_ARMS:
        arm_ids = arms[intv_id]
        treatment_gain = np.array(
            [engine.students[sid]["achievement_score"] - baseline_ach[sid]
             for sid in arm_ids],
            dtype=float)
        g, lo, hi = calc.compute_hedges_g(control_gain, treatment_gain)
        effect_sizes.append({
            "intervention_id": intv_id,
            "scene": scene,
            "hedges_g": round(float(g), 4),
            "ci_lower": round(float(lo), 4),
            "ci_upper": round(float(hi), 4),
            "sample_size": int(len(arm_ids) + len(control_ids)),
            "n_treatment": int(len(arm_ids)),
            "n_control": int(len(control_ids)),
            "control_mean_gain": round(float(np.mean(control_gain)), 3) if len(control_gain) else 0.0,
            "treatment_mean_gain": round(float(np.mean(treatment_gain)), 3) if len(treatment_gain) else 0.0,
        })

    # 5. Real trajectories + per-day timelines.
    report(94, "trajectories", "提取成长轨迹与逐日时间线…")
    trajectories, day_timelines = _trajectories_from_sim(sim_result)

    # 6. Real social network (final graph) + its evolution over the run.
    report(96, "network", "构建社会网络与场景对比…")
    graph = engine.network.graph
    network = {
        "nodes": [
            {"node_id": n,
             "achievement_score": float(engine.students[n]["achievement_score"])}
            for n in graph.nodes()
        ],
        "edges": [
            {"source": u, "target": v, "weight": float(graph[u][v]["weight"])}
            for u, v in graph.edges()
        ],
    }
    network_evolution = sim_result.get("network_metrics", [])

    # 7. Real scene comparison: pool each scene's treatment arms vs control.
    scene_groups: Dict[str, List[str]] = {}
    for intv_id, _t, _c, scene in _INTERVENTION_ARMS:
        scene_groups.setdefault(scene, []).extend(arms[intv_id])
    scene_comparison: Dict[str, Dict] = {}
    for scene, sids in scene_groups.items():
        treatment_gain = np.array(
            [engine.students[sid]["achievement_score"] - baseline_ach[sid]
             for sid in sids], dtype=float)
        g, lo, hi = calc.compute_hedges_g(control_gain, treatment_gain)
        scene_comparison[scene] = {
            "g": round(float(g), 4),
            "ci_lower": round(float(lo), 4),
            "ci_upper": round(float(hi), 4),
            "n": int(len(sids) + len(control_ids)),
        }

    report(100, "done", "运行完成")

    return {
        "run_id": run_id,
        "status": "completed",
        "config": config.model_dump(),
        "seed": seed,
        "students": students,
        "teachers": teachers,
        "parents": parents,
        "sim_days": sim_days,
        "created_at": datetime.now().isoformat(),
        "completed_at": datetime.now().isoformat(),
        "network": network,
        "trajectories": trajectories,
        # --- genuine evidence produced by the scientific chain ---
        "effect_sizes": effect_sizes,
        "day_timelines": day_timelines,
        "network_evolution": network_evolution,
        "scene_comparison": scene_comparison,
        "arms": {**arms, "control": list(control_ids)},
        "data_source": "simulation",
    }
