"""
L-Model 2.0: Multi-Agent Life Timeline Engine (v6.0)
Continuous 7×24 simulation with social network, events, relationships

Key features:
- Multi-agent parallel execution
- Social network evolution (homophily + influence)
- Event engine (scheduled + random with half-life decay)
- Relationship state machine (romantic, peer, teacher, parent)
- Continuous time with scene switching (5 scenes × ~288 min)
- Life course trajectory recording
- Cognitive modulation of daily learning gains (BKT mastery × fatigue)

Reference: 技术设计文档 §4.6, 需求说明文档 §4.2
"""
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import numpy as np
import json

from .social_network import SocialNetworkEngine, DynamicNetworkMonitor
from .event_engine import EventEngine, EventLogger, Event
from .relationship import RelationshipStateMachine, RelationshipType, RelationshipUpdateEngine
from ..cognitive_engine import BayesianKnowledgeTracer, BKTState


@dataclass
class SceneEvent:
    """Single event in a scene"""
    timestamp_min: float  # Minute of day
    scene: str  # school / shadow_edu / parent / self_study / fragment
    event_type: str  # 课堂练习 / 家长辅导 / 自学 / 社交
    learning_gain: float
    fatigue_change: float
    motivation_change: float


@dataclass
class DayTimeline:
    """Single day trajectory"""
    student_id: str
    sim_date: str  # YYYY-MM-DD
    events: List[SceneEvent]
    total_learning_gain: float
    fatigue_end: float
    stress_end: float
    emotion_end: float
    # Post-update state (recorded after network influence + intervention
    # delivery for the day) so life-course curves reflect the real dynamics.
    achievement_end: float = 0.0
    motivation_end: float = 0.5


class LifeTimeEngineV2:
    """
    Master L-Model 2.0 orchestrator with full feature integration
    
    Manages multi-agent parallel simulation with:
    - Social network evolution (from social_network.py)
    - Events (from event_engine.py)
    - Relationships (from relationship.py)
    """
    
    def __init__(self, students: List[Dict], teachers: List[Dict], 
                 parents: List[Dict], social_network: SocialNetworkEngine = None,
                 seed: int = None):
        self.students = {s["student_id"]: s for s in students}
        self.teachers = {t["teacher_id"]: t for t in teachers}
        self.parents = {p["parent_id"]: p for p in parents}
        
        # Initialize engines. Build the default network on the *real* student
        # ids so influence propagation actually reaches the cohort (the old
        # hard-coded S{i:04d} naming silently mismatched 5-digit ids).
        self.network = social_network or SocialNetworkEngine(
            node_ids=list(self.students.keys()), seed=seed,
            profiles=self.students)
        self.event_engine = EventEngine(seed=seed)
        self.event_logger = EventLogger()
        self.network_monitor = DynamicNetworkMonitor()
        
        # Relationship management
        self.relationship_manager = RelationshipStateMachine()
        self.relationship_updater = RelationshipUpdateEngine(self.relationship_manager)

        # Cognitive engine (BKT): per-student mastery states modulate daily
        # learning efficiency, so trajectories respond to each persona's
        # simulation_vector instead of being profile-independent noise.
        self.bkt = BayesianKnowledgeTracer()
        self.bkt_states: Dict[str, BKTState] = {}
        for s in students:
            sv = s.get("simulation_vector") or {}
            self.bkt_states[s["student_id"]] = BKTState(
                p_know=float(sv.get("p_know", 0.2)),
                p_learn=float(sv.get("p_learn", 0.25)),
                p_slip=float(sv.get("p_slip", 0.1)),
                p_guess=float(sv.get("p_guess", 0.1)),
            )

        # Results
        self.timelines = []  # Accumulated timelines
    
    def simulate_day(self, student_id: str, sim_date: str, 
                    interventions: List[Dict] = None) -> DayTimeline:
        """
        Simulate one day for one student (5 scenes × 288 min)
        """
        student = self.students[student_id]
        events = []
        
        # Scene 1: School (8:00-12:00, 4h = 240 min)
        for minute in range(480, 720, 20):
            event = SceneEvent(
                timestamp_min=minute,
                scene="school",
                event_type="classroom",
                learning_gain=np.random.normal(0.02, 0.01),
                fatigue_change=0.5,
                motivation_change=0.0
            )
            events.append(event)
        
        # Scene 2: Lunch/Social (12:00-13:00)
        event = SceneEvent(
            timestamp_min=720,
            scene="social",
            event_type="peer_interaction",
            learning_gain=0.0,
            fatigue_change=-2.0,
            motivation_change=0.05
        )
        events.append(event)
        
        # Scene 3: Afternoon School (14:00-18:00)
        for minute in range(840, 1080, 20):
            event = SceneEvent(
                timestamp_min=minute,
                scene="school",
                event_type="classroom",
                learning_gain=np.random.normal(0.015, 0.01),
                fatigue_change=0.4,
                motivation_change=-0.02
            )
            events.append(event)
        
        # Scene 4: After-school / Shadow education (18:00-20:00 or 20:00)
        if np.random.random() < 0.4:  # 40% have tutoring
            for minute in range(1080, 1140, 15):
                event = SceneEvent(
                    timestamp_min=minute,
                    scene="shadow_edu",
                    event_type="tutoring",
                    learning_gain=np.random.normal(0.03, 0.01),
                    fatigue_change=1.0,
                    motivation_change=0.0
                )
                events.append(event)
        
        # Scene 5: Self-study / Recreation (20:00-22:00)
        for minute in range(1200, 1320, 30):
            event = SceneEvent(
                timestamp_min=minute,
                scene="self_study",
                event_type="homework_or_recreation",
                learning_gain=np.random.normal(0.01, 0.005),
                fatigue_change=-1.0 if minute > 1260 else 0.5,
                motivation_change=0.01
            )
            events.append(event)
        
        # Cognitive modulation: BKT mastery raises learning efficiency,
        # fatigue lowers it (gains stay proportional to the persona).
        state = self.bkt_states.get(student_id)
        if state is not None:
            mastery_factor = 0.6 + 0.8 * state.p_know  # 0.6 .. 1.4
            fatigue_factor = max(0.4, 1.0 - student.get("fatigue", 50) / 250.0)
            cognitive_factor = mastery_factor * fatigue_factor
            for e in events:
                e.learning_gain *= cognitive_factor

        # Compute daily aggregates
        total_learning_gain = sum(e.learning_gain for e in events)
        total_fatigue_change = sum(e.fatigue_change for e in events)
        
        student["fatigue"] = min(100, max(0, student.get("fatigue", 50) + total_fatigue_change))

        # Daily BKT update: one simulated practice opportunity per day keeps
        # the mastery state evolving together with the trajectory.
        if state is not None:
            practiced_correct = np.random.random() < self.bkt.predict(state)
            self.bkt_states[student_id] = self.bkt.update(state, practiced_correct)

        return DayTimeline(
            student_id=student_id,
            sim_date=sim_date,
            events=events,
            total_learning_gain=total_learning_gain,
            fatigue_end=student["fatigue"],
            stress_end=student.get("stress", 50),
            emotion_end=student.get("emotion", 50)
        )
    
    def simulate(self, days: int = 90, interventions: List[Dict] = None,
                 intervention_engine=None, progress_callback=None) -> Dict:
        """
        Full multi-day simulation with all L-Model 2.0 features
        
        Args:
            days: Number of days to simulate
            interventions: (legacy) list passed through to simulate_day
            intervention_engine: Optional InterventionDeliveryEngine. When
                provided, every active intervention is applied to its student
                each day (mediated by real teacher fidelity / parent
                involvement), so the simulated achievement trajectories respond
                to the experimental manipulation. This is what makes the
                treatment-vs-control effect sizes genuine.
            progress_callback: Optional callable ``(day, days)`` invoked at the
                start of each simulated day so callers can report live progress.
        
        Returns simulation result with trajectories, network evolution, events log, relationships
        """
        result = {
            "trajectories": {},
            "network_snapshots": [],
            "events_log": [],
            "relationship_snapshots": []
        }
        
        for day in range(days):
            if progress_callback is not None:
                progress_callback(day, days)
            sim_date = (datetime.now() - timedelta(days=days-day)).strftime("%Y-%m-%d")
            
            # 1. Trigger scheduled events for this day
            scheduled_events = self.event_engine.trigger_scheduled_events(day)
            
            # 2. Simulate each student's day
            for student_id in self.students:
                student = self.students[student_id]
                
                # Generate random events for this student
                random_events = self.event_engine.generate_random_events(student_id, day)
                
                # Apply all event impacts to student
                self.event_engine.apply_events_to_student(student, day)
                
                # Simulate day timeline
                timeline = self.simulate_day(student_id, sim_date, interventions)
                
                if student_id not in result["trajectories"]:
                    result["trajectories"][student_id] = []
                result["trajectories"][student_id].append(timeline)
                
                # Log events
                for event in random_events:
                    self.event_logger.log_event(event, day, student)
                
                for event in scheduled_events:
                    if event.student_id == "ALL":
                        self.event_logger.log_event(event, day, student)
            
            # 3. Update social network influence
            influence_effects = self.network.propagate_influence(self.students, day)
            for student_id, influence in influence_effects.items():
                if student_id in self.students:
                    current_ach = self.students[student_id].get("achievement_score", 50)
                    self.students[student_id]["achievement_score"] = np.clip(
                        current_ach + influence, 0, 100
                    )
            
            # 3b. Apply interventions (real experimental manipulation). The
            # delivery engine mutates achievement_score / motivation according
            # to each intervention's channel efficacy and mediator quality.
            if intervention_engine is not None:
                for student_id in self.students:
                    intervention_engine.apply_interventions_to_student(
                        self.students[student_id], day,
                        self.teachers, self.parents)
            
            # 3c. Record the post-update state into this day's timeline so the
            # life-course curves reflect network + intervention dynamics.
            for student_id in self.students:
                timeline = result["trajectories"][student_id][day]
                timeline.achievement_end = float(
                    self.students[student_id].get("achievement_score", 50))
                timeline.motivation_end = float(
                    self.students[student_id].get("motivation", 0.5))
            
            # 4. Update network edges (homophily strengthening)
            network_stats = self.network.update_edges_homophily(self.students)
            self.network_monitor.record_snapshot(day, self.network)
            
            # 5. Update relationships
            relationship_stats = self.relationship_updater.update_all(day)
            
            # 6. Record events
            all_events = {
                "scheduled": [e.event_type for e in scheduled_events],
                "network_stats": network_stats,
                "relationship_stats": relationship_stats
            }
            result["events_log"].append({
                "day": day,
                "events": all_events
            })
        
        # Export final results
        result["network_metrics"] = self.network_monitor.history
        result["event_log"] = self.event_logger.export()
        
        return result
