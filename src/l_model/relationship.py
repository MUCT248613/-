"""
Relationship State Machine (RSM)
Manages student relationships: romantic, peer, teacher-student, parent-child

Reference: 技术设计文档 §4.7, 需求说明文档 §3.5
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from datetime import datetime


class RelationshipType(Enum):
    """Types of relationships"""
    ROMANTIC = "romantic"
    PEER = "peer"
    TEACHER_STUDENT = "teacher_student"
    PARENT_CHILD = "parent_child"
    SIBLING = "sibling"


class RelationshipState(Enum):
    """States in relationship lifecycle"""
    ACQUAINTANCE = "acquaintance"  # 初识
    FRIEND = "friend"  # 朋友
    CLOSE_FRIEND = "close_friend"  # 亲密朋友
    ROMANTIC_INTEREST = "romantic_interest"  # 有意向
    DATING = "dating"  # 恋爱
    BROKEN_UP = "broken_up"  # 分手
    MENTOR = "mentor"  # 师生指导
    CONFLICT = "conflict"  # 冲突


@dataclass
class RelationshipInstance:
    """Single relationship between two agents"""
    relationship_id: str
    relation_type: RelationshipType
    agent_a_id: str
    agent_b_id: str
    agent_a_type: str  # "student" / "teacher" / "parent"
    agent_b_type: str
    
    state: RelationshipState = RelationshipState.ACQUAINTANCE
    intensity: float = 0.1  # 0-1 closeness
    duration_days: int = 0
    last_interaction_day: int = 0
    
    # Emotional state
    satisfaction: float = 0.5  # 0-1
    trust: float = 0.3  # 0-1 (for trust-based rels)
    
    # History
    conflict_count: int = 0
    memorable_events: List[str] = field(default_factory=list)
    
    def __hash__(self):
        return hash(self.relationship_id)


class RelationshipStateMachine:
    """
    Manages all relationships and state transitions
    
    Key mechanisms:
    - Intensity growth with interaction
    - Decay without interaction
    - State transitions based on thresholds
    - Conflict/breakup logic
    """
    
    def __init__(self):
        self.relationships: Dict[str, RelationshipInstance] = {}
        self.agent_connections: Dict[str, List[str]] = {}  # agent_id -> [rel_ids]
    
    def create_relationship(self, agent_a_id: str, agent_b_id: str,
                          agent_a_type: str, agent_b_type: str,
                          rel_type: RelationshipType,
                          initial_intensity: float = 0.1) -> str:
        """Create new relationship"""
        rel_id = f"{agent_a_id}_{agent_b_id}_{rel_type.value}_{len(self.relationships)}"
        
        rel = RelationshipInstance(
            relationship_id=rel_id,
            relation_type=rel_type,
            agent_a_id=agent_a_id,
            agent_b_id=agent_b_id,
            agent_a_type=agent_a_type,
            agent_b_type=agent_b_type,
            intensity=initial_intensity
        )
        
        self.relationships[rel_id] = rel
        
        # Register connections
        if agent_a_id not in self.agent_connections:
            self.agent_connections[agent_a_id] = []
        if agent_b_id not in self.agent_connections:
            self.agent_connections[agent_b_id] = []
        
        self.agent_connections[agent_a_id].append(rel_id)
        self.agent_connections[agent_b_id].append(rel_id)
        
        return rel_id
    
    def update_relationship(self, rel_id: str, day: int,
                          interaction_occurred: bool = False,
                          interaction_quality: float = 0.5) -> RelationshipInstance:
        """
        Update relationship on each simulation day
        
        Args:
            rel_id: Relationship ID
            day: Current simulation day
            interaction_occurred: Whether agents interacted today
            interaction_quality: 0-1 quality of interaction
        
        Returns:
            Updated relationship
        """
        rel = self.relationships[rel_id]
        
        # Update duration
        rel.duration_days += 1
        
        # Handle interaction
        if interaction_occurred:
            rel.last_interaction_day = day
            
            # Intensity grows with interaction (with diminishing returns)
            growth = interaction_quality * (1 - rel.intensity) * 0.1
            rel.intensity = min(1.0, rel.intensity + growth)
            
            # Satisfaction increases
            rel.satisfaction = min(1.0, rel.satisfaction + interaction_quality * 0.05)
            rel.trust = min(1.0, rel.trust + interaction_quality * 0.03)
        else:
            # Decay without interaction
            days_since_interaction = day - rel.last_interaction_day
            decay_rate = 0.02 * (days_since_interaction / 7)  # Per week
            rel.intensity = max(0.0, rel.intensity - decay_rate)
            
            # Satisfaction decays slowly
            rel.satisfaction = max(0.3, rel.satisfaction - 0.01)
        
        # State transitions based on intensity and satisfaction
        self._update_state(rel)
        
        return rel
    
    def _update_state(self, rel: RelationshipInstance) -> None:
        """Update relationship state based on intensity, satisfaction, etc."""
        
        if rel.relation_type == RelationshipType.ROMANTIC:
            self._update_romantic_state(rel)
        elif rel.relation_type == RelationshipType.PEER:
            self._update_peer_state(rel)
        elif rel.relation_type == RelationshipType.TEACHER_STUDENT:
            self._update_teacher_state(rel)
        elif rel.relation_type == RelationshipType.PARENT_CHILD:
            self._update_parent_state(rel)
    
    def _update_romantic_state(self, rel: RelationshipInstance) -> None:
        """Romantic relationship state transitions"""
        
        if rel.state == RelationshipState.ACQUAINTANCE:
            if rel.intensity > 0.3:
                rel.state = RelationshipState.FRIEND
        
        elif rel.state == RelationshipState.FRIEND:
            if rel.intensity > 0.5 and rel.trust > 0.4:
                rel.state = RelationshipState.CLOSE_FRIEND
            elif rel.intensity < 0.2:
                rel.state = RelationshipState.ACQUAINTANCE
        
        elif rel.state == RelationshipState.CLOSE_FRIEND:
            if rel.intensity > 0.7 and rel.satisfaction > 0.6:
                rel.state = RelationshipState.ROMANTIC_INTEREST
            elif rel.intensity < 0.3:
                rel.state = RelationshipState.FRIEND
        
        elif rel.state == RelationshipState.ROMANTIC_INTEREST:
            if rel.intensity > 0.8 and np.random.random() < 0.3:
                rel.state = RelationshipState.DATING
                rel.memorable_events.append("started_dating")
            elif rel.satisfaction < 0.3:
                rel.state = RelationshipState.FRIEND
        
        elif rel.state == RelationshipState.DATING:
            if rel.satisfaction < 0.2 and rel.conflict_count > 3:
                rel.state = RelationshipState.BROKEN_UP
                rel.memorable_events.append("broken_up")
            elif rel.satisfaction > 0.8:
                pass  # Stay in dating
            elif rel.intensity < 0.4:
                rel.state = RelationshipState.FRIEND
    
    def _update_peer_state(self, rel: RelationshipInstance) -> None:
        """Peer relationship state transitions"""
        
        if rel.state == RelationshipState.ACQUAINTANCE:
            if rel.intensity > 0.25:
                rel.state = RelationshipState.FRIEND
        
        elif rel.state == RelationshipState.FRIEND:
            if rel.intensity > 0.5:
                rel.state = RelationshipState.CLOSE_FRIEND
            elif rel.intensity < 0.15:
                rel.state = RelationshipState.ACQUAINTANCE
        
        elif rel.state == RelationshipState.CLOSE_FRIEND:
            if rel.satisfaction < 0.25:
                rel.state = RelationshipState.FRIEND
            elif rel.conflict_count > 2 and np.random.random() < 0.2:
                rel.state = RelationshipState.CONFLICT
    
    def _update_teacher_state(self, rel: RelationshipInstance) -> None:
        """Teacher-student relationship state transitions"""
        
        if rel.state == RelationshipState.ACQUAINTANCE:
            if rel.intensity > 0.2:
                rel.state = RelationshipState.MENTOR
        
        elif rel.state == RelationshipState.MENTOR:
            # Teacher-student can deepen to close mentor
            if rel.intensity > 0.6 and rel.trust > 0.5:
                rel.state = RelationshipState.CLOSE_FRIEND
            elif rel.intensity < 0.15:
                rel.state = RelationshipState.ACQUAINTANCE
    
    def _update_parent_state(self, rel: RelationshipInstance) -> None:
        """Parent-child relationship is relatively stable"""
        # Parent-child relationships have high baseline intensity
        if rel.intensity < 0.3:
            rel.state = RelationshipState.CONFLICT
        else:
            rel.state = RelationshipState.PARENT_CHILD
    
    def add_conflict_event(self, rel_id: str) -> None:
        """Record conflict in relationship"""
        if rel_id in self.relationships:
            rel = self.relationships[rel_id]
            rel.conflict_count += 1
            rel.satisfaction = max(0.0, rel.satisfaction - 0.2)
            rel.memorable_events.append(f"conflict_{rel.conflict_count}")
    
    def add_event(self, rel_id: str, event_name: str) -> None:
        """Add memorable event to relationship"""
        if rel_id in self.relationships:
            self.relationships[rel_id].memorable_events.append(event_name)
    
    def get_agent_relationships(self, agent_id: str) -> List[RelationshipInstance]:
        """Get all relationships for an agent"""
        rel_ids = self.agent_connections.get(agent_id, [])
        return [self.relationships[rel_id] for rel_id in rel_ids if rel_id in self.relationships]
    
    def get_relationship_summary(self, agent_id: str) -> Dict:
        """Get summary of agent's relationships"""
        rels = self.get_agent_relationships(agent_id)
        
        summary = {
            "total_relationships": len(rels),
            "by_type": {},
            "by_state": {},
            "romantic": None,
            "close_friends": []
        }
        
        for rel in rels:
            # Count by type
            rel_type = rel.relation_type.value
            summary["by_type"][rel_type] = summary["by_type"].get(rel_type, 0) + 1
            
            # Count by state
            state = rel.state.value
            summary["by_state"][state] = summary["by_state"].get(state, 0) + 1
            
            # Track romantic
            if rel.state == RelationshipState.DATING:
                summary["romantic"] = {
                    "partner_id": rel.agent_a_id if rel.agent_b_id == agent_id else rel.agent_b_id,
                    "duration_days": rel.duration_days,
                    "satisfaction": rel.satisfaction
                }
            
            # Track close friends
            if rel.state == RelationshipState.CLOSE_FRIEND:
                summary["close_friends"].append(rel.agent_a_id if rel.agent_b_id == agent_id else rel.agent_b_id)
        
        return summary


