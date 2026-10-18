from __future__ import annotations

import hashlib
import json
import os
import statistics
import platform
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from .data import PUBLICATION_COLUMNS, load_questions, load_topics, validate_publication_rows
from .db import persist_run
from .decisions import decide, review_fallback
from .llm import OllamaClient
from .retrieval import CandidateRetriever
from .taxonomy import Taxonomy


def _dataset_sha256(questions_path: Path, topics_path: Path) -> str:
    digest = hashlib.sha256()
    for path in [questions_path, topics_path]:
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _baseline_row(question: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    row = review_fallback(
        str(question["id"]), candidates,
        "Sugestão lexical inicial, não validada semanticamente; revisão humana obrigatória.",
    )
    row["confianca"] = 0.50  # neutralidade deliberada: similaridade lexical não é probabilidade
    return row


def _process_with_ollama(
    question: dict[str, Any],
    candidates: list[dict[str, Any]],
    client: OllamaClient,
    taxonomy: Taxonomy,
    publish_threshold: float,
    verify_threshold: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    primary: dict[str, Any] | None = None
    verifier: dict[str, Any] | None = None
    try:
        primary = client.classify(question, candidates)
        verifier = client.verify(question, candidates, primary)
        row = decide(
            str(question["id"]), primary, verifier, candidates, taxonomy,
            publish_threshold=publish_threshold, verify_threshold=verify_threshold,
        )
        trace = {"primary": primary, "verifier": verifier, "candidates": candidates, "error": None}
        return row, trace
    except Exception as exc:  # falha de rede/modelo precisa degradar para revisão, nunca publicar
        row = review_fallback(
            str(question["id"]), candidates,
            f"Falha no modelo/verificação ({type(exc).__name__}); revisão humana obrigatória.",
        )
        trace = {
            "candidates": candidates,
            "primary": primary,
            "verifier": verifier,
            "error": f"{type(exc).__name__}: {exc}",
        }
        return row, trace


def write_publication(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(",".join(PUBLICATION_COLUMNS) + "\n")
        for row in rows:
            values = []
            for column in PUBLICATION_COLUMNS:
                value = row.get(column, "")
                if column == "confianca":
                    value = f"{float(value):.2f}"
                elif column in {"tema_central_id", "extras_ids", "motivo"}:
                    value = str(value if value is not None else "")
                else:
                    value = str(value)
                # CSV escaping: todos os campos textuais entre aspas quando necessário.
                if any(char in value for char in [',', '"', '\n', '\r']):
                    value = '"' + value.replace('"', '""') + '"'
                values.append(value)
            handle.write(",".join(values) + "\n")


def forecast_text(rows: list[dict[str, Any]], total: int, mode: str, model: str | None) -> str:
    published = [row for row in rows if row["decisao"] == "publicar"]
    coverage = (len(published) / total) if total else 0.0
    lines = [
        f"precisao_prevista: {statistics.mean(float(row['confianca']) for row in published):.2f}" if published else "precisao_prevista: 0.00",
        f"precisao_intervalo: {min(float(row['confianca']) for row in published):.2f}-{max(float(row['confianca']) for row in published):.2f}" if published else "precisao_intervalo: 0.00-0.00",
        f"cobertura_prevista: {coverage:.2f}",
        f"cobertura_intervalo: {coverage:.2f}-{coverage:.2f}",
        "",
    ]
    if not published:
        lines.append(
            "RASCUNHO TÉCNICO: não houve questões publicadas; portanto, a precisão nas publicadas é indefinida. "
            "Os zeros acima existem apenas para preservar o formato do arquivo e NÃO devem ser apresentados como previsão final."
        )
    else:
        lines.append(
            "A precisão pontual é a média das confianças declaradas pelo classificador nas questões publicadas; "
            "o intervalo é o mínimo-máximo dessas confianças. Isso é uma previsão subjetiva, não um intervalo estatístico "
            "nem uma garantia de precisão real. Calibrar com amostra rotulada e auditoria humana antes de alegar >=95%."
        )
    lines.append(f"Modo: {mode}. Modelo: {model or 'nenhum (baseline lexical)'}. Gerado em UTC: {datetime.now(timezone.utc).isoformat()}.")
    lines.append("Regra operacional: só publicar quando classificação primária e verificador concordam no mesmo ramo, com os limiares configurados; divergência, falha ou incerteza vai para revisão.")
    return "\n".join(lines) + "\n"


def run_pipeline(
    data_dir: Path,
    artifacts_dir: Path,
    mode: str = "baseline",
    top_k: int | None = None,
    publish_threshold: float | None = None,
    verify_threshold: float | None = None,
    max_workers: int | None = None,
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc)
    started_clock = time.perf_counter()
    questions_path = data_dir / "questoes.jsonl"
    topics_path = data_dir / "temas.csv"
    questions = load_questions(questions_path)
    topics_df = load_topics(topics_path)
    dataset_hash = _dataset_sha256(questions_path, topics_path)
    taxonomy = Taxonomy(topics_df)
    retriever = CandidateRetriever(taxonomy, top_k=top_k or int(os.getenv("TOP_K_CANDIDATES", "12")))
    candidates_by_id = {str(q["id"]): retriever.retrieve(q) for q in questions}

    publish_threshold = publish_threshold if publish_threshold is not None else float(os.getenv("PUBLISH_THRESHOLD", "0.95"))
    verify_threshold = verify_threshold if verify_threshold is not None else float(os.getenv("VERIFY_THRESHOLD", "0.90"))
    traces: dict[str, Any] = {}
    model = None

    if mode == "baseline":
        rows = [_baseline_row(q, candidates_by_id[str(q["id"])]) for q in questions]
        traces = {
            str(q["id"]): {"candidates": candidates_by_id[str(q["id"])], "mode": "baseline", "semantic_validation": False}
            for q in questions
        }
    elif mode == "ollama":
        client = OllamaClient()
        model = client.model
        worker_count = max(1, max_workers or int(os.getenv("OLLAMA_NUM_THREADS", "2")))
        result_by_id: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_map = {
                executor.submit(
                    _process_with_ollama,
                    q,
                    candidates_by_id[str(q["id"])],
                    client,
                    taxonomy,
                    publish_threshold,
                    verify_threshold,
                ): str(q["id"])
                for q in questions
            }
            for future in as_completed(future_map):
                qid = future_map[future]
                row, trace = future.result()
                result_by_id[qid] = row
                traces[qid] = trace
        rows = [result_by_id[str(q["id"])] for q in questions]
    else:
        raise ValueError("mode deve ser 'baseline' ou 'ollama'")

    question_ids = {str(q["id"]) for q in questions}
    active_topic_ids = taxonomy.active_ids
    validate_publication_rows(rows, question_ids, active_topic_ids)

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    publication_path = artifacts_dir / "publicacao.csv"
    write_publication(publication_path, rows)
    forecast_path = artifacts_dir / "previsao.txt"
    forecast_path.write_text(forecast_text(rows, len(questions), mode, model), encoding="utf-8")
    trace_path = artifacts_dir / "decision_audit.json"
    trace_path.write_text(json.dumps(traces, ensure_ascii=False, indent=2), encoding="utf-8")

    decision_counts = {decision: sum(row["decisao"] == decision for row in rows) for decision in ["publicar", "revisar", "fora"]}
    metadata = {
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.perf_counter() - started_clock, 3),
        "dataset_sha256": dataset_hash,
        "mode": mode,
        "model": model,
        "candidate_generator": "tfidf_word_bigram_char_ngram_v1",
        "top_k_candidates": top_k or int(os.getenv("TOP_K_CANDIDATES", "12")),
        "publish_threshold": publish_threshold,
        "verify_threshold": verify_threshold,
        "max_workers": (max_workers or int(os.getenv("OLLAMA_NUM_THREADS", "2"))) if mode == "ollama" else 0,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "total_questions": len(rows),
        "decision_counts": decision_counts,
        "semantic_validation_performed": mode == "ollama",
        "primary_calls_completed": sum(trace.get("primary") is not None for trace in traces.values()),
        "verification_calls_completed": sum(trace.get("verifier") is not None for trace in traces.values()),
        "estimated_api_cost": None,
        "cost_note": "Não estimado automaticamente; o modo atual usa Ollama local. Hardware, energia e custo de implantação não são medidos.",
        "precision_measured_against_gold_labels": False,
        "database_run_id": None,
    }
    metadata_path = artifacts_dir / "run_metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    db_run_id = persist_run(dataset_hash, mode, model, rows, traces)
    metadata["database_run_id"] = db_run_id
    metadata["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    metadata["duration_seconds"] = round(time.perf_counter() - started_clock, 3)
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "mode": mode,
        "model": model,
        "total": len(rows),
        "publicar": sum(row["decisao"] == "publicar" for row in rows),
        "revisar": sum(row["decisao"] == "revisar" for row in rows),
        "fora": sum(row["decisao"] == "fora" for row in rows),
        "publicacao_path": str(publication_path),
        "previsao_path": str(forecast_path),
        "trace_path": str(trace_path),
        "metadata_path": str(metadata_path),
        "db_run_id": db_run_id,
    }


def run_data_audit(data_dir: Path, artifacts_dir: Path) -> dict[str, Any]:
    questions = load_questions(data_dir / "questoes.jsonl")
    topics = load_topics(data_dir / "temas.csv")
    taxonomy = Taxonomy(topics)
    question_count = len(questions)
    missing_command = sum(not str(q.get("comando") or "").strip() for q in questions)
    missing_subject = sum(not str(q.get("assunto_origem") or "").strip() for q in questions)
    missing_discipline = sum(not str(q.get("disciplina_origem") or "").strip() for q in questions)
    disciplines = {}
    for q in questions:
        key = str(q.get("disciplina_origem") or "[vazio]").strip() or "[vazio]"
        disciplines[key] = disciplines.get(key, 0) + 1
    audit = {
        "questions": question_count,
        "topics": len(topics),
        "active_topics": len(taxonomy.active_ids),
        "inactive_topics": int((topics["status"].str.lower() != "active").sum()),
        "root_nodes": int((topics["nivel"] == 0).sum()),
        "selectable_active_topics": len(taxonomy.selectable_ids),
        "missing_command": missing_command,
        "missing_subject": missing_subject,
        "missing_discipline": missing_discipline,
        "discipline_origin_counts": disciplines,
        "duplicate_question_ids": question_count - len({q["id"] for q in questions}),
        "notes": [
            "O assunto e a disciplina de origem são metadados auxiliares, não rótulos verdadeiros.",
            "Não há rótulos de referência no pacote fornecido; precisão real não pode ser calculada localmente.",
            "O status inativo precisa bloquear publicação, mas os pais/filhos ativos continuam na árvore.",
        ],
    }
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "data_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit
