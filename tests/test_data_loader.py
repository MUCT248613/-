"""
Tests for the real data loader (FR-D1 / C6).

Verifies that genuine ASSISTments / EdNet CSV formats are parsed into the
unified per-learner sequence format, that real data is preferred over the
synthetic fallback, and that the fallback is transparently labelled.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_loader import (
    RealDataLoader,
    load_real_data,
    parse_assistments_2009,
    parse_ednet_kt1,
)


def _write(path: str, content: str):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)


def test_parse_assistments_2009():
    print("[TEST] Parse ASSISTments 2009-2010 CSV ...")
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "skill_builder_data_corrected.csv")
        _write(path, (
            "order_id,user_id,correct,skill_name\n"
            "1,101,1,Algebra\n"
            "2,101,0,Algebra\n"
            "3,101,1,Algebra\n"
            "4,102,0,Geometry\n"
            "5,102,1,Geometry\n"
        ))
        logs = parse_assistments_2009(path)
        by_id = {r["student_id"]: r for r in logs}
        assert set(by_id) == {"101", "102"}, by_id.keys()
        # order_id ordering must be respected
        assert by_id["101"]["sequence"] == [1, 0, 1]
        assert by_id["102"]["sequence"] == [0, 1]
        assert by_id["101"]["kc_id"] == "Algebra"
        assert by_id["101"]["n_responses"] == 3
    print("  [OK] ASSISTments 2009 parsed & ordered correctly")


def test_parse_ednet_kt1_single_user():
    print("[TEST] Parse EdNet KT1 single-user CSV ...")
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "u777.csv")
        _write(path, (
            "timestamp,action_type,item_id,correct,elapsed_time\n"
            "10,respond,i1,1,500\n"
            "20,respond,i2,0,700\n"
            "30,submit,i2,,0\n"          # non-respond action -> skipped
            "40,respond,i3,1,300\n"
        ))
        logs = parse_ednet_kt1(path)
        assert len(logs) == 1
        assert logs[0]["student_id"] == "u777"
        assert logs[0]["sequence"] == [1, 0, 1]
    print("  [OK] EdNet KT1 parsed, non-respond rows skipped")


def test_loader_prefers_real_over_synthetic():
    print("[TEST] Loader prefers real data when present ...")
    with tempfile.TemporaryDirectory() as d:
        _write(os.path.join(d, "skill_builder_data_corrected.csv"), (
            "order_id,user_id,correct,skill_name\n"
            "1,1,1,Alg\n2,1,1,Alg\n3,2,0,Alg\n"
        ))
        result = RealDataLoader(d).load()
        assert result["source"] == "real"
        assert result["dataset"] == "ASSISTments 2009-2010"
        assert result["n_learners"] == 2
        assert result["files"], "real files should be recorded"
    print("  [OK] Real dataset detected & labelled source=real")


def test_loader_synthetic_fallback_is_transparent():
    print("[TEST] Loader falls back to labelled synthetic when empty ...")
    with tempfile.TemporaryDirectory() as d:
        result = load_real_data(data_dir=d, n_synthetic=12, seed=7)
        assert result["source"] == "synthetic"
        assert result["dataset"] is None
        assert result["files"] == []
        assert result["n_learners"] == 12
        assert all(r["student_id"].startswith("SYN_") for r in result["logs"])
    print("  [OK] Synthetic fallback transparently labelled")


def test_loaded_real_data_feeds_calibrator():
    print("[TEST] Loaded real data feeds CognitiveCalibrator ...")
    from src.calibrate import CognitiveCalibrator
    with tempfile.TemporaryDirectory() as d:
        _write(os.path.join(d, "skill_builder_data_corrected.csv"), (
            "order_id,user_id,correct,skill_name\n"
            + "".join(
                f"{o},{u},{c},Alg\n"
                for u in range(1, 21)
                for o, c in enumerate([(o % 3 != 0) and 1 or 0 for o in range(10)], start=1)
            )
        ))
        result = RealDataLoader(d).load()
        assert result["source"] == "real"
        cal = CognitiveCalibrator(n_trials=10)
        out = cal.calibrate(result["logs"])
        assert "params" in out and "distance" in out
        for k in ("p_know", "p_learn", "p_slip", "p_guess"):
            assert k in out["params"]
    print("  [OK] Real-data calibration produced BKT params")


if __name__ == "__main__":
    print("=" * 70)
    print("Real Data Loader Tests (FR-D1 / C6)")
    print("=" * 70)
    test_parse_assistments_2009()
    test_parse_ednet_kt1_single_user()
    test_loader_prefers_real_over_synthetic()
    test_loader_synthetic_fallback_is_transparent()
    test_loaded_real_data_feeds_calibrator()
    print("\n" + "=" * 70)
    print("[SUCCESS] All data loader tests passed!")
    print("=" * 70)
