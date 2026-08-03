"""
VirtualStudent Sandbox v5.0 - Calibration Module (M3)

Implements §5 M3 校准 (Calibration).

Two calibration families:
  1. Cognitive calibration (v2.0): fit BKT parameters to real learning data
     using 4 objective targets (learning curve / error distribution /
     first-correct latency / variance ratio).
  2. Persona distribution calibration (v3.0 extended, §4.4): align the
     generated persona cohort's distributions against population norms
     (Big Five, family structure, shadow-education hours, daily schedule,
     teacher demographics).

Search is done with a lightweight random/grid search (Optuna optional).

Reference: 技术设计文档 §5 M3, §4.4
"""
from typing import Dict, List, Optional, Tuple, Any

import numpy as np


class CognitiveCalibrator:
    """
    Fit BKT parameters (p_know, p_learn, p_slip, p_guess) to real logs.
    
    Objective: minimize a weighted distance across 4 targets:
      - learning_curve: predicted P(correct) vs empirical by opportunity
      - error_dist: distribution of error runs
      - first_correct: latency to first correct response
      - variance_ratio: inter-student variance ratio
    """
    
    WEIGHTS = {
        "learning_curve": 0.4,
        "error_dist": 0.2,
        "first_correct": 0.2,
        "variance_ratio": 0.2,
    }
    
    # Parameter bounds
    BOUNDS = {
        "p_know": (0.05, 0.9),
        "p_learn": (0.01, 0.6),
        "p_slip": (0.01, 0.3),
        "p_guess": (0.05, 0.4),
    }
    
    def __init__(self, seed: int = 42, n_trials: int = 60):
        self.seed = seed
        self.n_trials = n_trials
    
    def calibrate(self, real_logs: List[Dict]) -> Dict[str, Any]:
        """
        Run calibration search over real log data.
        
        Args:
            real_logs: List of {"student_id", "sequence": [0/1, ...]} records
        
        Returns:
            {"params": {...}, "distance": float, "per_target": {...}}
        """
        rng = np.random.RandomState(self.seed)
        
        best_params = None
        best_dist = float("inf")
        best_per_target = {}
        
        for _ in range(self.n_trials):
            candidate = {
                name: float(rng.uniform(lo, hi))
                for name, (lo, hi) in self.BOUNDS.items()
            }
            per_target = self._evaluate(candidate, real_logs)
            dist = sum(self.WEIGHTS[k] * per_target[k] for k in per_target)
            
            if dist < best_dist:
                best_dist = dist
                best_params = candidate
                best_per_target = per_target
        
        return {
            "params": best_params,
            "distance": float(best_dist),
            "per_target": best_per_target,
            "n_trials": self.n_trials,
        }
    
    def _evaluate(self, params: Dict, real_logs: List[Dict]) -> Dict[str, float]:
        """Compute the 4 target distances for a parameter candidate."""
        from ..cognitive_engine import BayesianKnowledgeTracer
        
        # Simulate predicted P(correct) by opportunity using BKT forward model
        max_len = max((len(r.get("sequence", [])) for r in real_logs), default=1)
        predicted_curve = self._bkt_curve(params, max_len)
        empirical_curve = self._empirical_curve(real_logs, max_len)
        
        lc_dist = float(np.mean(np.abs(
            np.array(predicted_curve) - np.array(empirical_curve))))
        
        # Error distribution: predicted P(error) = P(know)*slip + P(~know)*(1-guess)
        pred_err = params["p_know"] * params["p_slip"] + \
                   (1 - params["p_know"]) * (1 - params["p_guess"])
        emp_err = self._empirical_error_rate(real_logs)
        err_dist = abs(pred_err - emp_err)
        
        # First-correct latency
        pred_fc = self._predicted_first_correct(params)
        emp_fc = self._empirical_first_correct(real_logs)
        fc_dist = abs(pred_fc - emp_fc) / max(emp_fc, 1.0)
        
        # Variance ratio (simple proxy)
        vr_dist = abs(self._predicted_variance(params) - self._empirical_variance(real_logs))
        
        return {
            "learning_curve": lc_dist,
            "error_dist": err_dist,
            "first_correct": fc_dist,
            "variance_ratio": vr_dist,
        }
    
    def _bkt_curve(self, params: Dict, length: int) -> List[float]:
        """Forward BKT P(correct) curve over opportunities."""
        p_know = params["p_know"]
        curve = []
        for _ in range(length):
            p_correct = p_know * (1 - params["p_slip"]) + (1 - p_know) * params["p_guess"]
            curve.append(p_correct)
            # BKT update after a correct response (learning transition)
            p_know = p_know + (1 - p_know) * params["p_learn"]
        return curve
    
    def _empirical_curve(self, real_logs: List[Dict], length: int) -> List[float]:
        """Empirical P(correct) by opportunity index."""
        curve = []
        for i in range(length):
            responses = [r["sequence"][i] for r in real_logs
                         if i < len(r.get("sequence", []))]
            curve.append(float(np.mean(responses)) if responses else 0.5)
        return curve
    
    def _empirical_error_rate(self, real_logs: List[Dict]) -> float:
        all_resp = [x for r in real_logs for x in r.get("sequence", [])]
        return 1.0 - float(np.mean(all_resp)) if all_resp else 0.5
    
    def _predicted_first_correct(self, params: Dict) -> float:
        """Expected opportunities until first correct (geometric approx)."""
        p = params["p_know"] * (1 - params["p_slip"]) + (1 - params["p_know"]) * params["p_guess"]
        return 1.0 / max(p, 1e-6)
    
    def _empirical_first_correct(self, real_logs: List[Dict]) -> float:
        latencies = []
        for r in real_logs:
            seq = r.get("sequence", [])
            for i, x in enumerate(seq):
                if x == 1:
                    latencies.append(i + 1)
                    break
        return float(np.mean(latencies)) if latencies else 1.0
    
    def _predicted_variance(self, params: Dict) -> float:
        p = params["p_know"] * (1 - params["p_slip"]) + (1 - params["p_know"]) * params["p_guess"]
        return p * (1 - p)
    
    def _empirical_variance(self, real_logs: List[Dict]) -> float:
        rates = [float(np.mean(r.get("sequence", [0.5]))) for r in real_logs]
        return float(np.var(rates)) if rates else 0.0


