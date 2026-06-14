"""CSV export helpers."""
from __future__ import annotations

import io

import pandas as pd
from fastapi.responses import StreamingResponse


def csv_response(df: pd.DataFrame, file_name: str) -> StreamingResponse:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )
