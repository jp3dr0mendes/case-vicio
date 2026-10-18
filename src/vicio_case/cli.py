from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .pipeline import run_data_audit, run_pipeline
from .runner import run_llm


def _env_path(name: str, default: str) -> Path:
    return Path(os.getenv(name, default)).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Classificação auditável de questões por tópico (case Vício)")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--data-dir", type=Path, default=_env_path("DATA_DIR", "data/input"))
        p.add_argument("--artifacts-dir", type=Path, default=_env_path("ARTIFACTS_DIR", "artifacts"))
        p.add_argument("--config-dir", type=Path, default=_env_path("CONFIG_DIR", "config"))

    audit = sub.add_parser("audit", help="Audita esquema, metadados e taxonomia -> artifacts/data_audit.json")
    common(audit)

    llm = sub.add_parser("run-llm", help="Roda um LLM local (Ollama) em todas as questões; retomável")
    common(llm)
    llm.add_argument("--model", default=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"))
    llm.add_argument("--workers", type=int, default=int(os.getenv("OLLAMA_WORKERS", "2")))
    llm.add_argument("--limit", type=int, default=None, help="Processa só N questões pendentes (teste)")

    classify = sub.add_parser("classify", help="Aplica a política e gera publicacao.csv / previsao.txt")
    common(classify)
    classify.add_argument("--mode", choices=["baseline", "ensemble"], default=os.getenv("CLASSIFICATION_MODE", "ensemble"))
    classify.add_argument("--annotations-dir", type=Path, default=_env_path("ANNOTATIONS_DIR", "data/anotacoes"))
    classify.add_argument("--deliver-dir", type=Path, default=None,
                          help="Copia publicacao.csv e previsao.txt para este diretório (ex.: raiz do repo)")

    args = parser.parse_args()
    if args.command == "audit":
        result = run_data_audit(args.data_dir, args.artifacts_dir, args.config_dir)
    elif args.command == "run-llm":
        result = run_llm(args.data_dir, args.artifacts_dir, args.config_dir, args.model, args.workers, args.limit)
    else:
        result = run_pipeline(args.data_dir, args.artifacts_dir, args.mode, args.config_dir,
                              args.annotations_dir, args.deliver_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
