"""
W3 Integration Test: L-Model 2.0 with full feature set
Tests social network, events, and relationships

Usage:
    python tests/test_w3_lmodel.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.l_model.engine import LifeTimeEngineV2, SceneEvent, DayTimeline
from src.l_model.social_network import SocialNetworkEngine
from src.l_model.event_engine import EventEngine, EventLogger
from src.l_model.relationship import RelationshipStateMachine, RelationshipType
import numpy as np


def create_sample_students(n: int = 10, seed: int = 42) -> list:
    """Create sample students for testing"""
    np.random.seed(seed)
    students = []
    
    for i in range(n):
        students.append({
            "student_id": f"S{i:04d}",
            "name": f"Student_{i}",
            "achievement_score": 50 + np.random.normal(0, 15),
            "fatigue": 50,
            "stress": 50,
            "emotion": 50,
            "susceptibility": 0.1 + np.random.uniform(0, 0.2),
            "simulation_vector": {"p_know": 0.5},
            "motivation": 0.5
        })
    
    return students


def create_sample_teachers(n: int = 2, seed: int = 100) -> list:
    """Create sample teachers"""
    np.random.seed(seed)
    teachers = []
    
    for i in range(n):
        teachers.append({
            "teacher_id": f"T{i:03d}",
            "name": f"Teacher_{i}",
            "simulation_vector": {"fidelity": 0.7}
        })
    
    return teachers


def create_sample_parents(n: int = 10, seed: int = 200) -> list:
    """Create sample parents"""
    np.random.seed(seed)
    parents = []
    
    for i in range(n):
        parents.append({
            "parent_id": f"P{i:04d}",
            "name": f"Parent_{i}",
            "simulation_vector": {"involvement_level": 0.5}
        })
    
    return parents


def test_social_network():
    """Test social network evolution"""
    print("[TEST] Social Network Engine...")
    
    n_students = 10
    network = SocialNetworkEngine(n_students, init_density=0.2, seed=42)
    
    # Check network properties
    assert len(network.graph.nodes()) == n_students, "Node count mismatch"
    assert len(network.graph.edges()) > 0, "No edges created"
    
    # Create sample students and convert to dict
    students_list = create_sample_students(n_students)
    students = {s["student_id"]: s for s in students_list}
    
    # Test influence propagation
    influence = network.propagate_influence(students, day=0)
    assert len(influence) == n_students, "Influence dict size mismatch"
    assert all(isinstance(v, float) for v in influence.values()), "Invalid influence values"
    
    # Test homophily update
    stats = network.update_edges_homophily(students)
    assert "avg_weight" in stats, "Missing avg_weight in stats"
    assert 0.0 <= stats["avg_weight"] <= 1.0, "Invalid avg_weight"
    
    print(f"  [OK] Network: {n_students} nodes, {len(network.graph.edges())} edges")
    print(f"      Avg weight: {stats['avg_weight']:.3f}")
    return True


def test_event_engine():
    """Test event generation and decay"""
    print("\n[TEST] Event Engine...")
    
    engine = EventEngine(seed=42)
    students = create_sample_students(5)
    student_id = students[0]["student_id"]
    
    # Trigger scheduled events
    engine.trigger_scheduled_events(day=60)  # Exam day
    
    # Generate random events
    events = engine.generate_random_events(student_id, day=10)
    
    # Test event impact decay
    if events:
        event = events[0]
        impact_today = engine.compute_event_impact(event, current_day=10)
        impact_later = engine.compute_event_impact(event, current_day=17)
        
        # Impact should decay
        total_today = sum(abs(v) for v in impact_today.values())
        total_later = sum(abs(v) for v in impact_later.values())
        
        assert total_later < total_today, "Event impact should decay"
        print(f"  [OK] Event decay verified: {total_today:.2f} -> {total_later:.2f}")
    
    # Apply events to student
    engine.apply_events_to_student(students[0], day=10)
    assert "achievement_score" in students[0], "Student attribute not updated"
    
    print(f"  [OK] Events triggered: {len(engine.event_history)} total")
    return True


def test_relationships():
    """Test relationship state machine"""
    print("\n[TEST] Relationship State Machine...")
    
    rsm = RelationshipStateMachine()
    
    # Create peer relationship
    rel_id = rsm.create_relationship(
        agent_a_id="S0001",
        agent_b_id="S0002",
        agent_a_type="student",
        agent_b_type="student",
        rel_type=RelationshipType.PEER,
        initial_intensity=0.2
    )
    
    rel = rsm.relationships[rel_id]
    assert rel.intensity == 0.2, "Initial intensity incorrect"
    
    # Update relationship with interaction
    for day in range(10):
        rsm.update_relationship(rel_id, day, interaction_occurred=True, interaction_quality=0.7)
    
    rel = rsm.relationships[rel_id]
    assert rel.intensity > 0.2, "Intensity should grow with interaction"
    
    # Get relationship summary
    summary = rsm.get_agent_relationships("S0001")
    assert len(summary) == 1, "Agent should have 1 relationship"
    
    print(f"  [OK] Relationship created and evolved: {rel.state.value}")
    print(f"      Intensity: {rel.intensity:.2f}, Duration: {rel.duration_days} days")
    return True


def test_lifetime_engine():
    """Test integrated L-Model 2.0 engine"""
    print("\n[TEST] LifeTimeEngine V2 Integration...")
    
    students = create_sample_students(8, seed=42)
    teachers = create_sample_teachers(2, seed=100)
    parents = create_sample_parents(8, seed=200)
    
    # Initialize engine
    engine = LifeTimeEngineV2(students, teachers, parents, seed=42)
    
    # Run short simulation (5 days)
    result = engine.simulate(days=5, interventions=None)
    
    # Check results
    assert "trajectories" in result, "Missing trajectories"
    assert "events_log" in result, "Missing events_log"
    assert "network_metrics" in result, "Missing network_metrics"
    assert "event_log" in result, "Missing event_log"
    
    # Check trajectory data
    for student_id, timelines in result["trajectories"].items():
        assert len(timelines) == 5, f"Should have 5 days of timeline for {student_id}"
        for timeline in timelines:
            assert isinstance(timeline, DayTimeline), "Invalid timeline object"
            assert timeline.total_learning_gain >= 0, "Invalid learning gain"
    
    # Check network metrics
    assert len(result["network_metrics"]) == 5, "Should have 5 network snapshots"
    
    print(f"  [OK] Simulation completed: {len(students)} students × 5 days")
    print(f"      Final avg achievement: {np.mean([s['achievement_score'] for s in engine.students.values()]):.1f}")
    return True


def test_full_workflow():
    """Full integration test"""
    print("\n[TEST] Full Workflow (10 students, 15 days)...")
    
    students = create_sample_students(10, seed=42)
    teachers = create_sample_teachers(2, seed=100)
    parents = create_sample_parents(10, seed=200)
    
    engine = LifeTimeEngineV2(students, teachers, parents, seed=42)
    result = engine.simulate(days=15, interventions=None)
    
    # Comprehensive checks
    assert len(result["trajectories"]) == 10, "Should have 10 student trajectories"
    assert len(result["events_log"]) == 15, "Should have 15 days of event logs"
    assert len(result["event_log"]) > 0, "Should have event logging"
    
    # Compute statistics
    final_achievements = [s["achievement_score"] for s in engine.students.values()]
    mean_ach = np.mean(final_achievements)
    std_ach = np.std(final_achievements)
    
    print(f"  [OK] Full workflow completed")
    print(f"      Final achievement: mean={mean_ach:.1f}, std={std_ach:.1f}")
    print(f"      Network density: {engine.network_monitor.history[-1]['density']:.3f}")
    print(f"      Total events logged: {len(result['event_log'])}")
    return True


if __name__ == "__main__":
    print("=" * 70)
    print("W3 Integration Tests: L-Model 2.0 Multi-Agent Engine")
    print("=" * 70)
    
    try:
        test_social_network()
        test_event_engine()
        test_relationships()
        test_lifetime_engine()
        test_full_workflow()
        
        print("\n" + "=" * 70)
        print("[SUCCESS] All W3 tests passed!")
        print("=" * 70)
    except AssertionError as e:
        print(f"\n[FAIL] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
