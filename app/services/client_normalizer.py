"""Normalize a detected client file into the standard internal schema.

One output row per (source row x period). Wide files are unpivoted; long and
mixed files are parsed row by row. Fields that do not exist in the source are
left null.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional

import pandas as pd

from ..utils.dates import (
    ParsedPeriod,
    infer_grain_from_dates,
    parse_fiscal_pair,
    parse_period_value,
    weekly_bounds,
)
from ..utils.text import (
    clean_label,
    is_total_like_market,
    normalize_upc,
    parse_description_tokens,
    upc_match_key,
)
from .file_reader import LoadedFile
from .schema_detector import SchemaDetection

NORMALIZED_COLUMNS = [
    "source_row_id", "source_file_name", "source_sheet_name",
    "customer_raw", "customer_standardized",
    "client_market_raw", "client_market_standardized", "market_level",
    "period_raw", "period_start", "period_end", "period_key", "time_grain",
    "product_key_raw", "upc_raw", "upc_normalized", "upc_key",
    "item_id_raw", "item_description_raw",
    "brand_raw", "brand_standardized",
    "manufacturer_raw", "manufacturer_standardized",
    "category_raw", "category_standardized",
    "metric_type_raw", "metric_name_raw", "metric_value",
    "sales_value", "unit_value", "volume_value",
    "comparison_mode", "mapping_confidence", "record_status", "exception_reason",
]


def _standardize(value: object) -> Optional[str]:
    s = clean_label(value)
    if s is None:
        return None
    # Title-case fully-uppercase/lowercase labels, but keep short acronyms (CSD, RTE).
    if (s.isupper() and len(s) > 4) or s.islower():
        return s.title()
    return s


def _row_period(row: pd.Series, det: SchemaDetection) -> Optional[ParsedPeriod]:
    for concept in ("week_end_date", "period", "month"):
        col = det.concept_columns.get(concept)
        if col is not None and col in row.index:
            p = parse_period_value(row[col])
            if p is not None:
                return p
    fy = det.concept_columns.get("fiscal_year")
    fm = det.concept_columns.get("fiscal_month")
    if fy and fm and fy in row.index and fm in row.index:
        return parse_fiscal_pair(row[fy], row[fm])
    if fm and fm in row.index:
        p = parse_period_value(row[fm])
        if p is not None:
            return p
    return None


def _num(value: object) -> Optional[float]:
    v = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(v) else float(v)


def normalize_client_file(loaded: LoadedFile, det: SchemaDetection) -> pd.DataFrame:
    df = loaded.df
    cc = det.concept_columns

    def col(concept: str) -> Optional[str]:
        c = cc.get(concept)
        return c if c is not None and c in df.columns else None

    base_conf = _base_confidence(det)

    records: List[dict] = []
    metric_kind_cols: Dict[str, str] = {}  # long-format: kind -> column
    if not det.wide_columns:
        ranked: Dict[str, List] = defaultdict(list)
        for c, info in det.metric_columns.items():
            if info.kind in ("sales", "unit", "volume"):
                ranked[info.kind].append((info.rank, c, info))
        for kind, lst in ranked.items():
            lst.sort(key=lambda t: -t[0])
            metric_kind_cols[kind] = lst[0][1]

    # Wide: group value columns by period, pick the best column per metric kind.
    wide_groups: Dict[tuple, Dict[str, object]] = {}
    if det.wide_columns:
        by_period: Dict[tuple, list] = defaultdict(list)
        for w in det.wide_columns:
            by_period[(w.period_start, w.period_end, w.grain)].append(w)
        for key, cols in by_period.items():
            picks: Dict[str, object] = {}
            for kind in ("sales", "unit", "volume"):
                kind_cols = sorted((c for c in cols if c.metric.kind == kind),
                                   key=lambda c: -c.metric.rank)
                if kind_cols:
                    picks[kind] = kind_cols[0]
            wide_groups[key] = picks

    for idx, row in df.iterrows():
        dims = {
            "customer_raw": clean_label(row[col("customer")]) if col("customer") else None,
            "client_market_raw": clean_label(row[col("client_market")]) if col("client_market") else None,
            "upc_raw": clean_label(row[col("upc")]) if col("upc") else None,
            "item_id_raw": clean_label(row[col("item_id")]) if col("item_id") else None,
            "item_description_raw": clean_label(row[col("item_description")]) if col("item_description") else None,
            "brand_raw": clean_label(row[col("brand")]) if col("brand") else None,
            "manufacturer_raw": clean_label(row[col("manufacturer")]) if col("manufacturer") else None,
            "category_raw": clean_label(row[col("category")]) if col("category") else None,
        }

        def make_record(period: Optional[ParsedPeriod], period_raw: Optional[str],
                        sales: Optional[float], units: Optional[float],
                        volume: Optional[float], metric_names: List[str]) -> dict:
            rec = dict(dims)
            rec["source_row_id"] = int(idx)
            rec["source_file_name"] = loaded.file_name
            rec["source_sheet_name"] = loaded.sheet_name
            rec["customer_standardized"] = _standardize(dims["customer_raw"])
            rec["client_market_standardized"] = _standardize(dims["client_market_raw"])
            rec["market_level"] = (
                "total" if is_total_like_market(dims["client_market_raw"]) else "detail"
            ) if dims["client_market_raw"] else None
            rec["brand_standardized"] = _standardize(dims["brand_raw"])
            rec["manufacturer_standardized"] = _standardize(dims["manufacturer_raw"])
            rec["category_standardized"] = _standardize(dims["category_raw"])
            rec["upc_normalized"] = normalize_upc(dims["upc_raw"])
            rec["upc_key"] = upc_match_key(dims["upc_raw"])
            rec["product_key_raw"] = dims["upc_raw"] or dims["item_id_raw"]
            rec["period_raw"] = period_raw
            rec["period_start"] = period.period_start.isoformat() if period else None
            rec["period_end"] = period.period_end.isoformat() if period else None
            rec["time_grain"] = None  # filled after grain resolution
            rec["period_key"] = None
            rec["sales_value"] = sales
            rec["unit_value"] = units
            rec["volume_value"] = volume
            rec["metric_name_raw"] = ", ".join(metric_names) if metric_names else None
            rec["metric_type_raw"] = det.business_type
            rec["metric_value"] = sales if sales is not None else (units if units is not None else volume)
            rec["comparison_mode"] = det.comparison_mode

            conf = base_conf
            status, reason = "normalized", None
            if period is None:
                status, reason = "needs_review", "period_unparsed"
                conf -= 0.3
            if sales is None and units is None and volume is None:
                status, reason = "needs_review", (reason + "; no_metric_values" if reason else "no_metric_values")
                conf -= 0.2
            if rec["upc_key"] is None and dims["upc_raw"]:
                conf -= 0.1
            rec["mapping_confidence"] = round(max(conf, 0.05), 2)
            rec["record_status"] = status
            rec["exception_reason"] = reason
            return rec

        if det.wide_columns:
            for (p_start, p_end, grain), picks in sorted(wide_groups.items()):
                period = ParsedPeriod(pd.Timestamp(p_start).date(), pd.Timestamp(p_end).date(), grain, p_start)
                sales = _num(row[picks["sales"].column]) if "sales" in picks else None
                units = _num(row[picks["unit"].column]) if "unit" in picks else None
                volume = _num(row[picks["volume"].column]) if "volume" in picks else None
                names = [p.column for p in picks.values()]
                records.append(make_record(period, p_start, sales, units, volume, names))
        else:
            period = _row_period(row, det)
            period_raw = None
            for concept in ("week_end_date", "period", "month", "fiscal_month"):
                c = col(concept)
                if c is not None and pd.notna(row[c]):
                    period_raw = str(row[c])
                    break
            sales = _num(row[metric_kind_cols["sales"]]) if "sales" in metric_kind_cols else None
            units = _num(row[metric_kind_cols["unit"]]) if "unit" in metric_kind_cols else None
            volume = _num(row[metric_kind_cols["volume"]]) if "volume" in metric_kind_cols else None
            records.append(make_record(period, period_raw, sales, units, volume,
                                       list(metric_kind_cols.values())))

    out = pd.DataFrame.from_records(records)

    # Resolve the file-level time grain from parsed periods, then period keys.
    grain = det.time_grain
    parsed_ends = pd.to_datetime(out["period_end"].dropna().unique(), errors="coerce")
    parsed_ends = [t.date() for t in parsed_ends if pd.notna(t)]
    if grain == "unknown" and parsed_ends:
        grain = infer_grain_from_dates(parsed_ends)
    out["time_grain"] = grain

    def period_key(rec_start, rec_end):
        if rec_end is None or (isinstance(rec_end, float) and pd.isna(rec_end)):
            return None
        end = pd.Timestamp(rec_end).date()
        if grain == "monthly":
            return f"{end.year:04d}-{end.month:02d}"
        return end.isoformat()

    out["period_key"] = [period_key(s, e) for s, e in zip(out["period_start"], out["period_end"])]

    # Weekly grain: a bare date is a week-ending date; backfill period_start.
    if grain == "weekly":
        def fix_start(s, e):
            if e is None or (isinstance(e, float) and pd.isna(e)):
                return s
            end = pd.Timestamp(e).date()
            start = pd.Timestamp(s).date() if s and not (isinstance(s, float) and pd.isna(s)) else end
            if start == end:
                return weekly_bounds(end)[0].isoformat()
            return s
        out["period_start"] = [fix_start(s, e) for s, e in zip(out["period_start"], out["period_end"])]

    for c in NORMALIZED_COLUMNS:
        if c not in out.columns:
            out[c] = None
    return out[NORMALIZED_COLUMNS]


def _base_confidence(det: SchemaDetection) -> float:
    keys = [k for k in ("customer", "client_market", "upc", "item_description",
                        "week_end_date", "period", "month", "fiscal_month")
            if k in det.concept_confidence]
    if not keys:
        return 0.4
    avg = sum(det.concept_confidence[k] for k in keys) / len(keys)
    return min(0.95, 0.55 + 0.45 * avg)


# ---------------------------------------------------------------------------
# Profile + quality summaries built on the normalized frame
# ---------------------------------------------------------------------------

def build_profile(norm: pd.DataFrame, det: SchemaDetection) -> dict:
    """Business-facing summary of what was detected, for the read-only review."""
    def top_values(col: str, limit: int = 10) -> List[dict]:
        s = norm[col].dropna()
        if s.empty:
            return []
        counts = s.value_counts().head(limit)
        return [{"value": str(v), "rows": int(c)} for v, c in counts.items()]

    markets = []
    if norm["client_market_standardized"].notna().any():
        counts = norm["client_market_standardized"].value_counts()
        for value, c in counts.items():
            markets.append({
                "value": str(value),
                "rows": int(c),
                "total_like": is_total_like_market(value),
            })

    desc_tokens = []
    descs = norm["item_description_raw"].dropna().unique()[:200]
    for d in descs:
        t = parse_description_tokens(d)
        if any(v is not None for v in t.values()):
            desc_tokens.append(t)
    pack_counts = sorted({t["pack_count"] for t in desc_tokens if t["pack_count"]})
    sizes = sorted({f"{t['size']:g}{t['size_unit']}" for t in desc_tokens if t["size"]})

    period_start = norm["period_start"].dropna().min()
    period_end = norm["period_end"].dropna().max()

    customer = None
    if norm["customer_standardized"].notna().any():
        customer = str(norm["customer_standardized"].mode().iloc[0])

    return {
        "customer": customer,
        "customer_values": top_values("customer_standardized", 5),
        "markets": markets[:25],
        "manufacturers": top_values("manufacturer_standardized", 8),
        "brands": top_values("brand_standardized", 12),
        "categories": top_values("category_standardized", 12),
        "period_start": period_start,
        "period_end": period_end,
        "time_grain": str(norm["time_grain"].iloc[0]) if len(norm) else "unknown",
        "product_identifier_fields": [
            det.concept_columns[c] for c in ("upc", "item_id") if c in det.concept_columns],
        "description_fields": [
            det.concept_columns[c] for c in ("item_description",) if c in det.concept_columns],
        "distinct_products": int(norm["upc_key"].nunique()) or int(norm["item_id_raw"].nunique()),
        "description_hints": {
            "pack_counts": pack_counts[:10],
            "sizes": sizes[:12],
        },
    }


def build_quality_summary(norm: pd.DataFrame, det: SchemaDetection) -> dict:
    total = len(norm)
    warnings: List[str] = list(det.warnings)

    period_ok = int(norm["period_key"].notna().sum())
    upc_present = int(norm["upc_raw"].notna().sum())
    upc_ok = int(norm["upc_key"].notna().sum())
    sales_ok = int(norm["sales_value"].notna().sum())
    needs_review = int((norm["record_status"] == "needs_review").sum())

    levels = set(norm["market_level"].dropna().unique())
    if levels == {"total", "detail"}:
        warnings.append(
            "File contains both total-level and detail-level market rows. Sales and "
            "unit KPIs use the total level to avoid double counting.")
    if upc_present and upc_ok < upc_present:
        warnings.append(
            f"{upc_present - upc_ok} rows have product identifiers that do not "
            "normalize to a UPC/GTIN pattern.")
    if period_ok < total:
        warnings.append(f"{total - period_ok} rows have periods that could not be parsed.")

    return {
        "total_rows": total,
        "period_parse_rate": round(period_ok / total, 3) if total else 0,
        "upc_valid_rate": round(upc_ok / upc_present, 3) if upc_present else None,
        "sales_present_rate": round(sales_ok / total, 3) if total else 0,
        "rows_needing_review": needs_review,
        "distinct_periods": int(norm["period_key"].nunique()),
        "distinct_markets": int(norm["client_market_standardized"].nunique()),
        "distinct_products": int(norm["upc_key"].nunique()),
        "warnings": warnings,
    }
