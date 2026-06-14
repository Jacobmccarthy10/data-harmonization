"""POST /api/coverage/run — run the coverage comparison."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import store
from ..models import CoverageRunRequest
from ..services import coverage_engine

router = APIRouter(prefix="/api/coverage", tags=["coverage"])


@router.post("/run")
def run_coverage(req: CoverageRunRequest):
    analysis = store.analyses.get(req.analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Unknown analysis_id.")
    discover = store.discover_uploads.get(req.discover_id)
    if discover is None:
        raise HTTPException(status_code=404, detail="Unknown discover_id.")

    det = analysis["detection"]
    norm = analysis["normalized"]
    result = coverage_engine.run_coverage(
        norm, discover["normalized"], det.comparison_mode,
        analysis["profile"].get("time_grain", det.time_grain),
        user_crosswalk=discover.get("user_crosswalk"))

    coverage_id = store.coverage_runs.put({
        "coverage_df": result.coverage_df,
        "exceptions_df": result.exceptions_df,
        "analysis_id": req.analysis_id,
    })

    return {
        "coverage_id": coverage_id,
        "blocked": result.blocked,
        "blocked_reasons": result.blocked_reasons,
        "coverage_summary": result.coverage_summary,
        "kpis": result.kpis,
        "trend": result.trend,
        "exceptions": result.exceptions,
        "drilldown": result.drilldown,
    }
