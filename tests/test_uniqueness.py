"""
Uniqueness tests (opt3): verify that generated personas are distinct across
all roles (students, teachers, parents) using attribute diversity metrics.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.persona_service.student_generator import StudentGenerator
from src.persona_service.teacher_parent_generator import TeacherGenerator, ParentGenerator


def test_student_name_uniqueness():
    """All generated student names must be unique."""
    print("[TEST] Student name uniqueness ...")
    gen = StudentGenerator()
    names = set()
    for i in range(50):
        profile, _ = gen.generate_student(f"S{i:05d}", seed=i)
        name = profile["name"]
        assert name not in names, f"Duplicate name: {name}"
        names.add(name)
    assert len(names) == 50
    print(f"  [OK] 50 unique student names")


def test_student_attribute_diversity():
    """Students should show diversity in names and cognitive params."""
    print("[TEST] Student attribute diversity ...")
    gen = StudentGenerator()
    all_names = set()
    p_know_values = set()
    for i in range(30):
        profile, _ = gen.generate_student(f"S{i:05d}", seed=i)
        all_names.add(profile.get("name"))
        sv = profile.get("simulation_vector", {})
        if sv.get("p_know") is not None:
            p_know_values.add(round(sv["p_know"], 2))
    # Names should all be unique
    assert len(all_names) == 30, f"Only {len(all_names)} unique names"
    # Cognitive params should vary
    assert len(p_know_values) >= 5, f"Only {len(p_know_values)} unique p_know values"
    print(f"  [OK] 30 unique names, {len(p_know_values)} distinct p_know values")


def test_teacher_uniqueness():
    """Teachers should have unique names and varied styles."""
    print("[TEST] Teacher uniqueness ...")
    gen = TeacherGenerator()
    names = set()
    styles = set()
    for i in range(20):
        profile = gen.generate_teacher(f"T{i:04d}", seed=i)
        name = profile["name"]
        assert name not in names, f"Duplicate teacher name: {name}"
        names.add(name)
        styles.add(profile.get("teaching_style"))
    assert len(names) == 20
    assert len(styles) >= 2, f"Only {len(styles)} teaching styles"
    print(f"  [OK] 20 unique teachers, {len(styles)} styles")


def test_parent_uniqueness():
    """Parents should have unique IDs and varied education levels."""
    print("[TEST] Parent uniqueness ...")
    gen = ParentGenerator()
    ids = set()
    edu_levels = set()
    for i in range(20):
        profile = gen.generate_parent(f"P{i:05d}", f"S{i:05d}", seed=i)
        pid = profile["parent_id"]
        assert pid not in ids, f"Duplicate parent ID: {pid}"
        ids.add(pid)
        edu_levels.add(profile.get("education_level"))
    assert len(ids) == 20
    assert len(edu_levels) >= 2, f"Only {len(edu_levels)} education levels"
    print(f"  [OK] 20 unique parents, {len(edu_levels)} education levels")


def test_cross_role_name_disjoint():
    """Student, teacher, and parent ID pools should not overlap."""
    print("[TEST] Cross-role ID disjointness ...")
    s_gen = StudentGenerator()
    t_gen = TeacherGenerator()
    p_gen = ParentGenerator()
    student_ids = {s_gen.generate_student(f"S{i:05d}", seed=i)[0]["student_id"] for i in range(20)}
    teacher_ids = {t_gen.generate_teacher(f"T{i:04d}", seed=i)["teacher_id"] for i in range(20)}
    parent_ids = {p_gen.generate_parent(f"P{i:05d}", f"S{i:05d}", seed=i)["parent_id"] for i in range(20)}
    # No overlap between roles
    assert not student_ids & teacher_ids, "Student-teacher ID overlap"
    assert not student_ids & parent_ids, "Student-parent ID overlap"
    assert not teacher_ids & parent_ids, "Teacher-parent ID overlap"
    print("  [OK] No cross-role ID collisions")


def test_full_archive_field_uniqueness():
    """Full archive fields should vary across students (not all identical)."""
    print("[TEST] Full archive field variation ...")
    from src.persona_service.full_archive import build_full_archive
    archives = []
    for i in range(10):
        skeleton = {"p_know": 0.3 + i * 0.05, "p_learn": 0.2 + i * 0.02,
                    "ses_level": "中等", "personality_type": "自信",
                    "misconception_type": "代数"}
        identity = {"name": f"Student_{i}", "birth_place": "中国",
                    "family_structure_type": "完整家庭",
                    "core_personality_seed": "勤奋", "unique_life_seed": f"经历{i}"}
        numerical = {"achievement_score": 50 + i * 3, "motivation_level": 0.5,
                     "self_efficacy": 0.5, "study_habits_score": 0.5}
        archives.append(build_full_archive(skeleton, identity, numerical, seed=i))
    # Check that D1 identity fields differ
    d1_values = [a["domains"]["D1"]["fields"]["name"] for a in archives]
    assert len(set(d1_values)) == 10, "D1 names not unique"
    print("  [OK] Full archive fields vary across 10 students")


if __name__ == "__main__":
    print("=" * 70)
    print("Uniqueness Tests (opt3)")
    print("=" * 70)
    test_student_name_uniqueness()
    test_student_attribute_diversity()
    test_teacher_uniqueness()
    test_parent_uniqueness()
    test_cross_role_name_disjoint()
    test_full_archive_field_uniqueness()
    print("\n" + "=" * 70)
    print("[SUCCESS] All uniqueness tests passed!")
    print("=" * 70)
