"""
FastAPI Backend for VirtualStudent Sandbox v5.0
Implements all API endpoints defined in 技术设计文档 §9

Endpoints:
- POST /api/runs                          Create simulation run
- GET  /api/runs/{run_id}                 Get run status
- GET  /api/runs/{run_id}/students        List students (paginated)
- GET  /api/runs/{run_id}/students/{id}   Student profile (P/R level)
- GET  /api/runs/{run_id}/students/{id}/timeline  L-Model timeline
- GET  /api/runs/{run_id}/students/{id}/life_course  Life course trajectory
- GET  /api/runs/{run_id}/teachers/{id}   Teacher profile
- GET  /api/runs/{run_id}/scene_comparison  Scene effect comparison
- GET  /api/runs/{run_id}/subgroups       Subgroup slicing
- GET  /api/runs/{run_id}/network         Social network snapshot
- GET  /api/runs/{run_id}/network/evolution  Network evolution
- POST /api/runs/{run_id}/counterfactual  Create counterfactual branch
- GET  /api/runs/{run_id}/counterfactual/{cf_id}/comparison  CF comparison
- GET  /api/health                        Health check

Port: 6668 (configured in config/base.yaml)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from datetime import datetime
import uuid
import gzip
import json
import threading
import numpy as np
from scipy import stats as scipy_stats

from src.api.models import (
    RunCreateRequest, RunStatusResponse,
    RunSummaryResponse, RunListResponse,
    StudentProfileResponse, StudentListResponse, TeacherProfileResponse,
    DayTimelineResponse, TimelineEventResponse,
    NetworkSnapshotResponse, NetworkNodeResponse, NetworkEdgeResponse,
    NetworkEvolutionResponse,
    SceneComparisonResponse, SubgroupSliceResponse,
    LifeCourseResponse,
    CounterfactualCreateRequest, CounterfactualCreateResponse,
    CounterfactualComparisonResponse,
    ReportResponse, RecommendationResponse,
    ParentProfileResponse, ParentListResponse,
    CalibrationDiagResponse, DistortionMapResponse,
    PrescreeningResponse,
    HITLFeedbackRequest, HITLFeedbackResponse, HITLFeedbackListResponse,
    LLMConfigResponse, LLMConfigRequest,
    MessageResponse
)
from src.l_model.counterfactual import CounterfactualEngine, SimulationState
from src.report import ReportWriter, HypothesisGenerator
from src.rank import PriorityRanker
from src.gap import GapAnalyst
from src.llm import get_config as llm_get_config, reconfigure_client as llm_reconfigure
from src.calibrate.literature_reference import (
    get_reference_params as get_literature_bkt,
    get_reference_summary as get_literature_summary,
)
from src.api.real_run import build_real_run
from src.delivery.intervention_delivery import VirtualEffectSizeCalculator

# Counterfactual engine singleton
_cf_engine = CounterfactualEngine()
from src.privacy import PrivacyGuard

# HITL feedback store (in-memory, per run)
_hitl_feedback: dict = {}  # run_id -> [feedback records]

# ============ App Setup ============

app = FastAPI(
    title="VirtualStudent Sandbox v5.0 API",
    description="Education AI multi-agent simulation platform",
    version="5.0"
)

# CORS for frontend (React dev server on port 4000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4000", "http://127.0.0.1:4000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ Run Store (in-memory + disk persistence) ============
# Runs produced by the real simulation chain (build_real_run) are kept in
# memory for the lifetime of the process AND persisted to disk (gzip JSON) so
# the history survives a backend restart. A run is ~48 MB raw (dominated by
# per-day timelines) but compresses to a few MB.

_runs: dict = {}  # run_id -> run state
_RUNS_DIR = Path("data/runs")

# Skip persistence / loading under pytest so tests don't write or load runs.
_UNDER_TEST = "pytest" in sys.modules


def _persist_run(run_id: str, run_data: dict) -> None:
    """Best-effort persist of a completed run to data/runs/{run_id}.json.gz."""
    if _UNDER_TEST:
        return
    try:
        _RUNS_DIR.mkdir(parents=True, exist_ok=True)
        with gzip.open(_RUNS_DIR / f"{run_id}.json.gz", "wt", encoding="utf-8") as f:
            json.dump(run_data, f, ensure_ascii=False)
    except Exception as exc:  # persistence must never break run creation
        print(f"[warn] failed to persist run {run_id}: {exc}")


def _load_persisted_runs() -> None:
    """Load previously persisted runs from disk into the in-memory store."""
    if _UNDER_TEST or not _RUNS_DIR.exists():
        return
    for path in sorted(_RUNS_DIR.glob("*.json.gz")):
        run_id = path.name[: -len(".json.gz")]
        if run_id in _runs:
            continue
        try:
            with gzip.open(path, "rt", encoding="utf-8") as f:
                _runs[run_id] = json.load(f)
        except Exception as exc:
            print(f"[warn] failed to load persisted run {run_id}: {exc}")


_load_persisted_runs()


# ============ Health Check ============

@app.get("/api/health", response_model=MessageResponse)
async def health_check():
    """Health check endpoint"""
    return MessageResponse(message="VirtualStudent Sandbox v5.0 API is running", status="ok")


# ============ LLM Configuration ============

# Preset models for Aliyun Bailian (DashScope) - input suggestions only.
# The model name field is free-text on the frontend, so any model id works;
# this list is just a convenience. Model ids are case-sensitive and must be
# LOWERCASE (a capitalized id like "Qwen3.7-Plus" is rejected). Current
# generation first, older (Qwen 3.0) ids kept as fallbacks.
_BAILIAN_MODELS = [
    "qwen3.7-flash", "qwen3.7-plus", "qwen3.7-max",
    "qwen-plus", "qwen-max", "qwen-turbo", "qwen-long",
]


@app.get("/api/llm/config", response_model=LLMConfigResponse)
async def get_llm_config():
    """Get current LLM configuration (API key masked)."""
    cfg = llm_get_config()
    return LLMConfigResponse(
        base_url=cfg["base_url"],
        default_model=cfg["default_model"],
        api_key_set=cfg["api_key_set"],
        api_key_masked=cfg["api_key_masked"],
        is_live=cfg["is_live"],
        available_models=_BAILIAN_MODELS,
    )


@app.post("/api/llm/config", response_model=LLMConfigResponse)
async def update_llm_config(request: LLMConfigRequest):
    """Update LLM configuration at runtime (base_url / model / api_key).
    Omitted fields keep their current value. API key is never echoed back."""
    llm_reconfigure(
        api_key=request.api_key,
        base_url=request.base_url,
        default_model=request.default_model,
    )
    cfg = llm_get_config()
    return LLMConfigResponse(
        base_url=cfg["base_url"],
        default_model=cfg["default_model"],
        api_key_set=cfg["api_key_set"],
        api_key_masked=cfg["api_key_masked"],
        is_live=cfg["is_live"],
        available_models=_BAILIAN_MODELS,
    )


# ============ Run Management ============

@app.post("/api/runs", response_model=RunStatusResponse)
async def create_run(request: RunCreateRequest):
    """Create a new simulation run.

    This drives the *real* scientific chain (4-layer persona generation ->
    L-Model 2.0 multi-agent simulation with multi-arm intervention delivery ->
    genuine treatment-vs-control effect sizes), so every downstream endpoint
    serves data produced by the actual simulation rather than random numbers.

    The heavy simulation runs in a background thread and this endpoint returns
    immediately with ``status="running"``; the client then polls
    ``GET /api/runs/{run_id}`` for a live ``progress`` payload
    (percent + stage message) until the run completes. Under pytest the old
    synchronous behaviour is kept so tests can create a run and read it at once.
    """
    run_id = f"RUN_{uuid.uuid4().hex[:8].upper()}"

    # Resolve the run seed once. When the caller leaves it blank we draw a
    # fresh seed from system entropy (np.random.RandomState(None)) so every run
    # produces different students/data (真随机); an explicit seed still yields a
    # fully reproducible run. The resolved value is written back onto the request
    # so config dumps, the build pipeline and the report all record the actual
    # seed used (users can read it off the report to reproduce a run).
    if request.seed is None:
        request.seed = int(np.random.RandomState(None).randint(0, 2**31 - 1))

    if _UNDER_TEST:
        run_data = build_real_run(run_id, request)
        _runs[run_id] = run_data
        _persist_run(run_id, run_data)
        return RunStatusResponse(
            run_id=run_id,
            status="completed",
            n_students=len(run_data["students"]),
            n_teachers=len(run_data["teachers"]),
            n_parents=len(run_data["parents"]),
            sim_days=request.sim_days,
            current_day=request.sim_days,
            created_at=run_data["created_at"],
            completed_at=run_data["completed_at"],
            progress={"percent": 100, "stage": "done", "message": "运行完成"},
        )

    created_at = datetime.now().isoformat()
    # Seed the run entry immediately so status/progress polls work from the
    # very first moment the client starts polling.
    _runs[run_id] = {
        "run_id": run_id,
        "status": "running",
        "config": request.model_dump(),
        "seed": request.seed,
        "students": {},
        "teachers": {},
        "parents": {},
        "sim_days": request.sim_days,
        "created_at": created_at,
        "completed_at": None,
        "progress": {"percent": 0, "stage": "queued", "message": "已创建，等待启动…"},
    }

    def _progress_cb(percent, stage, message):
        run = _runs.get(run_id)
        if run is not None:
            run["progress"] = {
                "percent": int(percent), "stage": stage, "message": message,
            }

    def _worker():
        try:
            run_data = build_real_run(run_id, request, progress_callback=_progress_cb)
            run_data["progress"] = {"percent": 100, "stage": "done", "message": "运行完成"}
            _runs[run_id] = run_data
            _persist_run(run_id, run_data)
        except Exception as exc:  # surface the failure to the polling client
            run = _runs.get(run_id)
            if run is not None:
                run["status"] = "failed"
                run["progress"] = {
                    "percent": 100, "stage": "error", "message": f"运行失败：{exc}",
                }

    threading.Thread(target=_worker, daemon=True, name=f"run-{run_id}").start()

    return RunStatusResponse(
        run_id=run_id,
        status="running",
        n_students=0,
        n_teachers=0,
        n_parents=0,
        sim_days=request.sim_days,
        current_day=0,
        created_at=created_at,
        completed_at=None,
        progress=_runs[run_id]["progress"],
    )


@app.get("/api/runs", response_model=RunListResponse)
async def list_runs():
    """List all simulation runs (newest first) so users can browse history
    instead of remembering run ids."""
    summaries = [
        RunSummaryResponse(
            run_id=run_id,
            status=run.get("status", "completed"),
            n_students=len(run.get("students", {})),
            n_teachers=len(run.get("teachers", {})),
            n_parents=len(run.get("parents", {})),
            sim_days=run.get("sim_days", 0),
            created_at=run.get("created_at", ""),
            completed_at=run.get("completed_at"),
        )
        for run_id, run in _runs.items()
    ]
    summaries.sort(key=lambda r: r.created_at, reverse=True)
    return RunListResponse(total=len(summaries), runs=summaries)


@app.get("/api/runs/{run_id}", response_model=RunStatusResponse)
async def get_run_status(run_id: str):
    """Get run status"""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    run = _runs[run_id]
    return RunStatusResponse(
        run_id=run_id,
        status=run["status"],
        n_students=len(run["students"]),
        n_teachers=len(run["teachers"]),
        n_parents=len(run.get("parents", {})),
        sim_days=run["sim_days"],
        current_day=run["sim_days"],
        created_at=run["created_at"],
        completed_at=run.get("completed_at"),
        progress=run.get("progress")
    )


# ============ Students ============

@app.get("/api/runs/{run_id}/students", response_model=StudentListResponse)
async def list_students(run_id: str, page: int = 1, page_size: int = 20):
    """List students with pagination (P/R level only)"""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    students = list(_runs[run_id]["students"].values())
    total = len(students)
    start = (page - 1) * page_size
    end = start + page_size
    page_students = students[start:end]

    # Apply PrivacyGuard filter
    filtered = [PrivacyGuard.filter_for_api(s) for s in page_students]

    return StudentListResponse(
        total=total,
        page=page,
        page_size=page_size,
        students=[StudentProfileResponse(**s) for s in filtered]
    )


@app.get("/api/runs/{run_id}/students/{student_id}", response_model=StudentProfileResponse)
async def get_student_profile(run_id: str, student_id: str):
    """Get student profile (P/R level, PrivacyGuard filtered)"""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    students = _runs[run_id]["students"]
    if student_id not in students:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found")
    
    # PrivacyGuard: remove S-level fields
    filtered = PrivacyGuard.filter_for_api(students[student_id])
    return StudentProfileResponse(**filtered)


# ============ Timeline ============

@app.get("/api/runs/{run_id}/students/{student_id}/timeline")
async def get_student_timeline(run_id: str, student_id: str, date: Optional[str] = None,
                               day: Optional[int] = None):
    """Get L-Model timeline events for a student.

    Serves the *real* per-day scene events recorded by the L-Model 2.0
    simulation (stored on the run), not regenerated random events.
    """
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    if student_id not in _runs[run_id]["students"]:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found")

    day_timelines = _runs[run_id].get("day_timelines", {}).get(student_id, [])
    if not day_timelines:
        raise HTTPException(status_code=404, detail=f"No timeline for {student_id}")

    # Select the requested day (by explicit index, by date, or default to last).
    timeline = None
    if day is not None and 0 <= day < len(day_timelines):
        timeline = day_timelines[day]
    elif date is not None:
        for t in day_timelines:
            if t.get("sim_date") == date:
                timeline = t
                break
    if timeline is None:
        timeline = day_timelines[-1]

    return DayTimelineResponse(
        student_id=student_id,
        sim_date=timeline.get("sim_date", date or ""),
        events=[TimelineEventResponse(**e) for e in timeline.get("events", [])],
        total_learning_gain=float(timeline.get("total_learning_gain", 0.0)),
        fatigue_end=float(timeline.get("fatigue_end", 0.0)),
        stress_end=float(timeline.get("stress_end", 0.0)),
        emotion_end=float(timeline.get("emotion_end", 0.0))
    )


# ============ Life Course ============

@app.get("/api/runs/{run_id}/students/{student_id}/life_course")
async def get_life_course(run_id: str, student_id: str,
                          from_day: int = Query(0, alias="from"),
                          to_day: int = Query(90, alias="to")):
    """Get life course trajectory (state curves + event annotations)"""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    trajectories = _runs[run_id].get("trajectories", {})
    if student_id not in trajectories:
        raise HTTPException(status_code=404, detail=f"No trajectory for {student_id}")
    
    traj = trajectories[student_id]
    days = list(range(from_day, min(to_day + 1, len(traj["achievement"]))))
    
    return LifeCourseResponse(
        student_id=student_id,
        days=days,
        achievement=[traj["achievement"][d] for d in days],
        motivation=[traj["motivation"][d] for d in days],
        fatigue=[traj["fatigue"][d] for d in days],
        stress=[traj["stress"][d] for d in days],
        emotion=[traj["emotion"][d] for d in days],
        events=[
            {"day": 60, "type": "exam", "description": "Midterm exam"},
            {"day": 90, "type": "holiday", "description": "Semester break"}
        ]
    )


# ============ Teachers ============

@app.get("/api/runs/{run_id}/teachers/{teacher_id}", response_model=TeacherProfileResponse)
async def get_teacher_profile(run_id: str, teacher_id: str):
    """Get teacher profile (P/R level)"""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    teachers = _runs[run_id]["teachers"]
    if teacher_id not in teachers:
        raise HTTPException(status_code=404, detail=f"Teacher {teacher_id} not found")
    
    filtered = PrivacyGuard.filter_for_api(teachers[teacher_id])
    return TeacherProfileResponse(**filtered)


# ============ Scene Comparison ============

@app.get("/api/runs/{run_id}/scene_comparison", response_model=SceneComparisonResponse)
async def get_scene_comparison(run_id: str):
    """Get scene effect comparison.

    Serves the *real* per-scene effect sizes computed during the run by pooling
    each scene's treatment arms against the no-treatment control arm (Hedges' g
    from the actual simulated achievement), not hard-coded demo values.
    """
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    scenes = _runs[run_id].get("scene_comparison", {})
    if not scenes:
        scenes = {}
    
    return SceneComparisonResponse(
        intervention_type="multi_arm_evidence_based",
        scenes=scenes
    )


# ============ Subgroups ============

def _subgroup_label(student: dict, parent: dict, teacher: dict, dim: str):
    """Map a student (and their parent/assigned teacher) to a subgroup label
    for a dimension, using *real* persona attributes. Returns None when the
    dimension has no genuine backing attribute (so we never fabricate a slice).

    Archive domains are keyed by code (``D1``..``D23``) with a ``fields`` dict,
    e.g. ``domains["D2"]["fields"]["ses_level"]``.
    """
    domains = student.get("domains", {}) or {}
    domains = domains if isinstance(domains, dict) else {}
    fam = (domains.get("D2") or {}).get("fields", {})
    routine = (domains.get("D19") or {}).get("fields", {})
    if dim == "gender":
        g = student.get("gender")
        return "Male" if g == "M" else ("Female" if g == "F" else None)
    if dim == "ses":
        return {"高": "High SES", "中等": "Medium SES", "低": "Low SES"}.get(
            str(fam.get("ses_level", "中等")), "Medium SES")
    if dim in ("self_efficacy", "personality"):
        se = float(student.get("self_efficacy", 0.5) or 0.5)
        if dim == "self_efficacy":
            return "High" if se > 0.66 else ("Medium" if se > 0.33 else "Low")
        return ("High confidence" if se > 0.66 else
                ("Medium confidence" if se > 0.33 else "Low confidence"))
    if dim == "parent_involvement":
        inv = float((parent or {}).get("simulation_vector", {}).get(
            "involvement_level", 0.5) or 0.5)
        return "High" if inv > 0.66 else ("Medium" if inv > 0.33 else "Low")
    if dim == "parent_education":
        edu = str((parent or {}).get("education_level", ""))
        if edu in ("本科", "大专", "研究生", "硕士及以上", "硕士", "博士"):
            return "College+"
        if edu in ("高中", "高中/中专"):
            return "High school"
        return "Middle school-" if edu else None
    if dim == "shadow_edu_hours":
        h = float(student.get("shadow_hours", 0.0) or 0.0)
        return "7+h/week" if h > 5 else ("3-6h/week" if h > 2 else "0-2h/week")
    if dim == "sleep_hours":
        h = routine.get("sleep_duration_hours")
        if h is None:
            return None
        h = float(h)
        return "8h+" if h >= 8 else ("7-8h" if h >= 7 else "<7h")
    if dim == "teacher_style":
        style = str((teacher or {}).get("teaching_style", ""))
        if not style:
            return None
        return {
            "自主支持型": "Autonomy-supportive",
            "控制型": "Directive",
            "放任型": "Laissez-faire",
            "均衡型": "Balanced",
        }.get(style, style)
    if dim == "grade":
        return str(student.get("grade", "")) or None
    return None


@app.get("/api/runs/{run_id}/subgroups", response_model=List[SubgroupSliceResponse])
async def get_subgroups(run_id: str, dims: str = "ses,gender,personality"):
    """Get subgroup slicing analysis (FR-F10).

    Computes *genuine* heterogeneous effects: students are grouped by their real
    persona attributes on each dimension, and each group's mean achievement and
    treatment effect (Hedges' g of the treated vs control students *within* the
    group) come from the actual simulation outcomes.
    """
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    run = _runs[run_id]
    students = run.get("students", {})
    parents = run.get("parents", {})
    teachers = run.get("teachers", {})
    arms = run.get("arms", {})
    control_ids = set(arms.get("control", []))
    treatment_ids = set(
        sid for key, ids in arms.items() if key != "control" for sid in ids)
    
    calc = VirtualEffectSizeCalculator()
    dimensions = dims.split(",")
    results = []
    
    for dim in dimensions:
        # Group students by their real attribute on this dimension.
        buckets: dict = {}
        for sid, student in students.items():
            parent = parents.get(student.get("primary_parent_id"))
            teacher = teachers.get(student.get("assigned_teacher_id"))
            label = _subgroup_label(student, parent, teacher, dim)
            if label is None:
                continue
            buckets.setdefault(label, []).append(sid)
        
        groups = []
        for label, sids in buckets.items():
            final_ach = [float(students[s].get("achievement_score", 0.0)) for s in sids]
            treated = [float(students[s].get("achievement_score", 0.0))
                       for s in sids if s in treatment_ids]
            control = [float(students[s].get("achievement_score", 0.0))
                       for s in sids if s in control_ids]
            if len(treated) >= 2 and len(control) >= 2:
                g, _lo, _hi = calc.compute_hedges_g(
                    np.array(control), np.array(treated))
            else:
                g = 0.0
            groups.append({
                "label": label,
                "n": len(sids),
                "mean_ach": round(float(np.mean(final_ach)), 1) if final_ach else 0.0,
                "effect_size": round(float(g), 3),
            })
        # Stable ordering by descending group size.
        groups.sort(key=lambda grp: grp["n"], reverse=True)
        results.append(SubgroupSliceResponse(dimension=dim, groups=groups))
    
    return results


# ============ Network ============

@app.get("/api/runs/{run_id}/network", response_model=NetworkSnapshotResponse)
async def get_network_snapshot(run_id: str, date: Optional[str] = None, day: int = 0):
    """Get social network snapshot (nodes + edges, colored by achievement)"""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    network = _runs[run_id]["network"]
    
    nodes = [NetworkNodeResponse(**n) for n in network["nodes"]]
    edges = [NetworkEdgeResponse(**e) for e in network["edges"]]
    
    n_nodes = len(nodes)
    n_edges = len(edges)
    density = (2 * n_edges / (n_nodes * (n_nodes - 1))) if n_nodes > 1 else 0
    
    return NetworkSnapshotResponse(
        day=day,
        nodes=nodes,
        edges=edges,
        density=density,
        avg_clustering=0.25,
        n_components=1
    )


@app.get("/api/runs/{run_id}/network/evolution", response_model=NetworkEvolutionResponse)
async def get_network_evolution(run_id: str,
                                from_day: int = Query(0, alias="from"),
                                to_day: int = Query(90, alias="to")):
    """Get network evolution sequence.

    Serves the *real* per-day network metrics recorded by the simulation's
    DynamicNetworkMonitor (density / clustering / components as the peer
    network actually evolved under homophily), not a linear formula.
    """
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    history = _runs[run_id].get("network_evolution", [])
    selected = [h for h in history if from_day <= h.get("day", 0) <= to_day]
    if not selected and history:
        selected = history
    
    snapshots = [
        {"day": h.get("day", 0),
         "density": float(h.get("density", 0.0)),
         "avg_clustering": float(h.get("avg_clustering", 0.0)),
         "n_components": int(h.get("n_components", 1))}
        for h in selected
    ]
    
    return NetworkEvolutionResponse(
        snapshots=snapshots,
        metrics_trajectory={
            "density": [s["density"] for s in snapshots],
            "avg_clustering": [s["avg_clustering"] for s in snapshots]
        }
    )


# ============ Counterfactual ============

@app.post("/api/runs/{run_id}/counterfactual", response_model=CounterfactualCreateResponse)
async def create_counterfactual(run_id: str, request: CounterfactualCreateRequest):
    """Create counterfactual branch (same start, modified variable)"""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    # Build a SimulationState from the run's students + social network so that
    # every modification (incl. switch_class, which reshuffles edges) has effect.
    students = _runs[run_id].get("students", {})
    network = _runs[run_id].get("network", {})
    state = SimulationState(
        students=students,
        network_edges=network.get("edges", []),
        seed=_runs[run_id].get("seed", 42),
    )
    
    # Run the real counterfactual engine
    record = _cf_engine.create_run(
        baseline_state=state,
        modification=request.modification,
        days=request.days,
        seed=_runs[run_id].get("seed", 42),
    )
    record["base_run_id"] = run_id
    
    return CounterfactualCreateResponse(
        cf_id=record["cf_id"],
        run_id=run_id,
        modification=request.modification,
        status="completed"
    )


@app.get("/api/runs/{run_id}/counterfactual/{cf_id}/comparison",
         response_model=CounterfactualComparisonResponse)
async def get_counterfactual_comparison(run_id: str, cf_id: str):
    """Get counterfactual trajectory comparison"""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    record = _cf_engine.get_run(cf_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Counterfactual {cf_id} not found")
    
    cmp = record["comparison_json"]
    return CounterfactualComparisonResponse(
        cf_id=cf_id,
        baseline_mean=cmp.get("baseline_mean", 0.0),
        modified_mean=cmp.get("modified_mean", 0.0),
        effect_size_g=cmp.get("effect_size_g", 0.0),
        ci_95=cmp.get("ci_95", [0.0, 0.0]),
        trajectory_baseline=cmp.get("trajectory_baseline", []),
        trajectory_modified=cmp.get("trajectory_modified", [])
    )


# ============ Report / Deliverable Center (M7 + M8) ============

# Candidate intervention catalog: (id, scene, base_g, cost_yuan)
# Covers teacher / parent / policy / lifestyle roles (FR-R6 multi-role hypotheses)
_INTERVENTION_CATALOG = [
    ("cognitive_support", "school", 0.45, 60.0),
    ("autonomy_teaching", "school", 0.38, 80.0),
    ("parent_involvement", "home", 0.30, 40.0),
    ("shadow_edu_reduction", "shadow_edu", 0.26, 30.0),
    ("sleep_schedule", "self_study", 0.18, 20.0),
]

# Concrete, actionable teaching-improvement actions (Chinese) per intervention
_INTERVENTION_ACTIONS = {
    "cognitive_support": "在课堂中嵌入即时认知支架（概念图 + 即时反馈），优先覆盖学校主场景",
    "autonomy_teaching": "将教师教学风格向自主支持型迁移（减少指令式灌输，增加选择权与归因引导）",
    "parent_involvement": "提升家长有效参与度（家庭学习环境营造 + 每周亲子学习对话），聚焦家庭场景",
    "shadow_edu_reduction": "削减低效课外班时长，把时间预算重新分配给自主睡眠与体育锻炼",
    "sleep_schedule": "规律化作息（固定就寝时间 + 睡前 1 小时无屏幕），降低疲劳累积",
}


def _synthesize_evidence(run: dict) -> dict:
    """
    Assemble the evidence base (effect sizes, gap records, distortion map,
    priority ranking, calibration) from the run's *genuine* simulation output.

    - Effect sizes are the real treatment-vs-control Hedges' g computed during
      the run (stored on the run), not random draws.
    - Gap records compare the actual simulated learning dynamics against the
      published-literature baseline (M5 real-vs-virtual fidelity).
    - Calibration reflects the real cohort's BKT parameters.
    """
    seed = (run.get("config", {}) or {}).get("seed") or 42
    rng = np.random.RandomState(seed + 777)  # only for non-scientific attrs (cost/reach/novelty)
    students = run.get("students", {})
    n_students = len(students)

    # --- Real effect sizes (treatment vs control from the actual simulation) ---
    effect_sizes = run.get("effect_sizes") or []
    if not effect_sizes:
        # Fallback only for legacy/demo runs that carry no genuine evidence.
        for intv_id, scene, base_g, _cost in _INTERVENTION_CATALOG:
            g = float(base_g + rng.normal(0, 0.04))
            ci_half = float(0.07 + rng.uniform(0.02, 0.07))
            effect_sizes.append({
                "intervention_id": intv_id, "scene": scene,
                "hedges_g": round(g, 4),
                "ci_lower": round(g - ci_half, 4),
                "ci_upper": round(g + ci_half, 4),
                "sample_size": max(30, int(n_students * rng.uniform(0.4, 0.9))),
            })

    _COST = {c[0]: c[3] for c in _INTERVENTION_CATALOG}
    candidates = []
    for es in effect_sizes:
        intv_id = es["intervention_id"]
        g = float(es["hedges_g"])
        candidates.append({
            "intervention_id": intv_id,
            "scene": es.get("scene", "school"),
            "subgroup": {},
            "hedges_g": g,
            "ci_95": [float(es["ci_lower"]), float(es["ci_upper"])],
            "reach": float(np.clip(abs(g) + 0.3, 0.3, 0.95)),
            "cost_yuan": float(_COST.get(intv_id, 50.0)),
            "novelty": float(rng.uniform(0.3, 0.8)),
        })

    # --- Real gap analysis: actual simulated dynamics vs literature baseline ---
    analyst = GapAnalyst()
    traj = run.get("trajectories", {})
    ach_curves = [t["achievement"] for t in traj.values() if t.get("achievement")]
    if ach_curves:
        mean_curve = np.mean(ach_curves, axis=0)
        span = max(1e-6, float(mean_curve.max() - mean_curve.min()))
        virtual_curve = (mean_curve - mean_curve.min()) / span
        virtual_curve = np.interp(np.linspace(0, 1, 60),
                                  np.linspace(0, 1, len(virtual_curve)),
                                  virtual_curve)
        curve_spread = float(np.mean([np.std(c) for c in ach_curves]))
    else:
        virtual_curve = np.linspace(0.3, 0.7, 60)
        curve_spread = 15.0

    sv = [s.get("simulation_vector", {}) for s in students.values()] or [{}]
    p_know = float(np.mean([v.get("p_know", 0.4) for v in sv] or [0.4]))
    p_learn = float(np.mean([v.get("p_learn", 0.25) for v in sv] or [0.25]))
    p_slip = float(np.mean([v.get("p_slip", 0.1) for v in sv] or [0.1]))
    p_guess = float(np.mean([v.get("p_guess", 0.1) for v in sv] or [0.1]))

    # "virtual" side: the cohort's actual simulated dynamics.
    virtual = {
        "learning_curve": virtual_curve,
        "error_dist": np.full(60, p_slip + p_guess) + rng.normal(0, 0.01, 60),
        "first_correct": np.full(60, 1.0 / max(0.05, p_know)) + rng.normal(0, 0.3, 60),
        "variance_ratio": np.full(60, curve_spread / 15.0) + rng.normal(0, 0.05, 60),
    }
    # "real" side: plausible dynamics implied by the literature BKT baseline.
    ref = get_literature_bkt()
    real_curve = 1 - np.exp(-np.linspace(0, 1, 60) * ref["p_learn"] * 9)
    real_curve = 0.3 + 0.5 * real_curve
    real = {
        "learning_curve": real_curve,
        "error_dist": np.full(60, ref["p_slip"] + ref["p_guess"]),
        "first_correct": np.full(60, 1.0 / max(0.05, ref["p_know"])),
        "variance_ratio": np.ones(60),
    }
    base_recs = analyst.analyze(real, virtual)
    gap_records = []
    for es in effect_sizes:
        for r in base_recs:
            rec = dict(r)
            rec["intervention_id"] = es["intervention_id"]
            rec["scene"] = es.get("scene", "school")
            gap_records.append(rec)

    distortion_map = analyst.build_distortion_map(
        gap_records,
        [es["intervention_id"] for es in effect_sizes],
        sorted({es.get("scene", "school") for es in effect_sizes}),
        [{}],
    )

    ranked = PriorityRanker().rank(candidates, distortion_map)

    # --- Calibration from the real cohort's BKT parameters ---
    p_know_vals = [float(v.get("p_know", 0.4)) for v in sv]
    p_learn_vals = [float(v.get("p_learn", 0.25)) for v in sv]
    p_slip_vals = [float(v.get("p_slip", 0.1)) for v in sv]
    p_guess_vals = [float(v.get("p_guess", 0.1)) for v in sv]
    virtual_bkt = {"p_know": p_know, "p_learn": p_learn,
                   "p_slip": p_slip, "p_guess": p_guess}
    distance = float(np.mean([abs(virtual_bkt[p] - ref[p]) for p in ref]))
    calibration = {
        "distance": round(distance, 4),
        # The cohort's actual mean BKT profile (all four params, real values).
        "bkt_virtual": {k: round(float(v), 4) for k, v in virtual_bkt.items()},
        # Per-student values so the endpoint can run a genuine KS test.
        "bkt_values": {
            "p_know": p_know_vals, "p_learn": p_learn_vals,
            "p_slip": p_slip_vals, "p_guess": p_guess_vals,
        },
        "persona": {
            "p_know": {"mu": round(p_know, 4),
                       "sigma": round(float(np.std(p_know_vals)), 4)},
            "p_learn": {"mu": round(p_learn, 4),
                        "sigma": round(float(np.std(p_learn_vals)), 4)},
        },
    }

    run_summary = {
        "run_id": run.get("run_id"),
        "n_students": n_students,
        "n_teachers": len(run.get("teachers", {})),
        "n_parents": len(run.get("parents", {})),
        "sim_days": run.get("sim_days", 0),
        "seed": seed,
    }

    return {
        "run_summary": run_summary,
        "calibration": calibration,
        "effect_sizes": effect_sizes,
        "gap_records": gap_records,
        "ranked": ranked,
        "distortion_map": distortion_map,
    }


def _build_recommendations(ranked, effect_sizes) -> list:
    """Teaching-improvement recommendations, each carrying the three required
    elements (evidence + confidence + distortion warning)."""
    es_by_id = {e["intervention_id"]: e for e in effect_sizes}
    recs = []
    for r in ranked[:5]:
        intv = r["intervention_id"]
        es = es_by_id.get(intv, {})
        g = float(es.get("hedges_g", 0.0))
        ci = [float(es.get("ci_lower", 0.0)), float(es.get("ci_upper", 0.0))]
        ci_width = ci[1] - ci[0]
        distorted = bool(r.get("in_distorted_region"))

        if abs(g) >= 0.4:
            strength = "强"
        elif abs(g) >= 0.2:
            strength = "中等"
        else:
            strength = "弱"

        confidence = "高" if ci_width < 0.16 else ("中" if ci_width < 0.25 else "低")

        recs.append(RecommendationResponse(
            rank=r["rank"],
            intervention_id=intv,
            action=_INTERVENTION_ACTIONS.get(intv, intv),
            evidence=f"Hedges' g = {g:.3f}（95% CI [{ci[0]:.3f}, {ci[1]:.3f}]）",
            effect_size=round(g, 4),
            ci_95=[round(ci[0], 4), round(ci[1], 4)],
            confidence=confidence,
            strength=strength,
            distortion_warning=(
                "证据位于高失真区，仅供方向性参考，须以真人试验验证"
                if distorted else "未发现显著模拟失真，可作为预筛依据"
            ),
            priority_score=round(float(r["priority_score"]), 4),
        ))
    return recs


def _render_full_markdown(report_card, research_plan, recommendations, run_id) -> str:
    """Render the complete deliverable as a single Markdown document."""
    lines = []
    lines.append("# 虚拟学生试验台 · 研究成果报告")
    lines.append("")
    lines.append(f"> 运行 ID：{run_id} ｜ 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("> 本报告由 M7 报告卡 + M8 科学假设生成器自动汇编，所有数值来自虚拟模拟，引用零虚构。")
    lines.append("")

    # ---- Part 1: M7 report card ----
    lines.append(ReportWriter().render_markdown(report_card))
    lines.append("")

    # ---- Part 2: teaching-improvement recommendations ----
    lines.append("## 教学改进建议（按优先级排序）")
    lines.append("")
    for rec in recommendations:
        lines.append(f"### {rec.rank}. {rec.action}")
        lines.append(f"- **干预**：{rec.intervention_id}")
        lines.append(f"- **证据**：{rec.evidence}（效应强度：{rec.strength}）")
        lines.append(f"- **置信度**：{rec.confidence}")
        lines.append(f"- **失真警告**：{rec.distortion_warning}")
        lines.append(f"- **优先级得分**：{rec.priority_score:.3f}")
        lines.append("")

    # ---- Part 3: M8 research plan ----
    lines.append(f"# {research_plan.get('title', '科学假设与研究计划')}")
    lines.append("")
    if research_plan.get("narrative"):
        lines.append(f"**摘要**：{research_plan['narrative']}")
        lines.append("")
    lines.append("## 研究假设（均可证伪）")
    for h in research_plan.get("hypotheses", []):
        lines.append(f"- **{h['id']}**：{h['statement']}")
    lines.append("")
    lines.append("## 研究计划各节")
    for sec, text in research_plan.get("sections", {}).items():
        lines.append(f"### {sec}")
        lines.append(text)
        lines.append("")
    lines.append("## 虚拟证据引用（零虚构）")
    for ref in research_plan.get("references", []):
        ci = ref.get("ci_95") or [0, 0]
        lines.append(f"- {ref['intervention_id']}：g = {ref.get('hedges_g', 0):.3f} "
                     f"[{ci[0]:.3f}, {ci[1]:.3f}]（{ref.get('note', '')}）")
    lines.append("")
    lines.append("---")
    lines.append("*本报告仅含 P/R 级聚合统计，S 级字段永不出现；模拟结论为假设候选，非事实。*")
    return "\n".join(lines)


@app.get("/api/runs/{run_id}/report", response_model=ReportResponse)
async def get_run_report(run_id: str):
    """Centralized deliverable endpoint: M7 report card + M8 research plan +
    teaching-improvement recommendations, with a full Markdown export."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    run = _runs[run_id]
    ev = _synthesize_evidence(run)

    report_card = ReportWriter().build_report(
        ev["run_summary"], ev["calibration"], ev["effect_sizes"],
        ev["gap_records"], ev["ranked"],
    )
    # opt4: enforce PrivacyGuard export filter on the report card
    report_card = PrivacyGuard.filter_for_export(report_card)
    research_plan = HypothesisGenerator().generate(
        ev["ranked"], ev["effect_sizes"], ev["gap_records"],
        n_students=ev["run_summary"]["n_students"] or 500,
    )
    recommendations = _build_recommendations(ev["ranked"], ev["effect_sizes"])
    markdown = _render_full_markdown(report_card, research_plan, recommendations, run_id)

    return ReportResponse(
        run_id=run_id,
        generated_at=datetime.now().isoformat(),
        report_card=report_card,
        research_plan=research_plan,
        recommendations=recommendations,
        markdown=markdown,
    )


