from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .annotations import load_local_votes, load_strong_annotations
from .data import (
    PUBLICATION_COLUMNS,
    load_questions,
    load_topics,
    validate_publication_rows,
)
from .db import persist_run
from .decisions import (
    REV_CLONE,
    REV_POSTERIOR,
    REV_RISCO,
    PolicyConfig,
    decide,
    load_ambiguity_groups,
)
from .estimation import (
    bootstrap_accuracies,
    bucket_accuracies,
    bucket_of,
    correlated_error_rate,
    pairwise_agreement,
    posterior_correct,
    triplet_accuracies,
)
from .forecast import forecast_text
from .llm import PROMPT_VERSION
from .retrieval import CandidateRetriever
from .runner import model_output_path
from .taxonomy import Taxonomy, load_clone_map

STRONG_NAME = "claude-opus-5-5"
STRONG_FILE = "claude_opus_5_5.psv"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def write_publication(path: Path, rows: list[dict[str, Any]]) -> None:
    """CSV no formato do entrega_modelo.csv (aspas só quando necessário)."""
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(PUBLICATION_COLUMNS)
        for row in rows:
            writer.writerow([
                row["id"], row["decisao"], row["tema_central_id"], row["extras_ids"],
                f"{float(row['confianca']):.2f}", row["motivo"],
            ])


def _local_models() -> list[str]:
    raw = os.getenv("LOCAL_MODELS", "qwen2.5:7b,llama3.1:8b")
    return [m.strip() for m in raw.split(",") if m.strip()]


def _estimate(taxonomy: Taxonomy, votes: dict[str, dict[str, dict[str, Any]]], ids: list[str],
              names: list[str]) -> dict[str, Any]:
    """Acurácias latentes (global e por faixa de confiança do forte) e taxa de erro coincidente."""
    est: dict[str, Any] = {"concordancia_par_a_par": pairwise_agreement(taxonomy, votes, ids)}
    if len(votes) != 3:
        est["observacao"] = "Estimativa por triplet exige 3 classificadores; indisponível."
        return est
    est["acuracia_latente_global"] = triplet_accuracies(taxonomy, votes, ids)
    est["acuracia_latente_ic90_bootstrap"] = bootstrap_accuracies(taxonomy, votes, ids)
    est["por_faixa_de_confianca"] = bucket_accuracies(taxonomy, votes, names[0], ids)
    r_emp = correlated_error_rate(taxonomy, votes, ids)
    est["r_empirico"] = r_emp
    est["r_usado"] = min(0.5, max(0.05, r_emp if r_emp is not None else 0.15))
    return est


def _posterior(est: dict[str, Any], names: list[str], row: dict[str, Any], strong_conf: float,
               acc_override: dict[str, Any] | None = None, r_override: float | None = None) -> float:
    """`confianca` do CSV: P(tema sugerido certo | faixa de confiança do forte, concordância dos verificadores).

    Nunca é a confiança bruta do LLM. Sem estimativa (menos de 3 classificadores), usa 0.5."""
    bucket = bucket_of(strong_conf)
    acc = acc_override or (est.get("por_faixa_de_confianca", {}).get(bucket, {}) or {}).get("acuracias") \
        or est.get("acuracia_latente_global")
    if not acc:
        return 0.5
    r = r_override if r_override is not None else est["r_usado"]
    if row["decisao"] == "fora":
        return round(min(strong_conf, 0.9), 2)
    trace = row["trace"]
    strong = trace.get("forte") or {}
    if not strong.get("valido") or strong.get("tema_central_id") is None:
        return round(acc[names[1]] * 0.5, 2)
    sid = int(strong["tema_central_id"])
    pattern = []
    for name in names[1:]:
        vote = trace.get("locais", {}).get(name)
        if not vote or not vote.get("valido") or vote.get("tema_central_id") is None:
            pattern.append((None, acc[name]))
        else:
            pattern.append((row["_tax"].branch_related(sid, int(vote["tema_central_id"])), acc[name]))
    value = posterior_correct(acc[names[0]], pattern, r)
    if row["estrato"] in (REV_CLONE,):  # sugestão é o original do clone: mesmo assunto, nó diferente
        value *= 0.8
    return round(max(0.0, min(1.0, value)), 2)


