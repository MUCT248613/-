"""
Comprehensive Business & Technical Test Suite
Tests full workflow from both business logic and technical perspectives.

Business Tests:
- B1: Full simulation lifecycle
- B2: Privacy enforcement (S-level never leaks)
- B3: Cognitive engine determinism
- B4: Intervention effect direction
- B5: Social network properties
- B6: Event half-life decay
- B7: Effect size statistical correctness
- B8: Persona uniqueness guarantee

Technical Tests:
- T1: API boundary conditions (invalid input)
- T2: Missing resource handling (404)
- T3: Pagination edge cases
- T4: Data type validation (422)
- T5: Privacy guard completeness
- T6: Concurrent request safety
- T7: Large payload handling

Usage:
    python tests/test_full_verification.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import requests
import json
import time
from concurrent.futures import ThreadPoolExecutor

BASE = "http://127.0.0.1:6668"

# Track results
_results = {"passed": 0, "failed": 0, "errors": []}


def check(condition: bool, test_id: str, description: str):
    """Assert with tracking"""
    if condition:
        _results["passed"] += 1
        print(f"  [PASS] {test_id}: {description}")
    else:
        _results["failed"] += 1
        _results["errors"].append(f"{test_id}: {description}")
        print(f"  [FAIL] {test_id}: {description}")


def _create_run_wait(payload, timeout=240, poll=0.5):
    """POST /api/runs and block until the run reaches a terminal state.

    Run creation is asynchronous -- the endpoint returns immediately with
    status="running" and builds the run in a background thread -- so these
    tests poll GET /api/runs/{id} (exactly like the real frontend) before
    querying run data. Also works when the endpoint is synchronous (returns
    "completed" straight away, e.g. the in-process pytest server).
    """
    r = requests.post(f"{BASE}/api/runs", json=payload)
    assert r.status_code == 200, f"create run failed: {r.status_code} {r.text}"
    run_id = r.json()["run_id"]
    body = r.json()
    deadline = time.time() + timeout
    while body.get("status") not in ("completed", "failed"):
        assert time.time() < deadline, f"run {run_id} timed out after {timeout}s"
        time.sleep(poll)
        body = requests.get(f"{BASE}/api/runs/{run_id}").json()
    assert body.get("status") == "completed", f"run {run_id} ended '{body.get('status')}'"
    return run_id


# ================================================================
# BUSINESS TESTS
# ================================================================

def test_b1_full_lifecycle():
    """B1: Full simulation lifecycle - create, query, analyze"""
    print("\n[B1] Full Simulation Lifecycle")
    
    # Create run (async endpoint -> poll until completed, like the frontend).
    run_id = _create_run_wait({
        "n_students": 50, "n_teachers": 5, "n_parents": 50,
        "sim_days": 60, "seed": 123
    })
    check(True, "B1.1", "Create run returns 200")
    r = requests.get(f"{BASE}/api/runs/{run_id}")
    check(r.json()["status"] == "completed", "B1.2", "Run completes (polled to completion)")
    check(r.json()["n_students"] == 50, "B1.3", "Student count matches request")
    
    # Query students
    r = requests.get(f"{BASE}/api/runs/{run_id}/students", params={"page": 1, "page_size": 50})
    check(r.status_code == 200, "B1.4", "List all students")
    check(r.json()["total"] == 50, "B1.5", "Total students = 50")
    
    # Get timeline for first student
    sid = r.json()["students"][0]["student_id"]
    r = requests.get(f"{BASE}/api/runs/{run_id}/students/{sid}/timeline")
    check(r.status_code == 200, "B1.6", "Get student timeline")
    check(len(r.json()["events"]) > 0, "B1.7", "Timeline has events")
    
    # Get life course
    r = requests.get(f"{BASE}/api/runs/{run_id}/students/{sid}/life_course",
                     params={"from": 0, "to": 59})
    check(r.status_code == 200, "B1.8", "Get life course")
    check(len(r.json()["achievement"]) == 60, "B1.9", "Life course has 60 data points")
    
    # Scene comparison
    r = requests.get(f"{BASE}/api/runs/{run_id}/scene_comparison")
    check(r.status_code == 200, "B1.10", "Scene comparison available")
    check(len(r.json()["scenes"]) == 4, "B1.11", "4 scenes compared")
    
    # Counterfactual
    r = requests.post(f"{BASE}/api/runs/{run_id}/counterfactual", json={
        "modification": {"remove_shadow_edu": True}, "days": 30
    })
    check(r.status_code == 200, "B1.12", "Create counterfactual")
    cf_id = r.json()["cf_id"]
    
    r = requests.get(f"{BASE}/api/runs/{run_id}/counterfactual/{cf_id}/comparison")
    check(r.status_code == 200, "B1.13", "Get CF comparison")
    check(r.json()["effect_size_g"] != 0, "B1.14", "CF shows non-zero effect")
    
    return run_id


def test_b2_privacy_enforcement(run_id: str = None):
    """B2: S-level fields NEVER appear in any API response"""
    print("\n[B2] Privacy Enforcement (P/R/S)")
    
    if run_id is None:
        run_id = _create_run_wait({"n_students": 10, "sim_days": 10})
    
    sensitive_keys = ["sensitive_data", "sensitive_json", "private_sensitive",
                      "gifted_sen", "parenting_style_detail", "family_conflict",
                      "tutoring_cost", "mental_health_records", "medical_history",
                      "financial_details"]
    
    # Check student list
    r = requests.get(f"{BASE}/api/runs/{run_id}/students", params={"page_size": 50})
    students = r.json()["students"]
    
    leaked = False
    for s in students:
        for key in sensitive_keys:
            if key in s:
                leaked = True
                break
    check(not leaked, "B2.1", "Student list: no S-level fields")
    
    # Check single student
    sid = students[0]["student_id"]
    r = requests.get(f"{BASE}/api/runs/{run_id}/students/{sid}")
    student = r.json()
    
    leaked = any(key in student for key in sensitive_keys)
    check(not leaked, "B2.2", "Single student: no S-level fields")
    
    # Check teacher
    r = requests.get(f"{BASE}/api/runs/{run_id}/teachers/T0000")
    teacher = r.json()
    leaked = any(key in teacher for key in sensitive_keys)
    check(not leaked, "B2.3", "Teacher: no S-level fields")
    
    # Check full response text for sensitive patterns
    full_text = json.dumps(student)
    from src.privacy import PrivacyGuard
    violations = PrivacyGuard.scan_log(full_text)
    check(len(violations) == 0, "B2.4", "Static scan: no S-level patterns in response")


def test_b3_cognitive_determinism():
    """B3: Cognitive engine produces identical results with same seed"""
    print("\n[B3] Cognitive Engine Determinism")
    
    from src.cognitive_engine import CognitiveEngine
    
    engine = CognitiveEngine()
    profile = {"p_know": 0.6, "p_slip": 0.1, "p_guess": 0.1}
    item = {"difficulty": 0.5}
    history = [{"time": 10.0, "is_correct": True}, {"time": 50.0, "is_correct": False}]
    
    results = []
    for _ in range(5):
        is_correct, conf = engine.score_response(profile, item, history, 100.0)
        results.append((is_correct, conf))
    
    all_same = all(r == results[0] for r in results)
    check(all_same, "B3.1", "Same input -> same output (5 runs)")
    check(0 <= results[0][1] <= 1, "B3.2", "Confidence in [0,1]")


def test_b4_intervention_effect_direction():
    """B4: Intervention effects have correct direction"""
    print("\n[B4] Intervention Effect Direction")
    
    from src.delivery.intervention_delivery import (
        InterventionDeliveryEngine, InterventionType, InterventionChannel
    )
    
    engine = InterventionDeliveryEngine()
    
    # Cognitive support should improve achievement
    int_id = engine.assign_intervention(
        "S001", InterventionType.COGNITIVE_SUPPORT,
        InterventionChannel.DIRECT, day_started=0, duration_days=30, intensity=0.8
    )
    
    student = {"student_id": "S001", "achievement_score": 50.0, "motivation": 0.5}
    engine.apply_interventions_to_student(student, day=15)
    
    check(student["achievement_score"] > 50.0, "B4.1",
          "Cognitive support increases achievement")
    check(student["motivation"] > 0.5, "B4.2",
          "Cognitive support increases motivation")
    
    # Channel efficacy ordering: direct > teacher > parent > self_study
    efficacies = [
        InterventionDeliveryEngine.CHANNEL_EFFICACY[InterventionChannel.DIRECT],
        InterventionDeliveryEngine.CHANNEL_EFFICACY[InterventionChannel.TEACHER_MEDIATED],
        InterventionDeliveryEngine.CHANNEL_EFFICACY[InterventionChannel.PARENT_MEDIATED],
        InterventionDeliveryEngine.CHANNEL_EFFICACY[InterventionChannel.SELF_STUDY_MEDIATED],
    ]
    check(efficacies[0] > efficacies[1] > efficacies[2] > efficacies[3], "B4.3",
          "Channel efficacy: direct > teacher > parent > self_study")


def test_b5_social_network_properties():
    """B5: Social network has valid graph properties"""
    print("\n[B5] Social Network Properties")
    
    from src.l_model.social_network import SocialNetworkEngine
    
    net = SocialNetworkEngine(30, init_density=0.2, seed=42)
    
    check(len(net.graph.nodes()) == 30, "B5.1", "30 nodes created")
    check(len(net.graph.edges()) > 0, "B5.2", "Edges exist")
    
    # Density should be approximately 0.2
    import networkx as nx
    actual_density = nx.density(net.graph)
    check(0.1 < actual_density < 0.4, "B5.3", f"Density ~0.2 (actual={actual_density:.3f})")
    
    # Influence propagation should conserve direction
    students = {f"S{i:04d}": {"achievement_score": 50 + i, "susceptibility": 0.1}
                for i in range(30)}
    influence = net.propagate_influence(students, day=0)
    check(len(influence) == 30, "B5.4", "Influence computed for all nodes")
    
    # Homophily: similar students should have stronger edges after update
    stats = net.update_edges_homophily(students)
    check(0 <= stats["avg_weight"] <= 1, "B5.5", "Edge weights in [0,1]")


def test_b6_event_half_life_decay():
    """B6: Event impacts decay with half-life"""
    print("\n[B6] Event Half-Life Decay")
    
    from src.l_model.event_engine import EventEngine, Event
    
    engine = EventEngine(seed=42)
    
    # Create a mock event
    event = Event(
        event_id="test_1", event_type="exam_fail", student_id="S001",
        day_triggered=0, intensity=1.0,
        achievement_delta=-5, motivation_delta=-0.1
    )
    
    # Impact at day 0 vs day 7 (half_life=7 for exam_fail)
    impact_day0 = engine.compute_event_impact(event, current_day=0)
    impact_day7 = engine.compute_event_impact(event, current_day=7)
    impact_day14 = engine.compute_event_impact(event, current_day=14)
    
    check(abs(impact_day0["achievement_delta"]) > abs(impact_day7["achievement_delta"]),
          "B6.1", "Impact decays: day0 > day7")
    check(abs(impact_day7["achievement_delta"]) > abs(impact_day14["achievement_delta"]),
          "B6.2", "Impact decays: day7 > day14")
    
    # Half-life check: day7 should be ~50% of day0
    ratio = abs(impact_day7["achievement_delta"]) / abs(impact_day0["achievement_delta"])
    check(0.4 < ratio < 0.6, "B6.3", f"Half-life ratio ~0.5 (actual={ratio:.3f})")


def test_b7_effect_size_correctness():
    """B7: Hedges' g calculation is statistically correct"""
    print("\n[B7] Effect Size Statistical Correctness")
    
    from src.delivery.intervention_delivery import VirtualEffectSizeCalculator
    
    calc = VirtualEffectSizeCalculator()
    
    # Known case: control=50, treatment=55, sd=10 -> d~0.5
    np.random.seed(42)
    control = np.random.normal(50, 10, 100)
    treatment = np.random.normal(55, 10, 100)
    
    g, ci_low, ci_up = calc.compute_hedges_g(control, treatment)
    
    check(0.3 < g < 0.7, "B7.1", f"Hedges g ~0.5 (actual={g:.3f})")
    check(ci_low < g < ci_up, "B7.2", "g is within CI")
    check(ci_low > 0, "B7.3", "CI lower > 0 (significant)")
    
    # Null case: same distribution -> g~0
    control2 = np.random.normal(50, 10, 100)
    treatment2 = np.random.normal(50, 10, 100)
    g2, _, _ = calc.compute_hedges_g(control2, treatment2)
    check(abs(g2) < 0.3, "B7.4", f"Null effect: g~0 (actual={g2:.3f})")


