import base64
import binascii
import json
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import tuple_
from sqlalchemy.ext.asyncio import AsyncSession


def serialize(row: Any) -> dict[str, Any]:
    data = dict(row)
    for key, value in data.items():
        if key.endswith("_id") and isinstance(value, int):
            data[key] = str(value)
        elif isinstance(value, datetime):
            data[key] = value.isoformat()
    return data


def now() -> str:
    return datetime.now(UTC).isoformat()


def valid_range(start: datetime | None, end: datetime | None) -> None:
    if (start and start.tzinfo is None) or (end and end.tzinfo is None):
        raise HTTPException(400, "시각에는 시간대를 포함해야 합니다.")
    if start and end and start >= end:
        raise HTTPException(400, "from은 to보다 빨라야 합니다.")


def encode_cursor(value: datetime | None, row_id: int) -> str:
    payload = {"time": value.isoformat() if value else None, "id": row_id}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime | None, int]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        row_id = payload["id"]
        if not isinstance(row_id, int) or row_id < 1:
            raise ValueError
        timestamp = datetime.fromisoformat(payload["time"]) if payload["time"] else None
        if timestamp and timestamp.tzinfo is None:
            raise ValueError
        return timestamp, row_id
    except (ValueError, KeyError, TypeError, UnicodeDecodeError, binascii.Error) as exc:
        raise HTTPException(400, "잘못된 cursor입니다.") from exc


async def page(
    db: AsyncSession,
    stmt: Any,
    id_column: Any,
    time_column: Any | None,
    limit: int,
    cursor: str | None,
) -> dict[str, Any]:
    if cursor:
        cursor_time, cursor_id = decode_cursor(cursor)
        if time_column is None:
            if cursor_time is not None:
                raise HTTPException(400, "잘못된 cursor입니다.")
            stmt = stmt.where(id_column < cursor_id)
        else:
            if cursor_time is None:
                raise HTTPException(400, "잘못된 cursor입니다.")
            stmt = stmt.where(tuple_(time_column, id_column) < (cursor_time, cursor_id))
    if time_column is None:
        stmt = stmt.order_by(id_column.desc())
    else:
        stmt = stmt.order_by(time_column.desc(), id_column.desc())
    rows = (await db.execute(stmt.limit(limit + 1))).mappings().all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    last = rows[-1] if rows else None
    return {
        "items": [serialize(row) for row in rows],
        "next_cursor": encode_cursor(
            last[time_column.key] if time_column is not None else None, last[id_column.key]
        )
        if has_more and last
        else None,
    }


async def all_rows(db: AsyncSession, stmt: Any) -> list[dict[str, Any]]:
    return [serialize(row) for row in (await db.execute(stmt)).mappings().all()]


def grouped(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        parent_id = row.pop(key)
        result[parent_id].append(row)
    return result
