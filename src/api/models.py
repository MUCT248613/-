"""
Pydantic models for API request/response schemas.
Reference: 技术设计文档 §9
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


# ============ Run Management ============

class CustomInterventionSpec(BaseModel):
    """Researcher-defined candidate intervention (FR-S1 researcher entry).

    Mirrors the YAML catalog schema so researcher hypotheses and built-in
    evidence arms flow through the same delivery engine. When a run carries
    one or more of these, they *are* the experiment: the built-in battery is
    not appended (a no-treatment control arm is always kept).
    """

    id: Optional[str] = None
    label: str
    type: Optional[str] = None
    description: str = ""
    target_scene: List[str] = Field(default_factory=lambda: ["school"])
    default_channel: str = "teacher_mediated"
    effect_achievement: float = Field(default=4.0, ge=-20.0, le=20.0)
    effect_motivation: float = Field(default=0.05, ge=-1.0, le=1.0)
    # Fraction of arm students actually exposed (individual-level randomness).
    # 1.0 = fully delivered; <1 dilutes the intent-to-treat effect honestly.
    exposure_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence_hedges_g: float = Field(default=0.3, ge=-1.0, le=2.0)
    cost_yuan: float = Field(default=50.0, ge=0.0)
    action: str = ""


class RunCreateRequest(BaseModel):
    """Request to create a new simulation run"""
    n_students: int = Field(default=500, ge=1, le=5000)
    n_teachers: int = Field(default=50, ge=1, le=500)
    n_parents: int = Field(default=500, ge=1, le=5000)
    sim_days: int = Field(default=90, ge=1, le=1095)
    seed: Optional[int] = Field(default=None)
    interventions: Optional[List[CustomInterventionSpec]] = None


class RunStatusResponse(BaseModel):
    """Run status response"""
    run_id: str
    status: str  # pending / running / completed / failed
    n_students: int
    n_teachers: int
    n_parents: int
    sim_days: int
    current_day: int = 0
    created_at: str
    completed_at: Optional[str] = None
    # Live progress while status == "running": {percent, stage, message}.
    progress: Optional[Dict[str, Any]] = None
    # Per-arm display/report metadata (researcher-defined or YAML arms) so the
    # frontend can label custom candidates without a rebuild.
    intervention_meta: Optional[List[Dict[str, Any]]] = None


class RunSummaryResponse(BaseModel):
    """Lightweight run summary for the history list."""
    run_id: str
    status: str
    n_students: int
    n_teachers: int
    n_parents: int
    sim_days: int
    created_at: str
    completed_at: Optional[str] = None


class RunListResponse(BaseModel):
    """List of all simulation runs (newest first)."""
    total: int
    runs: List[RunSummaryResponse]


# ============ Student / Teacher / Parent ============

class StudentProfileResponse(BaseModel):
    """Student profile (P/R level only, S filtered by PrivacyGuard)"""
    student_id: str
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    grade: Optional[str] = None
    achievement_score: Optional[float] = None
    motivation_level: Optional[float] = None
    personality_tags: Optional[List[str]] = None
    interests: Optional[List[str]] = None
    simulation_vector: Optional[Dict[str, Any]] = None
    assigned_teacher_id: Optional[str] = None
    primary_parent_id: Optional[str] = None
    # FR-A1: comprehensive 23-domain archive (S-level domains pre-filtered)
    domains: Optional[Dict[str, Any]] = None
    field_count: Optional[int] = None
    domain_count: Optional[int] = None
    sensitive_domains_hidden: Optional[List[str]] = None


class TeacherProfileResponse(BaseModel):
    """Teacher profile (P/R level)"""
    teacher_id: str
    name: Optional[str] = None
    subject: Optional[str] = None
    experience_years: Optional[int] = None
    teaching_style: Optional[str] = None
    classroom_management: Optional[str] = None
    teaching_philosophy: Optional[str] = None
    simulation_vector: Optional[Dict[str, Any]] = None


class TeacherListResponse(BaseModel):
    """Paginated teacher list"""
    total: int
    page: int
    page_size: int
    teachers: List[TeacherProfileResponse]


class StudentListResponse(BaseModel):
    """Paginated student list"""
    total: int
    page: int
    page_size: int
    students: List[StudentProfileResponse]


# ============ Timeline ============

class TimelineEventResponse(BaseModel):
    """Single timeline event"""
    timestamp_min: float
    scene: str
    event_type: str
    learning_gain: float
    fatigue_change: float
    motivation_change: float


class DayTimelineResponse(BaseModel):
    """Single day timeline"""
    student_id: str
    sim_date: str
    events: List[TimelineEventResponse]
    total_learning_gain: float
    fatigue_end: float
    stress_end: float
    emotion_end: float


# ============ Network ============

class NetworkNodeResponse(BaseModel):
    """Network node"""
    node_id: str
    achievement_score: float
    group: Optional[int] = None


class NetworkEdgeResponse(BaseModel):
    """Network edge"""
    source: str
    target: str
    weight: float


class NetworkSnapshotResponse(BaseModel):
    """Network snapshot at a given day"""
    day: int
    nodes: List[NetworkNodeResponse]
    edges: List[NetworkEdgeResponse]
    density: float
    avg_clustering: float
    n_components: int


class NetworkEvolutionResponse(BaseModel):
    """Network evolution over time"""
    snapshots: List[Dict[str, Any]]
    metrics_trajectory: Dict[str, List[float]]


# ============ Scene Comparison ============

class SceneComparisonResponse(BaseModel):
    """Scene effect comparison"""
    intervention_type: str
    scenes: Dict[str, Dict[str, float]]  # scene -> {g, ci_lower, ci_upper, n}


# ============ Subgroups ============

class SubgroupSliceResponse(BaseModel):
    """Subgroup analysis result"""
    dimension: str
    groups: List[Dict[str, Any]]  # [{label, n, mean_ach, effect_size}]


# ============ Life Course ============

class LifeCourseResponse(BaseModel):
    """Life course trajectory for a student"""
    student_id: str
    days: List[int]
    achievement: List[float]
    motivation: List[float]
    fatigue: List[float]
    stress: List[float]
    emotion: List[float]
    events: List[Dict[str, Any]]  # Key events with annotations


# ============ Counterfactual ============

class CounterfactualCreateRequest(BaseModel):
    """Create counterfactual branch"""
    modification: Dict[str, Any] = Field(default_factory=dict)
    custom_effects: Optional[Dict[str, Any]] = None
    days: int = Field(default=30, ge=1, le=365)
    seed: Optional[int] = None


class CounterfactualCreateResponse(BaseModel):
    """Counterfactual creation result"""
    cf_id: str
    run_id: str
    modification: Dict[str, Any]
    status: str


class CounterfactualComparisonResponse(BaseModel):
    """Counterfactual comparison result"""
    cf_id: str
    baseline_mean: float
    modified_mean: float
    effect_size_g: float
    ci_95: List[float]
    trajectory_baseline: List[float]
    trajectory_modified: List[float]
    ancova_g: Optional[float] = None
    ancova_ci_95: Optional[List[float]] = None
    ancova_adjusted_diff: Optional[float] = None


# ============ Report / Deliverable Center (M7 + M8) ============

class RecommendationResponse(BaseModel):
    """Teaching-improvement recommendation carrying the three required elements:
    evidence (effect size + CI), confidence, and distortion warning."""
    rank: int
    intervention_id: str
    action: str                    # concrete, actionable suggestion (Chinese)
    evidence: str                  # "Hedges' g = ... (95% CI [...])"
    effect_size: float
    ci_95: List[float]
    confidence: str                # 高 / 中 / 低
    strength: str                  # 强 / 中等 / 弱
    distortion_warning: str
    priority_score: float


class ReportResponse(BaseModel):
    """Centralized deliverable: M7 report card + M8 research plan + recommendations."""
    run_id: str
    generated_at: str
    report_card: Dict[str, Any]            # M7 报告卡
    research_plan: Dict[str, Any]          # M8 科学假设与研究计划
    recommendations: List[RecommendationResponse]  # 教学改进建议
    markdown: str                          # full exportable Markdown


# ============ Parent (FR-F7) ============

class ParentProfileResponse(BaseModel):
    """Parent profile (P/R level)"""
    parent_id: str
    name: Optional[str] = None
    education_level: Optional[str] = None
    involvement_style: Optional[str] = None
    occupation_category: Optional[str] = None
    daily_interaction_hours: Optional[float] = None
    homework_support_level: Optional[float] = None
    emotional_warmth: Optional[float] = None
    child_id: Optional[str] = None
    simulation_vector: Optional[Dict[str, Any]] = None


class ParentListResponse(BaseModel):
    """Paginated parent list"""
    total: int
    page: int
    page_size: int
    parents: List[ParentProfileResponse]


# ============ Calibration Diagnostics (FR-F2) ============

class CalibrationDiagResponse(BaseModel):
    """Calibration diagnostics: virtual-vs-literature cognitive parameter comparison"""
    run_id: str
    data_source: str  # "literature" (published BKT baselines) | "synthetic"
    cognitive_distance: float
    bkt_params_virtual: Dict[str, float]
    bkt_params_reference: Dict[str, float]
    persona_distribution: Dict[str, Any]
    ks_test_results: Dict[str, Any]
    diagnostics: List[Dict[str, Any]]
    verdict: str  # "pass" | "marginal" | "fail"
    reference_basis: Optional[Dict[str, Any]] = None  # literature citations & note


# ============ Distortion Map (FR-F3) ============

class DistortionMapResponse(BaseModel):
    """Distortion heat-map data: intervention × scene × metric"""
    run_id: str
    interventions: List[str]
    scenes: List[str]
    metrics: List[str]
    cells: List[Dict[str, Any]]  # {intervention, scene, metric, gap, category}
    n_high_distortion: int
    summary: str


# ============ Pre-screening Report (FR-F4) ============

class PrescreeningResponse(BaseModel):
    """Pre-screening report: go/no-go decision support for real trials"""
    run_id: str
    candidates: List[Dict[str, Any]]  # ranked interventions with decision
    go_count: int
    no_go_count: int
    conditional_count: int
    criteria: List[str]
    disclaimer: str


# ============ Human-in-the-Loop (FR-F5) ============

class HITLFeedbackRequest(BaseModel):
    """Expert feedback submission"""
    target_type: str  # "intervention" | "hypothesis" | "profile" | "distortion"
    target_id: str
    verdict: str  # "agree" | "disagree" | "adjust"
    comment: Optional[str] = None
    adjusted_value: Optional[float] = None
    expert_role: Optional[str] = None  # "teacher" | "researcher" | "parent"


class HITLFeedbackResponse(BaseModel):
    """Single feedback record"""
    feedback_id: str
    run_id: str
    target_type: str
    target_id: str
    verdict: str
    comment: Optional[str] = None
    adjusted_value: Optional[float] = None
    expert_role: Optional[str] = None
    created_at: str


class HITLFeedbackListResponse(BaseModel):
    """List of feedback records for a run"""
    run_id: str
    total: int
    feedbacks: List[HITLFeedbackResponse]


# ============ LLM Configuration ============

class LLMConfigResponse(BaseModel):
    """Current LLM configuration (API key masked)"""
    base_url: str
    default_model: str
    api_key_set: bool
    api_key_masked: str = ""
    is_live: bool
    available_models: List[str] = []


class LLMConfigRequest(BaseModel):
    """Update LLM configuration. Omit a field (None) to keep current value."""
    base_url: Optional[str] = None
    default_model: Optional[str] = None
    api_key: Optional[str] = None


# ============ LLM Parameter Suggestion ============

class LLMSuggestRequest(BaseModel):
    """Request LLM-based parameter suggestions for a custom intervention."""
    description: str
    target_scene: Optional[str] = None
    target_population: Optional[str] = None


class LLMSuggestResponse(BaseModel):
    """LLM-suggested intervention parameters with literature backing."""
    suggested_achievement_effect: float
    suggested_motivation_effect: float
    suggested_exposure_rate: float
    suggested_evidence_g: float
    suggested_cost_yuan: float
    suggested_action: str
    rationale: str
    literature_refs: List[str]
    source: str  # "llm" | "literature_fallback"
    confidence: str  # "high" | "medium" | "low"
    fallback_reason: Optional[str] = None


# ============ Generic ============

class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
    status: str = "ok"


class ErrorResponse(BaseModel):
    """Error response"""
    detail: str
    status: str = "error"
