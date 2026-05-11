"""SQL persistence for SDD artifacts and run metadata."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    select,
    update,
)
from sqlalchemy.engine import Engine

metadata = MetaData()

sdd_specs = Table(
    "sdd_specs",
    metadata,
    Column("spec_id", String(255), primary_key=True),
    Column("thread_id", String(255), nullable=False, index=True),
    Column("repo_owner", String(255), nullable=False),
    Column("repo_name", String(255), nullable=False),
    Column("issue_number", Integer, nullable=False),
    Column("payload", JSON().with_variant(Text(), "sqlite"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

sdd_plans = Table(
    "sdd_plans",
    metadata,
    Column("plan_id", String(255), primary_key=True),
    Column("spec_id", String(255), nullable=False, index=True),
    Column("payload", JSON().with_variant(Text(), "sqlite"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

sdd_subtasks = Table(
    "sdd_subtasks",
    metadata,
    Column("subtasks_id", String(255), primary_key=True),
    Column("plan_id", String(255), nullable=False, index=True),
    Column("payload", JSON().with_variant(Text(), "sqlite"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

sdd_runs = Table(
    "sdd_runs",
    metadata,
    Column("run_id", String(255), primary_key=True),
    Column("thread_id", String(255), nullable=False, index=True),
    Column("source", String(64), nullable=False),
    Column("status", String(64), nullable=False),
    Column("repo_owner", String(255), nullable=False),
    Column("repo_name", String(255), nullable=False),
    Column("issue_number", Integer, nullable=True),
    Column("pr_number", Integer, nullable=True),
    Column("ci_fix_rounds", Integer, nullable=False, default=0),
    Column("metadata_json", JSON().with_variant(Text(), "sqlite"), nullable=False, default={}),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)


def _normalize_database_url(url: str) -> str:
    if not url:
        return "sqlite:///open_swe.db"
    return url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    database_url = _normalize_database_url(os.getenv("DATABASE_URL", "sqlite:///open_swe.db"))
    return create_engine(database_url, future=True)


def _serialize_payload(payload: dict[str, Any]) -> Any:
    # SQLite Text fallback needs string payload.
    if _is_sqlite():
        return json.dumps(payload)
    return payload


@lru_cache(maxsize=1)
def _is_sqlite() -> bool:
    # DATABASE_URL is treated as process-static; changing it requires restart.
    return get_engine().dialect.name == "sqlite"


def _deserialize_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return {}
    if isinstance(payload, dict):
        return payload
    return {}


def init_storage() -> None:
    engine = get_engine()
    metadata.create_all(engine)


def _upsert(table: Table, row: dict[str, Any], key_column: str) -> None:
    now = datetime.now(UTC)
    row.setdefault("created_at", now)
    row["updated_at"] = now
    engine = get_engine()
    key = row[key_column]
    with engine.begin() as conn:
        existing = conn.execute(
            select(table.c[key_column]).where(table.c[key_column] == key)
        ).first()
        if existing:
            conn.execute(update(table).where(table.c[key_column] == key).values(**row))
        else:
            conn.execute(table.insert().values(**row))


def save_spec(
    *,
    spec_id: str,
    thread_id: str,
    repo_owner: str,
    repo_name: str,
    issue_number: int,
    payload: dict[str, Any],
) -> None:
    init_storage()
    _upsert(
        sdd_specs,
        {
            "spec_id": spec_id,
            "thread_id": thread_id,
            "repo_owner": repo_owner,
            "repo_name": repo_name,
            "issue_number": issue_number,
            "payload": _serialize_payload(payload),
        },
        "spec_id",
    )


def save_plan(*, plan_id: str, spec_id: str, payload: dict[str, Any]) -> None:
    init_storage()
    _upsert(
        sdd_plans,
        {"plan_id": plan_id, "spec_id": spec_id, "payload": _serialize_payload(payload)},
        "plan_id",
    )


def save_subtasks(*, subtasks_id: str, plan_id: str, payload: dict[str, Any]) -> None:
    init_storage()
    _upsert(
        sdd_subtasks,
        {
            "subtasks_id": subtasks_id,
            "plan_id": plan_id,
            "payload": _serialize_payload(payload),
        },
        "subtasks_id",
    )


def save_run(
    *,
    run_id: str,
    thread_id: str,
    source: str,
    status: str,
    repo_owner: str,
    repo_name: str,
    issue_number: int | None = None,
    pr_number: int | None = None,
    ci_fix_rounds: int = 0,
    metadata_json: dict[str, Any] | None = None,
) -> None:
    init_storage()
    _upsert(
        sdd_runs,
        {
            "run_id": run_id,
            "thread_id": thread_id,
            "source": source,
            "status": status,
            "repo_owner": repo_owner,
            "repo_name": repo_name,
            "issue_number": issue_number,
            "pr_number": pr_number,
            "ci_fix_rounds": ci_fix_rounds,
            "metadata_json": _serialize_payload(metadata_json or {}),
        },
        "run_id",
    )


def get_latest_run_for_pr(repo_owner: str, repo_name: str, pr_number: int) -> dict[str, Any] | None:
    init_storage()
    engine = get_engine()
    stmt = (
        select(sdd_runs)
        .where(
            sdd_runs.c.repo_owner == repo_owner,
            sdd_runs.c.repo_name == repo_name,
            sdd_runs.c.pr_number == pr_number,
        )
        .order_by(sdd_runs.c.updated_at.desc())
        .limit(1)
    )
    with engine.begin() as conn:
        row = conn.execute(stmt).mappings().first()
        if not row:
            return None
        data = dict(row)
        data["metadata_json"] = _deserialize_payload(data.get("metadata_json"))
        return data


def increment_ci_fix_rounds(run_id: str) -> int:
    init_storage()
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(select(sdd_runs).where(sdd_runs.c.run_id == run_id)).mappings().first()
        if not row:
            raise ValueError(f"Run not found: {run_id}")
        current = int(row.get("ci_fix_rounds") or 0)
        new_value = current + 1
        conn.execute(
            update(sdd_runs)
            .where(sdd_runs.c.run_id == run_id)
            .values(ci_fix_rounds=new_value, updated_at=datetime.now(UTC))
        )
        return new_value
