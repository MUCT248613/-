"""
VirtualStudent Sandbox v5.0 - Priority Ranking Module (M6)

Implements §5 M6 预筛排序 (Pre-screening & Priority Ranking).

Ranks candidate interventions by a composite priority score so researchers
can decide which virtual experiments to promote to real trials.

Key rule (guardrail): interventions whose supporting evidence sits in a
HIGH-DISTORTION region of the gap map are PENALIZED, never given high
priority. This prevents the system from confidently recommending something
the simulator is known to model poorly.

Priority score components:
  - effect_size: virtual Hedges' g (larger = better)
  - certainty: CI width (narrower = better)
  - reach: fraction of target population affected
  - cost_efficiency: effect per unit cost
  - distortion_penalty: down-weight if evidence is in a distorted region

Reference: 技术设计文档 §5 M6, §3.1 (PriorityRanker role)
"""
from typing import Dict, List, Optional, Any

import numpy as np


class PriorityRanker:
    """
    Deterministic priority scorer for candidate interventions.
    """
    
    # Component weights (sum to 1.0)
    WEIGHTS = {
        "effect_size": 0.35,
        "certainty": 0.20,
        "reach": 0.20,
        "cost_efficiency": 0.15,
        "novelty": 0.10,
    }
    
    # Maximum distortion penalty (a fully distorted cell loses this much)
    MAX_DISTORTION_PENALTY = 0.5
    
    def rank(self, candidates: List[Dict],
             distortion_map: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Score and rank candidate interventions.
        
        Args:
            candidates: List of dicts, each with:
                - intervention_id
                - hedges_g, ci_95 [low, high]
                - reach (0-1 fraction of population)
                - cost_yuan (estimated delivery cost)
                - scene, subgroup (for distortion lookup)
                - novelty (0-1, optional)
            distortion_map: Output of GapAnalyst.build_distortion_map()
        
        Returns:
            Sorted list (highest priority first) with score breakdowns.
        """
        distortion_map = distortion_map or {"map": {}, "high_distortion_cells": []}
        high_cells = self._index_high_cells(distortion_map)
        
        scored = []
        for cand in candidates:
            breakdown = self._score_candidate(cand, high_cells)
            scored.append({
                "intervention_id": cand.get("intervention_id"),
                "priority_score": breakdown["total"],
                "breakdown": breakdown,
                "in_distorted_region": breakdown["distortion_penalty"] > 0,
            })
        
        scored.sort(key=lambda x: x["priority_score"], reverse=True)
        for i, s in enumerate(scored):
            s["rank"] = i + 1
        return scored
    
    def _score_candidate(self, cand: Dict, high_cells: set) -> Dict[str, float]:
        """Compute the component scores for a single candidate."""
        g = float(cand.get("hedges_g", 0.0))
        ci = cand.get("ci_95", [0.0, 0.0])
        reach = float(cand.get("reach", 0.5))
        cost = float(cand.get("cost_yuan", 100.0))
        novelty = float(cand.get("novelty", 0.5))
        
        # Effect size: map g in [-0.5, 1.5] to [0, 1]
        effect_score = float(np.clip((g + 0.5) / 2.0, 0.0, 1.0))
        
        # Certainty: narrower CI = higher score
        ci_width = max(ci[1] - ci[0], 1e-6)
        certainty_score = float(np.clip(1.0 - ci_width / 1.0, 0.0, 1.0))
        
        # Reach: already 0-1
        reach_score = float(np.clip(reach, 0.0, 1.0))
        
        # Cost efficiency: effect per 100 yuan, saturating
        cost_eff = abs(g) / max(cost, 1.0) * 100.0
        cost_score = float(np.clip(cost_eff / 1.0, 0.0, 1.0))
        
        # Novelty: already 0-1
        novelty_score = float(np.clip(novelty, 0.0, 1.0))
        
        # Distortion penalty
        cell_key = self._cell_key(cand)
        penalty = self.MAX_DISTORTION_PENALTY if cell_key in high_cells else 0.0
        
        total = (
            self.WEIGHTS["effect_size"] * effect_score +
            self.WEIGHTS["certainty"] * certainty_score +
            self.WEIGHTS["reach"] * reach_score +
            self.WEIGHTS["cost_efficiency"] * cost_score +
            self.WEIGHTS["novelty"] * novelty_score
        ) * (1.0 - penalty)
        
        return {
            "effect_size": effect_score,
            "certainty": certainty_score,
            "reach": reach_score,
            "cost_efficiency": cost_score,
            "novelty": novelty_score,
            "distortion_penalty": penalty,
            "total": float(total),
        }
    
    def _index_high_cells(self, distortion_map: Dict) -> set:
        """Build a set of (intervention, scene, subgroup) keys flagged as distorted."""
        keys = set()
        for cell in distortion_map.get("high_distortion_cells", []):
            keys.add((
                cell.get("intervention", "default"),
                cell.get("scene", "school"),
                cell.get("subgroup", "all"),
            ))
        return keys
    
    @staticmethod
    def _cell_key(cand: Dict) -> tuple:
        subgroup = cand.get("subgroup", {})
        if isinstance(subgroup, dict):
            sg_key = (",".join(f"{k}={v}" for k, v in sorted(subgroup.items()))
                      if subgroup else "all")
        else:
            sg_key = str(subgroup)
        return (
            cand.get("intervention_id", "default"),
            cand.get("scene", "school"),
            sg_key,
        )
    
    def top_k(self, candidates: List[Dict], k: int = 5,
              distortion_map: Optional[Dict] = None) -> List[Dict]:
        """Return the top-k ranked interventions."""
        return self.rank(candidates, distortion_map)[:k]


def rank_interventions(candidates: List[Dict],
                       distortion_map: Optional[Dict] = None) -> List[Dict]:
    """Convenience wrapper for priority ranking."""
    return PriorityRanker().rank(candidates, distortion_map)
