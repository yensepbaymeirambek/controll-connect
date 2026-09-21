"""ChatGPT-backed chat and dashboard-card authoring.

The model never emits figures. It replies in prose and may propose card specs
describing what to filter, group and count; `analytics.execute_card` computes
the actual numbers from real records. A card therefore cannot contain data that
is not in the workspace.
"""
import json
import logging
from typing import Any

from openai import APIError, APITimeoutError, AsyncOpenAI, AuthenticationError, RateLimitError

from .analytics import CARD_KINDS, GROUPABLE_FIELDS
from .settings import Settings

logger = logging.getLogger(__name__)

MAX_CARDS = 6
MAX_HISTORY = 12

SYSTEM_PROMPT = f"""You are the analyst inside a workspace that aggregates work items from connected tools.

You are given a statistical summary of the current issue set and a sample of records.
You are NOT given every record, so never state a figure you were not shown.

Reply with JSON of this shape:
{{"answer": string, "cards": [card, ...]}}

`answer` is one to three sentences of plain prose answering the user. Do not list
numbers in it that you cannot see in the summary.

`cards` is how you build a dashboard. Emit cards whenever the user asks to see,
show, chart, break down, compare or track something; otherwise use an empty list.
You describe WHAT to compute and the backend computes it, so never put counts or
values in a card yourself.

A card is one of:
  {{"kind": "metric", "title": str, "filter": filter, "detail": str}}
  {{"kind": "bar",    "title": str, "filter": filter, "group_by": field, "limit": int}}
  {{"kind": "line",   "title": str, "filter": filter, "group_by": field, "limit": int}}
  {{"kind": "table",  "title": str, "filter": filter, "columns": [str], "sort": str, "order": "asc"|"desc", "limit": int}}

kind must be one of {list(CARD_KINDS)}.
group_by and sort must be one of {list(GROUPABLE_FIELDS)} or a record field such as "due", "created", "updated", "id", "title".
filter is an object; every key is optional:
  {{"overdue": true, "state": "todo"|"in_progress"|"done", "status": str|[str],
    "assignee": str|[str], "project": str|[str], "type": str|[str], "priority": str|[str]}}
Filter values must be values that appear in the summary. Emit at most {MAX_CARDS} cards.

If the workspace holds no records, say so plainly and emit no cards."""


class LLMError(Exception):
    """Raised when the model cannot be reached or returns something unusable."""


def _build_client(settings: Settings) -> AsyncOpenAI:
    kwargs: dict[str, Any] = {"api_key": settings.openai_api_key, "timeout": settings.openai_timeout}
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return AsyncOpenAI(**kwargs)


def _clean_cards(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [card for card in value[:MAX_CARDS] if isinstance(card, dict) and card.get("kind") in CARD_KINDS]


async def answer_with_cards(
    messages: list[dict[str, str]],
    summary: dict[str, Any],
    sample: list[dict[str, Any]],
    settings: Settings,
) -> dict[str, Any]:
    """Run one chat turn. Returns prose plus unexecuted card specs."""
    client = _build_client(settings)
    context = json.dumps({"summary": summary, "sample_records": sample}, ensure_ascii=False, default=str)
    history = [
        {"role": message["role"], "content": message["content"]}
        for message in messages[-MAX_HISTORY:]
        if message.get("role") in ("user", "assistant") and message.get("content")
    ]

    try:
        completion = await client.chat.completions.create(
            model=settings.openai_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "system", "content": f"Current workspace data:\n{context}"},
                *history,
            ],
        )
    except AuthenticationError as error:
        raise LLMError("OpenAI rejected the API key.") from error
    except RateLimitError as error:
        raise LLMError("OpenAI rate limit reached. Try again shortly.") from error
    except APITimeoutError as error:
        raise LLMError(f"OpenAI timed out after {settings.openai_timeout:.0f}s.") from error
    except APIError as error:
        raise LLMError(f"OpenAI request failed: {error}") from error
    finally:
        await client.close()

    content = completion.choices[0].message.content if completion.choices else None
    if not content:
        raise LLMError("OpenAI returned an empty response.")

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as error:
        logger.warning("model returned non-JSON content: %s", content[:200])
        raise LLMError("OpenAI returned malformed JSON.") from error

    if not isinstance(parsed, dict) or not isinstance(parsed.get("answer"), str):
        raise LLMError("OpenAI response did not match the expected shape.")

    return {"answer": parsed["answer"], "cards": _clean_cards(parsed.get("cards"))}
