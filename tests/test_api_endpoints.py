"""Quick API endpoint test"""
import requests
import json
import time

BASE = "http://127.0.0.1:6668"


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

def test_all():
    print("=" * 60)
    print("API Endpoint Tests")
    print("=" * 60)
    
    # 1. Health
    r = requests.get(f"{BASE}/api/health")
    print(f"\n[1] GET /api/health -> {r.status_code}")
    assert r.status_code == 200
    
    # 2. Create run (async endpoint -> poll until completed)
    run_id = _create_run_wait({
        "n_students": 20, "n_teachers": 3, "n_parents": 20,
        "sim_days": 30, "seed": 42
    })
    print(f"[2] POST /api/runs -> 200 (polled to completion)")
    print(f"    run_id = {run_id}")
    
    # 3. Get run status
    r = requests.get(f"{BASE}/api/runs/{run_id}")
    print(f"[3] GET /api/runs/{{run_id}} -> {r.status_code}")
    assert r.status_code == 200
    assert r.json()["n_students"] == 20
    
    # 4. List students
    r = requests.get(f"{BASE}/api/runs/{run_id}/students", params={"page": 1, "page_size": 5})
    print(f"[4] GET /api/runs/{{run_id}}/students -> {r.status_code}")
    assert r.status_code == 200
    data = r.json()
    print(f"    total={data['total']}, page_size={len(data['students'])}")
    # Verify privacy: no sensitive_data
    for s in data["students"]:
        assert "sensitive_data" not in s, "PRIVACY VIOLATION: sensitive_data leaked!"
    print(f"    [OK] PrivacyGuard: sensitive_data filtered")
    
    # 5. Get single student
    student_id = data["students"][0]["student_id"]
    r = requests.get(f"{BASE}/api/runs/{run_id}/students/{student_id}")
    print(f"[5] GET /api/runs/{{run_id}}/students/{{id}} -> {r.status_code}")
    assert r.status_code == 200
    assert "sensitive_data" not in r.json()
    
    # 6. Timeline
    r = requests.get(f"{BASE}/api/runs/{run_id}/students/{student_id}/timeline")
    print(f"[6] GET .../students/{{id}}/timeline -> {r.status_code}")
    assert r.status_code == 200
    tl = r.json()
    print(f"    events={len(tl['events'])}, total_gain={tl['total_learning_gain']:.3f}")
    
    # 7. Life course
    r = requests.get(f"{BASE}/api/runs/{run_id}/students/{student_id}/life_course",
                     params={"from": 0, "to": 29})
    print(f"[7] GET .../students/{{id}}/life_course -> {r.status_code}")
    assert r.status_code == 200
    lc = r.json()
    print(f"    days={len(lc['days'])}, ach_points={len(lc['achievement'])}")
    
    # 8. Teacher
    r = requests.get(f"{BASE}/api/runs/{run_id}/teachers/T0000")
    print(f"[8] GET /api/runs/{{run_id}}/teachers/T0000 -> {r.status_code}")
    assert r.status_code == 200
    print(f"    teacher: {r.json()['name']}, style={r.json()['teaching_style']}")
    
    # 9. Scene comparison
    r = requests.get(f"{BASE}/api/runs/{run_id}/scene_comparison")
    print(f"[9] GET .../scene_comparison -> {r.status_code}")
    assert r.status_code == 200
    scenes = r.json()["scenes"]
    print(f"    scenes: {list(scenes.keys())}")
    
    # 10. Subgroups
    r = requests.get(f"{BASE}/api/runs/{run_id}/subgroups", params={"dims": "ses,gender"})
    print(f"[10] GET .../subgroups -> {r.status_code}")
    assert r.status_code == 200
    print(f"     dimensions: {[s['dimension'] for s in r.json()]}")
    
    # 11. Network
    r = requests.get(f"{BASE}/api/runs/{run_id}/network")
    print(f"[11] GET .../network -> {r.status_code}")
    assert r.status_code == 200
    net = r.json()
    print(f"     nodes={len(net['nodes'])}, edges={len(net['edges'])}, density={net['density']:.3f}")
    
    # 12. Network evolution
    r = requests.get(f"{BASE}/api/runs/{run_id}/network/evolution",
                     params={"from": 0, "to": 30})
    print(f"[12] GET .../network/evolution -> {r.status_code}")
    assert r.status_code == 200
    print(f"      snapshots={len(r.json()['snapshots'])}")
    
    # 13. Counterfactual create
    r = requests.post(f"{BASE}/api/runs/{run_id}/counterfactual", json={
        "modification": {"remove_tutoring": True},
        "days": 30
    })
    print(f"[13] POST .../counterfactual -> {r.status_code}")
    assert r.status_code == 200
    cf_id = r.json()["cf_id"]
    print(f"      cf_id = {cf_id}")
    
    # 14. Counterfactual comparison
    r = requests.get(f"{BASE}/api/runs/{run_id}/counterfactual/{cf_id}/comparison")
    print(f"[14] GET .../counterfactual/{{cf_id}}/comparison -> {r.status_code}")
    assert r.status_code == 200
    cf = r.json()
    print(f"      g={cf['effect_size_g']:.2f}, CI={cf['ci_95']}")
    
    # 15. Report (成果输出中心)
    r = requests.get(f"{BASE}/api/runs/{run_id}/report")
    print(f"[15] GET .../report -> {r.status_code}")
    assert r.status_code == 200
    rep = r.json()
    for key in ("report_card", "research_plan", "recommendations", "markdown"):
        assert key in rep, f"report missing key: {key}"
    # 教学改进建议: top-5, each with three elements (evidence/confidence/distortion_warning)
    recs = rep["recommendations"]
    assert len(recs) == 5, f"expected 5 recommendations, got {len(recs)}"
    for rec in recs:
        for elem in ("evidence", "confidence", "distortion_warning"):
            assert rec.get(elem), f"recommendation missing element: {elem}"
    # 科学假设与研究计划: 8 sections, non-empty hypotheses & references (zero fabricated citations)
    plan = rep["research_plan"]
    assert len(plan["sections"]) == 8, f"expected 8 plan sections, got {len(plan['sections'])}"
    assert plan["hypotheses"], "research plan has no hypotheses"
    assert plan["references"], "research plan has no references"
    # Markdown export non-empty
    assert rep["markdown"].strip(), "markdown export is empty"
    print(f"      recs={len(recs)}, sections={len(plan['sections'])}, "
          f"hypotheses={len(plan['hypotheses'])}, md_chars={len(rep['markdown'])}")
    
    print("\n" + "=" * 60)
    print("[SUCCESS] All 15 API endpoint tests passed!")
    print("=" * 60)

if __name__ == "__main__":
    test_all()
