"""The robustness page must use a lightweight projection, not full reports."""

from fastapi.testclient import TestClient

import src.api.main as main


def test_robustness_summary_does_not_build_reports(monkeypatch):
    run_id = "RUN_ROBUSTNESS_FAST"
    main._runs[run_id] = {
        "run_id": run_id,
        "status": "completed",
        "created_at": "2099-01-01T00:00:00",
        "completed_at": "2099-01-01T00:00:01",
        "sim_days": 7,
        "students": {"S0001": {}},
        "teachers": {},
        "parents": {},
        "config": {"seed": 123},
        "effect_sizes": [{
            "intervention_id": "air_conditioning",
            "hedges_g": 0.2,
            "ci_lower": 0.1,
            "ci_upper": 0.3,
        }],
    }

    def fail_if_report_is_built(*args, **kwargs):
        raise AssertionError("robustness endpoint must not build a full report")

    monkeypatch.setattr(main, "_build_run_report", fail_if_report_is_built)
    response = TestClient(main.app).get("/api/robustness")

    assert response.status_code == 200
    body = response.json()
    item = next(item for item in body["runs"] if item["run_id"] == run_id)
    assert item["seed"] == 123
    assert item["effect_sizes"][0]["hedges_g"] == 0.2
