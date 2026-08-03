"""
Real Data Loader (FR-D1 / C6 比赛硬性)

Parses genuine public learning-log datasets into the unified per-learner
correctness-sequence format consumed by ``CognitiveCalibrator`` and the
pipeline DAG node ``n1_load_realdata``::

    [{"student_id": str, "sequence": [0|1, ...], "kc_id": str|None}, ...]

Supported real sources
----------------------
- ASSISTments 2009-2010 (``skill_builder_data_corrected.csv``)
    key columns: order_id, user_id, correct, skill_id/skill_name
- ASSISTments 2015 (``2015_100_skill_builders_main_problems.csv``)
    key columns: sequence_id, user_id, correct, skill_id
- EdNet KT1 (``KT1/u*.csv`` or a single ``ednet_kt1.csv``)
    key columns: timestamp, action_type, item_id, correct

Honesty guarantee
-----------------
The loader NEVER fabricates data and never relabels synthetic data as real.
If no recognised dataset file is present in the configured directory it
returns ``source="synthetic"`` so downstream code can transparently report
that calibration ran on synthetic logs (see ``data/real/README.md`` for how
to obtain and place the genuine public datasets).

Reference: 需求说明文档 §6 FR-D1, §2 C6; 技术设计文档 §5 M1/M3
"""
from __future__ import annotations

import csv
import glob
import os
from typing import Dict, List, Optional


# Filenames recognised as genuine ASSISTments / EdNet releases.
ASSISTMENTS_2009_NAMES = {
    "skill_builder_data_corrected.csv",
    "skill_builder_data.csv",
    "assistments_2009.csv",
}
ASSISTMENTS_2015_NAMES = {
    "2015_100_skill_builders_main_problems.csv",
    "assistments_2015.csv",
}
EDNET_NAMES = {
    "ednet_kt1.csv",
    "ednet.csv",
}


def _to_binary(value) -> Optional[int]:
    """Coerce a raw 'correct' cell into 0/1; return None if not a valid response."""
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in ("1", "1.0", "true", "correct", "yes"):
        return 1
    if s in ("0", "0.0", "false", "incorrect", "no"):
        return 0
    return None


def _group_into_sequences(rows: List[Dict], user_key: str, correct_key: str,
                          order_key: Optional[str], kc_key: Optional[str],
                          max_learners: Optional[int]) -> List[Dict]:
    """Group flat response rows into per-learner ordered correctness sequences."""
    learners: Dict[str, List] = {}
    for idx, row in enumerate(rows):
        uid = (row.get(user_key) or "").strip()
        if not uid:
            continue
        correct = _to_binary(row.get(correct_key))
        if correct is None:
            continue
        order = row.get(order_key) if order_key else idx
        try:
            order_val = float(order)
        except (TypeError, ValueError):
            order_val = float(idx)
        kc = (row.get(kc_key) or "").strip() if kc_key else ""
        learners.setdefault(uid, []).append((order_val, correct, kc))

    sequences: List[Dict] = []
    for uid, events in learners.items():
        events.sort(key=lambda t: t[0])
        seq = [c for _, c, _ in events]
        if not seq:
            continue
        # Representative KC for this learner (most frequent non-empty).
        kc_counts: Dict[str, int] = {}
        for _, _, kc in events:
            if kc:
                kc_counts[kc] = kc_counts.get(kc, 0) + 1
        kc_id = max(kc_counts, key=kc_counts.get) if kc_counts else None
        sequences.append({
            "student_id": str(uid),
            "sequence": seq,
            "kc_id": kc_id,
            "n_responses": len(seq),
        })

    sequences.sort(key=lambda r: r["student_id"])
    if max_learners:
        sequences = sequences[:max_learners]
    return sequences


def parse_assistments_2009(path: str, max_learners: Optional[int] = None) -> List[Dict]:
    """Parse ASSISTments 2009-2010 skill-builder data into sequences."""
    rows: List[Dict] = []
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    # The corrected release names the correctness column 'correct'.
    return _group_into_sequences(
        rows, user_key="user_id", correct_key="correct",
        order_key="order_id", kc_key="skill_name",
        max_learners=max_learners,
    )


def parse_assistments_2015(path: str, max_learners: Optional[int] = None) -> List[Dict]:
    """Parse ASSISTments 2015 main-problems data into sequences."""
    rows: List[Dict] = []
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return _group_into_sequences(
        rows, user_key="user_id", correct_key="correct",
        order_key="sequence_id", kc_key="skill_id",
        max_learners=max_learners,
    )


def parse_ednet_kt1(path: str, max_learners: Optional[int] = None) -> List[Dict]:
    """Parse an EdNet KT1 file (single user or concatenated) into sequences.

    A single ``u*.csv`` is one learner; a concatenated ``ednet_kt1.csv`` is
    expected to carry a ``user_id`` column.
    """
    rows: List[Dict] = []
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        for row in reader:
            # EdNet logs many action types; keep only graded responses.
            action = (row.get("action_type") or "").strip().lower()
            if action and action != "respond":
                continue
            rows.append(row)

    has_user = "user_id" in rows[0] if rows else False
    if has_user:
        return _group_into_sequences(
            rows, user_key="user_id", correct_key="correct",
            order_key="timestamp", kc_key="item_id",
            max_learners=max_learners,
        )

    # Single-learner file: derive a stable id from the filename (e.g. u12345.csv).
    uid = os.path.splitext(os.path.basename(path))[0]
    seq = _group_into_sequences(
        [{"__uid": uid, **r} for r in rows],
        user_key="__uid", correct_key="correct",
        order_key="timestamp", kc_key="item_id",
        max_learners=None,
    )
    return seq


def synthesize_logs(n_students: int = 50, seed: int = 42) -> List[Dict]:
    """Transparent synthetic fallback (clearly labelled by the caller)."""
    import numpy as np
    rng = np.random.RandomState(seed)
    logs: List[Dict] = []
    for i in range(n_students):
        seq_len = int(rng.randint(8, 20))
        p = float(rng.uniform(0.3, 0.8))
        seq = [int(rng.random() < p) for _ in range(seq_len)]
        logs.append({
            "student_id": f"SYN_{i:04d}",
            "sequence": seq,
            "kc_id": None,
            "n_responses": seq_len,
        })
    return logs


class RealDataLoader:
    """Discover and parse real learning-log datasets with a safe fallback."""

    def __init__(self, data_dir: str = "data/real"):
        self.data_dir = data_dir

    def discover(self) -> Dict[str, List[str]]:
        """Return recognised dataset files grouped by source type."""
        found: Dict[str, List[str]] = {
            "assistments_2009": [],
            "assistments_2015": [],
            "ednet_kt1": [],
        }
        if not os.path.isdir(self.data_dir):
            return found

        for path in glob.glob(os.path.join(self.data_dir, "**", "*.csv"),
                              recursive=True):
            name = os.path.basename(path).lower()
            if name in ASSISTMENTS_2009_NAMES:
                found["assistments_2009"].append(path)
            elif name in ASSISTMENTS_2015_NAMES:
                found["assistments_2015"].append(path)
            elif name in EDNET_NAMES or name.startswith("u") and "ednet" in path.lower():
                found["ednet_kt1"].append(path)
        return found

    def load(self, max_learners: Optional[int] = None,
             n_synthetic: int = 50, seed: int = 42) -> Dict:
        """Load real data if present; otherwise return labelled synthetic logs.

        Returns:
            {
              "logs": [...],                 # unified sequence records
              "source": "real"|"synthetic",
              "dataset": str|None,           # which real dataset was used
              "files": [str, ...],           # real files parsed
              "n_learners": int,
            }
        """
        found = self.discover()

        # Prefer ASSISTments 2009 (richest KC labels), then 2015, then EdNet.
        if found["assistments_2009"]:
            path = found["assistments_2009"][0]
            logs = parse_assistments_2009(path, max_learners)
            return self._result(logs, "real", "ASSISTments 2009-2010", [path])
        if found["assistments_2015"]:
            path = found["assistments_2015"][0]
            logs = parse_assistments_2015(path, max_learners)
            return self._result(logs, "real", "ASSISTments 2015", [path])
        if found["ednet_kt1"]:
            logs: List[Dict] = []
            for path in found["ednet_kt1"]:
                logs.extend(parse_ednet_kt1(path, max_learners))
            if max_learners:
                logs = logs[:max_learners]
            return self._result(logs, "real", "EdNet KT1", found["ednet_kt1"])

        # No real dataset present: transparent synthetic fallback.
        logs = synthesize_logs(n_synthetic, seed)
        return self._result(logs, "synthetic", None, [])

    @staticmethod
    def _result(logs: List[Dict], source: str, dataset: Optional[str],
                files: List[str]) -> Dict:
        return {
            "logs": logs,
            "source": source,
            "dataset": dataset,
            "files": files,
            "n_learners": len(logs),
        }


def load_real_data(data_dir: str = "data/real",
                   max_learners: Optional[int] = None,
                   n_synthetic: int = 50, seed: int = 42) -> Dict:
    """Module-level convenience wrapper around :class:`RealDataLoader`."""
    return RealDataLoader(data_dir).load(
        max_learners=max_learners, n_synthetic=n_synthetic, seed=seed)
