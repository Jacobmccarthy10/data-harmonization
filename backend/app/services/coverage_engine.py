"""Coverage comparison between a normalized client file and a Discover export.

Deterministic matching first (normalized UPC + period + customer + market),
with explicit fallbacks. Fuzzy description matching is never presented as an
exact match — it is classified as low_confidence_product_match.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd
from rapidfuzz import fuzz, process

from ..utils.text import is_total_like_market, norm_value
from . import crosswalk as crosswalk_service
from .market_aligner import align_markets as _align_markets_smart

MATCHED_STATUSES = {"matched", "matched_with_caveat"}
REVIEW_STATUSES = {"needs_review", "low_confidence_product_match"}

STATUS_ORDER = [
    "matched", "matched_with_caveat", "low_confidence_product_match",
    "missing_from_discover", "missing_from_client", "market_mismatch",
    "period_mismatch", "metric_mismatch", "not_comparable", "needs_review",
]


@dataclass
class CoverageResult:
    blocked: bool = False
    blocked_reasons: List[str] = field(default_factory=list)
    coverage_summary: dict = field(default_factory=dict)
    kpis: dict = field(default_factory=dict)
    trend: List[dict] = field(default_factory=list)
    exceptions: List[dict] = field(default_factory=list)
    drilldown: List[dict] = field(default_factory=list)
    coverage_df: Optional[pd.DataFrame] = None
    exceptions_df: Optional[pd.DataFrame] = None


def _f(value) -> Optional[float]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return round(float(value), 2)


def _discover_period_key(end: Optional[str], grain: str) -> Optional[str]:
    if end is None or (isinstance(end, float) and pd.isna(end)):
        return None
    d = pd.Timestamp(end).date()
    if grain == "monthly":
        return f"{d.year:04d}-{d.month:02d}"
    return d.isoformat()


def _align_customers(client_customers: List[str], discover_customers: List[str],
                     warnings: List[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for c in client_customers:
        best, best_score = None, 0.0
        for d in discover_customers:
            if norm_value(c) == norm_value(d):
                best, best_score = d, 100.0
                break
            score = fuzz.token_set_ratio(norm_value(c), norm_value(d))
            if score > best_score:
                best, best_score = d, score
        if best is not None and best_score >= 90:
            mapping[c] = best
    if not mapping and len(client_customers) == 1 and len(discover_customers) == 1:
        mapping[client_customers[0]] = discover_customers[0]
        warnings.append(
            f"Customer names differ ('{client_customers[0]}' vs "
            f"'{discover_customers[0]}'); both files contain a single customer, so "
            "they were aligned with a caveat.")
    return mapping


def _align_markets(client_markets: List[str], discover_markets: List[str],
                   warnings: List[str],
                   customer: str = "") -> Tuple[Dict[str, str], bool, Dict[str, bool], Dict[str, Tuple[str, ...]]]:
    """Returns (client -> discover map, rollup_mode, caveat_flags, geo_rollup_map).

    geo_rollup_map: when a client market was matched to a synthetic
    aggregate of multiple Discover sub-markets, this maps that synthetic
    name to the tuple of sub-market labels that should be summed together.
    """
    mapping, matches, smart_warnings = _align_markets_smart(
        client_markets, discover_markets, customer=customer)
    warnings.extend(smart_warnings)
    caveat_flags = {m.client: m.matched_with_caveat for m in matches if m.matched}
    geo_rollup_map: Dict[str, Tuple[str, ...]] = {}
    for m in matches:
        if m.matched and m.rollup_components:
            geo_rollup_map[m.discover] = m.rollup_components

    rollup_mode = False
    if not mapping and client_markets and discover_markets:
        rollup_mode = True
        warnings.append(
            "No client market aligned to a Discover market. Client markets were "
            "rolled up and compared to the Discover total; matches are flagged "
            "matched_with_caveat.")
    return mapping, rollup_mode, caveat_flags, geo_rollup_map


def run_coverage(norm: pd.DataFrame, disc: pd.DataFrame,
                 comparison_mode: str, time_grain: str,
                 user_crosswalk: Optional[pd.DataFrame] = None) -> CoverageResult:
    res = CoverageResult()

    if comparison_mode == "not_comparable":
        res.blocked = True
        res.blocked_reasons.append(
            "The client file is missing required dimensions or metrics, so a "
            "coverage run is blocked or limited.")
        return res

    warnings: List[str] = []
    norm = norm.copy()
    disc = disc.copy()
    grain = time_grain if time_grain in ("weekly", "monthly") else "weekly"
    disc["period_key"] = [_discover_period_key(e, grain) for e in disc["period_end"]]

    # ------------------------------------------------------------------
    # Customer alignment
    # ------------------------------------------------------------------
    client_customers = [c for c in norm["customer_standardized"].dropna().unique()]
    discover_customers = [c for c in disc["customer"].dropna().astype(str).unique()]
    cust_map = _align_customers(client_customers, discover_customers, warnings)
    if client_customers and discover_customers and not cust_map:
        res.blocked = True
        res.blocked_reasons.append(
            "No client customer could be aligned to a Discover customer. Check that "
            "the Discover pull matches the recommended retailer scope.")
        return res

    # ------------------------------------------------------------------
    # Market alignment (+ hierarchy handling)
    # ------------------------------------------------------------------
    client_markets = [m for m in norm["client_market_standardized"].dropna().unique()]
    discover_markets = [m for m in disc["market"].dropna().astype(str).unique()]
    primary_customer = client_customers[0] if client_customers else (
        discover_customers[0] if discover_customers else "")
    market_map, rollup_mode, market_caveats, geo_rollup_map = _align_markets(
        client_markets, discover_markets, warnings, customer=primary_customer)

    levels = set(norm["market_level"].dropna().unique())
    hierarchy = levels == {"total", "detail"}

    if rollup_mode:
        norm["_d_market"] = "(all markets rolled up)"
        disc["_d_market"] = "(all markets rolled up)"
        norm["_market_ok"] = True
        norm["_market_caveat"] = True
    else:
        norm["_d_market"] = norm["client_market_standardized"].map(market_map)
        disc["_d_market"] = disc["market"].astype(str)
        # Geo-rollup: any Discover row whose market was selected as a
        # component of a synthetic aggregate gets relabeled to that
        # aggregate, so groupby sums them together.
        if geo_rollup_map:
            component_to_synth: Dict[str, str] = {}
            for synth, comps in geo_rollup_map.items():
                for c in comps:
                    component_to_synth[c] = synth
            disc["_d_market"] = disc["_d_market"].map(
                lambda m: component_to_synth.get(m, m))
        norm["_market_ok"] = norm["_d_market"].notna()
        norm["_market_caveat"] = (
            norm["client_market_standardized"].map(market_caveats).fillna(False)
        )
        if not client_markets:
            norm["_d_market"] = discover_markets[0] if len(discover_markets) == 1 else None
            norm["_market_ok"] = norm["_d_market"].notna()
            norm["_market_caveat"] = False

    # KPI slice: avoid double counting when both total and detail rows exist.
    if hierarchy:
        kpi_mask = norm["market_level"].ne("detail")
    else:
        kpi_mask = pd.Series(True, index=norm.index)
    norm["_kpi_slice"] = kpi_mask

    # ------------------------------------------------------------------
    # Product key resolution: layered fallback (UPC -> fuzzy description ->
    # brand rollup). Each fallback flags matched_with_caveat so the user
    # sees that the match is coarser than SKU-level reconciliation.
    # ------------------------------------------------------------------
    norm["_pkey"] = norm["upc_key"]
    norm["_pmatch"] = pd.Series("upc", index=norm.index, dtype=object)
    norm.loc[norm["_pkey"].isna(), "_pmatch"] = None
    disc_upc_set = set(disc["upc_key"].dropna().astype(str))

    # Tier 2: fuzzy item description match. Fires when (a) client UPC is
    # missing OR (b) client UPC exists but has no Discover counterpart.
    disc_items = disc[["upc_key", "item_description"]].dropna(subset=["upc_key"]).drop_duplicates("upc_key")
    desc_lookup = {str(r["item_description"]): str(r["upc_key"])
                   for _, r in disc_items.iterrows() if pd.notna(r["item_description"])}
    upc_unmatched = norm["_pkey"].isna() | (~norm["_pkey"].astype(str).isin(disc_upc_set))
    tier2_mask = upc_unmatched & norm["item_description_raw"].notna()
    if tier2_mask.any() and desc_lookup:
        choices = list(desc_lookup.keys())
        cache: Dict[str, Optional[str]] = {}
        for d in norm.loc[tier2_mask, "item_description_raw"].unique():
            best = process.extractOne(str(d), choices, scorer=fuzz.token_set_ratio,
                                      score_cutoff=85)
            cache[str(d)] = desc_lookup[best[0]] if best else None
        mapped = norm.loc[tier2_mask, "item_description_raw"].astype(str).map(cache)
        hit = tier2_mask & mapped.notna()
        norm.loc[hit, "_pkey"] = mapped[hit]
        norm.loc[hit, "_pmatch"] = "description_fuzzy"

    # Tier 3: brand rollup. For client rows still unmatched, replace
    # _pkey with a synthetic "BRAND::<brand>" key. The same synthetic key
    # is assigned to Discover rows whose upc_key has no client counterpart,
    # so the two sides merge at the brand+period+market level. Generic --
    # works for any retailer; no hardcoded brand list.
    # Universal short-form aliases. Treated like state-abbreviation
    # expansion -- normalization layer, not a brand "rules" table. These
    # are English short-forms of widely-recognized products. NOT
    # client-specific; nothing here is tied to who's uploading.
    _BRAND_ALIASES: Dict[str, str] = {
        "coke": "coca-cola",
        "coke zero": "coca-cola zero sugar",
        "coke zero sugar": "coca-cola zero sugar",
        "diet coke": "coca-cola diet",
        "mt dew": "mountain dew",
        "mtn dew": "mountain dew",
        "dr pepper": "dr. pepper",
        "drpepper": "dr. pepper",
        "7up": "7-up",
        "7 up": "7-up",
        "pepsi cola": "pepsi",
        "pepsi-cola": "pepsi",
        "ab": "anheuser-busch",
        "abi": "anheuser-busch",
        "anheuser busch": "anheuser-busch",
        "bud": "budweiser",
    }

    def _norm_brand(value: object) -> Optional[str]:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        # Strip "(Manufacturer Name)" parentheticals NIQ adds, lowercase,
        # collapse whitespace.
        s = re.sub(r"\s*\([^)]*\)", "", str(value)).strip()
        s = re.sub(r"\s+", " ", s).lower()
        if not s:
            return None
        # Apply universal alias resolution.
        return _BRAND_ALIASES.get(s, s)

    # Generic stopwords for the "leading brand token" fallback. These show up
    # at the start of product descriptions across retail data and should not
    # be treated as brand names.
    _DESC_STOPWORDS = {
        "the", "a", "an", "private", "store", "generic",
        "regular", "original", "classic", "new", "old",
    }

    def _brand_from_desc(value: object) -> Optional[str]:
        """Fallback: when brand is missing, take the leading non-stopword
        token of the item description as the implicit brand. Generic --
        product descriptions in retail data universally lead with the brand."""
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        s = re.sub(r"\s*\([^)]*\)", "", str(value)).strip()
        tokens = re.findall(r"[A-Za-z][A-Za-z'\-]*", s)
        if not tokens:
            return None
        for t in tokens:
            if t.lower() not in _DESC_STOPWORDS and len(t) > 1:
                return t.lower()
        return tokens[0].lower()

    norm["_brand_norm"] = norm["brand_standardized"].map(_norm_brand)
    if norm["_brand_norm"].isna().all():
        norm["_brand_norm"] = norm["item_description_raw"].map(_brand_from_desc)

    # Discover: prefer the most specific brand layer available. NIQ Discover
    # exports can include BRAND LOW (a.k.a. sub-brand) which is more granular
    # than BRAND -- e.g. BRAND="GENERAL MILLS" / BRAND LOW="GENERAL MILLS
    # CHEERIOS". The lower layer aligns more cleanly with client item-level
    # brand text.
    if "brand_low" in disc.columns and disc["brand_low"].notna().any():
        disc["_brand_norm"] = disc["brand_low"].map(_norm_brand)
        disc.loc[disc["_brand_norm"].isna(), "_brand_norm"] = (
            disc.loc[disc["_brand_norm"].isna(), "brand"].map(_norm_brand)
            if "brand" in disc.columns else None
        )
    elif "brand" in disc.columns:
        disc["_brand_norm"] = disc["brand"].map(_norm_brand)
        if disc["_brand_norm"].isna().all():
            disc["_brand_norm"] = disc["item_description"].map(_brand_from_desc)
    else:
        disc["_brand_norm"] = disc["item_description"].map(_brand_from_desc) \
            if "item_description" in disc.columns else None

    # Brand fuzzy: build a client-brand -> discover-brand alias map.
    # Three signals checked, in order of preference:
    #   (1) substring containment: 'cheerios' in 'general mills cheerios'
    #   (2) whitespace-stripped equality: 'smartwater' vs 'smart water'
    #   (3) partial_ratio >= 82 corroborated by token_set_ratio >= 60
    client_brands_present = norm["_brand_norm"].dropna().astype(str).unique().tolist()
    disc_brands_present = disc["_brand_norm"].dropna().astype(str).unique().tolist()
    brand_alias_map: Dict[str, str] = {}

    def _no_space(s: str) -> str:
        return re.sub(r"\s+", "", s)

    if client_brands_present and disc_brands_present:
        disc_brand_set = set(disc_brands_present)
        # Pre-compute whitespace-stripped form of each discover brand once.
        disc_nospace_index = {_no_space(d): d for d in disc_brands_present}
        for cb in client_brands_present:
            if cb in disc_brand_set:
                continue
            # Tier 1: whitespace-stripped exact match.
            cb_nospace = _no_space(cb)
            if cb_nospace in disc_nospace_index and disc_nospace_index[cb_nospace] != cb:
                brand_alias_map[cb] = disc_nospace_index[cb_nospace]
                continue
            # Tier 2: substring containment (either direction).
            sub_hits = [d for d in disc_brands_present
                        if len(cb) >= 3 and (cb in d or d in cb)]
            if sub_hits:
                # Prefer the shortest containing string (most specific match).
                sub_hits.sort(key=len)
                brand_alias_map[cb] = sub_hits[0]
                continue
            # Tier 3: partial_ratio with token-set corroboration.
            best = process.extractOne(
                cb, disc_brands_present,
                scorer=fuzz.partial_ratio, score_cutoff=82,
            )
            if best is not None and fuzz.token_set_ratio(cb, best[0]) >= 60:
                brand_alias_map[cb] = best[0]
        if brand_alias_map:
            norm["_brand_norm"] = norm["_brand_norm"].map(
                lambda b: brand_alias_map.get(b, b))

    # ------------------------------------------------------------------
    # Tier 2.5: UPC crosswalk (auto-built + user-supplied override).
    # When a client UPC is not in the Discover UPC set, try to find a
    # Discover SKU that's the same product by brand + pack/size + item
    # description similarity. User-supplied crosswalk overrides.
    # ------------------------------------------------------------------
    auto_map, auto_entries = crosswalk_service.build_crosswalk(norm, disc)
    full_map, full_entries = crosswalk_service.merge_user_crosswalk(
        auto_map, auto_entries, user_crosswalk)
    if full_map:
        applied_mask = norm["_pkey"].astype(str).isin(full_map.keys())
        if applied_mask.any():
            mapped = norm.loc[applied_mask, "_pkey"].astype(str).map(full_map)
            norm.loc[applied_mask, "_pkey"] = mapped
            norm.loc[applied_mask, "_pmatch"] = "upc_crosswalk"

    # Recompute the UPC set after the crosswalk in case some discover UPCs
    # were never the original client values.
    disc_upc_set = set(disc["upc_key"].dropna().astype(str))
    still_unmatched = (norm["_pkey"].isna() | ~norm["_pkey"].astype(str).isin(disc_upc_set))
    tier3_mask = still_unmatched & norm["_brand_norm"].notna()
    if tier3_mask.any():
        norm.loc[tier3_mask, "_pkey"] = "BRAND::" + norm.loc[tier3_mask, "_brand_norm"].astype(str)
        norm.loc[tier3_mask, "_pmatch"] = "brand_rollup"

    # Mirror tier 3 on Discover side: any Discover row whose upc_key is NOT
    # in the post-tier-2 client _pkey set gets aggregated at brand level.
    client_keys = set(norm["_pkey"].dropna().astype(str))
    disc_unmatched = ~disc["upc_key"].astype(str).isin(client_keys)
    disc_tier3 = disc_unmatched & disc["_brand_norm"].notna()
    if disc_tier3.any():
        disc.loc[disc_tier3, "upc_key"] = "BRAND::" + disc.loc[disc_tier3, "_brand_norm"].astype(str)

    # ------------------------------------------------------------------
    # Aggregate both sides to the comparison grain
    # ------------------------------------------------------------------
    eligible = norm["_market_ok"] & norm["period_key"].notna() & norm["_pkey"].notna()
    group_cols = ["_pkey", "period_key", "_d_market"]

    def _sum(series):
        return series.sum(min_count=1)

    cg = (norm[eligible]
          .groupby(group_cols, dropna=False)
          .agg(client_sales=("sales_value", _sum),
               client_units=("unit_value", _sum),
               client_volume=("volume_value", _sum),
               client_desc=("item_description_raw", "first"),
               client_upc=("upc_normalized", "first"),
               brand=("brand_standardized", "first"),
               category=("category_standardized", "first"),
               pmatch=("_pmatch", "first"),
               confidence=("mapping_confidence", "mean"),
               kpi_slice=("_kpi_slice", "any"),
               market_caveat=("_market_caveat", "any"),
               row_count=("source_row_id", "count"))
          .reset_index())

    disc_eligible = disc["period_key"].notna() & disc["upc_key"].notna()
    mapped_discover_markets = set(market_map.values()) if not rollup_mode else {"(all markets rolled up)"}
    disc_aggs = {
        "niq_sales": ("dollar_sales", _sum),
        "niq_units": ("unit_sales", _sum),
        "niq_desc": ("item_description", "first"),
        "niq_upc": ("upc_normalized", "first"),
    }
    if "volume_sales" in disc.columns:
        disc_aggs["niq_volume"] = ("volume_sales", _sum)
    dg_all = (disc[disc_eligible]
              .groupby(["upc_key", "period_key", "_d_market"], dropna=False)
              .agg(**disc_aggs)
              .reset_index()
              .rename(columns={"upc_key": "_pkey"}))
    if "niq_volume" not in dg_all.columns:
        dg_all["niq_volume"] = None
    dg = dg_all[dg_all["_d_market"].isin(mapped_discover_markets)] if mapped_discover_markets else dg_all

    merged = cg.merge(dg, on=group_cols, how="outer", indicator=True)

    disc_keys = set(dg["_pkey"].dropna())
    disc_key_periods = set(zip(dg["_pkey"], dg["period_key"]))
    all_disc_keys = set(dg_all["_pkey"].dropna())

    def classify(row) -> Tuple[str, Optional[str]]:
        if row["_merge"] == "both":
            no_client_value = pd.isna(row["client_sales"]) and pd.isna(row["client_units"])
            if no_client_value:
                return "metric_mismatch", "client rows have no comparable sales/unit values"
            if row["pmatch"] == "description_fuzzy":
                return "low_confidence_product_match", "matched by description similarity, not UPC"
            if row["pmatch"] == "upc_crosswalk":
                return "matched_with_caveat", "matched via UPC crosswalk (brand + pack/size + description)"
            if row["pmatch"] == "brand_rollup":
                return "matched_with_caveat", "matched at brand level (UPC not found in Discover)"
            if rollup_mode:
                return "matched_with_caveat", "matched with client markets rolled up"
            if bool(row.get("market_caveat", False)):
                return "matched_with_caveat", "client market fuzzy-matched to a Discover aggregate market"
            return "matched", None
        if row["_merge"] == "left_only":
            key, period = row["_pkey"], row["period_key"]
            if key in disc_keys and (key, period) not in disc_key_periods:
                return "period_mismatch", "product exists in Discover but not in this period"
            if key not in disc_keys and key in all_disc_keys:
                return "market_mismatch", "product exists in Discover but only in unmapped markets"
            return "missing_from_discover", "product/period not present in the Discover export"
        return "missing_from_client", "Discover row with no client counterpart"

    classified = merged.apply(classify, axis=1, result_type="expand")
    merged["status"] = classified[0]
    merged["exception_reason"] = classified[1]
    merged["sales_delta"] = merged.apply(
        lambda r: _f(r["client_sales"] - r["niq_sales"])
        if pd.notna(r["client_sales"]) and pd.notna(r["niq_sales"]) else None, axis=1)
    merged["unit_delta"] = merged.apply(
        lambda r: _f(r["client_units"] - r["niq_units"])
        if pd.notna(r["client_units"]) and pd.notna(r["niq_units"]) else None, axis=1)

    # ------------------------------------------------------------------
    # Push statuses back onto client rows
    # ------------------------------------------------------------------
    status_map = {tuple(r[c] for c in group_cols): r["status"]
                  for _, r in merged[merged["_merge"] != "right_only"].iterrows()}
    reason_map = {tuple(r[c] for c in group_cols): r["exception_reason"]
                  for _, r in merged[merged["_merge"] != "right_only"].iterrows()}

    def row_status(r) -> Tuple[str, Optional[str]]:
        if r["record_status"] == "needs_review":
            return "needs_review", r["exception_reason"]
        if not r["_market_ok"]:
            return "market_mismatch", "client market could not be mapped to a Discover market"
        if pd.isna(r["period_key"]):
            return "needs_review", "period_unparsed"
        if pd.isna(r["_pkey"]):
            return "missing_from_discover", "no usable product key and no description match"
        key = (r["_pkey"], r["period_key"], r["_d_market"])
        return status_map.get(key, "needs_review"), reason_map.get(key)

    statuses = norm.apply(row_status, axis=1, result_type="expand")
    norm["coverage_status"] = statuses[0]
    norm["coverage_reason"] = statuses[1]

    # ------------------------------------------------------------------
    # KPIs
    # ------------------------------------------------------------------
    total_rows = len(norm)
    matched_mask = norm["coverage_status"].isin(MATCHED_STATUSES)
    kpi = norm[norm["_kpi_slice"]]
    kpi_matched = kpi[kpi["coverage_status"].isin(MATCHED_STATUSES)]
    kpi_rows = len(kpi)

    client_sales = kpi["sales_value"].sum(skipna=True)
    matched_client_sales = kpi_matched["sales_value"].sum(skipna=True)
    has_units = kpi["unit_value"].notna().any()
    client_units = kpi["unit_value"].sum(skipna=True) if has_units else None
    matched_client_units = kpi_matched["unit_value"].sum(skipna=True) if has_units else None

    matched_groups = merged[(merged["status"].isin(MATCHED_STATUSES)) & merged["kpi_slice"].fillna(False)]
    niq_sales = matched_groups["niq_sales"].sum(skipna=True)
    niq_units = matched_groups["niq_units"].sum(skipna=True) if has_units else None

    review_rows = int(norm["coverage_status"].isin(REVIEW_STATUSES).sum())
    uncovered_sales = client_sales - matched_client_sales

    delta_label = "directional" if comparison_mode == "directional" else "comparable"
    res.kpis = {
        "comparison_mode": comparison_mode,
        "delta_label": delta_label,
        "total_client_rows": int(total_rows),
        "matched_rows": int(matched_mask.sum()),
        "row_coverage_pct": round(float(matched_mask.mean()), 4) if total_rows else 0,
        "kpi_slice_rows": int(kpi_rows),
        "kpi_slice_row_coverage_pct": (round(float(len(kpi_matched) / kpi_rows), 4)
                                       if kpi_rows else 0),
        "client_sales_uploaded": _f(client_sales),
        "matched_client_sales": _f(matched_client_sales),
        "sales_coverage_pct": round(float(matched_client_sales / client_sales), 4) if client_sales else 0,
        "niq_comparable_sales": _f(niq_sales),
        "sales_delta": _f(matched_client_sales - niq_sales),
        "client_units_uploaded": _f(client_units),
        "matched_client_units": _f(matched_client_units),
        "unit_coverage_pct": (round(float(matched_client_units / client_units), 4)
                              if has_units and client_units else None),
        "niq_comparable_units": _f(niq_units),
        "unit_delta": (_f(matched_client_units - niq_units) if has_units and niq_units is not None else None),
        "rows_needing_review": review_rows,
        "uncovered_sales": _f(uncovered_sales),
        "kpi_slice_note": (
            "Sales/unit KPIs use total-level market rows to avoid double counting "
            "(file contains both total and detail market levels)." if hierarchy else None),
    }

    # ------------------------------------------------------------------
    # Trend by period
    # ------------------------------------------------------------------
    trend_rows = []
    for period in sorted(p for p in kpi["period_key"].dropna().unique()):
        slice_ = kpi[kpi["period_key"] == period]
        m_slice = slice_[slice_["coverage_status"].isin(MATCHED_STATUSES)]
        g = matched_groups[matched_groups["period_key"] == period]
        c_sales = slice_["sales_value"].sum(skipna=True)
        m_sales = m_slice["sales_value"].sum(skipna=True)
        n_sales = g["niq_sales"].sum(skipna=True)
        row = {
            "period": period,
            "client_sales": _f(c_sales),
            "niq_sales": _f(n_sales),
            "sales_delta": _f(m_sales - n_sales),
            "coverage_rate": round(float(m_sales / c_sales), 4) if c_sales else 0,
        }
        if has_units:
            row["client_units"] = _f(slice_["unit_value"].sum(skipna=True))
            row["niq_units"] = _f(g["niq_units"].sum(skipna=True))
        trend_rows.append(row)
    res.trend = trend_rows

    # ------------------------------------------------------------------
    # Exception breakdown (all client rows + Discover-only groups)
    # ------------------------------------------------------------------
    exc = []
    by_status = norm.groupby("coverage_status")
    for status in STATUS_ORDER:
        if status == "missing_from_client":
            only = merged[merged["status"] == "missing_from_client"]
            if len(only):
                exc.append({
                    "status": status,
                    "rows": int(len(only)),
                    "client_sales": None,
                    "niq_sales": _f(only["niq_sales"].sum(skipna=True)),
                    "note": "Discover item/periods with no client counterpart",
                })
            continue
        if status in by_status.groups:
            grp = by_status.get_group(status)
            exc.append({
                "status": status,
                "rows": int(len(grp)),
                "client_sales": _f(grp["sales_value"].sum(skipna=True)),
                "niq_sales": None,
                "note": grp["coverage_reason"].dropna().iloc[0] if grp["coverage_reason"].notna().any() else None,
            })
    res.exceptions = exc

    # ------------------------------------------------------------------
    # Drill-down (group grain)
    # ------------------------------------------------------------------
    drill = merged.copy()
    drill["customer"] = client_customers[0] if client_customers else (
        discover_customers[0] if discover_customers else None)
    def _s(value) -> Optional[str]:
        if value is None or (isinstance(value, float) and pd.isna(value)) or value is pd.NA:
            return None
        return str(value)

    drill_rows = []
    for _, r in drill.head(5000).iterrows():
        drill_rows.append({
            "status": _s(r["status"]),
            "exception_reason": _s(r["exception_reason"]),
            "period": _s(r["period_key"]),
            "customer": _s(r["customer"]),
            "market": _s(r["_d_market"]),
            "client_upc": _s(r.get("client_upc")),
            "client_item_description": _s(r.get("client_desc")),
            "discover_upc": _s(r.get("niq_upc")),
            "discover_item_description": _s(r.get("niq_desc")),
            "brand": _s(r.get("brand")),
            "category": _s(r.get("category")),
            "client_sales": _f(r.get("client_sales")),
            "discover_sales": _f(r.get("niq_sales")),
            "sales_delta": _f(r.get("sales_delta")),
            "client_units": _f(r.get("client_units")),
            "discover_units": _f(r.get("niq_units")),
            "unit_delta": _f(r.get("unit_delta")),
            "match_confidence": round(float(r["confidence"]), 2) if pd.notna(r.get("confidence")) else None,
            "client_row_count": int(r["row_count"]) if pd.notna(r.get("row_count")) else 0,
        })
    drill_rows.sort(key=lambda d: (d["period"] or "", d["status"], -(d["client_sales"] or 0)))
    res.drilldown = drill_rows

    # Brand-level diagnostic: which client brands matched, which didn't, and
    # what $ they carry. Built from the KPI slice (total-level rows) so the
    # numbers tie back to the headline KPIs.
    brand_diag_rows: List[dict] = []
    if "_brand_norm" in norm.columns:
        kpi_norm = norm[norm["_kpi_slice"]]
        per_brand = kpi_norm.groupby("_brand_norm", dropna=True).agg(
            client_sales=("sales_value", _sum),
            client_rows=("source_row_id", "count"),
            matched_rows=("coverage_status",
                          lambda s: int(s.isin(MATCHED_STATUSES).sum())),
        ).reset_index()
        for _, r in per_brand.iterrows():
            brand_diag_rows.append({
                "brand": str(r["_brand_norm"]),
                "client_rows": int(r["client_rows"]),
                "matched_rows": int(r["matched_rows"]),
                "client_sales": _f(r["client_sales"]),
                "match_rate": (round(float(r["matched_rows"] / r["client_rows"]), 3)
                                if r["client_rows"] else 0),
            })
    brand_diag_rows.sort(key=lambda d: -(d["client_sales"] or 0))

    # Period-level diagnostic: which client periods matched, which didn't.
    # Surfaces period-grain misalignment (e.g. client monthly 2025 vs Discover
    # multi-week 2021-2024).
    period_diag_rows: List[dict] = []
    kpi_norm_p = norm[norm["_kpi_slice"]]
    for period in sorted(p for p in kpi_norm_p["period_key"].dropna().unique()):
        slice_ = kpi_norm_p[kpi_norm_p["period_key"] == period]
        m = slice_[slice_["coverage_status"].isin(MATCHED_STATUSES)]
        client_sales_p = float(slice_["sales_value"].sum(skipna=True))
        matched_sales_p = float(m["sales_value"].sum(skipna=True))
        period_diag_rows.append({
            "period": period,
            "client_rows": int(len(slice_)),
            "matched_rows": int(len(m)),
            "client_sales": _f(client_sales_p),
            "matched_client_sales": _f(matched_sales_p),
            "match_rate": (round(matched_sales_p / client_sales_p, 3)
                            if client_sales_p else 0),
        })

    # Overall brand-overlap snapshot for the 0%-coverage warning case.
    client_brand_set = set(norm["_brand_norm"].dropna().astype(str).unique())
    disc_brand_set = set(disc["_brand_norm"].dropna().astype(str).unique())
    brand_overlap = client_brand_set & disc_brand_set
    brand_overlap_diag = {
        "client_brand_count": len(client_brand_set),
        "discover_brand_count": len(disc_brand_set),
        "overlap_count": len(brand_overlap),
        "client_unmatched_brands": sorted([
            b for b in client_brand_set
            if all(r["brand"] != b or r["matched_rows"] == 0 for r in brand_diag_rows)
        ])[:20],
    }
    if matched_mask.sum() == 0 and client_brand_set and disc_brand_set and not brand_overlap:
        warnings.append(
            f"Coverage is 0% because the Discover pull's brand scope "
            f"({len(disc_brand_set)} brands) does not overlap the client file's "
            f"brand scope ({len(client_brand_set)} brands). Likely the Discover "
            "pull was for a different product slice (e.g. new-product launches) "
            "than the client's portfolio. Re-pull Discover with brands that match "
            "the client file.")

    res.coverage_summary = {
        "comparison_mode": comparison_mode,
        "time_grain": grain,
        "customer_alignment": cust_map,
        "market_alignment": market_map,
        "market_rollup_mode": rollup_mode,
        "market_hierarchy_detected": hierarchy,
        "unmapped_client_markets": [m for m in client_markets if m not in market_map] if not rollup_mode else [],
        "warnings": warnings,
        "match_grain": "UPC/item + period + customer + market",
        "brand_overlap_diagnostic": brand_overlap_diag,
        "brand_diagnostic": brand_diag_rows,
        "period_diagnostic": period_diag_rows,
        "brand_alias_map": brand_alias_map,
        "upc_crosswalk_entries": [
            {
                "client_upc": e.client_upc, "discover_upc": e.discover_upc,
                "client_desc": e.client_desc, "discover_desc": e.discover_desc,
                "brand": e.brand, "score": e.score, "basis": e.basis,
            }
            for e in full_entries
        ],
        "geo_rollup_map": {k: list(v) for k, v in geo_rollup_map.items()},
    }

    # frames for CSV export
    res.coverage_df = pd.DataFrame(drill_rows)
    res.exceptions_df = norm[~norm["coverage_status"].isin(MATCHED_STATUSES)][[
        "source_row_id", "coverage_status", "coverage_reason", "period_key",
        "customer_standardized", "client_market_standardized", "upc_normalized",
        "item_description_raw", "sales_value", "unit_value", "volume_value",
        "mapping_confidence"]].rename(columns={"coverage_status": "status",
                                               "coverage_reason": "exception_reason"})
    return res
