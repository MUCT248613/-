"""
Uniqueness Guarantee Engine (v6.0)
- Fingerprinting: SHA256-based identity hash
- Bloom filter: Scalable deduplication for 20M+ scale
- Similarity detection: Approximate duplicate detection (LSH-like)
- Repair: LLM-based rewriting for near-duplicates

Reference: 档案设计文档 §1.4
"""
import hashlib
import json
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import numpy as np


@dataclass
class FingerprintResult:
    """Result of fingerprinting operation"""
    fingerprint: str  # 16-char SHA256 prefix
    key_fields: Dict  # Canonical key fields
    canonical_string: str  # For reproducibility


class FingerprintEngine:
    """
    Body identity fingerprinting for uniqueness guarantee
    """
    
    # Fields that uniquely identify a person
    KEY_FIELDS = [
        "name",
        "birth_date",
        "birth_place",
        "family_structure",
        "parents_occupation",
        "parents_education",
        "key_life_events",
        "aptitude_combo",
        "mbti",
        "core_personality"
    ]
    
    @staticmethod
    def _canonicalize(fields: Dict) -> str:
        """
        Normalize fields for deterministic hashing
        """
        canonical = {}
        for field in FingerprintEngine.KEY_FIELDS:
            value = fields.get(field)
            if value is None:
                canonical[field] = "__NONE__"
            elif isinstance(value, (list, dict)):
                canonical[field] = json.dumps(value, sort_keys=True)
            else:
                canonical[field] = str(value).lower().strip()
        
        return json.dumps(canonical, sort_keys=True)
    
    def fingerprint(self, persona: Dict) -> FingerprintResult:
        """
        Generate identity fingerprint
        
        Args:
            persona: Full persona dict
            
        Returns:
            FingerprintResult with 16-char SHA256 prefix
        """
        key_fields = {k: persona.get(k) for k in self.KEY_FIELDS}
        canonical = self._canonicalize(key_fields)
        
        hash_obj = hashlib.sha256(canonical.encode())
        fp = hash_obj.hexdigest()[:16]
        
        return FingerprintResult(
            fingerprint=fp,
            key_fields=key_fields,
            canonical_string=canonical
        )
    
    @staticmethod
    def similarity(persona_a: Dict, persona_b: Dict) -> float:
        """
        Approximate similarity between two personas
        Combines discrete (Jaccard) and continuous (cosine) distance
        
        Returns: Float in [0, 1], higher means more similar
        """
        # Discrete fields: set-based Jaccard
        discrete_fields = ["name", "birth_place", "family_structure"]
        discrete_jaccard = []
        for field in discrete_fields:
            a_val = str(persona_a.get(field, "")).lower()
            b_val = str(persona_b.get(field, "")).lower()
            
            a_tokens = set(a_val.split())
            b_tokens = set(b_val.split())
            
            if len(a_tokens | b_tokens) == 0:
                discrete_jaccard.append(1.0)
            else:
                jac = len(a_tokens & b_tokens) / len(a_tokens | b_tokens)
                discrete_jaccard.append(jac)
        
        discrete_score = np.mean(discrete_jaccard) if discrete_jaccard else 0.0
        
        # Continuous fields: cosine similarity
        continuous_fields = ["mbti", "core_personality"]
        continuous_dists = []
        for field in continuous_fields:
            a_val = str(persona_a.get(field, "")).lower()
            b_val = str(persona_b.get(field, "")).lower()
            # Simple string edit distance proxy
            dist = 1.0 - (sum(c1 == c2 for c1, c2 in zip(a_val, b_val)) 
                          / max(len(a_val), len(b_val), 1))
            continuous_dists.append(dist)
        
        continuous_score = 1.0 - np.mean(continuous_dists) if continuous_dists else 0.5
        
        # Weighted combination
        overall = 0.5 * discrete_score + 0.5 * continuous_score
        return float(np.clip(overall, 0.0, 1.0))


class BloomFilter:
    """
    Scalable probabilistic deduplication
    """
    
    def __init__(self, capacity: int = 20_000_000, error_rate: float = 0.001):
        """
        Args:
            capacity: Expected capacity
            error_rate: Target false positive rate
        """
        self.capacity = capacity
        self.error_rate = error_rate
        
        # Calculate filter size (bits)
        self.size_bits = int(-1 * capacity * np.log2(error_rate) / (np.log(2) ** 2))
        
        # Initialize bit array (using bytes)
        self.size_bytes = (self.size_bits + 7) // 8
        self.bit_array = bytearray(self.size_bytes)
        
        # Number of hash functions
        self.num_hashes = int(self.size_bits / capacity * np.log(2))
        
        self.count = 0
    
    def _hash(self, item: str, seed: int) -> int:
        """Generate hash for bloom filter"""
        h = hashlib.md5(f"{item}_{seed}".encode()).digest()
        return int.from_bytes(h, "big") % self.size_bits
    
    def add(self, item: str):
        """Add item to bloom filter"""
        for i in range(self.num_hashes):
            pos = self._hash(item, i)
            byte_idx = pos // 8
            bit_idx = pos % 8
            self.bit_array[byte_idx] |= (1 << bit_idx)
        self.count += 1
    
    def contains(self, item: str) -> bool:
        """Check if item might be in set (probabilistic)"""
        for i in range(self.num_hashes):
            pos = self._hash(item, i)
            byte_idx = pos // 8
            bit_idx = pos % 8
            if not (self.bit_array[byte_idx] & (1 << bit_idx)):
                return False
        return True


class UniquenessGuarantor:
    """
    Master uniqueness guarantee orchestrator
    """
    
    def __init__(self, capacity: int = 20_000_000):
        self.fingerprint_engine = FingerprintEngine()
        self.bloom_filter = BloomFilter(capacity=capacity, error_rate=0.001)
        self.personas = []  # For similarity detection
        self.fingerprints = set()  # Track exact fingerprints
    
    def ensure_unique(self, candidate: Dict, regenerator_func=None) -> Tuple[Dict, str]:
        """
        Ensure candidate persona is unique
        
        Args:
            candidate: Persona candidate
            regenerator_func: Function to regenerate if collision
            
        Returns:
            (unique_persona, status_message)
        """
        fp_result = self.fingerprint_engine.fingerprint(candidate)
        fp = fp_result.fingerprint
        
        # Check exact collision in bloom filter
        if self.bloom_filter.contains(fp):
            # May be collision - check exact fingerprints
            if fp in self.fingerprints:
                # Confirmed collision → regenerate
                if regenerator_func:
                    return regenerator_func()
                return candidate, "exact_collision_warning"
        
        # Check approximate similarity
        max_similarity = 0.0
        most_similar_idx = -1
        for i, existing in enumerate(self.personas):
            sim = self.fingerprint_engine.similarity(candidate, existing)
            if sim > max_similarity:
                max_similarity = sim
                most_similar_idx = i
        
        if max_similarity > 0.85:
            # Near-duplicate detected
            return candidate, f"near_duplicate_detected_sim_{max_similarity:.3f}"
        
        # Add to collections
        self.bloom_filter.add(fp)
        self.fingerprints.add(fp)
        self.personas.append(candidate)
        
        return candidate, "unique_accepted"