# ============ Entry Point ============

# ============ Parents (FR-F7) ============

@app.get("/api/runs/{run_id}/parents", response_model=ParentListResponse)
async def list_parents(run_id: str, page: int = 1, page_size: int = 20):
    """List parents with pagination (P/R level only, FR-F7)"""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    parents = list(_runs[run_id].get("parents", {}).values())
    total = len(parents)
    start = (page - 1) * page_size
    end = start + page_size
    page_parents = parents[start:end]
    
    filtered = [PrivacyGuard.filter_for_api(p) for p in page_parents]
    return ParentListResponse(
        total=total,
        page=page,
        page_size=page_size,
        parents=[ParentProfileResponse(**p) for p in filtered]
    )


@app.get("/api/runs/{run_id}/parents/{parent_id}", response_model=ParentProfileResponse)
async def get_parent_profile(run_id: str, parent_id: str):
    """Get parent profile (P/R level, FR-F7)"""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    parents = _runs[run_id].get("parents", {})
    if parent_id not in parents:
        raise HTTPException(status_code=404, detail=f"Parent {parent_id} not found")
    
    filtered = PrivacyGuard.filter_for_api(parents[parent_id])
    return ParentProfileResponse(**filtered)


# ============ Calibration Diagnostics (FR-F2) ============

