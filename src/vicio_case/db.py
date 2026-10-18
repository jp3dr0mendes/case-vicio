from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS classification_runs (
    run_id UUID PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL,
    dataset_sha256 TEXT NOT NULL,
    mode TEXT NOT NULL,
    model TEXT,
    total_questions INTEGER NOT NULL,
    published_count INTEGER NOT NULL,
    review_count INTEGER NOT NULL,
    outside_count INTEGER NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS classification_decisions (
    run_id UUID NOT NULL REFERENCES classification_runs(run_id) ON DELETE CASCADE,
    question_id TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('publicar','revisar','fora')),
    central_topic_id INTEGER,
    extras_topic_ids TEXT NOT NULL DEFAULT '',
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    reason TEXT NOT NULL DEFAULT '',
    trace JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (run_id, question_id)
);
CREATE INDEX IF NOT EXISTS idx_decisions_question_id ON classification_decisions(question_id);
"""


def persist_run(
    dataset_sha256: str,
    mode: str,
    model: str | None,
    rows: list[dict[str, Any]],
    trace_by_id: dict[str, Any],
) -> str | None:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        return None
    try:
        import psycopg
        from psycopg.types.json import Jsonb
    except ImportError as exc:  # pragma: no cover - dependency is installed in Docker
        raise RuntimeError("DATABASE_URL foi definido, mas psycopg não está instalado") from exc

    run_id = str(uuid.uuid4())
    counts = {decision: sum(row["decisao"] == decision for row in rows) for decision in ["publicar", "revisar", "fora"]}
    with psycopg.connect(database_url, connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            for statement in SCHEMA_SQL.split(";"):
                if statement.strip():
                    cursor.execute(statement)
            cursor.execute(
                """INSERT INTO classification_runs
                (run_id, started_at, dataset_sha256, mode, model, total_questions,
                 published_count, review_count, outside_count, status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (run_id, datetime.now(timezone.utc), dataset_sha256, mode, model,
                 len(rows), counts["publicar"], counts["revisar"], counts["fora"], "completed"),
            )
            for row in rows:
                central = row.get("tema_central_id")
                central = int(central) if str(central).strip() else None
                cursor.execute(
                    """INSERT INTO classification_decisions
                    (run_id, question_id, decision, central_topic_id, extras_topic_ids,
                     confidence, reason, trace)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (run_id, row["id"], row["decisao"], central, str(row.get("extras_ids", "")),
                     float(row["confianca"]), str(row.get("motivo", "")),
                     Jsonb(trace_by_id.get(row["id"], {}))),
                )
        connection.commit()
    return run_id
