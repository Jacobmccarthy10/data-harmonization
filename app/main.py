"""Coverage Harmonization Studio — backend entry point."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import client, coverage, discover, export, health

app = FastAPI(
    title="Coverage Harmonization Studio API",
    description=(
        "Analyzes messy client retail/shipment exports, standardizes them into "
        "NIQ-compatible concepts, recommends a Discover pull, validates a clean "
        "Discover export, and runs a coverage comparison."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(client.router)
app.include_router(discover.router)
app.include_router(coverage.router)
app.include_router(export.router)