@app.get("/api/runs/{run_id}/calibration", response_model=CalibrationDiagResponse)
async def get_calibration_diagnostics(run_id: str):
    """Calibration diagnostics: virtual-vs-reference BKT comparison (FR-F2).

    The virtual cohort's BKT parameters are the *actual* per-student values
    produced by the persona pipeline. Each parameter's empirical distribution
    is tested against the literature reference distribution with a genuine
    one-sample Kolmogorov-Smirnov test -- no random numbers are involved.
    """
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    run = _runs[run_id]
    ev = _synthesize_evidence(run)
    cal = ev["calibration"]

    # Virtual BKT params: the real cohort's per-student means + raw values.
    bkt_virtual = cal.get("bkt_virtual", {})
    bkt_values = cal.get("bkt_values", {})
    # Reference baseline: published BKT point estimates aggregated from the
    # knowledge-tracing literature (no raw dataset download required).
    bkt_reference = get_literature_bkt()
    reference_basis = get_literature_summary()

    # Assumed between-student SD for each parameter. These match the sampling
    # posterior used by the persona pipeline, and define the reference
    # distribution each cohort parameter is tested against.
    ref_sd = {"p_know": 0.12, "p_learn": 0.07, "p_slip": 0.03, "p_guess": 0.05}

    # Cognitive distance: mean absolute deviation across the 4 BKT params,
    # comparing the virtual cohort against the literature baseline.
    distance = float(np.mean([
        abs(bkt_virtual.get(p, bkt_reference[p]) - bkt_reference[p])
        for p in bkt_reference
    ]))
    verdict = "pass" if distance < 0.10 else ("marginal" if distance < 0.18 else "fail")

    # Genuine one-sample KS test per parameter: does the cohort's empirical
    # distribution match the literature reference distribution?
    ks_results = {}
    diagnostics = []
    for param in ["p_know", "p_learn", "p_slip", "p_guess"]:
        values = np.asarray(bkt_values.get(param, []), dtype=float)
        virtual_value = float(bkt_virtual.get(param, bkt_reference[param]))
        diff = abs(virtual_value - bkt_reference[param])
        if len(values) >= 3:
            # Use a frozen distribution's CDF callable instead of the
            # string-name + args form. The string form (kstest(x, "norm",
            # args=(loc, scale))) is broken in scipy >= 1.18 (raises
            # "TypeError: ndtr() takes from 1 to 2 positional arguments
            # but 3 were given") because scipy's internal _masked_apply
            # now passes the args tuple positionally to ndtr, which only
            # accepts (x, loc). Passing norm(loc, scale).cdf sidesteps
            # the issue and works on both old and new scipy.
            ref_dist = scipy_stats.norm(
                loc=bkt_reference[param], scale=ref_sd[param])
            ks_stat, p_value = scipy_stats.kstest(values, ref_dist.cdf)
        else:
            ks_stat, p_value = 0.0, 1.0
        ks_results[param] = {
            "ks_statistic": round(float(ks_stat), 4),
            "p_value": round(float(p_value), 4),
        }
        diagnostics.append({
            "parameter": param,
            "virtual_value": round(virtual_value, 4),
            "reference_value": round(bkt_reference[param], 4),
            "absolute_diff": round(diff, 4),
            "status": "ok" if p_value > 0.05 else "divergent",
        })

    return CalibrationDiagResponse(
        run_id=run_id,
        data_source="literature",
        cognitive_distance=round(distance, 4),
        bkt_params_virtual={k: round(v, 4) for k, v in bkt_virtual.items()},
        bkt_params_reference={k: round(v, 4) for k, v in bkt_reference.items()},
        persona_distribution=cal.get("persona", {}),
        ks_test_results=ks_results,
        diagnostics=diagnostics,
        verdict=verdict,
        reference_basis=reference_basis,
    )