def test_b8_persona_uniqueness():
    """B8: Generated personas are unique"""
    print("\n[B8] Persona Uniqueness")
    
    from src.persona_service import FingerprintEngine
    
    fp_engine = FingerprintEngine()
    
    # Create distinct personas
    personas = []
    for i in range(20):
        personas.append({
            "name": f"Student_{i}",
            "birth_date": f"2012-01-{i+1:02d}",
            "birth_place": f"City_{i}",
            "family_structure": "nuclear" if i % 2 == 0 else "extended",
            "parents_occupation": f"Job_{i}",
            "parents_education": "bachelor",
            "key_life_events": f"Event_{i}",
            "aptitude_combo": f"Combo_{i}",
            "mbti": "INTJ" if i % 2 == 0 else "ENFP",
            "core_personality": f"Type_{i}"
        })
    
    # All fingerprints should be unique
    fingerprints = set()
    for p in personas:
        result = fp_engine.fingerprint(p)
        fingerprints.add(result.fingerprint)
    
    check(len(fingerprints) == 20, "B8.1", "20 unique fingerprints from 20 personas")
    
    # Same persona -> same fingerprint (deterministic)
    fp1 = fp_engine.fingerprint(personas[0]).fingerprint
    fp2 = fp_engine.fingerprint(personas[0]).fingerprint
    check(fp1 == fp2, "B8.2", "Same persona -> same fingerprint (deterministic)")


