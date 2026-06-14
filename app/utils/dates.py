"""Generic period parsing for client files.

Handles weekly dates, week-ending labels, month-year strings, fiscal
year/period combinations, and wide-format headers that embed a period plus a
metric label (for example ``Jan-25 Net Rev``).
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional, Tuple

import pandas as pd

MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_name) if m})

_MONTH_ALT = "|".join(sorted(MONTHS.keys(), key=len, reverse=True))

# 'Jan-25', 'Jan 2025', 'January 2025', '2025 Jan'
_MONTH_YEAR_RE = re.compile(
    rf"\b(?:(?P<mon>{_MONTH_ALT})[\s\-_/]*(?P<yr>\d{{2,4}})|(?P<yr2>\d{{4}})[\s\-_/]*(?P<mon2>{_MONTH_ALT}))\b",
    re.IGNORECASE,
)
# '01/25/2025', '2025-01-25', '01-25-25'
_DATE_RE = re.compile(
    r"\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{4}[/\-]\d{1,2}[/\-]\d{1,2})\b"
)
# '2025-01' / '2025/01' style year-month
_YEAR_MONTH_RE = re.compile(r"\b(\d{4})[\-/](\d{1,2})\b")
# 'FY25 P01', 'FY2025 P1'
_FY_P_RE = re.compile(r"\bfy\s*(\d{2,4})\s*p\s*(\d{1,2})\b", re.IGNORECASE)
# leading qualifiers stripped before date parsing: 'WE', 'W/E', 'Week Ending', ...
_WEEK_PREFIX_RE = re.compile(
    r"^\s*(?:w/?e\.?|wk\s*end(?:ing)?|week\s*end(?:ing)?(?:\s*date)?)\s*[:\-]?\s*",
    re.IGNORECASE,
)

# NIQ Discover period syntax: '1 w/e 12/28/24', '5 w/e 07/26/25', 'Jun 21 - 5 w/e 07/26/25'
# The leading 'N w/e' or 'N week ending' indicates an N-week period ending on the given date.
_NIQ_PERIOD_RE = re.compile(
    r"(?:^|[\s\-])(?P<weeks>\d{1,2})\s*w(?:k|eek)?s?\.?\s*[/]?\s*e(?:nd(?:ing)?)?\.?\s*"
    r"(?P<date>\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{4}[/\-]\d{1,2}[/\-]\d{1,2})",
    re.IGNORECASE,
)


def _fix_year(y: int) -> int:
    return y + 2000 if y < 100 else y


@dataclass
class ParsedPeriod:
    period_start: date
    period_end: date
    grain: str  # 'weekly' | 'monthly' | 'daily_date'
    raw: str


def month_bounds(year: int, month: int) -> Tuple[date, date]:
    last = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def parse_period_value(value: object) -> Optional[ParsedPeriod]:
    """Parse a single period cell into start/end dates and a grain hint.

    A plain date is treated as a week-ending date ('daily_date' grain hint —
    the caller decides weekly vs daily from the spacing of distinct values).
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    raw = str(value).strip()
    if not raw or raw.lower() in ("nan", "nat", "none"):
        return None

    if isinstance(value, (pd.Timestamp,)) or str(type(value)).endswith("datetime.datetime'>"):
        d = pd.Timestamp(value).date()
        return ParsedPeriod(d, d, "daily_date", raw)
    if isinstance(value, date):
        return ParsedPeriod(value, value, "daily_date", raw)

    # NIQ Discover multi-week period: 'Jun 21 - 5 w/e 07/26/25' or '1 w/e 12/28/24'
    m = _NIQ_PERIOD_RE.search(raw)
    if m:
        try:
            weeks = int(m.group("weeks"))
            ts = pd.to_datetime(m.group("date"), dayfirst=False)
            end = ts.date()
            start = end - timedelta(days=7 * weeks - 1)
            grain = "weekly" if weeks == 1 else "multi_week"
            return ParsedPeriod(start, end, grain, raw)
        except (ValueError, TypeError):
            pass

    s = _WEEK_PREFIX_RE.sub("", raw)
    was_week_label = s != raw

    m = _FY_P_RE.search(s)
    if m:
        year = _fix_year(int(m.group(1)))
        month = int(m.group(2))
        if 1 <= month <= 12:
            start, end = month_bounds(year, month)
            return ParsedPeriod(start, end, "monthly", raw)

    m = _DATE_RE.search(s)
    if m:
        try:
            ts = pd.to_datetime(m.group(1), dayfirst=False)
            d = ts.date()
            if was_week_label:
                return ParsedPeriod(d - timedelta(days=6), d, "weekly", raw)
            return ParsedPeriod(d, d, "daily_date", raw)
        except (ValueError, TypeError):
            pass

    m = _MONTH_YEAR_RE.search(s)
    if m:
        mon = (m.group("mon") or m.group("mon2")).lower()
        yr = _fix_year(int(m.group("yr") or m.group("yr2")))
        start, end = month_bounds(yr, MONTHS[mon])
        return ParsedPeriod(start, end, "monthly", raw)

    m = _YEAR_MONTH_RE.fullmatch(s) or _YEAR_MONTH_RE.search(s)
    if m and 1 <= int(m.group(2)) <= 12:
        start, end = month_bounds(int(m.group(1)), int(m.group(2)))
        return ParsedPeriod(start, end, "monthly", raw)

    # Last resort: let pandas try (catches ISO datetimes serialized as text).
    try:
        ts = pd.to_datetime(s)
        if pd.notna(ts):
            d = ts.date()
            return ParsedPeriod(d, d, "daily_date", raw)
    except (ValueError, TypeError):
        pass
    return None


