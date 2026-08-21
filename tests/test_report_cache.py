"""Report endpoint must serve repeat requests from the in-memory cache."""
import time

from fastapi.testclient import TestClient

from src.api.main import app


def test_report_cached_after_first_build():
    client = TestClient(app)
    r = client.post(
        "/api/runs",
        json={"n_students": 12, "n_teachers": 2, "n_parents": 12,
              "sim_days": 7, "seed": 7},
    )
    assert r.status_code == 200
    rid = r.json()["run_id"]

    r1 = client.get(f"/api/runs/{rid}/report")
    assert r1.status_code == 200

    t0 = time.time()
    r2 = client.get(f"/api/runs/{rid}/report")
    d2 = time.time() - t0
    assert r2.status_code == 200
    assert d2 < 0.05, f"second report call took {d2:.2f}s, cache miss?"
