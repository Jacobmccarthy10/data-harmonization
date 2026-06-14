"""POST /api/discover/validate — upload + validate clean Discover export(s).

Discover caps exports around 2.5M cells, so a large pull may arrive split into
2-3 files. Multiple files are validated individually and stitched into one
dataset.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .. import store
from ..services import discover_validator, file_reader

router = APIRouter(prefix="/api/discover", tags=["discover"])


@router.post("/validate")
async def validate_discover(
    analysis_id: str = Form(...),
    files: List[UploadFile] = File(...),
    crosswalk_file: UploadFile = File(None),
):
    if store.analyses.get(analysis_id) is None:
        raise HTTPException(status_code=404, detail="Unknown analysis_id. Analyze a client file first.")
    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one Discover export.")

    loaded_files = []
    for f in files:
        content = await f.read()
        try:
            loaded_files.append(
                file_reader.load_tabular_file(content, f.filename or "discover_upload"))
        except file_reader.FileReadError as exc:
            raise HTTPException(
                status_code=400, detail=f"{f.filename}: {exc}") from exc

    result = discover_validator.validate_discover_files(loaded_files)

    # Optional user-supplied UPC crosswalk file.
    user_crosswalk_df = None
    if crosswalk_file is not None and crosswalk_file.filename:
        cw_content = await crosswalk_file.read()
        try:
            cw_loaded = file_reader.load_tabular_file(
                cw_content, crosswalk_file.filename)
            user_crosswalk_df = cw_loaded.df
        except file_reader.FileReadError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Crosswalk file {crosswalk_file.filename}: {exc}") from exc

    discover_id = None
    if result.valid:
        discover_id = store.discover_uploads.put({
            "normalized": result.normalized,
            "analysis_id": analysis_id,
            "file_name": ", ".join(lf.file_name for lf in loaded_files),
            "user_crosswalk": user_crosswalk_df,
        })

    notes = [n for lf in loaded_files for n in lf.notes]
    crosswalk_rows = (int(len(user_crosswalk_df))
                      if user_crosswalk_df is not None else 0)
    return {
        "discover_id": discover_id,
        "valid": result.valid,
        "user_crosswalk_rows": crosswalk_rows,
        "matched_fields": result.matched_fields,
        "missing_required_fields": result.missing_required_fields,
        "warnings": result.warnings,
        "row_count": result.row_count,
        "period_start": result.period_start,
        "period_end": result.period_end,
        "preview": result.preview,
        "files": result.files,
        "file_profile": {
            "file_name": ", ".join(lf.file_name for lf in loaded_files),
            "sheet_used": loaded_files[0].sheet_name if len(loaded_files) == 1 else None,
            "notes": notes,
        },
    }
