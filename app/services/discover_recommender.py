"""Build the on-screen Discover pull recommendation from a client profile."""
from __future__ import annotations

from typing import List

from .schema_detector import SchemaDetection

REQUIRED_DISCOVER_FIELDS = [
    "period", "customer", "market", "upc (or item/product key)",
    "item_description", "manufacturer", "brand", "category",
    "dollar_sales", "unit_sales",
]
OPTIONAL_DISCOVER_FIELDS = ["volume_sales"]

CONVERSION_NOTE = (
    "Future versions may include metric conversion or equivalency calculations, "
    "but v1 does not apply guessed conversion rules."
)


def build_recommendation(profile: dict, det: SchemaDetection,
                         quality: dict) -> dict:
    customer = profile.get("customer")
    markets = profile.get("markets") or []

    market_scope: List[str] = []
    total_markets = [m["value"] for m in markets if m.get("total_like")]
    detail_markets = [m["value"] for m in markets if not m.get("total_like")]
    if total_markets:
        market_scope.append(
            f"Total-account view detected ('{total_markets[0]}'): pull the closest "
            f"available total {customer or 'retailer'} market in Discover.")
    if detail_markets:
        shown = ", ".join(detail_markets[:6])
        more = f" (+{len(detail_markets) - 6} more)" if len(detail_markets) > 6 else ""
        market_scope.append(
            f"Client regional markets ({shown}{more}) are client-specific. Map them to "
            "the closest available NIQ market selections, or start with the total view.")
    if not market_scope:
        market_scope.append("No market field detected; pull the total US view for this retailer.")

    measures = ["Dollar sales", "Unit sales"]
    if "volume" in det.primary_metrics:
        measures.append("Volume sales if available")

    caveats: List[str] = []
    if det.comparison_mode == "directional":
        caveats.append(
            "Client file appears shipment-based. Coverage can be evaluated, but "
            "sales and unit deltas are directional unless a future conversion rule "
            "is defined.")
        caveats.append(CONVERSION_NOTE)
    elif det.comparison_mode == "comparable":
        caveats.append(
            "Client file appears POS-style. If the Discover export matches the "
            "recommended grain, coverage and deltas can be read as a closer "
            "like-for-like comparison.")
    else:
        caveats.append(
            "Key fields are missing from the client file; a full coverage "
            "comparison may be blocked or limited.")
    if detail_markets:
        caveats.append(
            "Client regional/market definitions are client-specific and will not "
            "match NIQ markets one-to-one without a mapping.")

    return {
        "country": "US",
        "recommended_dataset": "NIQ Discover measured retail sales",
        "customer_scope": [customer] if customer else [],
        "market_scope": market_scope,
        "category_scope": [c["value"] for c in (profile.get("categories") or [])][:10],
        "manufacturer_scope": [m["value"] for m in (profile.get("manufacturers") or [])][:6],
        "brand_scope": [b["value"] for b in (profile.get("brands") or [])][:12],
        "period_start": profile.get("period_start"),
        "period_end": profile.get("period_end"),
        "time_grain": profile.get("time_grain", "unknown"),
        "product_grain": "UPC/item level preferred, with fallback to brand/category rollups",
        "required_measures": measures,
        "comparison_mode": det.comparison_mode,
        "caveats": caveats,
        "required_discover_fields": REQUIRED_DISCOVER_FIELDS,
        "optional_discover_fields": OPTIONAL_DISCOVER_FIELDS,
    }
