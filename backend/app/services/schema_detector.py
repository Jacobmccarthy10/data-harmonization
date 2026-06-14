"""Generic schema detection for messy client files.

Nothing here is tied to specific retailers, manufacturers, categories,
filenames, or exact column names. Detection is layered:

1. name patterns (aliases / regex on normalized headers)
2. sample value profiling (date parse rate, UPC-like rate, numeric rate,
   cardinality)
3. confidence scoring combining both
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd

from ..utils.dates import (
    infer_grain_from_dates,
    parse_period_value,
    parse_wide_header,
)
from ..utils.text import (
    is_total_like_market,
    looks_like_upc_series,
    norm_header,
)

SAMPLE_SIZE = 250

# ---------------------------------------------------------------------------
# Metric label classification
# ---------------------------------------------------------------------------

_AUX_PATTERNS = [
    (r"\b(promo|promotion|promotional|allowance|discount|coupon|rebate|markdown|trade)\b",
     "promotional / allowance metric"),
    (r"\b(inventory|on hand|oh|in transit|in stock|stock)\b", "inventory metric"),
    (r"\b(store|door|outlet)s?\b", "store count metric"),
    (r"\b(acv|distribution|distr|tdp|pct|percent|share|price|avg|average)\b",
     "rate / pricing metric"),
]
_VOLUME_RE = re.compile(r"\b(cases?|ce|vol|volume|barrels?|gallons?|liters?|litres?|tonnage|lbs|pounds)\b")
_UNIT_RE = re.compile(r"\b(units?|qty|quantity|each(es)?)\b")
_SALES_RE = re.compile(r"(\$|\b(dollars?|sales?|rev|revenue|value|amount)\b)")
_POS_HINT_RE = re.compile(r"\b(pos|retail|scan|scanned|consumption|consumer|till|sell ?out)\b")
_SHIP_HINT_RE = re.compile(r"\b(ship|shipped|shipment|invoice|invoiced|wholesale|depletion|sell ?in|deliver(ed|y)?)\b")


@dataclass
class MetricInfo:
    label: str
    kind: str            # 'sales' | 'unit' | 'volume' | 'other'
    business_hint: Optional[str] = None   # 'pos' | 'shipment' | None
    modifier: Optional[str] = None        # 'net', 'gross', 'equivalized', aux note
    rank: float = 0.0


def classify_metric_label(label: object) -> MetricInfo:
    """Classify a metric label (column header or wide-header residual)."""
    n = norm_header(label)
    hint = None
    if _POS_HINT_RE.search(n):
        hint = "pos"
    elif _SHIP_HINT_RE.search(n):
        hint = "shipment"

    for pattern, note in _AUX_PATTERNS:
        if re.search(pattern, n):
            return MetricInfo(str(label), "other", hint, note)

    if _VOLUME_RE.search(n):
        mod = "equivalized" if re.search(r"\b(eq|equiv|equivalized)\b", n) else None
        if hint is None and re.search(r"\b(cases?|ce)\b", n):
            hint = "shipment"
        return MetricInfo(str(label), "volume", hint, mod, rank=1.0)
    if _UNIT_RE.search(n):
        mod = "equivalized" if re.search(r"\b(eq|equiv|equivalized)\b", n) else None
        return MetricInfo(str(label), "unit", hint, mod, rank=1.0)
    if _SALES_RE.search(n):
        if re.search(r"\bnet\b", n):
            mod, rank = "net", 1.2
            if hint is None:
                hint = "shipment"
        elif re.search(r"\bgross\b", n):
            mod, rank = "gross", 0.8
            if hint is None:
                hint = "shipment"
        else:
            mod, rank = None, 1.0
        return MetricInfo(str(label), "sales", hint, mod, rank=rank)
    return MetricInfo(str(label), "other", hint, "unrecognized metric")


# ---------------------------------------------------------------------------
# Dimension concept patterns
# ---------------------------------------------------------------------------

# (concept, regex on normalized header, base weight)
_CONCEPT_PATTERNS: List[Tuple[str, str, float]] = [
    ("customer", r"\b(customer|retailer|retail partner|banner|key account|chain)\b", 0.92),
    ("customer", r"\baccount\b", 0.55),
    ("client_market", r"\b(market|region|territory|zone|district|division|dma|geography|geo)\b", 0.88),
    ("client_market", r"\b(planning|sales) (area|region|zone)\b", 0.90),
    ("client_market", r"\barea\b", 0.60),
    ("client_market", r"\b(distributor|network|channel)\b", 0.45),
    ("fiscal_year", r"\bfiscal (year|yr)\b|\bfy\b", 0.92),
    ("fiscal_month", r"\bfiscal (period|month|mo|wk|week|p)\b", 0.92),
    ("week_end_date", r"\bweek\b.*\bend", 0.95),
    ("week_end_date", r"\b(we|wk)\b.*\b(date|label)\b", 0.80),
    ("week_end_date", r"\bweek\b", 0.70),
    ("month", r"\bmonth\b", 0.80),
    ("period", r"\b(period|date|day)\b", 0.62),
    ("upc", r"\b(upc|gtin|barcode|bar code|ean|plu)\b", 0.95),
    ("item_id", r"\b(item|product|sku|material|article) ?(id|number|num|no|code|key|#)(\b|$|\s)", 0.88),
    ("item_id", r"\bsku\b", 0.70),
    ("item_description", r"\b(desc|description)\b", 0.92),
    ("item_description", r"\b(item|product) ?(text|name|long desc)\b", 0.85),
    ("brand", r"\bbrand\b", 0.92),
    ("manufacturer", r"\b(manufacturer|mfr|mfg|supplier|vendor|maker)\b", 0.92),
    ("manufacturer", r"\b(business unit|parent company|company)\b", 0.65),
    ("category", r"\b(category|segment|universe|department|dept|subcategory|sub category|aisle|class)\b", 0.88),
    ("pack_size_text", r"\b(pack|size|config|configuration|uom|unit of measure|package)\b", 0.70),
]

_DATE_CONCEPTS = {"period", "week_end_date", "month"}
_PRODUCT_KEY_CONCEPTS = {"upc", "item_id"}
_IGNORE_RE = re.compile(r"\b(source|extract|file|batch|load|row id|record id|notes?|comment)\b")


@dataclass
class ColumnMapping:
    source_column: str
    concept: Optional[str]
    role: str               # 'mapped' | 'alternate' | 'metric' | 'auxiliary_metric' | 'wide_period' | 'ignored' | 'unmapped'
    confidence: float
    evidence: str
    sample_values: List[str] = field(default_factory=list)
    metric: Optional[MetricInfo] = None


@dataclass
class WidePeriodColumn:
    column: str
    period_start: str
    period_end: str
    grain: str
    metric: MetricInfo


@dataclass
class SchemaDetection:
    structure_type: str = "unknown"
    time_grain: str = "unknown"
    business_type: str = "unknown"
    comparison_mode: str = "not_comparable"
    comparison_reasons: List[str] = field(default_factory=list)
    column_mappings: List[ColumnMapping] = field(default_factory=list)
    concept_columns: Dict[str, str] = field(default_factory=dict)
    concept_confidence: Dict[str, float] = field(default_factory=dict)
    wide_columns: List[WidePeriodColumn] = field(default_factory=list)
    metric_columns: Dict[str, MetricInfo] = field(default_factory=dict)
    primary_metrics: Dict[str, str] = field(default_factory=dict)  # kind -> column/label
    warnings: List[str] = field(default_factory=list)


def _sample(series: pd.Series) -> pd.Series:
    s = series.dropna()
    if len(s) > SAMPLE_SIZE:
        s = s.sample(SAMPLE_SIZE, random_state=7)
    return s


def _numeric_rate(series: pd.Series) -> float:
    s = _sample(series)
    if s.empty:
        return 0.0
    return float(pd.to_numeric(s, errors="coerce").notna().mean())


def _date_parse_rate(series: pd.Series) -> float:
    s = _sample(series)
    if s.empty:
        return 0.0
    hits = sum(1 for v in s if parse_period_value(v) is not None)
    return hits / len(s)


def detect_schema(df: pd.DataFrame) -> SchemaDetection:
    det = SchemaDetection()
    columns = [str(c) for c in df.columns]

    # ------------------------------------------------------------------
    # Pass 1: wide period columns (period embedded in the header)
    # ------------------------------------------------------------------
    wide_candidates: Dict[str, WidePeriodColumn] = {}
    for col in columns:
        parsed = parse_wide_header(col)
        if parsed is None:
            continue
        period, residual = parsed
        if _numeric_rate(df[col]) < 0.6:
            continue  # period-looking header but not a value column
        metric = classify_metric_label(residual) if residual else MetricInfo(col, "sales", None, "unlabeled wide column")
        wide_candidates[col] = WidePeriodColumn(
            column=col,
            period_start=period.period_start.isoformat(),
            period_end=period.period_end.isoformat(),
            grain=period.grain,
            metric=metric,
        )
    if len(wide_candidates) >= 2:
        det.wide_columns = list(wide_candidates.values())

    # ------------------------------------------------------------------
    # Pass 2: dimension concepts for remaining columns
    # ------------------------------------------------------------------
    remaining = [c for c in columns if c not in {w.column for w in det.wide_columns}]
    candidates: List[Tuple[str, str, float, str]] = []  # (column, concept, score, evidence)

    for col in remaining:
        n = norm_header(col)
        series = df[col]
        numeric_rate = _numeric_rate(series)
        non_null = float(series.notna().mean())
        nunique = int(series.nunique())

        if _IGNORE_RE.search(n):
            det.column_mappings.append(ColumnMapping(
                col, None, "ignored", 0.3, "matches source/extract metadata pattern",
                _preview_values(series)))
            continue

        col_scores: Dict[str, Tuple[float, str]] = {}
        for concept, pattern, weight in _CONCEPT_PATTERNS:
            if re.search(pattern, n):
                score = weight
                evidence = [f"header matches /{pattern}/"]
                if concept in _DATE_CONCEPTS or concept == "week_end_date":
                    rate = _date_parse_rate(series)
                    if rate > 0.5:
                        score += 0.25 * rate
                        evidence.append(f"{rate:.0%} of sampled values parse as periods")
                    elif numeric_rate < 0.5 and rate < 0.2:
                        score -= 0.3
                elif concept == "upc":
                    rate = looks_like_upc_series(_sample(series))
                    score += 0.25 * rate
                    if rate > 0.5:
                        evidence.append(f"{rate:.0%} of sampled values are UPC-like")
                elif concept in ("customer", "client_market", "category", "brand",
                                 "manufacturer"):
                    if numeric_rate < 0.5 and nunique <= max(50, len(df) // 4):
                        score += 0.05
                        evidence.append(f"{nunique} distinct text values")
                    elif numeric_rate > 0.9:
                        score -= 0.4
                elif concept in ("fiscal_year", "fiscal_month"):
                    if numeric_rate > 0.9 or _date_parse_rate(series) > 0.5:
                        score += 0.05
                score *= 0.4 + 0.6 * non_null
                if score > col_scores.get(concept, (0.0, ""))[0]:
                    col_scores[concept] = (score, "; ".join(evidence))

        # Value-only fallbacks when no header pattern hit.
        if not col_scores:
            upc_rate = looks_like_upc_series(_sample(series))
            if upc_rate > 0.8:
                col_scores["upc"] = (0.55 + 0.25 * upc_rate,
                                     f"no header match, but {upc_rate:.0%} of values are UPC-like")
            else:
                date_rate = _date_parse_rate(series)
                if date_rate > 0.8 and numeric_rate < 0.5:
                    col_scores["period"] = (0.5 + 0.25 * date_rate,
                                            f"no header match, but {date_rate:.0%} of values parse as dates")

        for concept, (score, evidence) in col_scores.items():
            candidates.append((col, concept, min(score, 0.98), evidence))

    # Resolve: highest score wins each concept; one concept per column.
    candidates.sort(key=lambda t: t[2], reverse=True)
    assigned_cols: set = set()
    for col, concept, score, evidence in candidates:
        if concept in det.concept_columns or col in assigned_cols:
            continue
        if score < 0.45:
            continue
        det.concept_columns[concept] = col
        det.concept_confidence[concept] = round(score, 2)
        assigned_cols.add(col)
        det.column_mappings.append(ColumnMapping(
            col, concept, "mapped", round(score, 2), evidence, _preview_values(df[col])))

    # Alternates: columns that matched a concept already claimed by another column.
    seen_alt = set()
    for col, concept, score, evidence in candidates:
        if col in assigned_cols or col in seen_alt or score < 0.45:
            continue
        seen_alt.add(col)
        det.column_mappings.append(ColumnMapping(
            col, concept, "alternate", round(score, 2),
            f"also matches '{concept}' (claimed by '{det.concept_columns.get(concept)}')",
            _preview_values(df[col])))

    # ------------------------------------------------------------------
    # Pass 3: metric columns (numeric, unclaimed, long-format)
    # ------------------------------------------------------------------
    claimed = assigned_cols | seen_alt | {w.column for w in det.wide_columns} | {
        m.source_column for m in det.column_mappings if m.role == "ignored"}
    for col in remaining:
        if col in claimed:
            continue
        numeric_rate = _numeric_rate(df[col])
        if numeric_rate >= 0.7:
            info = classify_metric_label(col)
            det.metric_columns[col] = info
            role = "metric" if info.kind in ("sales", "unit", "volume") else "auxiliary_metric"
            det.column_mappings.append(ColumnMapping(
                col, f"{info.kind}_value" if role == "metric" else None, role,
                0.85 if role == "metric" else 0.6,
                _metric_evidence(info), _preview_values(df[col]), metric=info))
        else:
            det.column_mappings.append(ColumnMapping(
                col, None, "unmapped", 0.0, "no concept or metric pattern matched",
                _preview_values(df[col])))

    for w in det.wide_columns:
        det.column_mappings.append(ColumnMapping(
            w.column, f"{w.metric.kind}_value" if w.metric.kind != "other" else None,
            "wide_period", 0.9,
            f"header embeds period {w.period_start[:7]} + metric '{w.metric.label}' ({_metric_evidence(w.metric)})",
            _preview_values(df[w.column]), metric=w.metric))

    # ------------------------------------------------------------------
    # Primary metric per kind
    # ------------------------------------------------------------------
    if det.wide_columns:
        labels: Dict[str, MetricInfo] = {}
        for w in det.wide_columns:
            key = norm_header(w.metric.label)
            labels.setdefault(key, w.metric)
        pool = list(labels.values())
    else:
        pool = list(det.metric_columns.values())
    for kind in ("sales", "unit", "volume"):
        ranked = sorted((m for m in pool if m.kind == kind), key=lambda m: -m.rank)
        if ranked:
            det.primary_metrics[kind] = ranked[0].label

    # ------------------------------------------------------------------
    # Structure type
    # ------------------------------------------------------------------
    period_concepts = [c for c in ("week_end_date", "month", "period") if c in det.concept_columns]
    fiscal = [c for c in ("fiscal_year", "fiscal_month") if c in det.concept_columns]
    if det.wide_columns:
        det.structure_type = "wide"
    elif period_concepts and det.metric_columns:
        det.structure_type = "mixed" if (fiscal or len(period_concepts) > 1) else "long"
    elif fiscal and det.metric_columns:
        det.structure_type = "mixed"
    elif det.metric_columns or period_concepts:
        det.structure_type = "unknown"

    # ------------------------------------------------------------------
    # Time grain
    # ------------------------------------------------------------------
    det.time_grain = _detect_time_grain(df, det)

    # ------------------------------------------------------------------
    # Business type + comparison mode
    # ------------------------------------------------------------------
    det.business_type, det.comparison_mode, det.comparison_reasons = _detect_comparison(df, det)
    return det


def _preview_values(series: pd.Series, n: int = 4) -> List[str]:
    return [str(v)[:60] for v in series.dropna().unique()[:n]]


def _metric_evidence(info: MetricInfo) -> str:
    bits = [f"classified as {info.kind} metric"]
    if info.business_hint:
        bits.append(f"{info.business_hint}-style")
    if info.modifier:
        bits.append(info.modifier)
    return ", ".join(bits)


def _detect_time_grain(df: pd.DataFrame, det: SchemaDetection) -> str:
    if det.wide_columns:
        grains = {w.grain for w in det.wide_columns}
        for g in ("monthly", "weekly"):
            if g in grains:
                return g
        dates = [pd.Timestamp(w.period_end).date() for w in det.wide_columns]
        return infer_grain_from_dates(dates)

    for concept in ("week_end_date", "period", "month"):
        col = det.concept_columns.get(concept)
        if not col:
            continue
        parsed = [parse_period_value(v) for v in df[col].dropna().unique()[:300]]
        parsed = [p for p in parsed if p is not None]
        if not parsed:
            continue
        grains = pd.Series([p.grain for p in parsed])
        top = grains.mode().iloc[0]
        if top == "monthly":
            return "monthly"
        if top == "weekly":
            return "weekly"
        # plain dates: infer from spacing
        inferred = infer_grain_from_dates([p.period_end for p in parsed])
        if inferred != "unknown":
            return inferred
    if "fiscal_month" in det.concept_columns:
        return "monthly"
    if "month" in det.concept_columns:
        return "monthly"
    return "unknown"


def _detect_comparison(df: pd.DataFrame, det: SchemaDetection) -> Tuple[str, str, List[str]]:
    reasons: List[str] = []
    pos_votes = 0.0
    ship_votes = 0.0

    metric_infos = ([w.metric for w in det.wide_columns] or list(det.metric_columns.values()))
    for info in metric_infos:
        if info.business_hint == "pos":
            pos_votes += 2
        elif info.business_hint == "shipment":
            ship_votes += 2
        if info.kind == "volume" and re.search(r"\b(cases?|ce)\b", norm_header(info.label)):
            ship_votes += 1
    for col in df.columns:
        n = norm_header(col)
        if re.search(r"\b(supplier|distributor|warehouse|dc)\b", n):
            ship_votes += 1
        if re.search(r"\b(pos|store count|scan)\b", n):
            pos_votes += 1
        if re.search(r"\b(ship|shipment|shipped)\b", n):
            ship_votes += 1

    has_period = bool(det.wide_columns) or any(
        c in det.concept_columns for c in ("week_end_date", "month", "period", "fiscal_month"))
    has_product = any(c in det.concept_columns for c in _PRODUCT_KEY_CONCEPTS) or \
        "item_description" in det.concept_columns
    has_geo = "customer" in det.concept_columns or "client_market" in det.concept_columns
    has_metric = bool(det.primary_metrics)

    if not has_period:
        reasons.append("No usable period field was detected.")
    if not has_product:
        reasons.append("No product identifier or description field was detected.")
    if not has_geo:
        reasons.append("No customer or market field was detected.")
    if not has_metric:
        reasons.append("No usable sales/unit/volume metric was detected.")

    if reasons:
        return ("unknown", "not_comparable", reasons)

    if pos_votes > ship_votes:
        business = "pos"
        mode = "comparable"
        reasons.append(
            "Metrics appear POS-style (retail sales / units), which can reasonably "
            "compare to Discover measured retail metrics.")
    elif ship_votes > pos_votes:
        business = "shipment"
        mode = "directional"
        reasons.append(
            "Metrics appear shipment-based (cases / net revenue). Discover represents "
            "measured retail sales, so deltas are directional, not true reconciliation.")
    else:
        business = "unknown"
        mode = "directional"
        reasons.append(
            "Metric business type is unclear; treating the comparison as directional.")
    return (business, mode, reasons)
