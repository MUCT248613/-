"""
W2 Integration Test: End-to-end persona generation
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.persona_service.student_generator import StudentGenerator
from src.persona_service.teacher_parent_generator import TeacherGenerator, ParentGenerator


def test_student_generation():
    """Test student generation pipeline"""
    print("[TEST] Student generation (4-layer pipeline)...")
    
    generator = StudentGenerator()
    student, status = generator.generate_student("DEMO_S001", seed=42)
    
    assert student is not None, f"Generation failed: {status}"
    assert student["student_id"] == "DEMO_S001"
    assert "achievement_score" in student
    assert "simulation_vector" in student
    assert "sensitive_data" in student
    
    print(f"  [OK] Generated student: {student['name']}")
    print(f"       Achievement: {student['achievement_score']:.1f}")
    print(f"       Motivation: {student['simulation_vector']['motivation']:.2f}")
    return True


def test_teacher_generation():
    """Test teacher generation"""
    print("\n[TEST] Teacher generation (T-Model)...")
    
    teachers = TeacherGenerator.generate_batch(3, base_seed=100)
    
    assert len(teachers) == 3
    for t in teachers:
        assert "fidelity" in t["simulation_vector"]
        assert 0.0 <= t["simulation_vector"]["fidelity"] <= 1.0
    
    print(f"  [OK] Generated {len(teachers)} teachers")
    return True


def test_parent_generation():
    """Test parent generation"""
    print("\n[TEST] Parent generation (P-Model)...")
    
    parents = ParentGenerator.generate_batch_for_students(6, 3, base_seed=200)
    
    assert len(parents) == 6
    for p in parents:
        assert "parenting_effect_multiplier" in p["simulation_vector"]
        assert "involvement_level" in p["simulation_vector"]
    
    print(f"  [OK] Generated {len(parents)} parents")
    return True


def test_uniqueness_guarantee():
    """Test uniqueness guarantee engine"""
    print("\n[TEST] Uniqueness guarantee...")
    
    generator = StudentGenerator()
    
    # Generate 10 students
    students = []
    for i in range(10):
        student, status = generator.generate_student(f"UNIQUE_S{i:03d}", seed=300+i)
        if student:
            students.append(student)
    
    # Check uniqueness
    student_names = [s["name"] for s in students]
    unique_names = set(student_names)
    
    assert len(unique_names) == len(student_names), "Duplicate names detected!"
    
    print(f"  [OK] All {len(students)} students are unique")
    return True


if __name__ == "__main__":
    print("=" * 70)
    print("W2 Integration Tests: Persona Generation Pipeline")
    print("=" * 70)
    
    try:
        test_student_generation()
        test_teacher_generation()
        test_parent_generation()
        test_uniqueness_guarantee()
        
        print("\n" + "=" * 70)
        print("[SUCCESS] All W2 tests passed!")
        print("=" * 70)
    except AssertionError as e:
        print(f"\n[FAIL] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
