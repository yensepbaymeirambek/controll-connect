import os
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Signal Connector API", version="0.1.0")

# Direct browser calls need CORS; requests routed through the vite/nginx proxy
# are same-origin and unaffected.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SOURCES = [
    {"id": "jira", "name": "Jira Software", "status": "connected", "last_sync": "12 min ago", "records": 1248},
    {"id": "asana", "name": "Asana", "status": "connected", "last_sync": "18 min ago", "records": 863},
    {"id": "linear", "name": "Linear", "status": "connected", "last_sync": "1 hr ago", "records": 421},
]

class QueryRequest(BaseModel):
    question: str
    sources: list[str] | None = None

class ExportRequest(BaseModel):
    source: str
    format: str = "json"
    filters: dict[str, Any] = {}

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}

@app.get("/api/connectors")
def list_connectors() -> list[dict[str, Any]]:
    return SOURCES

@app.post("/api/query")
def query_workspace(request: QueryRequest) -> dict[str, Any]:
    # Local mode returns a stable shape until an LLM provider is configured.
    return {
        "question": request.question,
        "answer": "I found 18 overdue issues across 3 teams.",
        "sources": request.sources or [source["id"] for source in SOURCES],
        "rows": [{"team": "Platform", "overdue": 8}, {"team": "Frontend", "overdue": 6}, {"team": "Growth", "overdue": 4}],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

@app.post("/api/export")
def export_data(request: ExportRequest) -> dict[str, Any]:
    return {"status": "ready", "source": request.source, "format": request.format, "download_url": "/api/exports/latest"}
