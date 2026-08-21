"""Tests for ANCOVA-adjusted effect size estimator."""
import numpy as np
import pytest

from src.delivery.intervention_delivery import VirtualEffectSizeCalculator


class TestAncovaEstimator:
    """ANCOVA estimator tests."""

    def test_ancova_basic(self):
        """ANCOVA should detect a treatment effect with baseline covariate."""
        rng = np.random.RandomState(42)
        n = 50
        # Both groups have similar baseline
        control_pre = rng.normal(50, 10, n)
        treatment_pre = rng.normal(50, 10, n)
        # Treatment group improves more
        control_post = control_pre + rng.normal(2, 3, n)
        treatment_post = treatment_pre + rng.normal(5, 3, n)

        g, ci_lo, ci_hi, diff = VirtualEffectSizeCalculator.compute_ancova_g(
            control_pre, control_post, treatment_pre, treatment_post
        )
        # Effect should be positive (treatment > control)
        assert g > 0, f"Expected positive g, got {g}"
        assert diff > 0, f"Expected positive diff, got {diff}"
        # CI should be roughly reasonable
        assert ci_lo < g < ci_hi

    def test_ancova_no_effect(self):
        """ANCOVA should return ~0 when there is no treatment effect."""
        rng = np.random.RandomState(123)
        n = 50
        control_pre = rng.normal(50, 10, n)
        treatment_pre = rng.normal(50, 10, n)
        control_post = control_pre + rng.normal(3, 3, n)
        treatment_post = treatment_pre + rng.normal(3, 3, n)

        g, ci_lo, ci_hi, diff = VirtualEffectSizeCalculator.compute_ancova_g(
            control_pre, control_post, treatment_pre, treatment_post
        )
        # Effect should be near zero
        assert abs(g) < 0.5, f"Expected near-zero g, got {g}"

    def test_ancova_small_sample(self):
        """ANCOVA should handle small samples gracefully."""
        g, ci_lo, ci_hi, diff = VirtualEffectSizeCalculator.compute_ancova_g(
            np.array([50.0, 55.0]),
            np.array([52.0, 57.0]),
            np.array([50.0, 55.0]),
            np.array([55.0, 60.0]),
        )
        # Should not crash, returns zeros for very small samples
        assert isinstance(g, float)

    def test_ancova_reduces_variance(self):
        """ANCOVA should produce tighter CI than raw comparison when
        baseline is correlated with post-test."""
        rng = np.random.RandomState(99)
        n = 100
        # Strong correlation between pre and post
        control_pre = rng.normal(50, 10, n)
        treatment_pre = rng.normal(50, 10, n)
        control_post = 0.8 * control_pre + 10 + rng.normal(0, 2, n)
        treatment_post = 0.8 * treatment_pre + 13 + rng.normal(0, 2, n)

        g_ancova, ci_lo_a, ci_hi_a, _ = VirtualEffectSizeCalculator.compute_ancova_g(
            control_pre, control_post, treatment_pre, treatment_post
        )
        g_raw, ci_lo_r, ci_hi_r = VirtualEffectSizeCalculator.compute_hedges_g(
            control_post, treatment_post
        )
        # ANCOVA CI should be narrower (more precise)
        ancova_width = ci_hi_a - ci_lo_a
        raw_width = ci_hi_r - ci_lo_r
        assert ancova_width < raw_width, (
            f"ANCOVA CI ({ancova_width:.3f}) should be narrower than raw ({raw_width:.3f})"
        )

    def test_ancova_in_counterfactual(self):
        """Counterfactual comparison should include ANCOVA fields."""
        from src.l_model.counterfactual import CounterfactualEngine, SimulationState

        students = {
            f"S{i}": {
                "achievement_score": 50.0 + i,
                "motivation": 0.5,
                "parent_support": 0.5,
                "shadow_hours": 1.0,
                "tutoring_hours": 0.0,
                "homework_load": 1.0,
            }
            for i in range(10)
        }
        state = SimulationState(students=students, seed=42)
        engine = CounterfactualEngine()

        def modifier(s):
            for sid, st in s.students.items():
                st["tutoring_hours"] = st.get("tutoring_hours", 0.0) + 3.0
            return s

        base_traj, mod_traj = engine.branch(state, modifier, days=30, seed=42)
        cmp = engine.compare(base_traj, mod_traj)

        assert "ancova_g" in cmp
        assert "ancova_ci_95" in cmp
        assert "ancova_adjusted_diff" in cmp
        # tutoring should have positive effect
        assert cmp["ancova_g"] > 0 or cmp["effect_size_g"] > 0
