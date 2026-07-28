"""
BKT (Bayesian Knowledge Tracing) Cognitive Engine
- Core engine for mastery state tracking
- Reference: Corbett & Anderson (1994)
"""
from dataclasses import dataclass
from typing import Dict, List, Tuple
import numpy as np


@dataclass
class BKTState:
    """BKT state for a learner-KC pair"""
    p_know: float  # P(KC mastered | evidence)
    p_learn: float  # P(learn this interaction)
    p_slip: float   # P(slip | mastered)
    p_guess: float  # P(correct | not mastered)


class BayesianKnowledgeTracer:
    """
    Standard BKT implementation for mastery tracking
    
    Args:
        p_know_init: Initial prior P(knowledge)
        p_learn: Learning rate per attempt
        p_slip: Slip probability (correct despite mastery)
        p_guess: Guess probability (correct despite no mastery)
    """
    
    def __init__(self, 
                 p_know_init: float = 0.2,
                 p_learn: float = 0.25,
                 p_slip: float = 0.1,
                 p_guess: float = 0.1):
        self.p_know_init = p_know_init
        self.p_learn = p_learn
        self.p_slip = p_slip
        self.p_guess = p_guess
    
    def update(self, state: BKTState, is_correct: bool) -> BKTState:
        """
        Bayesian update after observation
        
        Args:
            state: Current BKT state
            is_correct: Whether response was correct
            
        Returns:
            Updated BKT state
        """
        p_k = state.p_know
        
        # Likelihood of observation given mastery
        if is_correct:
            p_correct_given_know = 1 - state.p_slip
            p_correct_given_not_know = state.p_guess
        else:
            p_correct_given_know = state.p_slip
            p_correct_given_not_know = 1 - state.p_guess
        
        # Posterior after observation (Bayes rule)
        numerator = p_correct_given_know * p_k
        denominator = (p_correct_given_know * p_k + 
                      p_correct_given_not_know * (1 - p_k))
        
        p_k_new = numerator / denominator if denominator > 0 else 0.5
        
        # Learning happens after correct response
        if is_correct:
            p_k_new = p_k_new + (1 - p_k_new) * state.p_learn
        
        return BKTState(
            p_know=p_k_new,
            p_learn=state.p_learn,
            p_slip=state.p_slip,
            p_guess=state.p_guess
        )
    
    def predict(self, state: BKTState) -> float:
        """
        Predict probability of correct response
        
        Returns: P(correct | current state)
        """
        return state.p_know * (1 - state.p_slip) + (1 - state.p_know) * state.p_guess
    
    def init_state(self) -> BKTState:
        """Initialize BKT state"""
        return BKTState(
            p_know=self.p_know_init,
            p_learn=self.p_learn,
            p_slip=self.p_slip,
            p_guess=self.p_guess
        )


class ACTRForgetting:
    """
    ACT-R forgetting model (continuous time decay)
    A(t) = ln(Σ_j (t - t_j)^(-d))
    where t_j are practice timestamps, d is decay parameter
    """
    
    def __init__(self, decay_param: float = 0.5):
        """
        Args:
            decay_param: Decay exponent (typical 0.5)
        """
        self.decay_param = decay_param
    
    def compute_activation(self, practice_times: List[float], current_time: float) -> float:
        """
        Compute activation (log odds of recall)
        
        Args:
            practice_times: List of practice timestamps (in minutes)
            current_time: Current time (minutes)
            
        Returns:
            Activation value (higher = more retrievable)
        """
        if not practice_times:
            return 0.0
        
        times_since_practice = [current_time - t for t in practice_times]
        times_since_practice = [max(t, 1.0) for t in times_since_practice]  # Avoid log(0)
        
        sum_term = sum(t ** (-self.decay_param) for t in times_since_practice)
        activation = np.log(sum_term) if sum_term > 0 else 0.0
        
        return activation
    
    def retrieval_prob(self, activation: float, tau: float = 1.0) -> float:
        """
        Convert activation to retrieval probability
        P(retrieve) = 1 / (1 + exp(-(activation - threshold) / tau))
        """
        threshold = 0.0
        prob = 1.0 / (1.0 + np.exp(-(activation - threshold) / tau))
        return float(np.clip(prob, 0.0, 1.0))


class CognitiveEngine:
    """
    Master cognitive engine combining BKT + ACT-R + deterministic rules
    - All state transitions are deterministic (given learner profile)
    - No LLM dependency (pure symbolic computation)
    - Used as oracle for is_correct determination
    """
    
    def __init__(self):
        self.bkt = BayesianKnowledgeTracer()
        self.actr = ACTRForgetting()
    
    def score_response(self, learner_profile: Dict, item_params: Dict, 
                      practice_history: List[Dict], current_time: float) -> Tuple[bool, float]:
        """
        Deterministically score a learner's response
        
        Args:
            learner_profile: {"p_know": float, "p_slip": float, "p_guess": float, ...}
            item_params: {"difficulty": float, "discrimination": float, ...}
            practice_history: [{"time": float, "is_correct": bool}, ...]
            current_time: Current simulation time (minutes)
            
        Returns:
            (is_correct, confidence)
        """
        # BKT predicted mastery
        state = BKTState(
            p_know=learner_profile.get("p_know", 0.2),
            p_learn=learner_profile.get("p_learn", 0.25),
            p_slip=learner_profile.get("p_slip", 0.1),
            p_guess=learner_profile.get("p_guess", 0.1)
        )
        
        p_correct_bkt = self.bkt.predict(state)
        
        # ACT-R forgetting decay
        practice_times = [h["time"] for h in practice_history if h.get("is_correct")]
        activation = self.actr.compute_activation(practice_times, current_time)
        p_retrieve = self.actr.retrieval_prob(activation)
        
        # Combine: P(correct) = P(know from BKT) * P(retrieve from ACT-R)
        p_correct_final = p_correct_bkt * p_retrieve
        
        # Stochastic decision (seeded by profile hash for reproducibility)
        random_seed = hash((tuple(sorted(learner_profile.items())), current_time)) % (2**31)
        np.random.seed(random_seed)
        is_correct = np.random.random() < p_correct_final
        
        return bool(is_correct), float(p_correct_final)