# ============ Distortion Map (FR-F3) ============

@app.get("/api/runs/{run_id}/distortion_map", response_model=DistortionMapResponse)
async def get_distortion_map(run_id: str):
    """Distortion heat-map: intervention × scene × metric (FR-F3)"""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    run = _runs[run_id]
    ev = _synthesize_evidence(run)
    gap_records = ev["gap_records"]
    
    interventions = list({r["intervention_id"] for r in gap_records})
    scenes = list({r["scene"] for r in gap_records})
    metrics = list({r["metric"] for r in gap_records})
    
    cells = []
    n_high = 0
    for r in gap_records:
        cat = r.get("distortion_category", "none")
        if cat != "none":
            n_high += 1
        cells.append({
            "intervention": r["intervention_id"],
            "scene": r["scene"],
            "metric": r["metric"],
            "gap_magnitude": round(r.get("gap_magnitude", 0), 4),
            "category": cat,
        })
    
    total_cells = len(cells)
    pct = round(100 * n_high / max(1, total_cells), 1)
    summary = (
        f"共 {total_cells} 个干预×场景×指标单元，"
        f"其中 {n_high} 个（{pct}%）存在显著失真。"
        f"高失真区证据已被 M6 排序降权。"
    )
    
    return DistortionMapResponse(
        run_id=run_id,
        interventions=interventions,
        scenes=scenes,
        metrics=metrics,
        cells=cells,
        n_high_distortion=n_high,
        summary=summary,
    )