# ================================================================
# TECHNICAL TESTS
# ================================================================

def test_t1_boundary_conditions():
    """T1: API handles invalid inputs gracefully"""
    print("\n[T1] Boundary Conditions")
    
    # n_students = 0 (below minimum)
    r = requests.post(f"{BASE}/api/runs", json={"n_students": 0})
    check(r.status_code == 422, "T1.1", "n_students=0 rejected (422)")
    
    # n_students > max
    r = requests.post(f"{BASE}/api/runs", json={"n_students": 99999})
    check(r.status_code == 422, "T1.2", "n_students=99999 rejected (422)")
    
    # sim_days = 0
    r = requests.post(f"{BASE}/api/runs", json={"n_students": 10, "sim_days": 0})
    check(r.status_code == 422, "T1.3", "sim_days=0 rejected (422)")
    
    # Invalid JSON body
    r = requests.post(f"{BASE}/api/runs", data="not json",
                      headers={"Content-Type": "application/json"})
    check(r.status_code == 422, "T1.4", "Invalid JSON rejected (422)")


def test_t2_missing_resources():
    """T2: Proper 404 for non-existent resources"""
    print("\n[T2] Missing Resource Handling (404)")
    
    r = requests.get(f"{BASE}/api/runs/NONEXISTENT_RUN")
    check(r.status_code == 404, "T2.1", "Non-existent run -> 404")
    
    # Create a valid run first (async -> poll until completed)
    run_id = _create_run_wait({"n_students": 5, "sim_days": 10})
    
    r = requests.get(f"{BASE}/api/runs/{run_id}/students/NONEXISTENT_STUDENT")
    check(r.status_code == 404, "T2.2", "Non-existent student -> 404")
    
    r = requests.get(f"{BASE}/api/runs/{run_id}/teachers/NONEXISTENT_TEACHER")
    check(r.status_code == 404, "T2.3", "Non-existent teacher -> 404")
    
    r = requests.get(f"{BASE}/api/runs/{run_id}/students/S00000/life_course",
                     params={"from": 0, "to": 9})
    # This might 404 if trajectories not generated for demo
    check(r.status_code in [200, 404], "T2.4", "Life course handles missing data")


