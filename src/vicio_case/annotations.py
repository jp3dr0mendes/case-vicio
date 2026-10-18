"""Leitura das saídas dos classificadores (anotador forte e LLMs locais) num formato único.

Formato comum por questão: {"tema_central_id": int|None, "extras_ids": [int], "fora": bool,
"confianca": float, "justificativa": str, "valido": bool, "erro": str|None}.
Saídas inválidas não são descartadas: viram valido=False e a política manda para revisão.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .runner import load_model_outputs
from .taxonomy import Taxonomy


def _invalid(reason: str) -> dict[str, Any]:
    return {
        "tema_central_id": None, "extras_ids": [], "fora": False, "confianca": 0.0,
        "justificativa": "", "valido": False, "erro": reason,
    }


def normalize_vote(raw: dict[str, Any], taxonomy: Taxonomy) -> dict[str, Any]:
    fora = str(raw.get("fora", "")).strip().lower() in {"1", "true", "sim"}
    try:
        confidence = float(raw.get("confianca"))
    except (TypeError, ValueError):
        return _invalid("confianca não numérica")
    if not 0.0 <= confidence <= 1.0:
        return _invalid("confianca fora de [0,1]")
    raw_central = raw.get("tema_central_id")
    central: int | None
    try:
        central = None if raw_central in (None, "") else int(raw_central)
    except (TypeError, ValueError):
        return _invalid(f"tema inválido: {raw_central!r}")
    if fora:
        central = None
    elif central is None:
        return _invalid("sem tema e sem fora")
    elif not taxonomy.is_active_selectable(central):
        return _invalid(f"tema {central} inexistente, inativo ou raiz")
    extras_raw = raw.get("extras_ids") or []
    if isinstance(extras_raw, str):
        extras_raw = [part for part in extras_raw.split(";") if part.strip()]
    extras: list[int] = []
    for item in extras_raw:
        try:
            extra = int(item)
        except (TypeError, ValueError):
            continue
        if taxonomy.is_active_selectable(extra) and extra != central and extra not in extras:
            extras.append(extra)
    return {
        "tema_central_id": central,
        "extras_ids": extras if central is not None else [],
        "fora": fora,
        "confianca": confidence,
        "justificativa": str(raw.get("justificativa") or "").strip(),
        "valido": True,
        "erro": None,
    }


def load_strong_annotations(path: Path, taxonomy: Taxonomy) -> dict[str, dict[str, Any]]:
    """Anotações do classificador forte (arquivo PSV versionado em data/anotacoes/)."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="|"))
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        qid = row["id"].strip()
        if qid in output:
            raise ValueError(f"Anotação duplicada para {qid} em {path}")
        output[qid] = normalize_vote(row, taxonomy)
    return output


def load_local_votes(path: Path, taxonomy: Taxonomy) -> dict[str, dict[str, Any]]:
    """Respostas de um LLM local gravadas por runner.run_llm (JSONL)."""
    output: dict[str, dict[str, Any]] = {}
    for qid, record in load_model_outputs(path).items():
        if record.get("error"):
            output[qid] = _invalid(str(record["error"]))
        else:
            output[qid] = normalize_vote(record, taxonomy)
    return output
