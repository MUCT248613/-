# VirtualStudent Sandbox v5.0 - Development Progress

## Project Overview

Building an AI-powered virtual student simulation system for educational intervention pre-screening using:
- **Qwen LLM** (千问) for natural language generation
- **DuckDB** for persistent storage
- **Python 3.11+** with FastAPI/React frontend
- **BKT + ACT-R** cognitive models
- **L-Model 2.0** for multi-agent life simulation

## 6-Week Milestone Plan

### ✅ W1: Project Initialization (COMPLETE - July 28)

**Deliverables:**
- [x] DuckDB schema (12 core tables)
- [x] CognitiveEngine (BKT + ACT-R implementation)
- [x] Project infrastructure (requirements, config, tests)
- [x] Sample data insertion validation

**Status:** W1 initialization script ran successfully. Database initialized with:
- real_logs, kc_params (real data tables)
- students, teachers, parents, institutions (persona tables)
- daily_timelines, social_networks, relationships, life_events (L-Model tables)
- sim_interactions, virtual_effect_sizes, gap_records, run_states (result tables)

**Next:** Start W2 Persona Service

---

### ⏳ W2: Persona Service (July 31 - Aug 6)

**Objectives:**
- [ ] Implement LLM-deep-participatory 4-layer pipeline
  - L1: Random skeleton sampling (保真锚点)
  - L2: LLM identity seed generation (身份种子, LLM 核心)
  - L3: Derivation + LLM narrative (规则+LLM 协同)
  - L4: Fingerprint verification + deduplication (去重校验)
- [ ] Uniqueness guarantee engine (FingerprintEngine + UniquenessGuarantor)
- [ ] Generate 500 students + 50 teachers + 500 parents
- [ ] Coherence engine validation

**Key Files to Create:**
- src/persona_service/pipeline.py
- src/persona_service/identity_seed.py
- src/persona_service/fingerprint.py
- src/persona_service/uniqueness.py
- src/persona_service/student_generator.py
- src/persona_service/teacher_generator.py
- src/persona_service/parent_generator.py

---

### ⏳ W3: L-Model & Calibration (Aug 7 - Aug 13)

**Objectives:**
- [ ] L-Model 2.0 engine with multi-agent simulation
- [ ] Social network evolution (networkx-based)
- [ ] Event engine (定时+随机事件)
- [ ] Relationship state machine (恋爱/亲子/师生)
- [ ] Calibration module (Optuna-based parameter search)

**Key Files:**
- src/l_model/engine.py
- src/l_model/social_network.py
- src/l_model/event_engine.py
- src/l_model/relationship.py
- src/calibrate/optimizer.py

---

### ⏳ W4: Intervention Simulation (Aug 14 - Aug 20)

**Objectives:**
- [ ] 5-channel intervention delivery
  - direct
  - teacher_mediated (T-Model)
  - parent_mediated (P-Model)
  - shadow_edu_mediated
  - self_study_mediated
- [ ] Virtual effect size calculation (Hedges g + CI)
- [ ] Scene comparison logic

**Key Files:**
- src/delivery/intervention_delivery.py
- src/simulate/effect_size.py

---

### ⏳ W5: Frontend & Gap Analysis (Aug 21 - Aug 27)

**Objectives:**
- [ ] DuckDB-backed FastAPI REST API
- [ ] React-based dashboard with 13 pages
- [ ] Gap quantification & distortion maps
- [ ] Priority ranking module
- [ ] Scientific hypothesis generator

**Key Pages:**
1. Run control console
2. Calibration diagnostics
3. Distortion map visualization
4. Intervention pre-screening report
5. Hypothesis & research plan (auto-generated)
6. Persona browsing (P/R-level, S-level hidden)
7. L-Model timeline visualization
8. Scene comparison chart
9. Subgroup slicing panel
10. Social network visualization
11. Life course replay
12. Counterfactual contrast
13. HITL review interface

---

### ⏳ W6: Testing & Submission (Aug 28 - Sep 5)

**Objectives:**
- [ ] Unit tests for all modules
- [ ] Integration tests (end-to-end pipeline)
- [ ] Privacy validation (P/R/S enforcement static scan)
- [ ] Performance benchmarking (500 students × 90 days ≤8hrs)
- [ ] True case study demonstration
- [ ] Final submission package

---

## Current State

**Repository Structure:**
```
virtual-student-sandbox/
├── src/
│   ├── cognitive_engine.py        [DONE] BKT + ACT-R
│   ├── data_layer.py              [DONE] DuckDB schema
│   ├── persona_service/           [TODO]
│   ├── l_model/                   [TODO]
│   ├── delivery/                  [TODO]
│   ├── calibrate/                 [TODO]
│   ├── privacy/                   [TODO]
│   ├── gap/                        [TODO]
│   └── api/                        [TODO]
├── tests/
│   ├── test_cognitive_engine.py   [DONE]
│   ├── test_data_layer.py         [DONE]
│   └── ...                        [TODO]
├── config/
│   └── base.yaml                  [DONE]
├── scripts/
│   └── w1_init.py                 [DONE]
├── requirements.txt               [DONE]
└── DEVELOPMENT.md                 [THIS FILE]
```

**Test Coverage:**
- ✅ BayesianKnowledgeTracer: 5 tests
- ✅ ACTRForgetting: 3 tests
- ✅ CognitiveEngine: 2 tests
- ✅ DataLayer: 3 tests
- Total: 13 passing tests

---

## Key Technical Decisions

1. **BKT + ACT-R**: Pure Python implementation (no external ML library dependencies) for reproducibility
2. **DuckDB**: Lightweight OLTP database, perfect for single-machine simulation workloads
3. **Pydantic**: Data validation and API serialization
4. **NetworkX**: Social network graph operations
5. **Privacy-First**: P/R/S three-level enforcement baked into data layer from day 1

---

## How to Run

### Setup
```bash
pip install -r requirements.txt
python scripts/w1_init.py
```

### Initialize Database
```python
from src.data_layer import DataLayer
db = DataLayer("data/virtual_student.db")
db.init_schema()
```

### Test Cognitive Engine
```python
from src.cognitive_engine import CognitiveEngine
engine = CognitiveEngine()
is_correct, confidence = engine.score_response(
    learner_profile={"p_know": 0.5, "p_slip": 0.1, "p_guess": 0.1},
    item_params={"difficulty": 0.5},
    practice_history=[],
    current_time=100.0
)
```

---

## References

- **技术设计文档**: Technical Architecture (§1-13)
- **虚拟学生全方位档案设计文档**: Persona Schema Spec (23-domain student, T1-T8 teacher, P1-P6 parent)
- **需求说明文档**: Product Requirements & Acceptance Criteria

---

## Contact & Notes

- Target submission: Sep 5, 2026
- Budget: ~100 CNY/simulation run
- Scale: 500 students × 50 teachers × 500 parents
- Simulation horizon: 90 days (1 semester)