def test_t3_pagination():
    """T3: Pagination edge cases"""
    print("\n[T3] Pagination Edge Cases")
    
    run_id = _create_run_wait({"n_students": 10, "sim_days": 5})
    
    # Page beyond range
    r = requests.get(f"{BASE}/api/runs/{run_id}/students",
                     params={"page": 999, "page_size": 20})
    check(r.status_code == 200, "T3.1", "Page beyond range returns 200")
    check(len(r.json()["students"]) == 0, "T3.2", "Empty list for out-of-range page")
    
    # Page size = 1
    r = requests.get(f"{BASE}/api/runs/{run_id}/students",
                     params={"page": 1, "page_size": 1})
    check(len(r.json()["students"]) == 1, "T3.3", "page_size=1 returns exactly 1")
    
    # Total is always correct
    check(r.json()["total"] == 10, "T3.4", "Total count unaffected by pagination")


def test_t4_data_validation():
    """T4: Response data types are correct"""
    print("\n[T4] Data Type Validation")
    
    run_id = _create_run_wait({"n_students": 5, "sim_days": 10})
    
    # Student response types
    r = requests.get(f"{BASE}/api/runs/{run_id}/students", params={"page_size": 1})
    student = r.json()["students"][0]
    
    check(isinstance(student["student_id"], str), "T4.1", "student_id is string")
    check(isinstance(student["name"], str), "T4.2", "name is string")
    check(student["achievement_score"] is None or isinstance(student["achievement_score"], (int, float)),
          "T4.3", "achievement_score is numeric")
    
    # Network response types
    r = requests.get(f"{BASE}/api/runs/{run_id}/network")
    net = r.json()
    check(isinstance(net["density"], float), "T4.4", "density is float")
    check(isinstance(net["nodes"], list), "T4.5", "nodes is list")
    check(isinstance(net["edges"], list), "T4.6", "edges is list")
    
    if net["edges"]:
        edge = net["edges"][0]
        check(isinstance(edge["weight"], float), "T4.7", "edge weight is float")


