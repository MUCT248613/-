with open('src/api/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Insert triad_network endpoint after network evolution endpoint
marker = '''    return NetworkEvolutionResponse(
        snapshots=snapshots,
        metrics_trajectory={
            "density": [s["density"] for s in snapshots],
            "avg_clustering": [s["avg_clustering"] for s in snapshots]
        }
    )


# ============ Counterfactual ============'''

new_endpoint = '''    return NetworkEvolutionResponse(
        snapshots=snapshots,
        metrics_trajectory={
            "density": [s["density"] for s in snapshots],
            "avg_clustering": [s["avg_clustering"] for s in snapshots]
        }
    )


# ============ Triad Network (Student-Teacher-Parent) ============

@app.get("/api/runs/{run_id}/triad_network")
async def get_triad_network(run_id: str, intervention_id: Optional[str] = None):
    """Return the tri-partite student-teacher-parent relationship graph.

    Optionally filter edges by intervention_id to show only the relationships
    through which a specific intervention was delivered.
    """
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    triad = _runs[run_id].get("triad_network")
    if not triad:
        raise HTTPException(status_code=404, detail="Triad network not available for this run")

    result = {
        "run_id": run_id,
        "nodes": triad["nodes"],
        "edges": triad["edges"],
        "teacher_influence": triad.get("teacher_influence", {}),
        "parent_trajectory": triad.get("parent_trajectory", {}),
        "summary": {
            "n_students": sum(1 for n in triad["nodes"] if n["type"] == "student"),
            "n_teachers": sum(1 for n in triad["nodes"] if n["type"] == "teacher"),
            "n_parents": sum(1 for n in triad["nodes"] if n["type"] == "parent"),
            "n_edges": len(triad["edges"]),
            "edge_types": {
                "student-teacher": sum(1 for e in triad["edges"] if e["type"] == "student-teacher"),
                "student-parent": sum(1 for e in triad["edges"] if e["type"] == "student-parent"),
                "student-student": sum(1 for e in triad["edges"] if e["type"] == "student-student"),
            },
        },
    }

    if intervention_id:
        affected = triad.get("intervention_edges", {}).get(intervention_id, [])
        result["filtered_edges"] = affected
        result["filter_intervention_id"] = intervention_id

    return result


# ============ Counterfactual ============'''

content = content.replace(marker, new_endpoint)

with open('src/api/main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("OK: main.py patched with triad_network endpoint")
