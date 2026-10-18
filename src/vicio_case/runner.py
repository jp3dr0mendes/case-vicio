"""Execução retomável de um LLM local (Ollama) sobre todas as questões.

Cada resposta vira uma linha em artifacts/llm/<modelo>.jsonl. Reexecutar só processa as
questões que ainda não têm resposta válida (falhas são tentadas de novo), sem duplicar linhas
válidas. A decisão publicar/revisar/fora NÃO é tomada aqui: ver decisions.py.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .data import load_questions, load_topics
from .llm import PROMPT_VERSION, HierarchicalPrompts, LLMResponseError, OllamaClient
from .taxonomy import Taxonomy, load_clone_map


def model_output_path(artifacts_dir: Path, model: str) -> Path:
    safe = model.replace(":", "_").replace("/", "_")
    return artifacts_dir / "llm" / f"{safe}.jsonl"


def load_model_outputs(path: Path) -> dict[str, dict[str, Any]]:
    """Última resposta por questão (respostas válidas têm precedência sobre erros)."""
    outputs: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return outputs
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            qid = record["id"]
            if record.get("error") and qid in outputs and not outputs[qid].get("error"):
                continue
            outputs[qid] = record
    return outputs


def run_llm(
    data_dir: Path,
    artifacts_dir: Path,
    config_dir: Path,
    model: str | None = None,
    workers: int = 2,
    limit: int | None = None,
) -> dict[str, Any]:
    questions = load_questions(data_dir / "questoes.jsonl")
    taxonomy = Taxonomy(load_topics(data_dir / "temas.csv"), load_clone_map(config_dir / "nos_duplicados.json"))
    client = OllamaClient(model=model)
    health = client.health()  # falha cedo e de forma explícita se o servidor/modelo não estiver disponível
    prompts = HierarchicalPrompts(taxonomy)
    prompt_sha = hashlib.sha256(prompts.step1.encode("utf-8")).hexdigest()[:12]
    out_path = model_output_path(artifacts_dir, client.model)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = {qid for qid, rec in load_model_outputs(out_path).items() if not rec.get("error")}
    pending = [q for q in questions if q["id"] not in done]
    if limit is not None:
        pending = pending[:limit]
    lock = threading.Lock()
    started = time.perf_counter()
    stats = {"ok": 0, "error": 0}

    def work(question: dict[str, Any]) -> dict[str, Any]:
        record: dict[str, Any] = {
            "id": question["id"],
            "model": client.model,
            "prompt_version": PROMPT_VERSION,
            "prompt_sha256_12": prompt_sha,
            "created_at_utc": datetime.now(UTC).isoformat(),
        }
        try:
            record.update(client.classify(question, prompts))
            record["error"] = None
        except Exception as exc:  # noqa: BLE001 - qualquer falha vira registro auditável; a política manda revisar
            record["error"] = f"{type(exc).__name__}: {exc}"
            if isinstance(exc, LLMResponseError):
                record["falha"] = {"passo": exc.passo, "parcial": exc.parcial, "tentativas": exc.tentativas}
        return record

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool, out_path.open("a", encoding="utf-8") as handle:
        futures = [pool.submit(work, q) for q in pending]
        for index, future in enumerate(as_completed(futures), start=1):
            record = future.result()
            with lock:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                handle.flush()
                stats["error" if record["error"] else "ok"] += 1
            if index % 20 == 0:
                print(f"[{client.model}] {index}/{len(pending)} ok={stats['ok']} erro={stats['error']}", flush=True)

    outputs = load_model_outputs(out_path)
    return {
        **health,
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256_12": prompt_sha,
        "output_path": str(out_path),
        "processed_now": len(pending),
        "ok_now": stats["ok"],
        "errors_now": stats["error"],
        "valid_total": sum(1 for r in outputs.values() if not r.get("error")),
        "questions_total": len(questions),
        "duration_seconds": round(time.perf_counter() - started, 1),
    }
