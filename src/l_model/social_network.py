"""
Enhanced Social Network Engine (separated from main engine for modularity)
Manages student social networks with selection and influence effects

Reference: 技术设计文档 §4.6.2
"""
from typing import Dict, List, Optional, Tuple
import networkx as nx
import numpy as np


class SocialNetworkEngine:
    """
    Social network with homophily (selection) and influence effects
    
    Key mechanisms:
    - Homophily: Students with similar achievement tend to be friends
    - Influence: Students influence each other's learning outcomes
    """
    
    # Tunables for homophily-driven topological evolution. Edge *weights*
    # alone leave density / clustering frozen (they are purely topological),
    # so the network also grows and prunes ties: similar students form new
    # ties (selection) while dissimilar, decayed ties dissolve.
    _PRUNE_THRESHOLD = 0.12     # edges weaker than this may dissolve
    _FORM_SIMILARITY = 0.82     # only form ties between very similar students
    _MIN_EDGES_FACTOR = 0.5     # never prune below factor * n_students edges
    _TARGET_DENSITY = 0.05      # realistic sparse ceiling; formation stops here

    def __init__(self, n_students: int = None, init_density: float = 0.04,
                 seed: int = None, node_ids: Optional[list] = None,
                 profiles: Optional[Dict] = None):
        """
        Args:
            n_students: Number of students (used when node_ids is not given)
            init_density: Initial edge density (0-1)
            seed: Random seed for reproducibility
            node_ids: Explicit node identifiers. When provided the network is
                built on these exact ids so influence propagation lines up with
                the real student cohort (fixes the previous hard-coded
                ``S{i:04d}`` naming that silently mismatched 5-digit student
                ids and made network influence a no-op).
        """
        if seed is not None:
            np.random.seed(seed)

        self.graph = nx.Graph()
        if node_ids is not None:
            ids = list(node_ids)
        else:
            ids = [f"S{i:04d}" for i in range(n_students or 0)]
        self.n_students = len(ids)
        self.profiles = profiles or {}

        # Dedicated RNG for topological evolution so edge formation / pruning
        # is reproducible WITHOUT perturbing the global np.random stream that
        # the daily scene / event simulation relies on.
        self._topo_rng = np.random.RandomState(
            None if seed is None else seed + 1)

        # Initialize nodes
        for nid in ids:
            self.graph.add_node(nid)

        # Initialize edges
        self._initialize_edges(init_density)
    
    def _initialize_edges(self, density: float) -> None:
        """Initialize a sparse, homophily-structured friendship network.

        With student profiles each student forms a small personal circle
        (3-8 ties) biased toward similar peers; tie strengths are drawn from
        a broad distribution so weak / mid ties dominate and only a few ties
        are strong (matching empirical adolescent friendship networks).
        Without profiles, fall back to uniform random edges at ``density``.
        """
        nodes = list(self.graph.nodes())
        n = len(nodes)
        if n < 2:
            return

        if self.profiles:
            rng = self._topo_rng
            for i, a in enumerate(nodes):
                ach_a = self.profiles.get(a, {}).get("achievement_score", 50)
                k = int(rng.randint(3, 9))  # personal circle of 3..8 friends
                for _ in range(k):
                    for _attempt in range(10):
                        j = int(rng.randint(0, n))
                        if j == i:
                            continue
                        b = nodes[j]
                        if self.graph.has_edge(a, b):
                            continue
                        ach_b = self.profiles.get(b, {}).get("achievement_score", 50)
                        sim = max(0.0, 1.0 - min(abs(ach_a - ach_b) / 40.0, 1.0))
                        if sim < 0.3 and rng.rand() > 0.15:
                            continue  # mostly befriend similar peers
                        w = float(np.clip(0.1 + 0.8 * sim * rng.beta(2, 2), 0.05, 1.0))
                        # per-tie heterogeneity: closeness converges toward
                        # similarity * bias instead of similarity alone, so
                        # weak / mid / strong tiers all persist over time
                        self.graph.add_edge(
                            a, b, weight=w, bias=float(rng.uniform(0.35, 1.0)))
                        break
            return

        n_possible = n * (n - 1) // 2
        n_edges = int(n_possible * density)
        edges_added = 0
        attempts = 0

        while edges_added < n_edges and attempts < n_edges * 10:
            i, j = np.random.choice(n, 2, replace=False)
            node_i, node_j = nodes[int(i)], nodes[int(j)]

            if not self.graph.has_edge(node_i, node_j):
                w = float(np.clip(0.05 + 0.9 * np.random.beta(2, 3), 0.05, 1.0))
                self.graph.add_edge(
                    node_i, node_j, weight=w,
                    bias=float(np.random.uniform(0.35, 1.0)))
                edges_added += 1

            attempts += 1
    
    def propagate_influence(self, students: Dict, day: int) -> Dict:
        """
        Propagate achievement influence along social connections
        
        Δach_i = Σ_j (w_ij × (ach_j - ach_i) × susceptibility_i)
        
        Args:
            students: Dict of {student_id: {achievement_score, susceptibility, ...}}
            day: Current simulation day
        
        Returns:
            Dict of {student_id: influence_delta}
        """
        influence_effects = {}
        
        for node_i in self.graph.nodes():
            student_i = students.get(node_i, {})
            achievement_i = student_i.get("achievement_score", 50)
            susceptibility = student_i.get("susceptibility", 0.1)
            
            total_influence = 0.0
            neighbor_count = 0
            
            for node_j in self.graph.neighbors(node_i):
                student_j = students.get(node_j, {})
                achievement_j = student_j.get("achievement_score", 50)
                
                weight = self.graph[node_i][node_j].get("weight", 0.5)
                
                # Influence equation: weighted difference scaled by susceptibility
                influence = weight * (achievement_j - achievement_i) * susceptibility
                total_influence += influence
                neighbor_count += 1
            
            # Average influence
            if neighbor_count > 0:
                influence_effects[node_i] = total_influence / neighbor_count
            else:
                influence_effects[node_i] = 0.0
        
        return influence_effects
    
    def update_edges_homophily(self, students: Dict) -> Dict:
        """
        Update edge weights based on homophily (similarity)
        Similar students strengthen edges, dissimilar students weaken
        
        Args:
            students: Dict of {student_id: student_profile}
        
        Returns:
            Statistics on edge updates
        """
        stats = {
            "total_edges": len(self.graph.edges()),
            "avg_weight": 0.0,
            "strengthened": 0,
            "weakened": 0
        }
        
        for (u, v) in self.graph.edges():
            student_u = students.get(u, {})
            student_v = students.get(v, {})
            
            # Similarity based on achievement (0-1)
            ach_u = student_u.get("achievement_score", 50)
            ach_v = student_v.get("achievement_score", 50)
            
            # Similarity: 1 if equal, 0 if diff >= 40 (stricter so weights
            # stay differentiated instead of converging to ~0.9 for everyone)
            similarity = max(0.0, 1.0 - min(abs(ach_u - ach_v) / 40.0, 1.0))

            # Update weight: decay + boost toward similarity * bias. The
            # per-edge bias models intrinsic closeness so ties between equally
            # similar students still settle at different strengths.
            current_weight = self.graph[u][v].get("weight", 0.5)
            bias = self.graph[u][v].get("bias", 0.7)
            new_weight = 0.9 * current_weight + 0.1 * (similarity * bias)
            
            if new_weight > current_weight:
                stats["strengthened"] += 1
            elif new_weight < current_weight:
                stats["weakened"] += 1
            
            self.graph[u][v]["weight"] = new_weight
        
        # 2. Topological evolution: dissolve decayed ties between dissimilar
        # students and form new ties between very similar, not-yet-connected
        # students. This is what makes density / clustering actually evolve.
        formed, pruned = self._evolve_topology(students)
        stats["formed"] = formed
        stats["pruned"] = pruned

        # Calculate average weight (recomputed after topology changes)
        if self.graph.edges():
            avg_weight = sum(self.graph[u][v]["weight"] for u, v in self.graph.edges()) / len(self.graph.edges())
            stats["avg_weight"] = avg_weight
        
        return stats

    def _similarity(self, students: Dict, a: str, b: str) -> float:
        """Achievement similarity in [0, 1]: 1 if equal, 0 if diff >= 40."""
        ach_a = students.get(a, {}).get("achievement_score", 50)
        ach_b = students.get(b, {}).get("achievement_score", 50)
        return max(0.0, 1.0 - min(abs(ach_a - ach_b) / 40.0, 1.0))

    def _evolve_topology(self, students: Dict) -> Tuple[int, int]:
        """Grow and prune the graph so its topology (hence density / clustering
        / components) evolves over the run instead of staying frozen.

        Returns (formed, pruned) edge counts. The number of operations per day
        is bounded by the current edge count so dynamics stay stable and the
        graph never collapses to empty nor explodes to complete.
        """
        nodes = list(self.graph.nodes())
        n = len(nodes)
        if n < 2:
            return 0, 0

        # Daily turnover scales with network size but stays gentle so the
        # structure evolves smoothly instead of churning violently.
        churn = max(1, self.graph.number_of_edges() // 20)
        min_edges = max(1, int(self._MIN_EDGES_FACTOR * n))
        max_edges = max(min_edges + 1,
                        int(self._TARGET_DENSITY * n * (n - 1) / 2))
        at_target = self.graph.number_of_edges() >= max_edges

        # --- Dissolution. Below the target only genuinely decayed ties go (so
        # the network can densify); at/above it the weakest ties turn over every
        # day so density / clustering keep evolving around equilibrium instead
        # of freezing flat. ---
        pruned = 0
        weak = sorted(
            (self.graph[u][v]["weight"], u, v) for u, v in self.graph.edges()
        )
        for _w, u, v in weak:
            if pruned >= churn or self.graph.number_of_edges() <= min_edges:
                break
            if not at_target and _w >= self._PRUNE_THRESHOLD:
                break  # sorted ascending: no more decayed ties beyond this
            if self.graph.degree(u) <= 1 or self.graph.degree(v) <= 1:
                continue  # keep every student connected
            self.graph.remove_edge(u, v)
            pruned += 1

        # --- Formation between similar, not-yet-connected students. A small
        # overshoot band above the target lets density breathe around it. ---
        formed = 0
        attempts = 0
        max_attempts = churn * 6
        soft_cap = max_edges + churn
        while (formed < churn and attempts < max_attempts
               and self.graph.number_of_edges() < soft_cap):
            attempts += 1
            i, j = self._topo_rng.choice(n, 2, replace=False)
            a, b = nodes[int(i)], nodes[int(j)]
            if self.graph.has_edge(a, b):
                continue
            sim = self._similarity(students, a, b)
            if sim < self._FORM_SIMILARITY:
                continue
            self.graph.add_edge(
                a, b,
                weight=float(np.clip(0.15 + 0.75 * sim * self._topo_rng.beta(2, 2),
                                 0.05, 1.0)),
                bias=float(self._topo_rng.uniform(0.35, 1.0)),
            )
            formed += 1

        return formed, pruned
    
    def detect_communities(self) -> List[List[str]]:
        """Detect student communities using Louvain algorithm"""
        from networkx.algorithms import community
        
        communities = list(community.greedy_modularity_communities(self.graph))
        return [list(c) for c in communities]
    
    def get_centrality(self) -> Dict[str, float]:
        """Get betweenness centrality for each student"""
        return nx.betweenness_centrality(self.graph, weight=None)
    
    def get_clustering_coefficient(self) -> Dict[str, float]:
        """Get clustering coefficient for each student"""
        return nx.clustering(self.graph, weight=None)
    
    def export_edges(self) -> List[Tuple[str, str, float]]:
        """Export edges as (source, target, weight) tuples"""
        return [(u, v, self.graph[u][v]["weight"]) for u, v in self.graph.edges()]


class DynamicNetworkMonitor:
    """Monitor network statistics over time"""
    
    def __init__(self):
        self.history = []
    
    def record_snapshot(self, day: int, network: SocialNetworkEngine) -> Dict:
        """Record network statistics at a given day"""
        
        # Compute network metrics
        density = nx.density(network.graph)
        avg_degree = 2 * len(network.graph.edges()) / len(network.graph.nodes()) if len(network.graph.nodes()) > 0 else 0
        avg_clustering = sum(nx.clustering(network.graph).values()) / len(network.graph.nodes()) if len(network.graph.nodes()) > 0 else 0
        
        # Components
        n_components = nx.number_connected_components(network.graph)
        
        # Average path length (for largest component)
        largest_cc = max(nx.connected_components(network.graph), key=len) if network.graph.nodes() else []
        if len(largest_cc) > 1:
            subgraph = network.graph.subgraph(largest_cc)
            avg_path_length = nx.average_shortest_path_length(subgraph)
        else:
            avg_path_length = 0.0
        
        snapshot = {
            "day": day,
            "density": density,
            "avg_degree": avg_degree,
            "avg_clustering": avg_clustering,
            "n_components": n_components,
            "avg_path_length": avg_path_length,
            "largest_component_size": len(largest_cc)
        }
        
        self.history.append(snapshot)
        return snapshot
    
    def get_trajectory(self, metric: str) -> List[float]:
        """Get trajectory of a metric over time"""
        return [h.get(metric, 0) for h in self.history]