class RelationshipUpdateEngine:
    """
    Efficiently updates all relationships in parallel
    """
    
    def __init__(self, rsm: RelationshipStateMachine):
        self.rsm = rsm
    
    def update_all(self, day: int, interaction_pairs: List[Tuple[str, str]] = None) -> Dict:
        """
        Update all relationships on a given day
        
        Args:
            day: Current simulation day
            interaction_pairs: List of (agent_a, agent_b) who interacted today
        
        Returns:
            Statistics on relationship changes
        """
        interaction_pairs = interaction_pairs or []
        
        stats = {
            "total_updated": 0,
            "state_changes": 0,
            "intensity_avg": 0.0,
            "new_relationships": 0
        }
        
        # Update existing relationships
        for rel_id, rel in self.rsm.relationships.items():
            # Check if these agents interacted today
            interacted = any(
                (rel.agent_a_id in (a, b) and rel.agent_b_id in (a, b))
                for a, b in interaction_pairs
            )
            
            old_state = rel.state
            self.rsm.update_relationship(rel_id, day, interacted, 0.6 if interacted else 0.0)
            
            if old_state != rel.state:
                stats["state_changes"] += 1
            
            stats["total_updated"] += 1
        
        # Calculate average intensity
        if self.rsm.relationships:
            avg_intensity = sum(r.intensity for r in self.rsm.relationships.values()) / len(self.rsm.relationships)
            stats["intensity_avg"] = avg_intensity
        
        return stats
