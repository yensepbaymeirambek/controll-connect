from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import analytics
from .connectors.registry import Workspace
from .llm import LLMError, answer_with_cards
from .settings import get_settings

app = FastAPI(title="Signal Connector API", version="0.2.0")

settings = get_settings()
workspace = Workspace(settings)

# Direct browser calls need CORS; requests routed through the vite/nginx proxy
# are same-origin and unaffected.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# How many records the model sees. The rest it reasons about via the summary.
SAMPLE_SIZE = 40


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    refresh: bool = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "timestamp": _now().isoformat()}


@app.get("/api/connectors")
async def list_connectors() -> dict[str, Any]:
    return {
        "connectors": await workspace.describe(),
        "configured": bool(workspace.ids()),
    }


@app.get("/api/metrics")
async def workspace_metrics(refresh: bool = False) -> dict[str, Any]:
    records, errors = await workspace.records(refresh=refresh)
    now = _now()
    return {
        "metrics": analytics.compute_metrics(records, now),
        "chart": analytics.compute_chart(records, now),
        "breakdown": {
            "by_state": analytics.execute_card({"kind": "bar", "title": "By state", "group_by": "state"}, records, now),
            "by_assignee": analytics.execute_card({"kind": "bar", "title": "Open work by assignee", "filter": {"state": ["todo", "in_progress"]}, "group_by": "assignee", "limit": 8}, records, now),
        },
        "last_sync": workspace.last_sync_iso(),
        "errors": errors,
        "configured": bool(workspace.ids()),
    }


@app.post("/api/chat")
async def chat(request: ChatRequest) -> dict[str, Any]:
    records, errors = await workspace.records(refresh=request.refresh)
    now = _now()
    base: dict[str, Any] = {
        "cards": [],
        "errors": errors,
        "generated_at": now.isoformat(),
        "record_count": len(records),
    }

    if not workspace.ids():
        return {**base, "answer": "No connectors are configured. Set JIRA_MCP_URL to connect Jira.", "mode": "unconfigured"}
    if not settings.llm_enabled:
        return {**base, "answer": "Chat needs an OpenAI key. Set OPENAI_API_KEY to enable it.", "mode": "unconfigured"}

    try:
        result = await answer_with_cards(
            [message.model_dump() for message in request.messages],
            analytics.summarize_for_model(records, now),
            records[:SAMPLE_SIZE],
            settings,
        )
    except LLMError as error:
        # Surface the reason inline instead of a 500, so the UI can show it.
        return {**base, "answer": str(error), "mode": "error"}

    cards = [card for card in (analytics.execute_card(spec, records, now) for spec in result["cards"]) if card]
    return {**base, "answer": result["answer"], "cards": cards, "mode": "llm"}
