"""UPC / GTIN normalization and matching helpers.

Real-world clients and NIQ rarely use identical UPC codes for the same
product. Differences include:

  - Format: leading zeros, hyphens, decimal artifacts from Excel
  - Hierarchy / digit count: 8-digit UPC-E, 10/11/12-digit UPC-A, 13-digit
    EAN, 14-digit GTIN-14 (with a packaging-indicator prefix)
  - Check-digit variants: the trailing check digit may differ if one side
    omitted or recalculated it
  - Masking: trailing digit replaced with 'X', '*', '?'
  - Pseudo-codes: client uses an internal SKU like 'ABI-00001' or
    'CCNA-10001' instead of a real UPC

This module produces a canonical "match key" that collapses all of those
representations into one comparable value when possible, and clearly
signals when the input is a pseudo-code that should not match by UPC at all.
"""
from __future__ import annotations

import re
from typing import Optional

# Characters that are valid noise in a UPC-like string and should be stripped.
_UPC_STRIP_RE = re.compile(r"[\s\-\.]")
# Masking characters that may stand in for a check digit ('X' is common).
_MASK_TAIL_RE = re.compile(r"[X*?]$", re.IGNORECASE)


def _strip_float_artifact(s: str) -> str:
    """Excel float artifacts: '71800000211.0' -> '71800000211'."""
    if re.fullmatch(r"\d+\.0+", s):
        return s.split(".")[0]
    return s


def normalize_upc(value: object) -> Optional[str]:
    """Normalize a UPC/GTIN-like value to its raw digit string.

    Returns None when the value is not UPC-like (pseudo-codes, free text,
    blank). Preserves any leading zeros as written. Accepts 8 to 14 digits
    after stripping hyphens, spaces, decimal artifacts, and a trailing
    masking character.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in ("nan", "none"):
        return None
    s = _strip_float_artifact(s)
    s = _UPC_STRIP_RE.sub("", s)
    s = _MASK_TAIL_RE.sub("", s)
    if not re.fullmatch(r"\d{8,14}", s):
        return None
    return s


def is_pseudo_code(value: object) -> bool:
    """True when the value looks like a client-internal SKU code (letters,
    hyphenated codes) rather than a real UPC/GTIN.

    Examples: 'ABI-00001', 'CCNA-10001', 'GM-CHE0001', 'SKU#12345'.
    """
    if value is None:
        return False
    s = str(value).strip()
    if not s:
        return False
    # Any letters at all means it cannot be a numeric UPC.
    if re.search(r"[A-Za-z]", s):
        return True
    return False


def gtin14_to_upc12(digits: str) -> str:
    """Strip the leading packaging-indicator + GS1 prefix to get the
    consumer UPC-12 from a 14-digit GTIN.

    GTIN-14 = [indicator digit (1)] + [GS1 prefix or padding (1-2)] + UPC-12.
    Generic heuristic: drop leading zeros until <= 12 digits remain.
    """
    return digits.lstrip("0")[-12:] if len(digits) > 12 else digits


def upc_match_key(value: object, *, ignore_check_digit: bool = True) -> Optional[str]:
    """Canonical match key for a UPC.

    Collapses every common variant of the same UPC to one comparable string:

      - 14-digit GTIN -> 12-digit UPC (drop leading packaging digit/prefix)
      - leading zeros stripped (so '07180000021' and '71800000021' match)
      - optionally the trailing check digit stripped, since one side may
        omit/recalculate it ('071800000211' and '07180000021' both -> '7180000021')
    """
    digits = normalize_upc(value)
    if digits is None:
        return None
    if len(digits) == 14:
        digits = gtin14_to_upc12(digits)
    # Strip leading zeros: '0001600018621' -> '1600018621'.
    no_zeros = digits.lstrip("0") or digits
    if ignore_check_digit and len(no_zeros) >= 8:
        # The check digit is the last digit. Two codes that share the same
        # company + item portion will share the check-digit-stripped key.
        return no_zeros[:-1]
    return no_zeros


def looks_like_upc_series(values) -> float:
    """Fraction of non-null sample values that normalize to a UPC."""
    vals = [v for v in values if v is not None and str(v).strip() != ""]
    if not vals:
        return 0.0
    hits = sum(1 for v in vals if normalize_upc(v) is not None)
    return hits / len(vals)