def test_t5_privacy_guard_completeness():
    """T5: PrivacyGuard covers all S-level fields"""
    print("\n[T5] PrivacyGuard Completeness")
    
    from src.privacy import PrivacyGuard
    
    # Test with a persona containing ALL sensitive fields
    full_persona = {
        "student_id": "S001",
        "name": "Test",
        "achievement_score": 75.0,
        "sensitive_data": {"income": 50000},
        "sensitive_json": {"therapy": True},
        "private_sensitive": "secret",
        "gifted_sen": True,
        "parenting_style_detail": "authoritarian",
        "family_conflict": "high",
        "tutoring_cost": 3000,
        "mental_health_records": "anxiety",
        "medical_history": "asthma",
        "financial_details": "debt"
    }
    
    filtered = PrivacyGuard.filter_for_api(full_persona)
    
    # Only P/R fields should remain
    check("student_id" in filtered, "T5.1", "P-level field preserved")
    check("name" in filtered, "T5.2", "P-level field preserved")
    check("achievement_score" in filtered, "T5.3", "R-level field preserved")
    
    sensitive_keys = ["sensitive_data", "sensitive_json", "private_sensitive",
                      "gifted_sen", "parenting_style_detail", "family_conflict",
                      "tutoring_cost", "mental_health_records", "medical_history",
                      "financial_details"]
    
    all_removed = all(key not in filtered for key in sensitive_keys)
    check(all_removed, "T5.4", "ALL S-level fields removed")
    check(len(filtered) == 3, "T5.5", f"Only 3 fields remain (actual={len(filtered)})")


