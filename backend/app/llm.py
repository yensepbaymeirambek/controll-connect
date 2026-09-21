"""ChatGPT-backed answering for workspace questions.

The model only summarizes records handed to it by the connector layer, so an
answer never invents work items that are not in the workspace.
"""
import json
import logging
from typing import Any

from openai import APIError, APITimeoutError, AsyncOpenAI, AuthenticationError, RateLimitError

from .settings import Settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the analyst inside a work-data workspace that aggregates Jira, Asana and Linear.

You answer questions using ONLY the records provided in the user message. Rules:
- Never invent issues, people, teams or numbers that are absent from the records.
- If the records cannot answer the question, say so plainly in `answer`.
- Keep `answer` to one or two sentences of plain prose.
- Put any supporting breakdown in `rows` as a list of flat objects sharing the same keys.
- Return an empty `rows` list when a table adds nothing.

Respond with JSON of the shape: {"answer": string, "rows": [object, ...]}"""


class LLMError(Exception):
    """Raised when the model cannot be reached or returns something unusable."""


def _build_client(settings: Settings) -> AsyncOpenAI:
    kwargs: dict[str, Any] = {"api_key": settings.openai_api_key, "timeout": settings.openai_timeout}
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return AsyncOpenAI(**kwargs)


def _coerce_rows(value: Any) -> list[dict[str, Any]]:
    """Keep only flat, table-shaped rows; the model occasionally nests things."""
    if not isinstance(value, list):
        return []
    return [
        {key: item[key] for key in item if not isinstance(item[key], (dict, list))}
        for item in value
        if isinstance(item, dict)
    ]


async def answer_question(
    question: str,
    records: list[dict[str, Any]],
    settings: Settings,
) -> dict[str, Any]:
    client = _build_client(settings)
    user_content = json.dumps({"question": question, "records": records}, ensure_ascii=False)

    try:
        completion = await client.chat.completions.create(
            model=settings.openai_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
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

    return {"answer": parsed["answer"], "rows": _coerce_rows(parsed.get("rows"))}
