"""Text normalization helpers used across schema detection and matching."""
from __future__ import annotations

import re
from typing import Optional

from rapidfuzz import fuzz

_WS_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9$#]+")


def norm_header(value: object) -> str:
    """Normalize a column header for pattern matching: lowercase, alnum tokens."""
    s = str(value).strip().lower()
    s = _NON_ALNUM_RE.sub(" ", s)
    return _WS_RE.sub(" ", s).strip()


def norm_value(value: object) -> str:
    """Normalize a cell value for equality matching."""
    s = str(value).strip().lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return _WS_RE.sub(" ", s).strip()


def clean_label(value: object) -> Optional[str]:
    """Trim and collapse whitespace, preserving original casing."""
    if value is None:
        return None
    s = _WS_RE.sub(" ", str(value)).strip()
    return s or None


# UPC normalization lives in upc.py — re-exported here for backwards
# compatibility with the rest of the codebase.
from .upc import (  # noqa: F401
    looks_like_upc_series,
    normalize_upc,
    upc_match_key,
    is_pseudo_code,
)


_PACK_RE = re.compile(r"(\d+)\s*(?:pk|pack|ct|count)\b", re.IGNORECASE)
_SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(oz|fl ?oz|ml|l|lb|lbs|g|kg|gal)\b", re.IGNORECASE)
_PKG_RE = re.compile(r"\b(can|btl|bottle|box|bag|cup|pouch|jar|carton|keg)s?\b", re.IGNORECASE)


def parse_description_tokens(desc: object) -> dict:
    """Extract pack count, size, and package type hints from a description."""
    out: dict = {"pack_count": None, "size": None, "size_unit": None, "package_type": None}
    if desc is None:
        return out
    s = str(desc)
    # Insert spaces in compact forms like '24PK12OZCAN' before matching.
    spaced = re.sub(r"(?<=[0-9])(?=[A-Za-z])|(?<=[A-Za-z])(?=[0-9])", " ", s)
    spaced = re.sub(r"(?i)\b(oz|ml|lb|kg|gal|l)(can|btl|bottle|box|bag|cup|pouch|jar|carton)s?\b",
                    r"\1 \2", spaced)
    m = _PACK_RE.search(spaced)
    if m:
        out["pack_count"] = int(m.group(1))
    m = _SIZE_RE.search(spaced)
    if m:
        out["size"] = float(m.group(1))
        out["size_unit"] = m.group(2).upper().replace(" ", "")
    m = _PKG_RE.search(spaced)
    if m:
        out["package_type"] = m.group(1).upper()
    return out


def similarity(a: object, b: object) -> float:
    """Token-set similarity between two strings on a 0-100 scale."""
    if a is None or b is None:
        return 0.0
    return float(fuzz.token_set_ratio(norm_value(a), norm_value(b)))


_TOTAL_MARKET_RE = re.compile(
    r"\b(total|national|all|overall|combined|corporate|enterprise|company ?wide)\b",
    re.IGNORECASE,
)


def is_total_like_market(label: object) -> bool:
    """True when a market/region label looks like a total or national rollup."""
    if label is None:
        return False
    return bool(_TOTAL_MARKET_RE.search(str(label)))
