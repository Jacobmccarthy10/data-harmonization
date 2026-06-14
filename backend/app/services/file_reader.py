"""Read client/Discover uploads (.xlsx, .xls, .csv) into a DataFrame.

Handles multi-sheet workbooks (picks the first sheet with meaningful tabular
data) and files where the header row is not the first row.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

SUPPORTED_EXTENSIONS = (".xlsx", ".xls", ".csv")


@dataclass
class LoadedFile:
    df: pd.DataFrame
    file_name: str
    sheet_name: Optional[str]
    sheet_names: List[str] = field(default_factory=list)
    header_row: int = 0
    notes: List[str] = field(default_factory=list)


class FileReadError(Exception):
    pass


def _meaningful_score(df: pd.DataFrame) -> float:
    """Score a sheet by how much real tabular data it holds."""
    if df.empty:
        return 0.0
    non_null = df.notna().sum().sum()
    return float(non_null) * min(df.shape[1], 40)


def _find_header_row(raw: pd.DataFrame, max_scan: int = 10) -> int:
    """Find the first row that looks like a header: mostly non-null strings,
    followed by rows of data."""
    best_row = 0
    best_score = -1.0
    limit = min(max_scan, len(raw))
    for i in range(limit):
        row = raw.iloc[i]
        non_null = row.notna().sum()
        if non_null < 2:
            continue
        str_cells = sum(1 for v in row if isinstance(v, str) and v.strip())
        uniq = row.dropna().astype(str).nunique()
        score = non_null + str_cells * 2 + (2 if uniq == non_null else 0) - i * 0.5
        if score > best_score:
            best_score = score
            best_row = i
    return best_row


def _frame_from_raw(raw: pd.DataFrame, header_row: int) -> pd.DataFrame:
    header = [str(v).strip() if pd.notna(v) else f"Unnamed_{j}" for j, v in enumerate(raw.iloc[header_row])]
    df = raw.iloc[header_row + 1:].copy()
    df.columns = header
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    df = df.reset_index(drop=True)
    # Restore numeric dtypes lost by reading with header=None — but skip
    # identifier-like columns where leading zeros are significant (UPC/GTIN/
    # item codes/SKUs).
    id_pattern = re.compile(
        r"\b(upc|gtin|barcode|ean|plu|item|product|sku|material|article)"
        r"|\b(code|id|number|num|no|key|#)\b",
        re.IGNORECASE,
    )
    # Strip currency symbols, thousands separators, and parens (accounting
    # negatives) before attempting numeric coercion — client exports often
    # format dollars as "$2,044.05" or "(123.45)".
    currency_re = re.compile(r"[\$£€¥,]")
    paren_re = re.compile(r"^\(([\d.,]+)\)$")
    def _try_numeric(s: pd.Series) -> pd.Series:
        if s.dtype != object:
            return s
        stripped = s.astype(str).str.strip()
        stripped = stripped.str.replace(currency_re, "", regex=True)
        stripped = stripped.str.replace(paren_re, r"-\1", regex=True)
        return pd.to_numeric(stripped, errors="coerce")

    for c in df.columns:
        if df[c].dtype != object:
            continue
        if id_pattern.search(str(c)):
            continue
        converted = _try_numeric(df[c])
        if converted.notna().sum() >= max(1, int(df[c].notna().sum() * 0.95)):
            df[c] = converted
    return df


def load_tabular_file(content: bytes, file_name: str) -> LoadedFile:
    """Load an uploaded file into a DataFrame, choosing the best sheet."""
    lower = file_name.lower()
    if not lower.endswith(SUPPORTED_EXTENSIONS):
        raise FileReadError(
            f"Unsupported file type for '{file_name}'. Supported: .xlsx, .xls, .csv"
        )

    if lower.endswith(".csv"):
        try:
            raw = pd.read_csv(io.BytesIO(content), header=None, dtype=object,
                              skip_blank_lines=False, encoding_errors="replace")
        except Exception as exc:  # pragma: no cover - defensive
            raise FileReadError(f"Could not read CSV file: {exc}") from exc
        header_row = _find_header_row(raw)
        df = _frame_from_raw(raw, header_row)
        if df.empty:
            raise FileReadError("The CSV file contains no tabular data.")
        return LoadedFile(df=df, file_name=file_name, sheet_name=None,
                          sheet_names=[], header_row=header_row)

    engine = "xlrd" if lower.endswith(".xls") else "openpyxl"
    try:
        xl = pd.ExcelFile(io.BytesIO(content), engine=engine)
    except Exception as exc:
        raise FileReadError(f"Could not open workbook: {exc}") from exc

    best: Optional[LoadedFile] = None
    best_score = 0.0
    for sheet in xl.sheet_names:
        try:
            raw = xl.parse(sheet, header=None, dtype=object)
        except Exception:
            continue
        if raw.empty:
            continue
        header_row = _find_header_row(raw)
        df = _frame_from_raw(raw, header_row)
        score = _meaningful_score(df)
        if score > best_score:
            best_score = score
            best = LoadedFile(df=df, file_name=file_name, sheet_name=sheet,
                              sheet_names=list(xl.sheet_names), header_row=header_row)

    if best is None or best.df.empty:
        raise FileReadError("No sheet with meaningful tabular data was found.")
    if len(best.sheet_names) > 1:
        best.notes.append(
            f"Workbook has {len(best.sheet_names)} sheets; used '{best.sheet_name}' "
            "(first sheet with meaningful tabular data)."
        )
    if best.header_row > 0:
        best.notes.append(f"Header detected on row {best.header_row + 1} of the sheet.")
    return best
