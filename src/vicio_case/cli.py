from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .pipeline import run_data_audit, run_pipeline


def _default_data_dir() -> Path:
    return Path(os.getenv("DATA_DIR", "data/input")).resolve()


def _default_artifacts_dir() -> Path:
    return Path(os.getenv("ARTIFACTS_DIR", "artifacts")).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Classificação auditável de questões por tópico")
    subparsers = parser.add_subparsers(dest="command", required=True)

    classify = subparsers.add_parser("classify", help="Gera publicacao.csv e previsao.txt")
    classify.add_argument("--mode", choices=["baseline", "ollama"], default=os.getenv("CLASSIFICATION_MODE", "baseline"))
    classify.add_argument("--data-dir", type=Path, default=_default_data_dir())
    classify.add_argument("--artifacts-dir", type=Path, default=_default_artifacts_dir())
    classify.add_argument("--top-k", type=int, default=None)
    classify.add_argument("--publish-threshold", type=float, default=None)
    classify.add_argument("--verify-threshold", type=float, default=None)
    classify.add_argument("--max-workers", type=int, default=None)

    audit = subparsers.add_parser("audit", help="Audita esquema, metadados e taxonomia")
    audit.add_argument("--data-dir", type=Path, default=_default_data_dir())
    audit.add_argument("--artifacts-dir", type=Path, default=_default_artifacts_dir())

    args = parser.parse_args()
    if args.command == "classify":
        result = run_pipeline(
            args.data_dir, args.artifacts_dir, args.mode, args.top_k,
            args.publish_threshold, args.verify_threshold, args.max_workers,
        )
    else:
        result = run_data_audit(args.data_dir, args.artifacts_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