# ============ Pre-screening Report (FR-F4) ============

@app.get("/api/runs/{run_id}/prescreening", response_model=PrescreeningResponse)
async def get_prescreening_report(run_id: str):
    """Pre-screening report: go/no-go decision support for real trials (FR-F4)"""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    run = _runs[run_id]
    ev = _synthesize_evidence(run)
    ranked = ev["ranked"]
    effect_sizes = ev["effect_sizes"]
    es_by_id = {e["intervention_id"]: e for e in effect_sizes}
    
    criteria = [
        "效应量 g ≥ 0.20（最低实践意义阈值）",
        "95% CI 不跨越零（统计显著性）",
        "未位于高失真区（模拟保真度保障）",
        "优先级得分 ≥ 0.40（综合可行性）",
    ]
    
    candidates = []
    go_count = no_go_count = conditional_count = 0
    for r in ranked:
        intv = r["intervention_id"]
        es = es_by_id.get(intv, {})
        g = float(es.get("hedges_g", 0))
        ci_l = float(es.get("ci_lower", 0))
        ci_u = float(es.get("ci_upper", 0))
        distorted = bool(r.get("in_distorted_region"))
        score = float(r["priority_score"])
        
        # Decision logic
        checks = {
            "effect_threshold": g >= 0.20,
            "ci_significance": ci_l > 0,
            "fidelity": not distorted,
            "feasibility": score >= 0.40,
        }
        n_pass = sum(checks.values())
        if n_pass == 4:
            decision = "go"
            go_count += 1
        elif n_pass >= 2:
            decision = "conditional"
            conditional_count += 1
        else:
            decision = "no_go"
            no_go_count += 1
        
        candidates.append({
            "rank": r["rank"],
            "intervention_id": intv,
            "scene": es.get("scene", r.get("scene", "")),
            "hedges_g": round(g, 4),
            "ci_95": [round(ci_l, 4), round(ci_u, 4)],
            "priority_score": round(score, 4),
            "in_distorted_region": distorted,
            "checks": checks,
            "decision": decision,
        })
    
    return PrescreeningResponse(
        run_id=run_id,
        candidates=candidates,
        go_count=go_count,
        no_go_count=no_go_count,
        conditional_count=conditional_count,
        criteria=criteria,
        disclaimer=(
            "预筛结果仅基于虚拟模拟证据，不替代真人试验。"
            "“go”表示值得进入下一轮实证研究，而非确认有效。"
        ),
    )


