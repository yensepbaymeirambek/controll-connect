"""Aggregations over normalized workspace records.

Every number the dashboard shows is computed here from real records. The model
never produces figures: it emits a card spec (what to filter, group and count)
and this module executes it, so a card cannot contain invented data.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

GROUPABLE_FIELDS = ("assignee", "project", "status", "state", "type", "priority", "source")
CARD_KINDS = ("metric", "bar", "line", "table")
DEFAULT_COLUMNS = ("id", "title", "status", "assignee", "due")


def parse_date(value: Any) -> datetime | None:
    """Parse the date formats Jira and friends emit, tolerating junk."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    # "+0300" -> "+03:00", which fromisoformat wants on older shapes.
    if len(text) > 5 and text[-5] in "+-" and text[-3] != ":":
        text = f"{text[:-2]}:{text[-2:]}"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.strptime(text[:10], "%Y-%m-%d")
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def is_overdue(record: dict[str, Any], now: datetime) -> bool:
    if record.get("state") == "done":
        return False
    due = parse_date(record.get("due"))
    return due is not None and due < now


def apply_filter(records: list[dict[str, Any]], spec: dict[str, Any] | None, now: datetime) -> list[dict[str, Any]]:
    """Filter records by a card spec. Unknown keys are ignored, not guessed at."""
    if not spec:
        return records
    result = records
    if spec.get("overdue") is True:
        result = [record for record in result if is_overdue(record, now)]
    for field in ("state", "status", "assignee", "project", "type", "priority", "source"):
        wanted = spec.get(field)
        if wanted in (None, "", []):
            continue
        allowed = {str(item).lower() for item in (wanted if isinstance(wanted, list) else [wanted])}
        result = [record for record in result if str(record.get(field, "")).lower() in allowed]
    return result


def _counts_by(records: list[dict[str, Any]], field: str, limit: int) -> list[dict[str, Any]]:
    counter = Counter(str(record.get(field) or "Unspecified") for record in records)
    return [{"label": label, "value": value} for label, value in counter.most_common(limit)]


def compute_metrics(records: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    open_records = [record for record in records if record.get("state") != "done"]
    overdue = [record for record in records if is_overdue(record, now)]
    assignees = {record.get("assignee") for record in open_records if record.get("assignee") and record["assignee"] != "Unassigned"}
    done = len(records) - len(open_records)

    return [
        {"id": "total", "label": "Issues in scope", "value": str(len(records)), "detail": "matched by the sync query", "change": "", "direction": "flat"},
        {"id": "open", "label": "Open work", "value": str(len(open_records)), "detail": f"{done} done", "change": "", "direction": "flat"},
        {"id": "overdue", "label": "Overdue", "value": str(len(overdue)), "detail": "past due date", "change": "", "direction": "down" if overdue else "flat"},
        {"id": "contributors", "label": "Active assignees", "value": str(len(assignees)), "detail": "on open work", "change": "", "direction": "flat"},
    ]


def compute_chart(records: list[dict[str, Any]], now: datetime, weeks: int = 8) -> dict[str, Any]:
    """Weekly created vs. resolved counts, derived from record timestamps."""
    start = (now - timedelta(weeks=weeks - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    buckets = [start + timedelta(weeks=index) for index in range(weeks)]
    created = [0] * weeks
    resolved = [0] * weeks

    def bucket_index(moment: datetime | None) -> int | None:
        if moment is None or moment < start:
            return None
        index = int((moment - start).days // 7)
        return index if 0 <= index < weeks else None

    for record in records:
        index = bucket_index(parse_date(record.get("created")))
        if index is not None:
            created[index] += 1
        if record.get("state") == "done":
            index = bucket_index(parse_date(record.get("updated")))
            if index is not None:
                resolved[index] += 1

    y_max = max([*created, *resolved, 1])
    return {
        "y_max": y_max,
        "labels": [bucket.strftime("%b %d") for bucket in buckets],
        "series": [
            {"id": "created", "label": "Created", "points": created},
            {"id": "resolved", "label": "Resolved", "points": resolved},
        ],
    }


def execute_card(spec: dict[str, Any], records: list[dict[str, Any]], now: datetime) -> dict[str, Any] | None:
    """Turn one model-authored card spec into a card carrying computed data."""
    kind = spec.get("kind")
    if kind not in CARD_KINDS:
        return None

    title = str(spec.get("title") or "Untitled")
    rows = apply_filter(records, spec.get("filter"), now)
    limit = max(1, min(int(spec.get("limit") or 8), 50))

    if kind == "metric":
        return {"kind": "metric", "title": title, "value": str(len(rows)), "detail": spec.get("detail") or f"of {len(records)} issues"}

    if kind in ("bar", "line"):
        field = spec.get("group_by")
        if field not in GROUPABLE_FIELDS:
            return None
        data = _counts_by(rows, field, limit)
        if not data:
            return None
        return {"kind": kind, "title": title, "group_by": field, "data": data}

    columns = [column for column in (spec.get("columns") or DEFAULT_COLUMNS) if isinstance(column, str)]
    sort_field = spec.get("sort") if isinstance(spec.get("sort"), str) else None
    if sort_field:
        reverse = str(spec.get("order", "asc")).lower() == "desc"
        rows = sorted(rows, key=lambda record: (record.get(sort_field) is None, str(record.get(sort_field) or "")), reverse=reverse)
    return {
        "kind": "table",
        "title": title,
        "columns": columns,
        "rows": [{column: record.get(column) for column in columns} for record in rows[:limit]],
    }


def summarize_for_model(records: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    """Compact picture of the dataset, so the model can pick fields without seeing every issue."""
    return {
        "total_issues": len(records),
        "overdue": sum(1 for record in records if is_overdue(record, now)),
        "groupable_fields": list(GROUPABLE_FIELDS),
        "states": _counts_by(records, "state", 10),
        "statuses": _counts_by(records, "status", 15),
        "projects": _counts_by(records, "project", 15),
        "assignees": _counts_by(records, "assignee", 20),
        "types": _counts_by(records, "type", 15),
        "priorities": _counts_by(records, "priority", 10),
    }