class PersonaDistributionCalibrator:
    """
    v3.0 extended (§4.4): align generated persona cohort distributions
    against population norms.
    
    Each norm defines a target distribution; the calibrator measures the
    distance (KL / total-variation / standardized mean diff) and returns
    a calibration report. Optionally resamples mismatched personas.
    """
    
    def __init__(self, norms: Optional[Dict[str, Dict]] = None):
        # norms: {field: {"type": "categorical"|"continuous", "target": ...}}
        self.norms = norms or self._default_norms()
    
    def _default_norms(self) -> Dict[str, Dict]:
        """Default population norms (placeholder values for pilot calibration)."""
        return {
            "family_structure": {
                "type": "categorical",
                "target": {"完整家庭": 0.80, "单亲": 0.10, "留守": 0.07, "重组": 0.03},
            },
            "big5_conscientiousness": {
                "type": "continuous", "target_mean": 0.55, "target_sd": 0.15,
            },
            "shadow_education_hours": {
                "type": "continuous", "target_mean": 4.5, "target_sd": 3.0,
            },
            "teacher_experience_years": {
                "type": "continuous", "target_mean": 12.0, "target_sd": 7.0,
            },
        }
    
    def calibrate(self, personas: List[Dict]) -> Dict[str, Any]:
        """
        Measure cohort-vs-norm distances for every calibrated field.
        
        Returns:
            {"fields": {field: {"distance": ..., "ok": bool}}, "overall": float}
        """
        report = {"fields": {}, "overall": 0.0}
        distances = []
        
        for field, norm in self.norms.items():
            values = [p.get(field) for p in personas if p.get(field) is not None]
            if not values:
                continue
            
            if norm["type"] == "categorical":
                dist = self._categorical_distance(values, norm["target"])
            else:
                dist = self._continuous_distance(
                    values, norm["target_mean"], norm["target_sd"])
            
            ok = dist < 0.15  # tolerance threshold (TODO: calibrate after pilot)
            report["fields"][field] = {"distance": float(dist), "ok": bool(ok)}
            distances.append(dist)
        
        report["overall"] = float(np.mean(distances)) if distances else 0.0
        return report
    
    def _categorical_distance(self, values: List, target: Dict[str, float]) -> float:
        """Total variation distance between empirical and target proportions."""
        from collections import Counter
        counts = Counter(values)
        total = sum(counts.values())
        emp = {k: counts.get(k, 0) / total for k in target}
        return 0.5 * sum(abs(emp[k] - p) for k, p in target.items())
    
    def _continuous_distance(self, values: List, target_mean: float,
                             target_sd: float) -> float:
        """Standardized distance: |mean diff| + |sd diff|, normalized."""
        emp_mean = float(np.mean(values))
        emp_sd = float(np.std(values)) or 1e-6
        mean_diff = abs(emp_mean - target_mean) / max(abs(target_mean), 1e-6)
        sd_diff = abs(emp_sd - target_sd) / max(target_sd, 1e-6)
        return 0.5 * (mean_diff + sd_diff)


def calibrate_cognitive(real_logs: List[Dict], seed: int = 42) -> Dict[str, Any]:
    """Convenience wrapper for cognitive (BKT) calibration."""
    return CognitiveCalibrator(seed=seed).calibrate(real_logs)


def calibrate_personas(personas: List[Dict], norms: Optional[Dict] = None) -> Dict[str, Any]:
    """Convenience wrapper for persona distribution calibration."""
    return PersonaDistributionCalibrator(norms).calibrate(personas)
