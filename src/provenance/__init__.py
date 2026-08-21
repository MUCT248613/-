"""
VirtualStudent Sandbox v6.0 - Provenance Module

Implements data 溯源 (provenance / lineage) tracking, backed by the
`provenance` table (§6).

Every generated entity (student / teacher / parent / event / edge) records
WHERE it came from:
  - source: llm / rule / real_data / derived
  - lineage: the full derivation chain (which module, which seed, which
    upstream entities it was derived from)

This supports the auditability requirement: any virtual artifact can be
traced back to its origin, which is essential for scientific credibility
and for the LLM-participation accounting (llm_generated_fields).

Reference: 技术设计文档 §6 provenance table, §13 provenance/ module
"""
from typing import Dict, List, Optional, Any

import time
import uuid


class ProvenanceTracker:
    """
    Record and query entity lineage.
    """
    
    VALID_SOURCES = {"llm", "rule", "real_data", "derived", "mixed"}
    
    def __init__(self, db_layer=None):
        self.db_layer = db_layer  # optional DataLayer for persistence
        self._records: List[Dict] = []
    
    def record(self, entity_type: str, entity_id: str, source: str,
               lineage: Optional[Dict] = None, run_id: Optional[str] = None) -> Dict:
        """
        Record the provenance of a generated entity.
        
        Args:
            entity_type: student / teacher / parent / event / edge / institution
            entity_id: The entity's unique ID
            source: llm / rule / real_data / derived / mixed
            lineage: Full derivation chain (module, seed, upstream IDs, ...)
            run_id: Associated run ID
        
        Returns:
            The provenance record dict
        """
        if source not in self.VALID_SOURCES:
            source = "derived"
        
        record = {
            "prov_id": str(uuid.uuid4()),
            "run_id": run_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "source": source,
            "lineage_json": lineage or {},
            "timestamp_ms": int(time.time() * 1000),
        }
        self._records.append(record)
        
        # Persist if a data layer is available
        if self.db_layer is not None:
            try:
                self.db_layer.insert("provenance", record)
            except Exception:
                pass
        
        return record
    
    def record_llm_generation(self, entity_type: str, entity_id: str,
                              model: str, llm_fields: List[str],
                              run_id: Optional[str] = None) -> Dict:
        """Convenience: record an LLM-generated entity."""
        return self.record(
            entity_type, entity_id, "llm",
            lineage={"model": model, "llm_generated_fields": llm_fields},
            run_id=run_id,
        )
    
    def record_derivation(self, entity_type: str, entity_id: str,
                          module: str, seed: Optional[int],
                          upstream_ids: List[str],
                          run_id: Optional[str] = None) -> Dict:
        """Convenience: record a rule/derived entity with upstream lineage."""
        return self.record(
            entity_type, entity_id, "derived",
            lineage={"module": module, "seed": seed, "derived_from": upstream_ids},
            run_id=run_id,
        )
    
    def query(self, entity_id: Optional[str] = None,
              entity_type: Optional[str] = None,
              source: Optional[str] = None) -> List[Dict]:
        """Query provenance records with optional filters."""
        results = self._records
        if entity_id is not None:
            results = [r for r in results if r["entity_id"] == entity_id]
        if entity_type is not None:
            results = [r for r in results if r["entity_type"] == entity_type]
        if source is not None:
            results = [r for r in results if r["source"] == source]
        return results
    
    def get_lineage(self, entity_id: str) -> List[Dict]:
        """
        Get the full lineage chain for an entity (walks derived_from links).
        """
        chain = []
        visited = set()
        current = entity_id
        
        while current and current not in visited:
            visited.add(current)
            records = self.query(entity_id=current)
            if not records:
                break
            rec = records[-1]  # latest record for this entity
            chain.append(rec)
            upstream = rec["lineage_json"].get("derived_from", [])
            current = upstream[0] if upstream else None
        
        return chain
    
    def llm_participation_ratio(self, entity_type: Optional[str] = None) -> float:
        """
        Fraction of entities generated (at least partly) by LLM.
        Supports the LLM-participation accounting requirement.
        """
        records = self.query(entity_type=entity_type) if entity_type else self._records
        if not records:
            return 0.0
        llm_count = sum(1 for r in records if r["source"] in ("llm", "mixed"))
        return llm_count / len(records)
    
    def summary(self) -> Dict[str, Any]:
        """Aggregate provenance summary."""
        by_source: Dict[str, int] = {}
        by_type: Dict[str, int] = {}
        for r in self._records:
            by_source[r["source"]] = by_source.get(r["source"], 0) + 1
            by_type[r["entity_type"]] = by_type.get(r["entity_type"], 0) + 1
        return {
            "total_records": len(self._records),
            "by_source": by_source,
            "by_entity_type": by_type,
            "llm_participation_ratio": self.llm_participation_ratio(),
        }
