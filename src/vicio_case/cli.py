from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .pipeline import run_data_audit, run_pipeline
from .runner import run_llm
from .verification import build_blind_sheet, max_errors_to_prove, score_publication


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

    sheet = sub.add_parser("folha-auditoria", help="Gera folha HTML de auditoria cega (publicadas + controles)")
    common(sheet)
    sheet.add_argument("--publicacao", type=Path, default=Path("publicacao.csv"))
    sheet.add_argument("--saida", type=Path, default=Path("auditoria"))
    sheet.add_argument("--controles", type=int, default=30)

    score = sub.add_parser("medir-precisao", help="Mede a precisão contra rótulos humanos ou o gabarito (id,tema_id)")
    common(score)
    score.add_argument("--publicacao", type=Path, default=Path("publicacao.csv"))
    score.add_argument("--rotulos", type=Path, required=True)
    score.add_argument("--previsao", type=Path, default=Path("previsao.txt"))

    args = parser.parse_args()
    if args.command == "audit":
        result = run_data_audit(args.data_dir, args.artifacts_dir, args.config_dir)
    elif args.command == "run-llm":
        result = run_llm(args.data_dir, args.artifacts_dir, args.config_dir, args.model, args.workers, args.limit)
    elif args.command == "folha-auditoria":
        result = build_blind_sheet(args.publicacao, args.data_dir, args.config_dir, args.saida, args.controles)
        published = result["publicadas"]
        result["regra_de_decisao"] = (f"Com as {published} publicadas auditadas, até "
                                      f"{max_errors_to_prove(published)} erro(s) ainda comprovam precisão >= 95% "
                                      "(limite inferior unilateral de 95%).")
    elif args.command == "medir-precisao":
        interval = None
        if args.previsao.exists():
            for line in args.previsao.read_text(encoding="utf-8").splitlines():
                if line.startswith("precisao_intervalo:"):
                    low, high = line.split(":", 1)[1].strip().split("-")
                    interval = (float(low), float(high))
        result = score_publication(args.publicacao, args.rotulos, args.data_dir, args.config_dir, interval)
    else:
        result = run_pipeline(args.data_dir, args.artifacts_dir, args.mode, args.config_dir,
                              args.annotations_dir, args.deliver_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
