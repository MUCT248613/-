"""
Tests for new API endpoints: FR-F2 (calibration), FR-F3 (distortion map),
FR-F4 (prescreening), FR-F5 (HITL), FR-F7 (parents), FR-F10 (subgroups).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


@pytest.fixture(scope="module")
def run_id():
    """Create a run and return its ID."""
    resp = client.post("/api/runs", json={
        "n_students": 30, "n_teachers": 5, "n_parents": 30, "sim_days": 30, "seed": 42
    })
    assert resp.status_code == 200
    return resp.json()["run_id"]


def test_parents_endpoint(run_id):
    """FR-F7: parent list + single parent profile."""
    print("[TEST] FR-F7 parents endpoint ...")
    resp = client.get(f"/api/runs/{run_id}/parents?page=1&page_size=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 30
    assert len(data["parents"]) == 10
    p = data["parents"][0]
    assert "parent_id" in p
    assert "education_level" in p
    assert "involvement_style" in p
    # Single parent
    pid = p["parent_id"]
    resp2 = client.get(f"/api/runs/{run_id}/parents/{pid}")
    assert resp2.status_code == 200
    assert resp2.json()["parent_id"] == pid
    print("  [OK] Parents list + profile work")


def test_calibration_endpoint(run_id):
    """FR-F2: calibration diagnostics."""
    print("[TEST] FR-F2 calibration diagnostics ...")
    resp = client.get(f"/api/runs/{run_id}/calibration")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == run_id
    assert data["data_source"] in ("literature", "real", "synthetic")
    assert 0 <= data["cognitive_distance"] <= 1
    assert data["verdict"] in ("pass", "marginal", "fail")
    assert len(data["bkt_params_virtual"]) == 4
    assert len(data["diagnostics"]) == 4
    for d in data["diagnostics"]:
        assert d["parameter"] in ("p_know", "p_learn", "p_slip", "p_guess")
        assert d["status"] in ("ok", "divergent")
    # Literature reference baseline (published BKT point estimates)
    if data["data_source"] == "literature":
        assert data["reference_basis"]["n_studies"] >= 1
        assert len(data["bkt_params_reference"]) == 4
    print(f"  [OK] Calibration verdict={data['verdict']}, distance={data['cognitive_distance']}, source={data['data_source']}")


def test_distortion_map_endpoint(run_id):
    """FR-F3: distortion map."""
    print("[TEST] FR-F3 distortion map ...")
    resp = client.get(f"/api/runs/{run_id}/distortion_map")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == run_id
    assert len(data["interventions"]) > 0
    assert len(data["scenes"]) > 0
    assert len(data["metrics"]) > 0
    assert len(data["cells"]) > 0
    assert data["n_high_distortion"] >= 0
    assert data["summary"]
    for cell in data["cells"][:5]:
        assert "intervention" in cell
        assert "scene" in cell
        assert "metric" in cell
        assert "category" in cell
    print(f"  [OK] {len(data['cells'])} cells, {data['n_high_distortion']} distorted")


def test_prescreening_endpoint(run_id):
    """FR-F4: prescreening report."""
    print("[TEST] FR-F4 prescreening report ...")
    resp = client.get(f"/api/runs/{run_id}/prescreening")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == run_id
    assert len(data["candidates"]) > 0
    assert data["go_count"] + data["no_go_count"] + data["conditional_count"] == len(data["candidates"])
    assert len(data["criteria"]) == 4
    assert data["disclaimer"]
    for c in data["candidates"]:
        assert c["decision"] in ("go", "conditional", "no_go")
        assert "checks" in c
        assert len(c["checks"]) == 4
    print(f"  [OK] GO={data['go_count']}, COND={data['conditional_count']}, NO_GO={data['no_go_count']}")


def test_hitl_feedback(run_id):
    """FR-F5: human-in-the-loop feedback submit + list."""
    print("[TEST] FR-F5 HITL feedback ...")
    # Initially empty
    resp = client.get(f"/api/runs/{run_id}/hitl/feedback")
    assert resp.status_code == 200
    initial_total = resp.json()["total"]

    # Submit feedback
    payload = {
        "target_type": "intervention",
        "target_id": "cognitive_support",
        "verdict": "agree",
        "comment": "证据充分，支持进入实证",
        "expert_role": "researcher",
    }
    resp2 = client.post(f"/api/runs/{run_id}/hitl/feedback", json=payload)
    assert resp2.status_code == 200
    fb = resp2.json()
    assert fb["feedback_id"].startswith("FB_")
    assert fb["verdict"] == "agree"
    assert fb["target_id"] == "cognitive_support"

    # List should now have one more
    resp3 = client.get(f"/api/runs/{run_id}/hitl/feedback")
    assert resp3.json()["total"] == initial_total + 1
    print("  [OK] HITL submit + list work")


def test_subgroups_extended(run_id):
    """FR-F10: extended subgroup dimensions."""
    print("[TEST] FR-F10 extended subgroups ...")
    dims = "ses,gender,grade,sleep_hours,self_efficacy,teacher_style"
    resp = client.get(f"/api/runs/{run_id}/subgroups?dims={dims}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 6
    for slice_result in data:
        assert slice_result["dimension"] in dims.split(",")
        assert len(slice_result["groups"]) > 0, f"dim {slice_result['dimension']} has no groups"
        for g in slice_result["groups"]:
            assert "label" in g
            assert "n" in g
            assert "mean_ach" in g
            assert "effect_size" in g
    print(f"  [OK] All 6 extended dimensions return data")


if __name__ == "__main__":
    print("=" * 70)
    print("New API Endpoint Tests (FR-F2/F3/F4/F5/F7/F10)")
    print("=" * 70)
    pytest.main([__file__, "-v"])