def parse_fiscal_pair(year_val: object, month_val: object) -> Optional[ParsedPeriod]:
    """Build a monthly period from separate fiscal year + fiscal month values."""
    try:
        year = _fix_year(int(float(str(year_val))))
        month = int(float(str(month_val)))
    except (ValueError, TypeError):
        return None
    if not (1 <= month <= 12) or not (1990 <= year <= 2100):
        return None
    start, end = month_bounds(year, month)
    return ParsedPeriod(start, end, "monthly", f"FY{year} P{month:02d}")


def parse_wide_header(header: object) -> Optional[Tuple[ParsedPeriod, str]]:
    """Split a wide-format header into (period, residual metric label).

    'Jan-25 Net Rev' -> (Jan 2025 monthly period, 'Net Rev')
    'Week Ending 01/25/2025 Units' -> (week of 01/25, 'Units')
    Returns None when no period is embedded in the header.
    """
    if header is None:
        return None
    s = str(header).strip()

    for regex in (_MONTH_YEAR_RE, _DATE_RE, _FY_P_RE):
        m = regex.search(s)
        if m:
            period = parse_period_value(m.group(0))
            if period is None:
                continue
            residual = (s[: m.start()] + " " + s[m.end():]).strip(" -_/|")
            residual = _WEEK_PREFIX_RE.sub("", residual).strip(" -_/|")
            return period, residual
    return None


def infer_grain_from_dates(dates: list) -> str:
    """Infer weekly/monthly/unknown from the spacing of distinct period dates."""
    uniq = sorted(set(dates))
    if len(uniq) < 2:
        return "unknown"
    diffs = [(b - a).days for a, b in zip(uniq, uniq[1:])]
    diffs = [d for d in diffs if d > 0]
    if not diffs:
        return "unknown"
    diffs.sort()
    median = diffs[len(diffs) // 2]
    if 6 <= median <= 8:
        return "weekly"
    if 27 <= median <= 32:
        return "monthly"
    return "unknown"


def weekly_bounds(end: date) -> Tuple[date, date]:
    return end - timedelta(days=6), end
