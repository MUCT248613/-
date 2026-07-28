"""
Unit tests for CognitiveEngine (BKT + ACT-R)
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cognitive_engine import (
    BayesianKnowledgeTracer, ACTRForgetting, CognitiveEngine, BKTState
)


class TestBayesianKnowledgeTracer:
    """Test BKT core functionality"""
    
    def setup_method(self):
        self.bkt = BayesianKnowledgeTracer(
            p_know_init=0.2,
            p_learn=0.25,
            p_slip=0.1,
            p_guess=0.1
        )
    
    def test_init_state(self):
        """Test initial state"""
        state = self.bkt.init_state()
        assert state.p_know == 0.2
        assert state.p_learn == 0.25
        assert state.p_slip == 0.1
        assert state.p_guess == 0.1
    
    def test_predict_initial(self):
        """Test prediction before update"""
        state = self.bkt.init_state()
        p_correct = self.bkt.predict(state)
        # P(correct) = P(know) * (1 - slip) + (1 - P(know)) * guess
        #            = 0.2 * 0.9 + 0.8 * 0.1 = 0.18 + 0.08 = 0.26
        assert abs(p_correct - 0.26) < 0.01
    
    def test_update_correct_response(self):
        """Test state update after correct response"""
        state = self.bkt.init_state()
        new_state = self.bkt.update(state, is_correct=True)
        
        # After correct: posterior increases, learning happens
        assert new_state.p_know > state.p_know
        assert new_state.p_know < 1.0  # Not fully mastered
    
    def test_update_incorrect_response(self):
        """Test state update after incorrect response"""
        state = self.bkt.init_state()
        new_state = self.bkt.update(state, is_correct=False)
        
        # After incorrect: posterior decreases or stays low
        assert new_state.p_know <= state.p_know
    
    def test_learning_curve(self):
        """Test progression with multiple correct responses"""
        state = self.bkt.init_state()
        
        for _ in range(5):
            state = self.bkt.update(state, is_correct=True)
        
        # Should converge toward mastery
        assert state.p_know > 0.5


class TestACTRForgetting:
    """Test ACT-R forgetting model"""
    
    def setup_method(self):
        self.actr = ACTRForgetting(decay_param=0.5)
    
    def test_no_practice_history(self):
        """Test with empty practice history"""
        activation = self.actr.compute_activation([], 100.0)
        assert activation == 0.0
    
    def test_recent_practice(self):
        """Test activation with recent practice"""
        practice_times = [100.0]  # Just practiced
        current_time = 101.0
        activation = self.actr.compute_activation(practice_times, current_time)
        
        # Should be high activation
        assert activation > 0.0
    
    def test_distant_practice(self):
        """Test activation with old practice"""
        practice_times = [0.0]
        current_time = 1000.0
        recent_activation = self.actr.compute_activation([1000.0], 1001.0)
        old_activation = self.actr.compute_activation(practice_times, current_time)
        
        # Recent should have higher activation than old
        assert recent_activation > old_activation
    
    def test_retrieval_probability(self):
        """Test retrieval probability conversion"""
        # High activation
        p_high = self.actr.retrieval_prob(activation=1.0)
        # Low activation
        p_low = self.actr.retrieval_prob(activation=-1.0)
        
        assert p_high > p_low
        assert 0 <= p_high <= 1.0
        assert 0 <= p_low <= 1.0


class TestCognitiveEngine:
    """Test master cognitive engine"""
    
    def setup_method(self):
        self.engine = CognitiveEngine()
    
    def test_score_response_deterministic(self):
        """Test deterministic scoring (same seed → same result)"""
        learner_profile = {
            "p_know": 0.5,
            "p_slip": 0.1,
            "p_guess": 0.1,
            "p_learn": 0.25
        }
        item_params = {"difficulty": 0.5}
        practice_history = []
        current_time = 100.0
        
        # Call twice with same inputs
        is_correct_1, conf_1 = self.engine.score_response(
            learner_profile, item_params, practice_history, current_time
        )
        is_correct_2, conf_2 = self.engine.score_response(
            learner_profile, item_params, practice_history, current_time
        )
        
        # Should be deterministic (same result)
        assert is_correct_1 == is_correct_2
        assert abs(conf_1 - conf_2) < 0.001
    
    def test_score_response_confidence_range(self):
        """Test confidence is in valid range"""
        learner_profile = {"p_know": 0.3, "p_slip": 0.1, "p_guess": 0.1}
        item_params = {"difficulty": 0.5}
        practice_history = []
        
        is_correct, confidence = self.engine.score_response(
            learner_profile, item_params, practice_history, 100.0
        )
        
        assert isinstance(is_correct, bool)
        assert 0.0 <= confidence <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
