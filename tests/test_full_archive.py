"""
Tests for the FR-A1 full 23-domain archive (210+ fields).

Verifies:
- the archive covers all 23 domains (D1–D23) with 210+ fields total;
- StudentGenerator embeds the full archive into each student;
- PrivacyGuard enforces FR-A8: the internal archive keeps all 23 domains,
  but the API/prompt/export filters strip the S-level D11 domain.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.persona_service.full_archive import build_full_archive, DOMAIN_SPECS
from src.persona_service.student_generator import StudentGenerator
from src.privacy import PrivacyGuard


def _sample_inputs():
    skeleton = {"p_know": 0.4, "p_learn": 0.25, "ses_level": "中等",
                "personality_type": "中等自信", "misconception_type": "代数"}
    seed = {"name": "示例学生", "birth_place": "浙江省金华市",
            "family_structure_type": "完整家庭",
            "core_personality_seed": "内向但执着", "unique_life_seed": "一段经历"}
    numerical = {"achievement_score": 66.0, "motivation_level": 0.6,
                 "self_efficacy": 0.55, "study_habits_score": 0.6}
    return skeleton, seed, numerical


def test_archive_covers_23_domains_210_fields():
    print("[TEST] Archive covers 23 domains / 210+ fields ...")
    skeleton, seed, numerical = _sample_inputs()
    fa = build_full_archive(skeleton, seed, numerical, seed=1)
    assert fa["domain_count"] == 23, fa["domain_count"]
    assert fa["field_count"] >= 210, fa["field_count"]
    codes = set(fa["domains"].keys())
    expected = {spec["code"] for spec in DOMAIN_SPECS}
    assert codes == expected, codes ^ expected
    print(f"  [OK] {fa['domain_count']} domains, {fa['field_count']} fields")


def test_archive_is_deterministic():
    print("[TEST] Archive is deterministic for a fixed seed ...")
    skeleton, seed, numerical = _sample_inputs()
    a = build_full_archive(skeleton, seed, numerical, seed=7)
    b = build_full_archive(skeleton, seed, numerical, seed=7)
    assert a == b, "same seed must yield identical archive"
    print("  [OK] Deterministic")


def test_student_generator_embeds_full_archive():
    print("[TEST] StudentGenerator embeds full archive ...")
    gen = StudentGenerator()
    student, status = gen.generate_student("FA_S001", seed=42)
    assert student is not None, status
    assert student["domain_count"] == 23
    assert student["field_count"] >= 210
    assert "D13" in student["domains"]  # hidden psych traits present
    print(f"  [OK] Student archive: {student['field_count']} fields")


def test_privacy_enforcement_strips_sensitive_domain():
    print("[TEST] PrivacyGuard strips the S-level D11 domain (FR-A8) ...")
    skeleton, seed, numerical = _sample_inputs()
    fa = build_full_archive(skeleton, seed, numerical, seed=3)
    persona = {"student_id": "X", "name": "X", "domains": fa["domains"],
               "field_count": fa["field_count"], "domain_count": fa["domain_count"]}
    d11_field_count = len(fa["domains"]["D11"].get("fields", {}))

    filtered = PrivacyGuard.filter_for_api(persona)
    assert "D11" not in filtered["domains"], "D11 must never reach the API"
    assert filtered["domain_count"] == 22
    assert filtered["field_count"] == fa["field_count"] - d11_field_count
    assert filtered["sensitive_domains_hidden"] == ["D11"]

    # Prompt and export paths enforce the same stripping.
    assert "D11" not in PrivacyGuard.filter_for_prompt(persona)["domains"]
    assert "D11" not in PrivacyGuard.filter_for_export({"domains": fa["domains"]})["domains"]

    # Filtering must never mutate the internal archive object.
    assert "D11" in persona["domains"]
    assert persona["domain_count"] == 23
    print(f"  [OK] D11 stripped; served fields={filtered['field_count']}")


if __name__ == "__main__":
    print("=" * 70)
    print("FR-A1 Full Archive Tests (23 domains / 210+ fields)")
    print("=" * 70)
    test_archive_covers_23_domains_210_fields()
    test_archive_is_deterministic()
    test_student_generator_embeds_full_archive()
    test_privacy_enforcement_strips_sensitive_domain()
    print("\n" + "=" * 70)
    print("[SUCCESS] All FR-A1 archive tests passed!")
    print("=" * 70)
