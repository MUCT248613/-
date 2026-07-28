"""
L-Model 2.0: Multi-Agent Life Timeline Engine (v4.0)
Continuous 7×24 simulation with social network, events, relationships

Key features:
- Multi-agent parallel execution
- Social network evolution (networkx)
- Event engine (scheduled + random)
- Relationship state machine
- Continuous time with scene switching
- Life course trajectory recording

Reference: 技术设计文档 §4.6, 需求说明文档 §4.2
"""
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import networkx as nx
import numpy as np
import json


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


class SocialNetworkEngine:
    """
    Social network evolution with selection + influence effects
    
    References:
    - Selection effect: homophily, students with similar achievement cluster
    - Influence effect: students on same edge converge in achievement
    """
    
    def __init__(self, n_students: int, init_density: float = 0.15):
        """
        Args:
            n_students: Number of students in network
            init_density: Initial network edge density
        """
        self.graph = nx.Graph()
        
        # Initialize nodes (students)
        for i in range(n_students):
            self.graph.add_node(f"S{i:04d}")
        
        # Initialize edges (friendships) - random initialization
        n_possible_edges = n_students * (n_students - 1) // 2
        n_edges = int(n_possible_edges * init_density)
        
        nodes = list(self.graph.nodes())
        edges = []
        attempts = 0
        while len(edges) < n_edges and attempts < n_edges * 10:
            i, j = np.random.choice(n_students, 2, replace=False)
            if (nodes[i], nodes[j]) not in edges:
                edges.append((nodes[i], nodes[j]))
                self.graph.add_edge(nodes[i], nodes[j], weight=0.5)
            attempts += 1
    
    def propagate_influence(self, students: Dict, day: int) -> Dict:
        """
        Propagate achievement influence along edges
        
        Δach_i = Σ_j (w_ij × (ach_j - ach_i) × susceptibility_i)
        """
        influence_effects = {}
        
        for node_i in self.graph.nodes():
            student_i = students.get(node_i, {})
            achievement_i = student_i.get("achievement_score", 50)
            susceptibility = student_i.get("susceptibility", 0.1)
            
            total_influence = 0.0
            neighbors = list(self.graph.neighbors(node_i))
            
            for node_j in neighbors:
                student_j = students.get(node_j, {})
                achievement_j = student_j.get("achievement_score", 50)
                
                weight = self.graph[node_i][node_j]["weight"]
                influence = weight * (achievement_j - achievement_i) * susceptibility
                total_influence += influence
            
            influence_effects[node_i] = total_influence
        
        return influence_effects
    
    def update_edges(self, students: Dict) -> None:
        """
        Update edge weights based on similarity (homophily)
        Similar students strengthen edges, dissimilar students weaken
        """
        for (u, v) in self.graph.edges():
            student_u = students.get(u, {})
            student_v = students.get(v, {})
            
            # Similarity based on achievement
            ach_u = student_u.get("achievement_score", 50)
            ach_v = student_v.get("achievement_score", 50)
            similarity = 1.0 - min(abs(ach_u - ach_v) / 100, 1.0)
            
            # Update weight (decay + similarity boost)
            current_weight = self.graph[u][v]["weight"]
            new_weight = 0.9 * current_weight + 0.1 * similarity
            self.graph[u][v]["weight"] = new_weight