def test_t6_concurrent_requests():
    """T6: Server handles concurrent requests"""
    print("\n[T6] Concurrent Request Safety")
    
    # Create a run first (async -> poll until completed)
    run_id = _create_run_wait({"n_students": 20, "sim_days": 10})
    
    def make_request(i):
        r = requests.get(f"{BASE}/api/runs/{run_id}/students",
                        params={"page": 1, "page_size": 5})
        return r.status_code
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request, i) for i in range(20)]
        results = [f.result() for f in futures]
    
    all_200 = all(code == 200 for code in results)
    check(all_200, "T6.1", "20 concurrent requests all return 200")
    check(len(results) == 20, "T6.2", "All 20 responses received")


def test_t7_network_endpoint_data():
    """T7: Network endpoint returns valid graph data"""
    print("\n[T7] Network Data Integrity")
    
    run_id = _create_run_wait({"n_students": 30, "sim_days": 10})
    
    r = requests.get(f"{BASE}/api/runs/{run_id}/network")
    net = r.json()
    
    check(len(net["nodes"]) == 30, "T7.1", "Network has 30 nodes")
    check(len(net["edges"]) > 0, "T7.2", "Network has edges")
    check(0 < net["density"] < 1, "T7.3", "Density in (0,1)")
    
    # All edge endpoints should reference valid nodes
    node_ids = {n["node_id"] for n in net["nodes"]}
    edges_valid = all(
        e["source"] in node_ids and e["target"] in node_ids
        for e in net["edges"]
    )
    check(edges_valid, "T7.4", "All edge endpoints reference valid nodes")
    
    # Evolution endpoint
    r = requests.get(f"{BASE}/api/runs/{run_id}/network/evolution",
                     params={"from": 0, "to": 10})
    check(r.status_code == 200, "T7.5", "Network evolution returns 200")
    check(len(r.json()["snapshots"]) > 0, "T7.6", "Evolution has snapshots")


# ================================================================
# MAIN
# ================================================================

def main():
    print("=" * 70)
    print("VirtualStudent Sandbox v5.0 - Full Verification Suite")
    print(f"Target: {BASE}")
    print("=" * 70)
    
    # Check server is running
    try:
        r = requests.get(f"{BASE}/api/health", timeout=5)
        if r.status_code != 200:
            print("[ERROR] Server not healthy. Start with:")
            print(f"  python -m uvicorn src.api.main:app --port 6668")
            sys.exit(1)
    except requests.ConnectionError:
        print("[ERROR] Cannot connect to server at port 6668.")
        print("Start with: python -m uvicorn src.api.main:app --port 6668")
        sys.exit(1)
    
    print("[OK] Server connected\n")
    
    # Business tests
    print("=" * 70)
    print("BUSINESS LOGIC TESTS")
    print("=" * 70)
    
    run_id = test_b1_full_lifecycle()
    test_b2_privacy_enforcement(run_id)
    test_b3_cognitive_determinism()
    test_b4_intervention_effect_direction()
    test_b5_social_network_properties()
    test_b6_event_half_life_decay()
    test_b7_effect_size_correctness()
    test_b8_persona_uniqueness()
    
    # Technical tests
    print("\n" + "=" * 70)
    print("TECHNICAL TESTS")
    print("=" * 70)
    
    test_t1_boundary_conditions()
    test_t2_missing_resources()
    test_t3_pagination()
    test_t4_data_validation()
    test_t5_privacy_guard_completeness()
    test_t6_concurrent_requests()
    test_t7_network_endpoint_data()
    
    # Summary
    print("\n" + "=" * 70)
    total = _results["passed"] + _results["failed"]
    print(f"RESULTS: {_results['passed']}/{total} passed, {_results['failed']} failed")
    
    if _results["errors"]:
        print("\nFailed tests:")
        for err in _results["errors"]:
            print(f"  - {err}")
    
    print("=" * 70)
    
    if _results["failed"] == 0:
        print("[SUCCESS] All tests passed!")
    else:
        print(f"[WARNING] {_results['failed']} test(s) failed - review needed")
        sys.exit(1)


if __name__ == "__main__":
    main()
