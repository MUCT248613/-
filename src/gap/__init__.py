"""
VirtualStudent Sandbox v6.0 - Gap Analysis Module (M5)

Implements §5 M5 差距量化 (Gap Quantification).

Quantifies the divergence between REAL observed data and VIRTUAL simulated
data across 4 metric families (v2.0):
  - learning_curve: P(correct) by opportunity
  - error_dist: error pattern distribution
  - first_correct: latency to first correct
  - variance_ratio: inter-student variance

v3.0 extends the distortion map to THREE dimensions:
  intervention x scene x subgroup

Each gap record carries a distortion_category (direction of bias) so that
downstream ranking (M6) can avoid over-prioritizing distorted regions.

Reference: 技术设计文档 §5 M5, §4.5, §6 gap_records table
"""
from typing import Dict, List, Optional, Any, Callable

import numpy as np


class GapAnalyst:
    """
    Compute real-vs-virtual gaps and build the 3D distortion map.
    """
    
    METRICS = ["learning_curve", "error_dist", "first_correct", "variance_ratio"]
    
    # Distortion categories (direction of bias)
    DISTORTION_CATEGORIES = [
        "overestimate",        # virtual > real (optimistic bias)
        "underestimate",       # virtual < real (pessimistic bias)
        "variance_mismatch",   # spread differs
        "shape_mismatch",      # curve shape differs
        "none",                # within tolerance
    ]
    
    def __init__(self, tolerance: float = 0.10):
        self.tolerance = tolerance
    
    def analyze(self, real_data: Dict[str, np.ndarray],
                virtual_data: Dict[str, np.ndarray],
                subgroup_filter: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Compute gap records for all metrics.
        
        Args:
            real_data: {metric_name: array of real values}
            virtual_data: {metric_name: array of virtual values}
            subgroup_filter: Optional subgroup definition (e.g. {"gender": "F"})
        
        Returns:
            List of gap_records (one per metric)
        """
        records = []
        for metric in self.METRICS:
            real = np.asarray(real_data.get(metric, []), dtype=float)
            virtual = np.asarray(virtual_data.get(metric, []), dtype=float)
            
            if len(real) == 0 or len(virtual) == 0:
                continue
            
            gap_magnitude, distortion = self._compute_gap(metric, real, virtual)
            
            records.append({
                "metric": metric,
                "real_value": float(np.mean(real)),
                "virtual_value": float(np.mean(virtual)),
                "gap_magnitude": float(gap_magnitude),
                "distortion_category": distortion,
                "subgroup_filter": subgroup_filter or {},
            })
        
        return records
    
    def _compute_gap(self, metric: str, real: np.ndarray,
                     virtual: np.ndarray) -> tuple:
        """Compute gap magnitude and distortion category for one metric."""
        real_mean = float(np.mean(real))
        virt_mean = float(np.mean(virtual))
        
        if metric == "variance_ratio":
            # virtual is a ratio series (cohort spread / reference spread),
            # so a well-calibrated simulation has mean ~= 1. Compare on that
            # scale (the old var-of-ratio comparison divided by ~1e-6 and
            # flagged every run as distorted).
            magnitude = abs(virt_mean - 1.0)
            category = ("variance_mismatch" if magnitude > self.tolerance else "none")
            return magnitude, category
        
        if metric == "learning_curve":
            # Shape-aware: mean absolute difference across the curve
            n = min(len(real), len(virtual))
            magnitude = float(np.mean(np.abs(real[:n] - virtual[:n])))
            bias = virt_mean - real_mean
            if magnitude <= self.tolerance:
                category = "none"
            elif abs(bias) > magnitude * 0.7:
                category = "overestimate" if bias > 0 else "underestimate"
            else:
                category = "shape_mismatch"
            return magnitude, category
        
        # Default: relative mean difference with direction
        magnitude = abs(virt_mean - real_mean) / max(abs(real_mean), 1e-6)
        bias = virt_mean - real_mean
        if magnitude <= self.tolerance:
            category = "none"
        else:
            category = "overestimate" if bias > 0 else "underestimate"
        return magnitude, category
    
    def build_distortion_map(self, gap_records: List[Dict],
                             interventions: List[str],
                             scenes: List[str],
                             subgroups: List[Dict]) -> Dict[str, Any]:
        """
        Build the 3D distortion map: intervention x scene x subgroup.
        
        Organizes gap records into a nested structure and flags cells where
        distortion is high (so M6 can down-rank them).
        
        Returns:
            {"map": {intervention: {scene: {subgroup_key: [records]}}},
             "high_distortion_cells": [...]}
        """
        dist_map: Dict[str, Any] = {}
        high_cells = []
        
        for rec in gap_records:
            intv = rec.get("intervention_id", "default")
            scene = rec.get("scene", "school")
            sg_key = self._subgroup_key(rec.get("subgroup_filter", {}))
            
            dist_map.setdefault(intv, {}).setdefault(scene, {}).setdefault(sg_key, [])
            dist_map[intv][scene][sg_key].append(rec)
            
            if rec["distortion_category"] != "none" and \
               rec["gap_magnitude"] > self.tolerance * 2:
                high_cells.append({
                    "intervention": intv, "scene": scene, "subgroup": sg_key,
                    "metric": rec["metric"], "category": rec["distortion_category"],
                })
        
        return {"map": dist_map, "high_distortion_cells": high_cells}
    
    def heldout_validation(self, real_logs: List[Dict],
                           predictor: Callable, holdout_ratio: float = 0.2,
                           seed: int = 42) -> Dict[str, float]:
        """
        Held-out validation (v2.0 n9): fit on a subset, evaluate gap on the
        held-out portion to guard against overfitting the calibration.
        
        Args:
            real_logs: Full real log set
            predictor: fn(student_logs) -> predicted metric array
            holdout_ratio: Fraction held out
        
        Returns:
            {"train_gap": ..., "holdout_gap": ..., "overfit_ratio": ...}
        """
        rng = np.random.RandomState(seed)
        n = len(real_logs)
        idx = rng.permutation(n)
        split = int(n * (1 - holdout_ratio))
        train, holdout = [real_logs[i] for i in idx[:split]], \
                         [real_logs[i] for i in idx[split:]]
        
        train_pred = np.asarray(predictor(train), dtype=float)
        holdout_pred = np.asarray(predictor(holdout), dtype=float)
        
        train_real = np.array([np.mean(r.get("sequence", [0.5])) for r in train])
        holdout_real = np.array([np.mean(r.get("sequence", [0.5])) for r in holdout])
        
        train_gap = float(np.mean(np.abs(train_pred - train_real))) if len(train_pred) else 0.0
        holdout_gap = float(np.mean(np.abs(holdout_pred - holdout_real))) if len(holdout_pred) else 0.0
        
        overfit = holdout_gap / max(train_gap, 1e-6)
        return {
            "train_gap": train_gap,
            "holdout_gap": holdout_gap,
            "overfit_ratio": float(overfit),
        }
    
    @staticmethod
    def _subgroup_key(subgroup_filter: Dict) -> str:
        """Stable string key for a subgroup filter dict."""
        if not subgroup_filter:
            return "all"
        return ",".join(f"{k}={v}" for k, v in sorted(subgroup_filter.items()))


def analyze_gaps(real_data: Dict, virtual_data: Dict,
                 subgroup_filter: Optional[Dict] = None) -> List[Dict]:
    """Convenience wrapper for gap analysis."""
    return GapAnalyst().analyze(real_data, virtual_data, subgroup_filter)