class EventEngine:
    """
    Scheduled and random event generation
    
    Scheduled: 考试, 假期, 学期转换
    Random: 考砸, 表白, 获奖, 家庭变故 (按半衰期衰减)
    """
    
    SCHEDULED_EVENTS = {
        "exam": {"days": [60, 120], "fatigue_impact": 5, "stress_impact": 3},
        "holiday": {"days": [90], "motivation_boost": 2, "fatigue_recovery": 10},
        "semester_transition": {"days": [90], "social_impact": 2}
    }
    
    RANDOM_EVENTS = {
        "exam_fail": {"probability": 0.02, "fatigue": -2, "motivation": -0.1, "half_life": 7},
        "confession": {"probability": 0.01, "emotion": 5, "learning_distraction": -0.1, "half_life": 14},
        "achievement": {"probability": 0.03, "motivation": 0.1, "emotion": 2, "half_life": 21},
        "family_incident": {"probability": 0.01, "stress": 3, "motivation": -0.15, "half_life": 30}
    }
    
    @staticmethod
    def should_trigger_scheduled(sim_day: int, event_type: str) -> bool:
        """Check if scheduled event should occur"""
        days = EventEngine.SCHEDULED_EVENTS.get(event_type, {}).get("days", [])
        return sim_day in days
    
    @staticmethod
    def generate_random_events(sim_day: int) -> List[Tuple[str, float]]:
        """
        Generate random events for a given day
        
        Returns: List of (event_type, impact_multiplier)
        """
        events = []
        for event_type, config in EventEngine.RANDOM_EVENTS.items():
            prob = config.get("probability", 0.01)
            if np.random.random() < prob:
                # Impact decays with half-life
                half_life = config.get("half_life", 7)
                # For today, impact = 1.0; decay exponentially
                impact_mult = 1.0
                events.append((event_type, impact_mult))
        
        return events


class LifeTimeEngineV2:
    """
    Master L-Model 2.0 orchestrator
    
    Manages multi-agent parallel simulation with network, events, relationships
    """
    
    def __init__(self, students: List[Dict], teachers: List[Dict], 
                 parents: List[Dict], social_network: SocialNetworkEngine = None):
        self.students = {s["student_id"]: s for s in students}
        self.teachers = {t["teacher_id"]: t for t in teachers}
        self.parents = {p["parent_id"]: p for p in parents}
        
        self.network = social_network or SocialNetworkEngine(len(students))
        self.event_engine = EventEngine()
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
        
        # Compute daily aggregates
        total_learning_gain = sum(e.learning_gain for e in events)
        total_fatigue_change = sum(e.fatigue_change for e in events)
        
        student["fatigue"] = min(100, max(0, student.get("fatigue", 50) + total_fatigue_change))
        
        return DayTimeline(
            student_id=student_id,
            sim_date=sim_date,
            events=events,
            total_learning_gain=total_learning_gain,
            fatigue_end=student["fatigue"],
            stress_end=student.get("stress", 50),
            emotion_end=student.get("emotion", 50)
        )
    
    def simulate(self, days: int = 90, interventions: List[Dict] = None) -> Dict:
        """
        Full multi-day simulation
        
        Returns simulation result with trajectories, network evolution, events log
        """
        result = {
            "trajectories": {},
            "network_snapshots": [],
            "events_log": []
        }
        
        for day in range(days):
            sim_date = (datetime.now() - timedelta(days=days-day)).strftime("%Y-%m-%d")
            
            # 1. Simulate each student's day
            for student_id in self.students:
                timeline = self.simulate_day(student_id, sim_date, interventions)
                
                if student_id not in result["trajectories"]:
                    result["trajectories"][student_id] = []
                result["trajectories"][student_id].append(timeline)
            
            # 2. Update social network influence
            influence_effects = self.network.propagate_influence(self.students, day)
            for student_id, influence in influence_effects.items():
                if student_id in self.students:
                    current_ach = self.students[student_id].get("achievement_score", 50)
                    self.students[student_id]["achievement_score"] = current_ach + influence
            
            # 3. Update network edges (homophily strengthening)
            self.network.update_edges(self.students)
            
            # 4. Trigger scheduled/random events
            scheduled_events = []
            for event_type in EventEngine.SCHEDULED_EVENTS:
                if EventEngine.should_trigger_scheduled(day, event_type):
                    scheduled_events.append(event_type)
            
            random_events = EventEngine.generate_random_events(day)
            
            all_events = {"scheduled": scheduled_events, "random": random_events}
            result["events_log"].append({
                "day": day,
                "events": all_events
            })
        
        return result
