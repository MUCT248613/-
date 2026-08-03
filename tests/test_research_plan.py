"""
Tests for FR-R6 multi-role hypothesis generation.

Verifies that research-plan hypotheses carry role + scene fields and include
teacher / parent / scene differentiated hypotheses (not just student achievement).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.report import HypothesisGenerator


def _sample_inputs():
    ranked = [
        {"rank": 1, "intervention_id": "I3_feedback", "priority_score": 0.82,
         "channel": "teacher_mediated", "scene": "school"},
        {"rank": 2, "intervention_id": "I4_retrieval_practice", "priority_score": 0.71,
         "channel": "self_study_mediated", "scene": "self_study"},
    ]
    effect_sizes = [
        {"intervention_id": "I3_feedback", "hedges_g": 0.55,
         "ci_lower": 0.30, "ci_upper": 0.80, "scene": "school"},
        {"intervention_id": "I4_retrieval_practice", "hedges_g": 0.50,
         "ci_lower": 0.25, "ci_upper": 0.75, "scene": "self_study"},
    ]
    gap_records = [{"metric": "learning_curve", "distortion_category": "none"}]
    return ranked, effect_sizes, gap_records


def test_hypotheses_carry_role_and_scene():
    print("[TEST] Every hypothesis carries role + scene ...")
    ranked, es, gap = _sample_inputs()
    plan = HypothesisGenerator().generate(ranked, es, gap, n_students=400)
    assert plan["hypotheses"], "no hypotheses generated"
    for h in plan["hypotheses"]:
        assert h.get("role"), f"hypothesis {h['id']} missing role"
        assert h.get("scene"), f"hypothesis {h['id']} missing scene"
    print(f"  [OK] {len(plan['hypotheses'])} hypotheses, all role+scene tagged")


def test_multi_role_hypotheses_present():
    print("[TEST] Teacher / parent / scene hypotheses present ...")
    ranked, es, gap = _sample_inputs()
    plan = HypothesisGenerator().generate(ranked, es, gap)
    roles = {h["role"] for h in plan["hypotheses"]}
    for expected in ("teacher", "parent", "scene_comparison"):
        assert expected in roles, f"missing {expected} hypothesis; roles={roles}"
    print(f"  [OK] roles covered: {sorted(roles)}")


def test_plan_sections_still_eight():
    print("[TEST] Plan still has 8 sections + zero-fabrication refs ...")
    ranked, es, gap = _sample_inputs()
    plan = HypothesisGenerator().generate(ranked, es, gap)
    assert len(plan["sections"]) == 8, len(plan["sections"])
    assert plan["references"], "no references"
    for ref in plan["references"]:
        assert ref["type"] == "virtual_experiment"
        assert "非真实文献" in ref["note"]
    print("  [OK] 8 sections, references are virtual-only")


if __name__ == "__main__":
    print("=" * 70)
    print("FR-R6 Multi-Role Hypothesis Tests")
    print("=" * 70)
    test_hypotheses_carry_role_and_scene()
    test_multi_role_hypotheses_present()
    test_plan_sections_still_eight()
    print("\n" + "=" * 70)
    print("[SUCCESS] All FR-R6 tests passed!")
    print("=" * 70)
