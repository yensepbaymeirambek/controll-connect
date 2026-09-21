from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .connectors import registry
from .llm import LLMError, answer_question
from .settings import get_settings

app = FastAPI(title="Signal Connector API", version="0.1.0")

settings = get_settings()

# Direct browser calls need CORS; requests routed through the vite/nginx proxy
# are same-origin and unaffected.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dashboard payload. Values are still local-mode constants; they move behind the
# connector registry once a live adapter lands.
METRICS = [
    {"id": "tasks_completed", "label": "Tasks completed", "value": "428", "change": "+18.4%", "detail": "vs. previous period", "direction": "up"},
    {"id": "open_work", "label": "Open work", "value": "164", "change": "-6.2%", "detail": "vs. previous period", "direction": "down"},
    {"id": "contributors", "label": "Active contributors", "value": "32", "change": "+4", "detail": "this month", "direction": "up"},
    {"id": "freshness", "label": "Data freshness", "value": "12 min", "change": "Healthy", "detail": "last sync", "direction": "flat"},
]

CHART = {
    "y_max": 200,
    "labels": ["Aug 23", "Aug 30", "Sep 06", "Sep 13", "Sep 20"],
    "series": [
        {"id": "completed", "label": "Completed", "points": [32, 55, 48, 72, 86, 95, 121, 140, 163, 175]},
        {"id": "created", "label": "Created", "points": [16, 34, 28, 47, 55, 66, 74, 84, 96, 104]},
    ],
}

INSIGHT = {
    "headline": "Delivery pace is up 18% this month",
    "detail": "Frontend and Platform teams are driving the change.",
}

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
    return registry.describe_connectors()

@app.get("/api/metrics")
def workspace_metrics() -> dict[str, Any]:
    return {"metrics": METRICS, "chart": CHART, "insight": INSIGHT}

LOCAL_MODE_ANSWER = {
    "answer": "Local mode: set OPENAI_API_KEY to answer this with ChatGPT.",
    "rows": [{"team": "Platform", "overdue": 8}, {"team": "Frontend", "overdue": 6}, {"team": "Growth", "overdue": 4}],
}

@app.post("/api/query")
async def query_workspace(request: QueryRequest) -> dict[str, Any]:
    sources = request.sources or registry.connector_ids()
    base = {
        "question": request.question,
        "sources": sources,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    if not settings.llm_enabled:
        return {**base, **LOCAL_MODE_ANSWER, "mode": "local"}

    records = await registry.collect_records(sources)
    try:
        result = await answer_question(request.question, records, settings)
    except LLMError as error:
        # Surface the reason instead of a 500 so the UI can show it inline.
        return {**base, "answer": str(error), "rows": [], "mode": "error"}
    return {**base, **result, "mode": "llm"}

@app.post("/api/export")
def export_data(request: ExportRequest) -> dict[str, Any]:
    return {"status": "ready", "source": request.source, "format": request.format, "download_url": "/api/exports/latest"}
