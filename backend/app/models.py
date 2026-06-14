"""Request models. Response payloads are built as dicts by the services.

The normalized data model intentionally reserves comparison/conversion fields
(comparison_mode, conversion_required, conversion_rule_id, conversion_note)
for future metric conversion rules — v1 never applies guessed conversions.
"""
from __future__ import annotations

from pydantic import BaseModel


class CoverageRunRequest(BaseModel):
    analysis_id: str
    discover_id: str
