"""
Enhanced Event Engine (separated for modularity)
Manages scheduled and random events with half-life decay

Reference: 技术设计文档 §4.6.3, 需求说明文档 §3.4
"""
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import numpy as np
from datetime import datetime


@dataclass
class Event:
    """Single event instance"""
    event_id: str
    event_type: str  # exam_fail, confession, achievement, etc.
    student_id: str
    day_triggered: int
    intensity: float  # 0-1, may decay over time
    
    # Effects (can be positive or negative)
    achievement_delta: float = 0.0
    fatigue_delta: float = 0.0
    motivation_delta: float = 0.0
    stress_delta: float = 0.0
    emotion_delta: float = 0.0
    
    # Metadata
    description: str = ""
    related_agents: List[str] = None  # Other affected agents
    
    def __post_init__(self):
        if self.related_agents is None:
            self.related_agents = []


class EventConfig:
    """Configuration for event types"""
    
    SCHEDULED_EVENTS = {
        "exam": {
            "days": [60, 120],
            "fatigue_impact": 5,
            "stress_impact": 3,
            "motivation_delta": -0.1,
            "description": "期中/期末考试"
        },
        "holiday": {
            "days": [90],
            "motivation_boost": 2,
            "fatigue_recovery": -10,  # Negative = recovery
            "emotion_delta": 1.0,
            "description": "假期休息"
        },
        "semester_transition": {
            "days": [90],
            "social_impact": 2,
            "motivation_delta": 0.0,
            "description": "学期转换"
        }
    }
    
    RANDOM_EVENTS = {
        "exam_fail": {
            "probability": 0.02,
            "achievement_delta": -5,
            "fatigue_delta": -2,
            "motivation_delta": -0.1,
            "stress_delta": 2,
            "half_life": 7,
            "description": "考试失利"
        },
        "confession": {
            "probability": 0.005,
            "emotion_delta": 5,
            "motivation_delta": 0.05,
            "fatigue_delta": 2,  # Distracted
            "half_life": 14,
            "description": "学生表白"
        },
        "achievement": {
            "probability": 0.03,
            "achievement_delta": 5,
            "motivation_delta": 0.1,
            "emotion_delta": 2,
            "half_life": 21,
            "description": "获得成就/表扬"
        },
        "family_incident": {
            "probability": 0.01,
            "stress_delta": 3,
            "motivation_delta": -0.15,
            "fatigue_delta": 1,
            "half_life": 30,
            "description": "家庭变故"
        },
        "friend_breakup": {
            "probability": 0.02,
            "emotion_delta": -3,
            "stress_delta": 1,
            "motivation_delta": -0.05,
            "half_life": 10,
            "description": "友谊破裂"
        },
        "health_issue": {
            "probability": 0.01,
            "fatigue_delta": 5,
            "motivation_delta": -0.1,
            "achievement_delta": -3,
            "half_life": 5,
            "description": "身体不适"
        }
    }


class EventEngine:
    """
    Manages event generation, decay, and impact on students
    """
    
    def __init__(self, seed: int = None):
        if seed is not None:
            np.random.seed(seed)
        
        self.events: Dict[str, Event] = {}
        self.event_history: List[Event] = []
    
    def trigger_scheduled_events(self, day: int) -> List[Event]:
        """
        Check and trigger all scheduled events for a given day
        
        Args:
            day: Current simulation day
        
        Returns:
            List of triggered events
        """
        triggered = []
        
        for event_type, config in EventConfig.SCHEDULED_EVENTS.items():
            if day in config.get("days", []):
                # This event triggers today - generate for all students
                event = Event(
                    event_id=f"scheduled_{event_type}_{day}",
                    event_type=event_type,
                    student_id="ALL",
                    day_triggered=day,
                    intensity=1.0,
                    achievement_delta=config.get("achievement_delta", 0),
                    fatigue_delta=config.get("fatigue_delta", 0),
                    motivation_delta=config.get("motivation_delta", 0),
                    stress_delta=config.get("stress_delta", 0),
                    emotion_delta=config.get("emotion_delta", 0),
                    description=config.get("description", "")
                )
                self.events[event.event_id] = event
                self.event_history.append(event)
                triggered.append(event)
        
        return triggered
    
    def generate_random_events(self, student_id: str, day: int) -> List[Event]:
        """
        Generate random events for a given student on a given day
        
        Args:
            student_id: Student ID
            day: Current simulation day
        
        Returns:
            List of events triggered for this student
        """
        events = []
        
        for event_type, config in EventConfig.RANDOM_EVENTS.items():
            probability = config.get("probability", 0.01)
            
            if np.random.random() < probability:
                event_id = f"random_{event_type}_{student_id}_{day}_{len(events)}"
                
                event = Event(
                    event_id=event_id,
                    event_type=event_type,
                    student_id=student_id,
                    day_triggered=day,
                    intensity=1.0,
                    achievement_delta=config.get("achievement_delta", 0),
                    fatigue_delta=config.get("fatigue_delta", 0),
                    motivation_delta=config.get("motivation_delta", 0),
                    stress_delta=config.get("stress_delta", 0),
                    emotion_delta=config.get("emotion_delta", 0),
                    description=config.get("description", "")
                )
                
                self.events[event_id] = event
                self.event_history.append(event)
                events.append(event)
        
        return events
    
    def compute_event_impact(self, event: Event, current_day: int) -> Dict[str, float]:
        """
        Compute impact of event at current day (with half-life decay)
        
        Args:
            event: Event instance
            current_day: Current simulation day
        
        Returns:
            Dict of {attribute: impact_value}
        """
        event_type = event.event_type
        config = EventConfig.RANDOM_EVENTS.get(event_type, {})
        
        # Check if this is a random or scheduled event
        if event_type not in config:
            config = EventConfig.SCHEDULED_EVENTS.get(event_type, {})
        
        half_life = config.get("half_life", 7)
        days_elapsed = current_day - event.day_triggered
        
        # Exponential decay: impact(t) = impact_0 × 0.5^(t / half_life)
        decay_factor = (0.5) ** (days_elapsed / half_life)
        
        return {
            "achievement_delta": event.achievement_delta * decay_factor,
            "fatigue_delta": event.fatigue_delta * decay_factor,
            "motivation_delta": event.motivation_delta * decay_factor,
            "stress_delta": event.stress_delta * decay_factor,
            "emotion_delta": event.emotion_delta * decay_factor
        }
    
    def apply_events_to_student(self, student: Dict, day: int) -> Dict:
        """
        Apply all active events' impacts to a student
        
        Args:
            student: Student profile dict
            day: Current simulation day
        
        Returns:
            Updated student dict with event impacts applied
        """
        # Get the events that fire *today* for this student. Each event is a
        # discrete shock applied once on its trigger day. (Re-applying every
        # past event's decayed impact on every subsequent day would integrate
        # each delta over its whole decay curve -- a single exam_fail would
        # accumulate to ~-50 points and drive an unrealistic random walk that
        # swamps the experimental intervention effect.)
        student_id = student.get("student_id")
        active_events = [e for e in self.event_history 
                        if (e.student_id == student_id or e.student_id == "ALL") 
                        and e.day_triggered == day]
        
        # Apply impacts
        total_impacts = {
            "achievement_delta": 0.0,
            "fatigue_delta": 0.0,
            "motivation_delta": 0.0,
            "stress_delta": 0.0,
            "emotion_delta": 0.0
        }
        
        for event in active_events:
            impacts = self.compute_event_impact(event, day)
            for key, val in impacts.items():
                total_impacts[key] += val
        
        # Update student attributes
        if "achievement_score" not in student:
            student["achievement_score"] = 50
        student["achievement_score"] = np.clip(
            student["achievement_score"] + total_impacts["achievement_delta"],
            0, 100
        )
        
        if "fatigue" not in student:
            student["fatigue"] = 50
        student["fatigue"] = np.clip(
            student["fatigue"] + total_impacts["fatigue_delta"],
            0, 100
        )
        
        if "motivation" not in student:
            student["motivation"] = 0.5
        student["motivation"] = np.clip(
            student["motivation"] + total_impacts["motivation_delta"],
            0, 1
        )
        
        if "stress" not in student:
            student["stress"] = 50
        student["stress"] = np.clip(
            student["stress"] + total_impacts["stress_delta"],
            0, 100
        )
        
        if "emotion" not in student:
            student["emotion"] = 50
        student["emotion"] = np.clip(
            student["emotion"] + total_impacts["emotion_delta"],
            0, 100
        )
        
        return student
    
    def get_event_summary(self, day: int) -> Dict:
        """Get summary of all events up to a given day"""
        events_by_type = {}
        
        for event in self.event_history:
            if event.day_triggered <= day:
                event_type = event.event_type
                events_by_type[event_type] = events_by_type.get(event_type, 0) + 1
        
        return {
            "total_events": len(self.event_history),
            "events_by_type": events_by_type
        }


class EventLogger:
    """Log and track events for analysis and debugging"""
    
    def __init__(self):
        self.log = []
    
    def log_event(self, event: Event, day: int, student_state: Dict = None) -> None:
        """Log an event with student state snapshot"""
        log_entry = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "day": day,
            "student_id": event.student_id,
            "description": event.description,
            "student_achievement": student_state.get("achievement_score") if student_state else None,
            "student_stress": student_state.get("stress") if student_state else None
        }
        self.log.append(log_entry)
    
    def export(self) -> List[Dict]:
        """Export log as list of dicts"""
        return self.log
