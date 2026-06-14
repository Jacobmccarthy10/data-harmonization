"""POST /api/client/analyze — upload + analyze a messy client file."""
from __future__ import annotations

from dataclasses import asdict

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile

from .. import store
from ..services import client_normalizer, discover_recommender, file_reader, schema_detector

router = APIRouter(prefix="/api/client", tags=["client"])


def _jsonable(value):
    if isinstance(value, float) and pd.isna(value):
        return None
    if pd.isna(value) if not isinstance(value, (list, dict)) else False:
        return None
    return value


@router.post("/analyze")
async def analyze_client_file(file: UploadFile = File(...)):
    content = await file.read()
    try:
        loaded = file_reader.load_tabular_file(content, file.filename or "upload")
    except file_reader.FileReadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    det = schema_detector.detect_schema(loaded.df)
    norm = client_normalizer.normalize_client_file(loaded, det)
    profile = client_normalizer.build_profile(norm, det)
    quality = client_normalizer.build_quality_summary(norm, det)
    recommendation = discover_recommender.build_recommendation(profile, det, quality)

    preview_cols = [
        "source_row_id", "customer_standardized", "client_market_standardized",
        "market_level", "period_key", "period_start", "period_end",
        "upc_normalized", "item_description_raw", "brand_standardized",
        "category_standardized", "sales_value", "unit_value", "volume_value",
        "comparison_mode", "mapping_confidence", "record_status",
    ]
    preview = norm[preview_cols].head(25)
    preview_records = [
        {k: (None if pd.isna(v) else v) for k, v in row.items()}
        for _, row in preview.iterrows()
    ]

    analysis_id = store.analyses.put({
        "normalized": norm,
        "detection": det,
        "profile": profile,
        "quality": quality,
        "recommendation": recommendation,
        "file_name": loaded.file_name,
    })

    column_mappings = []
    for m in det.column_mappings:
        d = asdict(m)
        d.pop("metric", None)
        column_mappings.append(d)

    return {
        "analysis_id": analysis_id,
        "file_profile": {
            "file_name": loaded.file_name,
            "sheet_used": loaded.sheet_name,
            "sheet_names": loaded.sheet_names,
            "rows": int(len(loaded.df)),
            "columns": int(loaded.df.shape[1]),
            "notes": loaded.notes,
        },
        "schema_detection": {
            "structure_type": det.structure_type,
            "time_grain": profile.get("time_grain", det.time_grain),
            "business_type": det.business_type,
            "primary_metrics": det.primary_metrics,
            "wide_period_columns": len(det.wide_columns),
        },
        "column_mapping_summary": column_mappings,
        "structure_type": det.structure_type,
        "normalized_preview": preview_records,
        "quality_summary": quality,
        "comparison_mode": {
            "mode": det.comparison_mode,
            "reasons": det.comparison_reasons,
        },
        "metric_summary": {
            "business_type": det.business_type,
            "primary_metrics": det.primary_metrics,
            "metric_fields": [
                {"column": c, "kind": i.kind, "business_hint": i.business_hint,
                 "modifier": i.modifier}
                for c, i in det.metric_columns.items()
            ] or [
                {"column": w.column, "kind": w.metric.kind,
                 "business_hint": w.metric.business_hint, "modifier": w.metric.modifier}
                for w in det.wide_columns[:12]
            ],
        },
        "client_profile": profile,
        "discover_recommendation": recommendation,
    }
