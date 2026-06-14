"""Validate a clean Discover export against the preferred schema.

Light synonym tolerance only — the Discover side is expected to be clean.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from ..utils.dates import parse_period_value
from ..utils.text import norm_header, normalize_upc, upc_match_key
from .file_reader import LoadedFile

# canonical field -> accepted header synonyms (normalized).
# The first match wins, so longer/more specific phrases come before bare tokens.
_SYNONYMS: Dict[str, List[str]] = {
    "period": ["periods", "period", "time period", "week ending date", "week ending",
               "week end", "week", "period description", "time", "date", "month"],
    "customer": ["customer", "retailer", "banner", "account", "channel", "chain"],
    "market": ["markets", "market", "market name", "market description",
               "geography", "geo"],
    "upc": ["upc", "upc code", "item upc", "gtin", "barcode", "product key",
            "item code", "upc ean", "consumer upc"],
    "item_description": ["item_description", "item description", "item desc",
                         "product description", "product text", "item name",
                         "product name", "item long desc", "item", "product"],
    "manufacturer": ["manufacturer", "mfr", "mfr name", "mfg", "supplier",
                     "vendor", "parent company", "company"],
    "brand_low": ["brand low", "brand_low", "brandlow", "sub brand",
                  "subbrand", "sub-brand", "low brand", "brand lowest",
                  "lowest brand", "brand detail", "brand level 2",
                  "brand hierarchy low"],
    "brand": ["brand family", "brand text", "brand name", "brand"],
    "category": ["sub category", "subcategory", "category name", "category",
                 "product category", "module", "segment", "super category"],
    "dollar_sales": ["dollar sales", "dollar_sales", "dollar volume", "value sales",
                     "sales value", "$ sales", "sales $", "$", "dollars", "sales"],
    "unit_sales": ["unit sales", "unit_sales", "unit volume", "units", "qty", "quantity"],
    "volume_sales": ["volume sales", "volume_sales", "equivalized volume", "eq volume",
                     "volume eq", "volume", "eq", "ce", "equiv units"],
}

# Customer can be auto-derived from market (e.g. Discover "Markets" values like
# "Publix Atlanta TA" embed the retailer), so it is checked separately rather
# than blocking the upload. item_description is optional when brand is present
# (older Discover exports omit the long item description).
REQUIRED = ["period", "market", "category", "dollar_sales", "unit_sales"]
# plus: upc OR a product key, manufacturer OR brand, and item_description OR brand
# — checked separately


@dataclass
class DiscoverValidation:
    valid: bool
    matched_fields: Dict[str, str] = field(default_factory=dict)
    missing_required_fields: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    row_count: int = 0
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    preview: List[dict] = field(default_factory=list)
    normalized: Optional[pd.DataFrame] = None
    files: List[dict] = field(default_factory=list)  # per-file detail for multi-file uploads


def validate_discover_file(loaded: LoadedFile) -> DiscoverValidation:
    df = loaded.df
    result = DiscoverValidation(valid=False, row_count=len(df))

    norm_map = {norm_header(c): c for c in df.columns}
    for canonical, synonyms in _SYNONYMS.items():
        for syn in synonyms:
            if syn in norm_map and canonical not in result.matched_fields:
                result.matched_fields[canonical] = norm_map[syn]
                break

    missing = [f for f in REQUIRED if f not in result.matched_fields]
    if "upc" not in result.matched_fields:
        missing.append("upc (or item/product key)")
    if "manufacturer" not in result.matched_fields and "brand" not in result.matched_fields:
        missing.append("manufacturer or brand")
    if ("item_description" not in result.matched_fields
            and "brand" not in result.matched_fields):
        missing.append("item_description or brand")
    result.missing_required_fields = missing

    if "volume_sales" not in result.matched_fields:
        result.warnings.append("volume_sales not found (optional field).")

    if missing:
        result.warnings.append(
            "The Discover export should match the recommended pull. Re-export with "
            "the required fields included.")
        result.preview = _preview(df)
        return result

    # Build the normalized Discover frame.
    out = pd.DataFrame()
    for canonical, source in result.matched_fields.items():
        out[canonical] = df[source]

    # If item_description was not provided, fall back to brand text so the
    # downstream coverage drill-down has something to display per item.
    if "item_description" not in out.columns and "brand" in out.columns:
        out["item_description"] = out["brand"]

    # Drop junk/footer rows that NIQ exports sometimes append (copyright
    # disclaimers, "Dataset: ..." rows). Generic test: a real row must have
    # numeric dollar_sales and a non-null market and upc.
    out["dollar_sales"] = pd.to_numeric(out["dollar_sales"], errors="coerce")
    junk_mask = (out["dollar_sales"].isna() | out["market"].isna()
                 | out["upc"].isna())
    junk = int(junk_mask.sum())
    if junk:
        out = out[~junk_mask].reset_index(drop=True)
        result.warnings.append(
            f"Dropped {junk} non-data rows from the Discover export "
            "(blank or footer/disclaimer rows).")
    result.row_count = len(out)

    # Customer is often implicit in NIQ Discover Markets ("Publix Atlanta TA",
    # "Wegmans Buffalo TA"). When no Customer column was provided, derive a
    # customer from the leading retailer token in Markets so the coverage engine
    # can align it to the client file's customer.
    if "customer" not in out.columns:
        out["customer"] = out["market"].astype(str).map(_extract_customer_from_market)
        if out["customer"].notna().any():
            derived = out["customer"].dropna().unique()[:3]
            result.warnings.append(
                "No Customer column found; customer was derived from Markets "
                f"({', '.join(map(str, derived))}). Coverage alignment uses the "
                "derived customer.")
        else:
            result.missing_required_fields.append(
                "customer (no Customer column and could not derive from market)")
            result.preview = _preview(df)
            return result

    parsed = [parse_period_value(v) for v in out["period"]]
    out["period_start"] = [p.period_start.isoformat() if p else None for p in parsed]
    out["period_end"] = [p.period_end.isoformat() if p else None for p in parsed]
    unparsed = sum(1 for p in parsed if p is None)
    if unparsed:
        result.warnings.append(f"{unparsed} of {len(out)} period values could not be parsed.")

    out["upc_key"] = [upc_match_key(v) for v in out["upc"]]
    out["upc_normalized"] = [normalize_upc(v) for v in out["upc"]]
    bad_upc = int(out["upc"].notna().sum() - out["upc_key"].notna().sum())
    if bad_upc:
        result.warnings.append(f"{bad_upc} rows have UPC values that are not UPC/GTIN-like.")

    for col in ("unit_sales", "volume_sales"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    if out["dollar_sales"].isna().all():
        result.warnings.append("dollar_sales column contains no numeric values.")
        result.missing_required_fields.append("dollar_sales (numeric)")
        result.preview = _preview(df)
        return result

    ends = out["period_end"].dropna()
    if not ends.empty:
        result.period_start = str(out["period_start"].dropna().min())
        result.period_end = str(ends.max())

    result.valid = True
    result.normalized = out
    result.preview = _preview(df)
    return result


def validate_discover_files(loaded_files: List[LoadedFile]) -> DiscoverValidation:
    """Validate one or more Discover exports and stitch them into a single frame.

    Discover caps exports (~2.5M cells), so large pulls arrive as 2-3 files
    split by period, category, or brand. Each file is validated independently,
    then the normalized frames are concatenated. Exact duplicate rows across
    files are dropped; remaining key overlaps are kept (and summed by the
    coverage engine) with a warning.
    """
    if len(loaded_files) == 1:
        single = validate_discover_file(loaded_files[0])
        single.files = [_file_detail(loaded_files[0], single)]
        return single

    combined = DiscoverValidation(valid=False)
    frames: List[pd.DataFrame] = []
    for lf in loaded_files:
        result = validate_discover_file(lf)
        combined.files.append(_file_detail(lf, result))
        for w in result.warnings:
            combined.warnings.append(f"{lf.file_name}: {w}")
        if not result.valid:
            for m in result.missing_required_fields:
                combined.missing_required_fields.append(f"{lf.file_name}: {m}")
        else:
            frames.append(result.normalized.assign(_source_file=lf.file_name))
        if not combined.matched_fields:
            combined.matched_fields = result.matched_fields

    combined.row_count = sum(f["row_count"] for f in combined.files)
    if combined.missing_required_fields:
        combined.warnings.append(
            "All files in a split Discover export must contain the required fields. "
            "Fix the listed files and re-upload.")
        return combined

    out = pd.concat(frames, ignore_index=True, sort=False)

    # Drop rows that are identical across files (accidental overlap in pulls).
    data_cols = [c for c in out.columns if c != "_source_file"]
    before = len(out)
    out = out.drop_duplicates(subset=data_cols, keep="first").reset_index(drop=True)
    dropped = before - len(out)
    if dropped:
        combined.warnings.append(
            f"{dropped} duplicate rows appeared in more than one file and were "
            "removed when stitching.")

    # Same key, different values: legitimate splits never repeat a key, so warn.
    key_cols = [c for c in ("upc_key", "period_end", "market", "customer") if c in out.columns]
    if key_cols:
        overlaps = int(out.duplicated(subset=key_cols).sum())
        if overlaps:
            combined.warnings.append(
                f"{overlaps} item/period/market combinations appear in more than one "
                "file with different values. They were kept and will be summed — "
                "check that the split files do not overlap.")

    combined.valid = True
    combined.normalized = out.drop(columns=["_source_file"])
    combined.row_count = len(out)
    ends = out["period_end"].dropna()
    if not ends.empty:
        combined.period_start = str(out["period_start"].dropna().min())
        combined.period_end = str(ends.max())
    combined.preview = _preview(out.drop(columns=["_source_file"]))
    combined.warnings.append(
        f"Stitched {len(frames)} files into one Discover dataset "
        f"({combined.row_count:,} rows).")
    return combined


def _file_detail(loaded: LoadedFile, result: DiscoverValidation) -> dict:
    return {
        "file_name": loaded.file_name,
        "sheet_used": loaded.sheet_name,
        "valid": result.valid,
        "row_count": result.row_count,
        "period_start": result.period_start,
        "period_end": result.period_end,
        "missing_required_fields": result.missing_required_fields,
        "warnings": result.warnings,
    }


import re as _re

# Trailing tokens that describe a sub-market or rollup type (TA = Total Account,
# etc.). Stripped when deriving the customer from a Discover Markets value so
# "Publix Atlanta TA" reduces to "Publix".
_MARKET_TRAILING_TOKENS = (
    "ta", "tac", "total", "us", "remaining", "region", "area", "trade",
    "channel", "market", "geography", "geo", "all", "outlets",
)


def _extract_customer_from_market(market: object) -> Optional[str]:
    """Pull the retailer-like leading token from a NIQ Discover Markets value.

    Generic logic: take the first whitespace-separated token and discard
    descriptive trailing tokens. Works for "Publix Atlanta TA" -> "Publix",
    "Wegmans Buffalo TA" -> "Wegmans", "Walmart US" -> "Walmart". When the
    market is empty/None the result is None and the validator falls back to
    treating customer as missing.
    """
    if market is None:
        return None
    s = str(market).strip()
    if not s or s.lower() in ("nan", "none"):
        return None
    # Drop any parenthetical descriptors first: "Publix (Atlanta TA)" -> "Publix"
    s = _re.sub(r"\s*\([^)]*\)", "", s).strip()
    tokens = s.split()
    if not tokens:
        return None
    first = tokens[0]
    # If the leading token itself is descriptive ("Total Publix"), use the next one.
    if first.lower() in _MARKET_TRAILING_TOKENS and len(tokens) > 1:
        first = tokens[1]
    return first


def _preview(df: pd.DataFrame, n: int = 8) -> List[dict]:
    head = df.head(n)
    return [
        {str(k): (None if pd.isna(v) else str(v)) for k, v in row.items()}
        for _, row in head.iterrows()
    ]