def _precision_interval(est: dict[str, Any], names: list[str], rows: list[dict[str, Any]],
                        strong: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Precisão do modelo nas publicadas = média das posteriores; IC por bootstrap das acurácias."""
    published = [r for r in rows if r["decisao"] == "publicar"]
    if not published or "por_faixa_de_confianca" not in est:
        return {}
    point = sum(r["confianca"] for r in published) / len(published)
    lows, highs = [], []
    for r_value in (est["r_usado"] / 2, est["r_usado"] * 2):
        for side in (0, 1):
            vals = []
            for row in published:
                bucket = bucket_of(strong.get(row["id"], {}).get("confianca", 0))
                info = est["por_faixa_de_confianca"].get(bucket, {})
                ci = info.get("ic90") or {}
                base = info.get("acuracias") or est["acuracia_latente_global"]
                acc = {n: (ci[n][side] if n in ci else base[n]) for n in names}
                vals.append(_posterior(est, names, row, strong.get(row["id"], {}).get("confianca", 0), acc, r_value))
            (lows if side == 0 else highs).append(sum(vals) / len(vals))
    return {"pontual": round(point, 4), "pessimista": round(min(lows), 4), "otimista": round(max(highs), 4),
            "n_publicadas": len(published)}


def _threshold_curve(decisions: list[tuple[str, float]], current: float) -> list[dict[str, Any]]:
    """Cobertura e precisão média estimada (posterior) para limiares alternativos — evidência da escolha."""
    curve = []
    for gate in [0.0, 0.8, 0.85, 0.9, 0.92, 0.94, 0.95, 0.96, 0.97, 0.98]:
        kept = [c for d, c in decisions if d == "publicar" and c >= gate]
        curve.append({"limiar": gate, "publicadas": len(kept),
                      "precisao_media_estimada": round(sum(kept) / len(kept), 4) if kept else None,
                      "atual": abs(gate - current) < 1e-9})
    return curve


def run_pipeline(
    data_dir: Path,
    artifacts_dir: Path,
    mode: str = "ensemble",
    config_dir: Path = Path("config"),
    annotations_dir: Path = Path("data/anotacoes"),
    deliver_dir: Path | None = None,
) -> dict[str, Any]:
    started_at = datetime.now(UTC)
    clock = time.perf_counter()
    questions_path, topics_path = data_dir / "questoes.jsonl", data_dir / "temas.csv"
    questions = load_questions(questions_path)
    taxonomy = Taxonomy(load_topics(topics_path), load_clone_map(config_dir / "nos_duplicados.json"))
    groups = load_ambiguity_groups(config_dir / "grupos_ambiguos.json")
    policy = PolicyConfig.load(config_dir / "politica.json")
    retriever = CandidateRetriever(taxonomy, top_k=int(os.getenv("TOP_K_CANDIDATES", "12")))
    ids = [str(q["id"]) for q in questions]
    lexical = {str(q["id"]): retriever.retrieve(q) for q in questions}

    names: list[str] = []
    votes: dict[str, dict[str, dict[str, Any]]] = {}
    inputs: dict[str, str] = {"questoes.jsonl": sha256_file(questions_path), "temas.csv": sha256_file(topics_path)}
    for cfg in ["nos_duplicados.json", "grupos_ambiguos.json", "politica.json"]:
        inputs[f"config/{cfg}"] = sha256_file(config_dir / cfg)

    if mode == "baseline":
        rows = []
        for q in ids:
            top = lexical[q][0]["tema_id"] if lexical[q] else None
            rows.append({
                "id": q, "decisao": "revisar", "tema_central_id": top, "extras_ids": "", "confianca": 0.0,
                "motivo": "Baseline lexical (TF-IDF), sem validação semântica; serve só para testar o contrato.",
                "estrato": "revisar:baseline_lexical", "trace": {"candidatos_lexicais": lexical[q][:5]},
            })
        est: dict[str, Any] = {"observacao": "Modo baseline: nenhuma publicação, precisão indefinida."}
    elif mode == "ensemble":
        strong_path = annotations_dir / STRONG_FILE
        strong = load_strong_annotations(strong_path, taxonomy)
        if not strong:
            raise FileNotFoundError(f"Anotações do classificador forte não encontradas em {strong_path}")
        inputs[f"anotacoes/{STRONG_FILE}"] = sha256_file(strong_path)
        names.append(STRONG_NAME)
        votes[STRONG_NAME] = strong
        for model in _local_models():
            path = model_output_path(artifacts_dir, model)
            if path.exists():
                votes[model] = load_local_votes(path, taxonomy)
                names.append(model)
                inputs[f"llm/{path.name}"] = sha256_file(path)
        if len(names) < 2:
            raise FileNotFoundError("Nenhuma saída de LLM local encontrada; rode `run-llm` antes.")
        rows = []
        for q in ids:
            locals_ = [(n, votes[n].get(q)) for n in names[1:]]
            fallback = lexical[q][0]["tema_id"] if lexical[q] else None
            row = decide(q, strong.get(q), locals_, taxonomy, groups, policy, fallback)
            row["trace"]["candidatos_lexicais"] = [c["tema_id"] for c in lexical[q][:5]]
            rows.append(row)
        est = _estimate(taxonomy, votes, ids, names)
        for row in rows:
            row["_tax"] = taxonomy
            row["confianca"] = _posterior(est, names, row, strong.get(row["id"], {}).get("confianca", 0.0))
        rows_before_gate = [(r["decisao"], r["confianca"]) for r in rows]
        # Portão final: publicada só se a probabilidade estimada de acerto alcança o limiar declarado.
        gate = policy.limiar_posterior_publicacao
        for row in rows:
            if row["decisao"] == "publicar" and row["confianca"] < gate:
                row["decisao"], row["estrato"] = "revisar", REV_POSTERIOR
                row["tema_central_id"] = int(strong[row["id"]]["tema_central_id"])
                row["extras_ids"] = ""
                row["motivo"] = (f"Probabilidade estimada de acerto {row['confianca']:.2f} abaixo do limiar "
                                 f"de publicação ({gate:.2f}); confirmar a sugestão.")
        est["precisao_modelo_publicadas"] = _precision_interval(est, names, rows, strong)
        est["curva_limiar_posterior"] = _threshold_curve(rows_before_gate, gate)
        # Coluna `confianca` coerente com a previsão: posterior do modelo x (1 - risco de critério).
        # Nos ramos com nó equivalente em outro lugar da árvore, o especialista pode ter escolhido
        # o outro nó: sem conhecer a regra da equipe, a chance do nosso nó cai pela metade.
        fcfg = json.loads((config_dir / "previsao.json").read_text(encoding="utf-8")) \
            if (config_dir / "previsao.json").exists() else {}
        amb = float(fcfg.get("risco_divergencia_de_criterio", [0, 0.04, 0])[1])
        for row in rows:
            row["trace"]["posterior_modelo"] = row["confianca"]
            factor = (1 - amb) * (0.5 if row["estrato"] == REV_RISCO else 1.0)
            if row["decisao"] != "fora":
                row["confianca"] = round(row["confianca"] * factor, 2)
        for row in rows:
            row.pop("_tax", None)
    else:
        raise ValueError("mode deve ser 'baseline' ou 'ensemble'")

    # Sugestão de revisão nunca pode ficar vazia (contrato do LEIA-ME).
    for row in rows:
        if row["decisao"] == "revisar" and row["tema_central_id"] in ("", None):
            row["tema_central_id"] = lexical[row["id"]][0]["tema_id"]
    validate_publication_rows(rows, set(ids), taxonomy.selectable_ids)

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    pub_path = artifacts_dir / "publicacao.csv"
    write_publication(pub_path, rows)
    counts = Counter(row["decisao"] for row in rows)
    strata = Counter(row["estrato"] for row in rows)
    forecast = forecast_text(rows, est, names, mode, config_dir / "previsao.json")
    (artifacts_dir / "previsao.txt").write_text(forecast, encoding="utf-8")
    audit = {row["id"]: {k: row[k] for k in ["decisao", "tema_central_id", "extras_ids", "confianca", "motivo", "estrato", "trace"]}
             for row in rows}
    (artifacts_dir / "decision_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=1), encoding="utf-8")
    (artifacts_dir / "estimativa.json").write_text(json.dumps(est, ensure_ascii=False, indent=2), encoding="utf-8")

    llm_stats = {}
    for n in names[1:]:
        recs = votes[n]
        llm_stats[n] = {"respostas_validas": sum(v["valido"] for v in recs.values()),
                        "respostas_invalidas_ou_falhas": sum(not v["valido"] for v in recs.values()),
                        "sem_resposta": len(ids) - len(recs)}
    metadata = {
        "started_at_utc": started_at.isoformat(),
        "mode": mode,
        "classificadores": names,
        "classificador_forte": {"nome": STRONG_NAME, "como": "Claude Opus 5.5 via Claude Code (anotação em lote, mesmo protocolo de prompts/classificacao.md)"} if mode == "ensemble" else None,
        "prompt_version": PROMPT_VERSION,
        "policy": policy.__dict__,
        "input_sha256": inputs,
        "total_questions": len(rows),
        "decision_counts": dict(counts),
        "strata_counts": dict(strata),
        "llm_local_stats": llm_stats,
        "precision_measured_against_gold_labels": False,
        "observacao_precisao": "Não há gabarito no pacote do case; a precisão é estimada, não medida.",
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
    }
    output_hash = sha256_file(pub_path)
    metadata["publicacao_sha256"] = output_hash
    try:
        metadata["database_run_id"] = persist_run(metadata, rows)
    except Exception as exc:  # noqa: BLE001 - banco é trilha de auditoria; falha não pode corromper artefatos
        metadata["database_run_id"] = None
        metadata["database_error"] = f"{type(exc).__name__}: {exc}"
    metadata["duration_seconds"] = round(time.perf_counter() - clock, 2)
    (artifacts_dir / "run_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    if deliver_dir is not None:
        for name in ["publicacao.csv", "previsao.txt"]:
            shutil.copyfile(artifacts_dir / name, deliver_dir / name)
    return {"mode": mode, "classificadores": names, **dict(counts), "estratos": dict(strata),
            "publicacao_sha256": output_hash, "database_run_id": metadata.get("database_run_id"),
            "database_error": metadata.get("database_error")}


def run_data_audit(data_dir: Path, artifacts_dir: Path, config_dir: Path = Path("config")) -> dict[str, Any]:
    questions = load_questions(data_dir / "questoes.jsonl")
    topics = load_topics(data_dir / "temas.csv")
    taxonomy = Taxonomy(topics, load_clone_map(config_dir / "nos_duplicados.json"))
    disciplines = Counter((str(q.get("disciplina_origem") or "").strip() or "[vazio]") for q in questions)
    subjects = Counter((str(q.get("assunto_origem") or "").strip() or "[vazio]") for q in questions)
    titles = Counter(t.titulo.lower() for t in taxonomy.by_id.values() if t.nivel >= 1)
    audit = {
        "questions": len(questions),
        "topics": len(topics),
        "active_topics": len(taxonomy.active_ids),
        "inactive_topic_ids": sorted(set(taxonomy.by_id) - taxonomy.active_ids),
        "root_nodes": sum(t.nivel == 0 for t in taxonomy.by_id.values()),
        "selectable_active_topics": len(taxonomy.selectable_ids),
        "topics_without_description": sorted(i for i, t in taxonomy.by_id.items() if not t.descricao.strip()),
        "clone_nodes": {str(k): v for k, v in sorted(taxonomy.clones.items())},
        "duplicate_titles_across_branches": sorted(t for t, c in titles.items() if c > 1),
        "missing_command": sum(not str(q.get("comando") or "").strip() for q in questions),
        "missing_subject": sum(not str(q.get("assunto_origem") or "").strip() for q in questions),
        "missing_discipline": sum(not str(q.get("disciplina_origem") or "").strip() for q in questions),
        "alternatives_count_distribution": dict(Counter(len(q.get("alternativas") or {}) for q in questions)),
        "discipline_origin_counts": dict(disciplines),
        "top_subject_origin_counts": dict(subjects.most_common(15)),
        "duplicate_question_ids": len(questions) - len({q["id"] for q in questions}),
        "notes": [
            "Disciplina e assunto de origem são pistas ruidosas, não rótulos.",
            "Não há rótulos de referência no pacote: a precisão real não pode ser medida localmente.",
            "Temas inativos e nós-clone vazios nunca são publicados.",
        ],
    }
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "data_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit
