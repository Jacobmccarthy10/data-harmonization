"""Auto-built UPC crosswalk.

Client and NIQ UPCs frequently differ for the same product (client-internal
SKUs, GTIN-14 vs UPC-12, pseudo-codes, masking). This module produces a
runtime crosswalk between client and Discover UPCs based on shared
signals OTHER THAN the UPC itself:

  - same normalized brand (after the brand-alias pass)
  - same pack count and size unit (e.g. 12PK 12OZ CAN)
  - high item-description similarity (token_set_ratio)

Generic and deterministic: no client- or brand-specific entries. The
crosswalk is recomputed on every run and surfaced in the dashboard so
the user can audit individual mappings.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd
from rapidfuzz import fuzz

from ..utils.text import parse_description_tokens


@dataclass
class CrosswalkEntry:
    client_upc: str
    discover_upc: str
    client_desc: Optional[str]
    discover_desc: Optional[str]
    brand: Optional[str]
    score: float           # 0-1 composite confidence
    basis: str             # 'brand+size+pack' | 'brand+desc' | 'desc'


def _size_key(desc: object) -> Optional[str]:
    """Canonical size signature: '12pk-12oz-can'. None if not extractable."""
    if desc is None:
        return None
    t = parse_description_tokens(desc)
    parts: List[str] = []
    if t.get("pack_count"):
        parts.append(f"{int(t['pack_count'])}pk")
    if t.get("size"):
        parts.append(f"{t['size']:g}{(t.get('size_unit') or '').lower()}")
    if t.get("package_type"):
        parts.append(t["package_type"].lower())
    return "-".join(parts) if parts else None


def build_crosswalk(
    norm: pd.DataFrame, disc: pd.DataFrame,
    *, score_cutoff: float = 0.65,
) -> Tuple[Dict[str, str], List[CrosswalkEntry]]:
    """Build a client_upc -> discover_upc map for SKUs whose UPCs don't
    match directly but which appear to be the same product.

    Returns (map, entries) where entries describe each mapping for audit.
    """
    entries: List[CrosswalkEntry] = []
    if "_brand_norm" not in norm.columns or "_brand_norm" not in disc.columns:
        return {}, entries
    if "upc_key" not in norm.columns or "upc_key" not in disc.columns:
        return {}, entries

    # Per-row distinct client SKUs that have no Discover UPC counterpart.
    disc_upc_set = set(disc["upc_key"].dropna().astype(str))
    client_unmatched = (
        norm.dropna(subset=["upc_key"])
        [~norm["upc_key"].astype(str).isin(disc_upc_set)]
        [["upc_key", "item_description_raw", "_brand_norm"]]
        .drop_duplicates("upc_key")
    )
    if client_unmatched.empty:
        return {}, entries

    # Index Discover SKUs by upc_key with their brand/desc/size signature.
    disc_unique = (
        disc.dropna(subset=["upc_key"])
        [["upc_key", "item_description", "_brand_norm"]]
        .drop_duplicates("upc_key")
        .copy()
    )
    disc_unique["_size_key"] = disc_unique["item_description"].map(_size_key)

    mapping: Dict[str, str] = {}
    for _, c_row in client_unmatched.iterrows():
        c_upc = str(c_row["upc_key"])
        c_brand = c_row["_brand_norm"]
        c_desc = c_row["item_description_raw"]
        c_size = _size_key(c_desc)
        if c_brand is None or (isinstance(c_brand, float) and pd.isna(c_brand)):
            continue

        # First try: SKUs in the same brand on the Discover side.
        same_brand = disc_unique[disc_unique["_brand_norm"] == c_brand]
        candidates = same_brand
        # Fall back: brand-token-contained discover brands.
        if candidates.empty:
            candidates = disc_unique[
                disc_unique["_brand_norm"].apply(
                    lambda b: isinstance(b, str) and str(c_brand) in b)
            ]
        if candidates.empty:
            continue

        # Prefer matches that ALSO share the pack/size signature.
        size_matches = (candidates[candidates["_size_key"] == c_size]
                        if c_size else candidates.iloc[0:0])
        target_pool = size_matches if not size_matches.empty else candidates

        # Score by item-description token-set similarity.
        if c_desc is None or (isinstance(c_desc, float) and pd.isna(c_desc)):
            continue
        best_upc, best_score, best_desc = None, 0.0, None
        for _, d_row in target_pool.iterrows():
            d_desc = d_row["item_description"]
            if d_desc is None or (isinstance(d_desc, float) and pd.isna(d_desc)):
                continue
            score = fuzz.token_set_ratio(str(c_desc), str(d_desc))
            # Reward size+pack agreement.
            if c_size and d_row["_size_key"] == c_size:
                score = min(100, score + 8)
            if score > best_score:
                best_score = score
                best_upc = str(d_row["upc_key"])
                best_desc = str(d_desc)
        if best_upc and best_score / 100 >= score_cutoff:
            mapping[c_upc] = best_upc
            basis = ("brand+size+pack" if c_size and best_score >= 92
                     else "brand+desc")
            entries.append(CrosswalkEntry(
                client_upc=c_upc, discover_upc=best_upc,
                client_desc=str(c_desc) if c_desc is not None else None,
                discover_desc=best_desc, brand=str(c_brand),
                score=round(best_score / 100, 3), basis=basis))

    return mapping, entries


def merge_user_crosswalk(
    auto_map: Dict[str, str], auto_entries: List[CrosswalkEntry],
    user_df: Optional[pd.DataFrame],
) -> Tuple[Dict[str, str], List[CrosswalkEntry]]:
    """Merge a user-supplied crosswalk file on top of the auto-built map.

    User entries override auto entries when the client UPC appears in both.
    The user file is expected to have two columns: client UPC and discover UPC,
    detected by header name (any of: client_upc/sku/code on the left,
    discover_upc/niq_upc/upc on the right).
    """
    if user_df is None or user_df.empty:
        return auto_map, auto_entries

    cols = [str(c).strip().lower() for c in user_df.columns]
    left = next((c for c in user_df.columns
                 if str(c).strip().lower() in (
                     "client_upc", "client upc", "client_sku", "client sku",
                     "client", "sku", "internal_upc", "internal upc",
                     "internal_sku", "client_item", "client item")), None)
    right = next((c for c in user_df.columns
                  if str(c).strip().lower() in (
                      "discover_upc", "discover upc", "niq_upc", "niq upc",
                      "upc", "gtin", "discover", "niq")), None)
    if left is None or right is None:
        return auto_map, auto_entries

    from ..utils.upc import upc_match_key
    merged_map = dict(auto_map)
    merged_entries = [e for e in auto_entries
                      if e.client_upc not in
                      set(str(x) for x in user_df[left].dropna())]
    for _, row in user_df.iterrows():
        c = upc_match_key(row[left]) or str(row[left]).strip()
        d = upc_match_key(row[right]) or str(row[right]).strip()
        if not c or not d:
            continue
        merged_map[c] = d
        merged_entries.append(CrosswalkEntry(
            client_upc=c, discover_upc=d, client_desc=None,
            discover_desc=None, brand=None, score=1.0, basis="user-supplied"))
    return merged_map, merged_entries
