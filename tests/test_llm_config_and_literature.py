"""
Tests for:
  - LLM runtime configuration endpoints (GET/POST /api/llm/config)
  - Literature reference BKT baselines (src.calibrate.literature_reference)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient
from src.api.main import app
from src.calibrate.literature_reference import (
    LITERATURE_BKT,
    BKT_PARAM_NAMES,
    get_reference_params,
    get_reference_summary,
    list_studies,
)
import src.llm as llm_module

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_llm_client():
    """The config tests install a FAKE api key on the module-level singleton.
    Force it back to offline deterministic mode afterwards so later test files
    (persona generation, etc.) don't attempt real API calls and fail auth."""
    yield
    offline = llm_module.LLMClient(api_key=None, base_url=None, default_model="qwen-plus")
    offline.api_key = ""      # bypass any DASHSCOPE_API_KEY env fallback
    offline._client = None    # force offline / mock mode
    llm_module._default_client = offline


# ============ LLM configuration endpoints ============

def test_llm_config_get():
    """GET /api/llm/config returns preset Bailian base URL and model list."""
    print("[TEST] GET /api/llm/config ...")
    resp = client.get("/api/llm/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "token-plan.cn-beijing.maas.aliyuncs.com" in data["base_url"]
    assert data["default_model"]
    assert isinstance(data["api_key_set"], bool)
    assert isinstance(data["is_live"], bool)
    assert len(data["available_models"]) >= 1
    assert "qwen-plus" in data["available_models"]
    # API key must never be echoed in plaintext
    assert "api_key" not in data or data.get("api_key_masked", "") != data.get("api_key", "")
    print(f"  [OK] base_url={data['base_url']}, model={data['default_model']}, live={data['is_live']}")


def test_llm_config_update():
    """POST /api/llm/config updates model/base_url at runtime; key is masked."""
    print("[TEST] POST /api/llm/config ...")
    resp = client.post("/api/llm/config", json={
        "base_url": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-max",
        "api_key": "sk-test-1234567890abcdef",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["default_model"] == "qwen-max"
    assert data["api_key_set"] is True
    # Masked, never plaintext
    assert "1234567890abcdef" not in data["api_key_masked"]
    assert data["api_key_masked"].endswith("cdef")
    print(f"  [OK] model updated to {data['default_model']}, key masked={data['api_key_masked']}")


def test_llm_config_partial_update_keeps_key():
    """Omitting api_key keeps the previously configured key."""
    print("[TEST] POST /api/llm/config (partial, keep key) ...")
    # First set a key
    client.post("/api/llm/config", json={"api_key": "sk-partial-keepme-9999"})
    # Then update only the model
    resp = client.post("/api/llm/config", json={"default_model": "qwen-turbo"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["default_model"] == "qwen-turbo"
    assert data["api_key_set"] is True  # key preserved
    print("  [OK] partial update preserved existing API key")


# ============ Literature reference baselines ============

def test_literature_studies_structure():
    """Each literature study has a citation, dataset, and 4 BKT params."""
    print("[TEST] literature reference structure ...")
    studies = list_studies()
    assert len(studies) >= 3
    for s in studies:
        assert s["citation"], f"study {s['study_id']} missing citation"
        assert s["dataset"]
        for p in BKT_PARAM_NAMES:
            assert 0.0 < s["params"][p] < 1.0, f"{s['study_id']}.{p} out of (0,1)"
    print(f"  [OK] {len(studies)} literature studies, all params in (0,1)")


def test_literature_aggregated_reference():
    """Aggregated reference is the mean across studies for each param."""
    print("[TEST] literature aggregated reference ...")
    agg = get_reference_params()
    assert set(agg.keys()) == set(BKT_PARAM_NAMES)
    for name in BKT_PARAM_NAMES:
        values = [e["params"][name] for e in LITERATURE_BKT.values()]
        expected = sum(values) / len(values)
        assert abs(agg[name] - expected) < 1e-9
    print(f"  [OK] aggregated={ {k: round(v, 3) for k, v in agg.items()} }")


def test_literature_single_study_lookup():
    """get_reference_params(study_id) returns that study's point estimates."""
    print("[TEST] literature single-study lookup ...")
    sid = next(iter(LITERATURE_BKT))
    params = get_reference_params(sid)
    assert params == LITERATURE_BKT[sid]["params"]
    # Unknown study raises
    try:
        get_reference_params("does_not_exist")
        assert False, "expected KeyError"
    except KeyError:
        pass
    print(f"  [OK] single-study lookup works for {sid}")


def test_literature_summary_for_display():
    """Summary exposes aggregated params, study count, and a note."""
    print("[TEST] literature summary ...")
    summary = get_reference_summary()
    assert summary["n_studies"] == len(LITERATURE_BKT)
    assert len(summary["aggregated"]) == 4
    assert summary["note"]
    print(f"  [OK] summary n_studies={summary['n_studies']}")
