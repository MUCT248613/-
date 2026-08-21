# -*- coding: utf-8 -*-
with open('src/api/real_run.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the effect_sizes loop and add channel_breakdown computation
old_code = '''    effect_sizes = []
    for intv_id, _t, _c, scene, _d in arms_table:
        arm_ids = arms[intv_id]
        treatment_gain = np.array(
            [engine.students[sid]["achievement_score"] - baseline_ach[sid]
             for sid in arm_ids],
            dtype=float)
        g, lo, hi = calc.compute_hedges_g(control_gain, treatment_gain)
        breakdown = _compute_mediation_breakdown(
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

new_code = '''    effect_sizes = []
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
        })'''

if old_code in content:
    content = content.replace(old_code, new_code)
    print("OK: Added channel_breakdown to effect_sizes")
else:
    print("ERROR: Could not find target code block")
    exit(1)

with open('src/api/real_run.py', 'w', encoding='utf-8') as f:
    f.write(content)