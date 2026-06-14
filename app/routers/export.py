"""CSV export endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import store
from ..services.export_service import csv_response

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/normalized-client/{analysis_id}")
def export_normalized_client(analysis_id: str):
    analysis = store.analyses.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Unknown analysis_id.")
    return csv_response(analysis["normalized"], "normalized_client.csv")


@router.get("/coverage/{coverage_id}")
def export_coverage(coverage_id: str):
    run = store.coverage_runs.get(coverage_id)
    if run is None or run.get("coverage_df") is None:
        raise HTTPException(status_code=404, detail="Unknown coverage_id.")
    return csv_response(run["coverage_df"], "coverage_results.csv")


@router.get("/exceptions/{coverage_id}")
def export_exceptions(coverage_id: str):
    run = store.coverage_runs.get(coverage_id)
    if run is None or run.get("exceptions_df") is None:
        raise HTTPException(status_code=404, detail="Unknown coverage_id.")
    return csv_response(run["exceptions_df"], "exception_report.csv")
