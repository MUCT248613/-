"""
Real end-to-end simulation runner (v6.0 scientific chain).

This module replaces the old ``np.random`` demo generator with the genuine
pipeline, so every number the API serves is produced by the actual scientific
chain rather than drawn from a random number generator:

    4-layer persona generation (L1 skeleton -> L2 LLM identity seed ->
    L3 derivation + narrative -> L4 coherence/uniqueness)
        -> L-Model 2.0 multi-agent simulation (social network influence +
           event engine + relationship state machine)
        -> multi-arm intervention delivery (arms declared in
           config/intervention_delivery.yaml, each routed through a distinct
           delivery channel) vs a no-treatment control arm
        -> *real* Hedges' g effect sizes (treatment vs control final
           achievement), real trajectories, real social network.

The resulting run dict is stored under the same keys the API endpoints already
consume (``students`` / ``teachers`` / ``parents`` / ``network`` /
``trajectories``), plus new keys carrying the genuine evidence
(``effect_sizes`` / ``day_timelines`` / ``network_evolution`` /
``scene_comparison`` / ``arms``).
"""
import copy
from dataclasses import asdict
from datetime import datetime
from typing import Dict, List

import numpy as np
from concurrent.futures import ThreadPoolExecutor

from src.persona_service.student_generator import StudentGenerator
from src.persona_service.teacher_parent_generator import (
    TeacherGenerator, ParentGenerator,
)
from src.persona_service.family_background import family_info_from_archive
from src.l_model.engine import LifeTimeEngineV2
from src.delivery.intervention_delivery import (
    InterventionDeliveryEngine, InterventionType, InterventionChannel,
    VirtualEffectSizeCalculator, load_intervention_catalog,
)
from src.calibrate.literature_reference import get_reference_params