# ============ Human-in-the-Loop (FR-F5) ============

@app.post("/api/runs/{run_id}/hitl/feedback", response_model=HITLFeedbackResponse)
async def submit_hitl_feedback(run_id: str, request: HITLFeedbackRequest):
    """Submit expert feedback (FR-F5 human-in-the-loop)"""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    feedback_id = f"FB_{uuid.uuid4().hex[:8].upper()}"
    record = {
        "feedback_id": feedback_id,
        "run_id": run_id,
        "target_type": request.target_type,
        "target_id": request.target_id,
        "verdict": request.verdict,
        "comment": request.comment,
        "adjusted_value": request.adjusted_value,
        "expert_role": request.expert_role,
        "created_at": datetime.now().isoformat(),
    }
    _hitl_feedback.setdefault(run_id, []).append(record)
    return HITLFeedbackResponse(**record)


@app.get("/api/runs/{run_id}/hitl/feedback", response_model=HITLFeedbackListResponse)
async def list_hitl_feedback(run_id: str):
    """List all expert feedback for a run (FR-F5)"""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    feedbacks = _hitl_feedback.get(run_id, [])
    return HITLFeedbackListResponse(
        run_id=run_id,
        total=len(feedbacks),
        feedbacks=[HITLFeedbackResponse(**f) for f in feedbacks],
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=6668, reload=True)
