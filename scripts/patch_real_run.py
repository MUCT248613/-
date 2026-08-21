import re

with open('src/api/real_run.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add _build_triad_network and _compute_mediation_breakdown before build_real_run
triad_func = r'''

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

'''

# Insert before build_real_run
marker = "\ndef build_real_run(run_id: str, config, progress_callback=None) -> Dict:"
content = content.replace(marker, triad_func + marker)

# 2. Add mediation breakdown to effect_sizes
old_effect = '''        effect_sizes.append({
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
        })'''

new_effect = '''        breakdown = _compute_mediation_breakdown(
            _c, arm_ids, engine.students, baseline_ach, calc, control_gain)
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
        })'''

content = content.replace(old_effect, new_effect)

# 3. Add triad_network construction before report(100, ...)
old_report100 = '    report(100, "done", "\u8fd0\u884c\u5b8c\u6210")'
new_report100 = '''    # 8. Triad network: student-teacher-parent relationship graph.
    triad_network = _build_triad_network(
        list(students.values()), list(teachers.values()), list(parents.values()),
        arms_table, arms, sim_days)

    report(100, "done", "\u8fd0\u884c\u5b8c\u6210")'''

content = content.replace(old_report100, new_report100)

# 4. Add triad_network to return dict
old_return_end = '        "data_source": "simulation",'
new_return_end = '        "data_source": "simulation",\n        "triad_network": triad_network,'

content = content.replace(old_return_end, new_return_end)

with open('src/api/real_run.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("OK: real_run.py patched")
