"""
Tests for the FR-S1 intervention catalog (I1–I4, YAML-extensible).

Verifies:
- the four evidence-based interventions (I1 样例 / I2 间隔 / I3 反馈 / I4 检索)
  exist with effect sizes;
- the YAML catalog loads and is registered into the delivery engine;
- a brand-new intervention declared only in YAML works WITHOUT code changes;
- intervention effect direction is correct.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.delivery.intervention_delivery import (
    InterventionDeliveryEngine,
    InterventionType,
    InterventionChannel,
    load_intervention_catalog,
)


def test_i1_i4_enum_and_effects():
    print("[TEST] I1–I4 enum members & built-in effects ...")
    for member in (InterventionType.WORKED_EXAMPLES,
                   InterventionType.SPACED_PRACTICE,
                   InterventionType.FEEDBACK,
                   InterventionType.RETRIEVAL_PRACTICE):
        effects = InterventionDeliveryEngine.TYPE_EFFECTS[member]
        assert effects["achievement"] > 0, member
    print("  [OK] I1–I4 present with positive achievement effects")


def test_yaml_catalog_loads_four_interventions():
    print("[TEST] YAML catalog declares I1–I4 ...")
    catalog = load_intervention_catalog()
    assert len(catalog) >= 4, f"expected >=4 interventions, got {len(catalog)}"
    types = {spec.get("type") for spec in catalog.values()}
    for expected in ("worked_examples", "spaced_practice", "feedback",
                     "retrieval_practice"):
        assert expected in types, f"missing {expected} in catalog"
    # Each entry must carry scene routing + default channel
    for _id, spec in catalog.items():
        assert spec.get("target_scene"), f"{_id} missing target_scene"
        assert spec.get("default_channel"), f"{_id} missing default_channel"
    print(f"  [OK] Catalog has {len(catalog)} interventions: {sorted(types)}")


def test_engine_registers_catalog():
    print("[TEST] Engine registers YAML catalog into custom_effects ...")
    engine = InterventionDeliveryEngine()
    assert "feedback" in engine.custom_effects
    assert engine.custom_effects["feedback"]["achievement"] > 0
    print("  [OK] Engine merged YAML catalog")


def test_new_intervention_without_code_change():
    print("[TEST] Brand-new YAML-only intervention works (no code change) ...")
    yaml_text = (
        "interventions:\n"
        "  IX_interleaving:\n"
        "    label: '交错练习'\n"
        "    type: interleaving_practice\n"
        "    target_scene: [school]\n"
        "    default_channel: teacher_mediated\n"
        "    effect_achievement: 4.7\n"
        "    effect_motivation: 0.06\n"
    )
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "intervention_delivery.yaml")
        with open(path, "w", encoding="utf-8") as f:
            f.write(yaml_text)
        engine = InterventionDeliveryEngine(catalog_path=path)
        assert "interleaving_practice" in engine.custom_effects
        # Assign purely by string type — no enum member exists for it.
        int_id = engine.assign_intervention(
            "S001", "interleaving_practice",
            InterventionChannel.TEACHER_MEDIATED, day_started=0,
            duration_days=30, intensity=1.0)
        student = {"student_id": "S001", "achievement_score": 50.0,
                   "motivation": 0.5}
        engine.apply_interventions_to_student(student, day=10)
        assert student["achievement_score"] > 50.0, "YAML-only intervention had no effect"
    print("  [OK] New intervention added via YAML alone, effect applied")


def test_i3_feedback_effect_direction():
    print("[TEST] I3 feedback improves achievement ...")
    engine = InterventionDeliveryEngine()
    engine.assign_intervention(
        "S002", InterventionType.FEEDBACK,
        InterventionChannel.DIRECT, day_started=0,
        duration_days=30, intensity=0.9)
    student = {"student_id": "S002", "achievement_score": 50.0, "motivation": 0.5}
    engine.apply_interventions_to_student(student, day=15)
    assert student["achievement_score"] > 50.0
    print(f"  [OK] Feedback raised achievement to {student['achievement_score']:.2f}")


if __name__ == "__main__":
    print("=" * 70)
    print("FR-S1 Intervention Catalog Tests (I1–I4)")
    print("=" * 70)
    test_i1_i4_enum_and_effects()
    test_yaml_catalog_loads_four_interventions()
    test_engine_registers_catalog()
    test_new_intervention_without_code_change()
    test_i3_feedback_effect_direction()
    print("\n" + "=" * 70)
    print("[SUCCESS] All FR-S1 intervention tests passed!")
    print("=" * 70)
