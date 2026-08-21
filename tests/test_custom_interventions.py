"""
Tests for researcher-defined candidate interventions.

The API's ``RunCreateRequest.interventions`` field lets a researcher submit
their own hypotheses; the run then evaluates exactly those candidates
(researcher-first) instead of the built-in evidence battery, and the report /
prescreening endpoints label them from the run's own metadata.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

from src.api.main import app
from src.api.real_run import (
    build_real_run, _resolve_run_arms, _assign_arms, _INTERVENTION_ARMS,
)
from src.api.models import RunCreateRequest

client = TestClient(app)


def _config(**kw):
    base = dict(n_students=48, n_teachers=5, n_parents=48, sim_days=24, seed=7)
    base.update(kw)
    return RunCreateRequest(**base)


def test_researcher_arms_replace_builtin():
    """Submitted candidates become the whole experiment (control kept)."""
    cfg = _config(interventions=[
        {"label": "增加家教", "default_channel": "parent_mediated",
         "target_scene": ["home"], "effect_achievement": 6.0,
         "evidence_hedges_g": 0.4, "cost_yuan": 120.0,
         "action": "为低 SES 家庭匹配志愿家教，每周三次"},
        {"label": "晨读计划", "default_channel": "teacher_mediated",
         "target_scene": ["school"], "effect_achievement": 3.0},
    ])
    arms, metas = _resolve_run_arms(cfg)
    ids = [a[0] for a in arms]
    assert len(ids) == 2 and len(set(ids)) == 2
    assert metas[0]["label"] == "增加家教"
    assert metas[0]["source"] == "researcher"
    assert arms[0][4]["achievement"] == 6.0

    run = build_real_run("RUN_TEST_CUSTOM", cfg)
    es_ids = {e["intervention_id"] for e in run["effect_sizes"]}
    assert es_ids == set(ids)
    assert set(run["arms"].keys()) == set(ids) | {"control"}
    assert run["intervention_meta"][0]["label"] == "增加家教"
    # Provenance: the submitted hypotheses are stored with the run config.
    assert run["config"]["interventions"][0]["label"] == "增加家教"


def test_default_run_still_uses_yaml_arms():
    """Without submitted candidates the YAML battery remains the default."""
    arms, metas = _resolve_run_arms(_config(n_students=12))
    assert [a[0] for a in arms] == [a[0] for a in _INTERVENTION_ARMS]
    assert all(m["source"] == "yaml" for m in metas)


def test_api_accepts_researcher_interventions():
    """POST /api/runs carries the candidates; prescreening evaluates them."""
    resp = client.post("/api/runs", json={
        "n_students": 24, "n_teachers": 4, "n_parents": 24,
        "sim_days": 10, "seed": 11,
        "interventions": [
            {"label": "我的方案", "default_channel": "self_study_mediated",
             "effect_achievement": 5.0},
        ],
    })
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]
    detail = client.get(f"/api/runs/{run_id}").json()
    meta = detail.get("intervention_meta") or []
    assert [m["label"] for m in meta] == ["我的方案"]
    pre = client.get(f"/api/runs/{run_id}/prescreening").json()
    assert {c["intervention_id"] for c in pre["candidates"]} == {"C1_custom"}


def test_risk_factor_negative_dose_and_exposure():
    """Risk factors (negative dose) with individual-level exposure randomness."""
    cfg = _config(interventions=[
        {"label": "社区帮派暴露", "default_channel": "direct",
         "target_scene": ["school"], "effect_achievement": -5.0,
         "exposure_rate": 0.5},
    ])
    arms, metas = _resolve_run_arms(cfg)
    assert arms[0][4]["achievement"] == -5.0
    assert arms[0][4]["exposure_rate"] == 0.5

    students = {f"S{i:03d}": {"achievement_score": 50.0} for i in range(200)}
    engine, arm_map, _control = _assign_arms(students, cfg, arms)
    treated = arm_map[arms[0][0]]
    adh = {i.student_id: i.adherence_rate for i in engine.intervention_history}
    frac = sum(1 for sid in treated if adh[sid] == 1.0) / len(treated)
    assert 0.35 <= frac <= 0.65, frac

    # Exposed students lose achievement; unexposed stay untouched.
    day_started = max(1, cfg.sim_days // 4)
    exposed = next(sid for sid in treated if adh[sid] == 1.0)
    unexposed = next(sid for sid in treated if adh[sid] == 0.0)
    stu = {"student_id": exposed, "achievement_score": 50.0}
    engine.apply_interventions_to_student(stu, day_started + 1)
    assert stu["achievement_score"] < 50.0
    stu0 = {"student_id": unexposed, "achievement_score": 50.0}
    engine.apply_interventions_to_student(stu0, day_started + 1)
    assert stu0["achievement_score"] == 50.0