# Multi-arm experimental design (FR-S1, single source of truth). The arms are
# declared in config/intervention_delivery.yaml; each is delivered through its
# default channel (exercising the 5-channel delivery system) and attributed to
# its first target scene for the scene-comparison analysis. The built-in list
# is only a fallback for when the YAML catalog is unavailable.
#   (intervention_id, intervention_type, InterventionChannel, scene)
_FALLBACK_ARMS = [
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


def _build_intervention_arms() -> List:
    """Build the treatment-arm table from the YAML intervention catalog.

    Falls back to ``_FALLBACK_ARMS`` when the catalog is unavailable
    (missing file / missing yaml dependency) so the pipeline still runs.
    """
    arms = []
    for intv_id, spec in load_intervention_catalog().items():
        type_str = str(spec.get("type") or intv_id)
        try:
            channel = InterventionChannel(spec.get("default_channel", "direct"))
        except ValueError:
            channel = InterventionChannel.DIRECT
        scenes = spec.get("target_scene") or ["school"]
        if isinstance(scenes, (list, tuple)) and scenes:
            scene = str(scenes[0])
        else:
            scene = str(scenes)
        arms.append((intv_id, type_str, channel, scene))
    return arms or list(_FALLBACK_ARMS)


_INTERVENTION_ARMS = _build_intervention_arms()


def _resolve_run_arms(config) -> (List, List[Dict]):
    """Resolve the treatment-arm table for one run (researcher-first).

    Researcher-submitted candidates (``config.interventions``) take priority:
    when present they *are* the experiment -- the built-in battery is not
    appended (a no-treatment control arm is always kept by ``_assign_arms``),
    so each run tests exactly the hypotheses the researcher stated. Without
    them the YAML-declared catalog arms are used, then the built-in fallback.

    Returns ``(arms, metas)``: arms is a list of
    ``(id, type, channel, scene, dose-or-None)`` tuples; metas carries the
    display/report metadata (label/action/cost/evidence) for each arm.
    """
    specs = getattr(config, "interventions", None) or []
    if specs:
        arms: List = []
        metas: List[Dict] = []
        seen = set()
        for k, spec in enumerate(specs):
            s = spec.model_dump() if hasattr(spec, "model_dump") else dict(spec)
            intv_id = str(s.get("id") or f"C{k + 1}_custom")
            if intv_id in seen:
                intv_id = f"{intv_id}_{k + 1}"
            seen.add(intv_id)
            type_str = str(s.get("type") or intv_id)
            try:
                channel = InterventionChannel(
                    s.get("default_channel") or "teacher_mediated")
            except ValueError:
                channel = InterventionChannel.TEACHER_MEDIATED
            scenes = s.get("target_scene") or ["school"]
            if isinstance(scenes, str):
                scenes = [scenes]
            scene = str(scenes[0]) if scenes else "school"
            arms.append((intv_id, type_str, channel, scene, {
                "achievement": float(s.get("effect_achievement", 4.0)),
                "motivation": float(s.get("effect_motivation", 0.05)),
                "exposure_rate": float(s.get("exposure_rate", 1.0)),
            }))
            metas.append({
                "id": intv_id,
                "label": str(s.get("label") or intv_id),
                "type": type_str,
                "scene": scene,
                "evidence_hedges_g": float(s.get("evidence_hedges_g", 0.3)),
                "cost_yuan": float(s.get("cost_yuan", 50.0)),
                "action": str(s.get("action") or ""),
                "description": str(s.get("description") or ""),
                "exposure_rate": float(s.get("exposure_rate", 1.0)),
                "source": "researcher",
            })
        return arms, metas

    arms, metas = [], []
    for intv_id, spec in load_intervention_catalog().items():
        type_str = str(spec.get("type") or intv_id)
        try:
            channel = InterventionChannel(spec.get("default_channel", "direct"))
        except ValueError:
            channel = InterventionChannel.DIRECT
        scenes = spec.get("target_scene") or ["school"]
        if isinstance(scenes, (list, tuple)) and scenes:
            scene = str(scenes[0])
        else:
            scene = str(scenes)
        arms.append((intv_id, type_str, channel, scene, None))
        metas.append({
            "id": intv_id,
            "label": str(spec.get("label") or intv_id),
            "type": type_str,
            "scene": scene,
            "evidence_hedges_g": float(spec.get("evidence_hedges_g", 0.0)),
            "cost_yuan": float(spec.get("cost_yuan", 0.0)),
            "action": str(spec.get("action") or ""),
            "description": str(spec.get("description") or ""),
            "source": "yaml",
        })
    if arms:
        return arms, metas
    return (
        [(a[0], a[1], a[2], a[3], None) for a in _FALLBACK_ARMS],
        [{"id": a[0], "label": a[0], "type": a[1].value, "scene": a[3],
          "evidence_hedges_g": 0.0, "cost_yuan": 50.0, "action": "",
          "description": "", "source": "builtin"} for a in _FALLBACK_ARMS],
    )

# Intervention intensity. The YAML effect_* values denote the expected TOTAL
# gain over the treatment window at perfect delivery; the engine spreads them
# per day and attenuates by channel efficacy x mediator quality, so delivered
# totals land at roughly 2-4 achievement points -- large enough to dominate
# the treatment-vs-control contrast while the (realistic, modest) peer-network
# drift stays in the background. The result is a stable, plausible Hedges' g
# gradient in the realistic 0.1-0.6 band.
_INTENSITY = 1.0


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
    # Peer susceptibility is kept low so the social-network influence stays a
    # realistic background drift (~1-2 points over the run). The influence rule
    # is a convergence force (students drift toward their neighbors'
    # achievement), so a high susceptibility contaminates the experimental
    # contrast: treatment gains leak into the control arm and vice versa,
    # erasing about half of the true effect by the final measurement (with
    # weight 0.5 and susceptibility 0.03 the contrast half-life is only ~46
    # days). At susceptibility ~0.012 the half-life is ~115 days, well beyond
    # a typical run, while peer drift remains visible in the trajectories.
    student["susceptibility"] = float(np.clip(rng.normal(0.012, 0.006), 0.002, 0.05))
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
    # Teacher personas are independent; when the LLM is live each carries a
    # slow network narrative call, so generate them concurrently.
    _t_specs = [
        (f"T{i:04d}",
         int(np.random.RandomState(seed + i).randint(3, 28)), seed + i)
        for i in range(n_teachers)
    ]
    with ThreadPoolExecutor(max_workers=16) as ex:
        for tid, teacher in ex.map(
                lambda s: (s[0], TeacherGenerator.generate_teacher(
                    s[0], experience_years=s[1], seed=s[2])), _t_specs):
            teachers[tid] = teacher
    report(0.92, f"已生成 {n_teachers} 名教师画像")

    # One primary parent per student so parent-mediated delivery always has a
    # real mediator. The parent persona is linked to the student's own D2 family
    # background (统一口径): education / occupation mirror the D2 father/mother
    # fields by relation, so the 家长档案页 and the student archive never disagree.
    parents: Dict[str, Dict] = {}

    def _gen_parent(item):
        i, sid = item
        pid = f"P{i:05d}"
        domains = students[sid].get("domains", {})
        family_info = family_info_from_archive(domains)
        parent = ParentGenerator.generate_parent(pid, student_id=sid,
                                                 seed=seed + i,
                                                 family_info=family_info,
                                                 skip_narrative=True)
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
        return pid

    with ThreadPoolExecutor(max_workers=16) as ex:
        list(ex.map(_gen_parent, list(enumerate(students.keys()))))
    # Narratives now come from batched concurrent LLM calls (8 parents each)
    # instead of one slow call per parent.
    ParentGenerator.batch_parent_narratives(list(parents.values()))
    report(1.0, f"已生成 {len(parents)} 名家长画像")

    return students, teachers, parents


def _assign_arms(students: Dict, config, arms_table: List) -> (
        InterventionDeliveryEngine, Dict, List):
    """Split the cohort into len(arms_table) treatment arms + a control arm
    and assign the corresponding intervention to each treatment student."""
    seed = config.seed or 42
    sim_days = config.sim_days
    rng = np.random.RandomState(seed + 12345)
    ids = list(students.keys())
    shuffled = list(rng.permutation(ids))

    n_groups = len(arms_table) + 1
    arm_size = max(1, len(shuffled) // n_groups)

    arms: Dict[str, List[str]] = {}
    control_ids = shuffled[:arm_size]
    for k, (intv_id, _t, _c, _s, _d) in enumerate(arms_table):
        arms[intv_id] = shuffled[arm_size * (k + 1): arm_size * (k + 2)]
    # Any remainder joins the control arm.
    control_ids = control_ids + shuffled[arm_size * n_groups:]

    engine = InterventionDeliveryEngine()
    day_started = max(1, sim_days // 4)
    duration = max(5, min(30, sim_days // 3))
    for intv_id, intv_type, channel, _scene, dose in arms_table:
        exposure = float((dose or {}).get("exposure_rate", 1.0))
        for sid in arms[intv_id]:
            int_id = engine.assign_intervention(
                student_id=sid,
                intervention_type=intv_type,
                channel=channel,
                day_started=day_started,
                duration_days=duration,
                intensity=_INTENSITY,
                expected_effects=dose,
            )
            # Individual-level randomness: only the exposed fraction of the
            # arm actually receives the dose (others adhere 0), so the
            # estimated effect is an honest intent-to-treat average diluted
            # by the exposure rate -- the same dilution a real trial sees.
            if exposure < 1.0:
                engine.interventions[int_id].adherence_rate = float(
                    rng.random() < exposure)
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



# ---------------------------------------------------------------------------
# Triad network: student-teacher-parent relationship graph
# ---------------------------------------------------------------------------

_TEACHING_STYLE_WEIGHT = {
    "\u81ea\u4e3b\u652f\u6301\u578b": 1.0,
    "\u5747\u8861\u578b": 0.8,
    "\u63a7\u5236\u578b": 0.6,
    "\u653e\u4efb\u578b": 0.4,
}


def _build_triad_network(students, teachers, parents, arms_table, arms, sim_days):
    """Build a tri-partite relationship graph among students, teachers, parents.

    Returns a dict with ``nodes`` (each tagged ``type``: student/teacher/parent)
    and ``edges`` (student-teacher, student-parent, student-student).
    """
    nodes = []
    teacher_map = {t["teacher_id"]: t for t in teachers}
    parent_map = {p["parent_id"]: p for p in parents}

    # --- per-student teacher influence & parent involvement trajectory ---
    teacher_influence = {}
    parent_trajectory = {}

    for s in students:
        sid = s.get("student_id", s.get("id", ""))
        tid = s.get("assigned_teacher_id", "")
        pid = s.get("primary_parent_id", "")

        # Teacher influence score: experience + style match
        t = teacher_map.get(tid, {})
        exp = float(t.get("experience_years", 5))
        style = t.get("teaching_style", "")
        style_w = _TEACHING_STYLE_WEIGHT.get(style, 0.5)
        influence = round(float(np.clip((exp / 30.0) * 0.6 + style_w * 0.4, 0, 1)), 3)
        teacher_influence[sid] = {"teacher_id": tid, "score": influence}

        # Parent involvement trajectory: base involvement + sinusoidal fluctuation
        p = parent_map.get(pid, {})
        sv = p.get("simulation_vector", {})
        base_inv = float(sv.get("involvement_level", 0.5))
        trajectory = []
        for day in range(sim_days):
            wave = 0.08 * float(np.sin(2 * np.pi * day / max(1, sim_days)))
            val = round(float(np.clip(base_inv + wave, 0, 1)), 3)
            trajectory.append(val)
        parent_trajectory[sid] = {"parent_id": pid, "trajectory": trajectory,
                                  "mean_involvement": round(float(np.mean(trajectory)), 3)}

    # --- nodes ---
    for s in students:
        sid = s.get("student_id", s.get("id", ""))
        ach = float(s.get("achievement_score", 50))
        nodes.append({
            "id": sid, "type": "student",
            "label": s.get("name", sid),
            "size": round(ach / 10.0, 2),
            "achievement_score": round(ach, 2),
            "teacher_influence_score": teacher_influence.get(sid, {}).get("score", 0.5),
            "parent_involvement_mean": parent_trajectory.get(sid, {}).get("mean_involvement", 0.5),
        })
    for t in teachers:
        tid = t["teacher_id"]
        exp = float(t.get("experience_years", 5))
        nodes.append({
            "id": tid, "type": "teacher",
            "label": t.get("name", tid),
            "size": round(exp / 5.0, 2),
            "experience_years": int(exp),
            "teaching_style": t.get("teaching_style", ""),
        })
    for p in parents:
        pid = p["parent_id"]
        sv = p.get("simulation_vector", {})
        inv = float(sv.get("involvement_level", 0.5))
        nodes.append({
            "id": pid, "type": "parent",
            "label": p.get("name", pid),
            "size": round(inv * 8.0, 2),
            "involvement_level": round(inv, 3),
        })

    # --- edges ---
    edges = []
    # student-teacher
    for s in students:
        sid = s.get("student_id", s.get("id", ""))
        tid = s.get("assigned_teacher_id", "")
        if tid in teacher_map:
            w = teacher_influence.get(sid, {}).get("score", 0.5)
            edges.append({"source": sid, "target": tid, "type": "student-teacher",
                          "weight": w})
    # student-parent
    for s in students:
        sid = s.get("student_id", s.get("id", ""))
        pid = s.get("primary_parent_id", "")
        if pid in parent_map:
            inv = parent_trajectory.get(sid, {}).get("mean_involvement", 0.5)
            edges.append({"source": sid, "target": pid, "type": "student-parent",
                          "weight": inv})
    # student-student (from peer links if available)
    for s in students:
        sid = s.get("student_id", s.get("id", ""))
        peers = s.get("peer_ids", [])
        for peer_id in peers:
            edges.append({"source": sid, "target": peer_id, "type": "student-student",
                          "weight": 0.5})

    # --- per-intervention affected edges ---
    intervention_edges = {}
    for intv_id, _t, channel, _scene, _d in arms_table:
        affected = []
        channel_val = channel.value if hasattr(channel, "value") else str(channel)
        for sid in arms.get(intv_id, []):
            for e in edges:
                if e["source"] == sid or e["target"] == sid:
                    if channel_val == "teacher_mediated" and e["type"] == "student-teacher":
                        affected.append(e)
                    elif channel_val == "parent_mediated" and e["type"] == "student-parent":
                        affected.append(e)
                    elif channel_val in ("direct", "self_study_mediated", "shadow_edu_mediated"):
                        affected.append(e)
        intervention_edges[intv_id] = affected

    return {
        "nodes": nodes,
        "edges": edges,
        "teacher_influence": teacher_influence,
        "parent_trajectory": parent_trajectory,
        "intervention_edges": intervention_edges,
    }


def _compute_mediation_breakdown(channel, arm_ids, engine_students, baseline_ach, calc, control_gain):
    """Simplified mediation decomposition for one intervention.

    Splits the total effect into teacher-mediated, parent-mediated, and direct
    channels based on the delivery channel.
    """
    channel_val = channel.value if hasattr(channel, "value") else str(channel)
    treatment_gain = np.array(
        [engine_students[sid]["achievement_score"] - baseline_ach[sid]
         for sid in arm_ids], dtype=float) if arm_ids else np.array([0.0])
    total_g = float(calc.compute_hedges_g(control_gain, treatment_gain)[0]) if len(arm_ids) >= 2 else 0.0

    if channel_val == "teacher_mediated":
        teacher_frac, parent_frac, direct_frac = 0.55, 0.15, 0.30
    elif channel_val == "parent_mediated":
        teacher_frac, parent_frac, direct_frac = 0.15, 0.55, 0.30
    elif channel_val == "shadow_edu_mediated":
        teacher_frac, parent_frac, direct_frac = 0.10, 0.20, 0.70
    elif channel_val == "self_study_mediated":
        teacher_frac, parent_frac, direct_frac = 0.05, 0.10, 0.85
    else:
        teacher_frac, parent_frac, direct_frac = 0.10, 0.10, 0.80

    return {
        "teacher_mediated": round(total_g * teacher_frac, 4),
        "parent_mediated": round(total_g * parent_frac, 4),
        "direct": round(total_g * direct_frac, 4),
        "teacher_fraction": round(teacher_frac, 2),
        "parent_fraction": round(parent_frac, 2),
        "direct_fraction": round(direct_frac, 2),
    }


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

    # 2. Multi-arm intervention assignment (treatment vs control). The arm
    #    table is researcher-first: submitted candidates replace the built-in
    #    battery for this run (see _resolve_run_arms).
    report(51, "arms", "划分实验组与对照组…")
    arms_table, intervention_meta = _resolve_run_arms(config)
    intervention_engine, arms, control_ids = _assign_arms(
        students, config, arms_table)

    # Counterfactuals must branch from the pre-simulation state. Using the
    # final students here would start the what-if run after all growth had
    # already happened and makes ceiling effects look like intervention gains.
    initial_students = copy.deepcopy(students)

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
    for intv_id, _t, _c, scene, _d in arms_table:
        arm_ids = arms[intv_id]
        treatment_gain = np.array(
            [engine.students[sid]["achievement_score"] - baseline_ach[sid]
             for sid in arm_ids],
            dtype=float)
        g, lo, hi = calc.compute_hedges_g(control_gain, treatment_gain)
        breakdown = _compute_mediation_breakdown(
            _c, arm_ids, engine.students, baseline_ach, calc, control_gain)
        
        # Compute channel_breakdown: per-channel stats for this intervention
        channel_val = _c.value if hasattr(_c, "value") else str(_c)
        channel_breakdown = {}
        for ch_name in ["teacher_mediated", "parent_mediated", "direct", 
                        "shadow_edu_mediated", "self_study_mediated"]:
            if ch_name == channel_val:
                # This intervention uses this channel
                channel_breakdown[ch_name] = {
                    "n": int(len(arm_ids)),
                    "avg_g": round(float(g), 4) if len(arm_ids) >= 2 else None,
                }
            else:
                channel_breakdown[ch_name] = {"n": 0, "avg_g": None}
        
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
            "breakdown": breakdown,
            "channel_breakdown": channel_breakdown,
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
    for intv_id, _t, _c, scene, _d in arms_table:
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

    # 8. Triad network: student-teacher-parent relationship graph.
    triad_network = _build_triad_network(
        list(students.values()), list(teachers.values()), list(parents.values()),
        arms_table, arms, sim_days)

    report(100, "done", "运行完成")

    return {
        "run_id": run_id,
        "status": "completed",
        "config": config.model_dump(),
        "seed": seed,
        "students": students,
        "students_initial": initial_students,
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
        "intervention_meta": intervention_meta,
        "data_source": "simulation",
        "triad_network": triad_network,
    }
