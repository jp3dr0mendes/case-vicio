"""Trilha de auditoria no PostgreSQL (opcional: só roda se DATABASE_URL estiver definido).

Cada execução é append-only (novo run_id). Reprocessar o mesmo conjunto não sobrescreve o
histórico; execuções com saída idêntica ficam visíveis pela coluna publicacao_sha256.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

SCHEMA_SQL = [
    """CREATE TABLE IF NOT EXISTS classification_runs (
        run_id UUID PRIMARY KEY,
        created_at TIMESTAMPTZ NOT NULL,
        mode TEXT NOT NULL,
        classifiers TEXT NOT NULL,
        prompt_version TEXT,
        policy_version TEXT,
        input_sha256 JSONB NOT NULL,
        publicacao_sha256 TEXT NOT NULL,
        total_questions INTEGER NOT NULL,
        published_count INTEGER NOT NULL,
        review_count INTEGER NOT NULL,
        outside_count INTEGER NOT NULL,
        metadata JSONB NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS classification_decisions (
        run_id UUID NOT NULL REFERENCES classification_runs(run_id) ON DELETE CASCADE,
        question_id TEXT NOT NULL,
        decision TEXT NOT NULL CHECK (decision IN ('publicar','revisar','fora')),
        central_topic_id INTEGER,
        extras_topic_ids TEXT NOT NULL DEFAULT '',
        confidence DOUBLE PRECISION NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
        reason TEXT NOT NULL DEFAULT '',
        stratum TEXT NOT NULL,
        trace JSONB NOT NULL DEFAULT '{}'::jsonb,
        PRIMARY KEY (run_id, question_id),
        CHECK ((decision = 'fora') = (central_topic_id IS NULL))
    )""",
    "CREATE INDEX IF NOT EXISTS idx_decisions_question ON classification_decisions(question_id)",
    "CREATE INDEX IF NOT EXISTS idx_runs_output ON classification_runs(publicacao_sha256)",
]


def persist_run(metadata: dict[str, Any], rows: list[dict[str, Any]]) -> str | None:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        return None
    import psycopg
    from psycopg.types.json import Jsonb

    run_id = str(uuid.uuid4())
    counts = {d: sum(r["decisao"] == d for r in rows) for d in ("publicar", "revisar", "fora")}
    with psycopg.connect(database_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            for stmt in SCHEMA_SQL:
                cur.execute(stmt)
            cur.execute(
                """INSERT INTO classification_runs (run_id, created_at, mode, classifiers, prompt_version,
                policy_version, input_sha256, publicacao_sha256, total_questions, published_count,
                review_count, outside_count, metadata) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (run_id, datetime.now(timezone.utc), metadata["mode"], ",".join(metadata["classificadores"]),
                 metadata.get("prompt_version"), metadata.get("policy", {}).get("versao"),
                 Jsonb(metadata["input_sha256"]), metadata["publicacao_sha256"], len(rows),
                 counts["publicar"], counts["revisar"], counts["fora"],
                 Jsonb(json.loads(json.dumps(metadata, default=str)))),
            )
            cur.executemany(
                """INSERT INTO classification_decisions (run_id, question_id, decision, central_topic_id,
                extras_topic_ids, confidence, reason, stratum, trace) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                [(run_id, r["id"], r["decisao"],
                  int(r["tema_central_id"]) if str(r["tema_central_id"]).strip() else None,
                  r["extras_ids"], float(r["confianca"]), r["motivo"], r["estrato"],
                  Jsonb(json.loads(json.dumps(r.get("trace", {}), default=str)))) for r in rows],
            )
        conn.commit()
    return run_id
