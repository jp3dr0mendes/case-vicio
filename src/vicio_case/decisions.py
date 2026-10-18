from __future__ import annotations

import math
from typing import Any

from .taxonomy import Taxonomy


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return max(0.0, min(1.0, number))


def safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def review_fallback(question_id: str, candidates: list[dict[str, Any]], reason: str = "Falha/ambiguidade na classificação; exige especialista.") -> dict[str, Any]:
    topic_id = safe_int(candidates[0].get("tema_id")) if candidates else None
    return {
        "id": question_id,
        "decisao": "revisar",
        "tema_central_id": topic_id if topic_id is not None else "",
        "extras_ids": "",
        "confianca": 0.50,
        "motivo": reason,
    }


def decide(
    question_id: str,
    primary: dict[str, Any],
    verifier: dict[str, Any] | None,
    candidates: list[dict[str, Any]],
    taxonomy: Taxonomy,
    publish_threshold: float = 0.95,
    verify_threshold: float = 0.90,
) -> dict[str, Any]:
    """Aplica abstenção conservadora e valida a consistência hierárquica."""
    candidate_ids = {safe_int(item.get("tema_id")) for item in candidates}
    candidate_ids.discard(None)
    fallback = review_fallback(question_id, candidates)
    if verifier is None:
        fallback["motivo"] = "Sem verificação independente; encaminhada para revisão."
        return fallback

    primary_decision = primary.get("decisao")
    verifier_decision = verifier.get("decisao")
    primary_id = safe_int(primary.get("tema_central_id"))
    verifier_id = safe_int(verifier.get("tema_central_id"))
    primary_conf = safe_float(primary.get("confianca"))
    verifier_conf = safe_float(verifier.get("confianca"))
    verified_agreement = bool(verifier.get("concorda", False))

    # 'fora' tem alto custo de exclusão: precisa de concordância explícita dos dois estágios.
    if primary_decision == "fora" or verifier_decision == "fora":
        if (
            primary_decision == "fora"
            and verifier_decision == "fora"
            and verified_agreement
            and primary_conf >= verify_threshold
            and verifier_conf >= verify_threshold
        ):
            return {
                "id": question_id, "decisao": "fora", "tema_central_id": "",
                "extras_ids": "", "confianca": round(min(primary_conf, verifier_conf), 2),
                "motivo": str(primary.get("justificativa_fora") or "").strip() or str(verifier.get("motivo") or "").strip() or "Nenhum tema ativo é compatível.",
            }
        return {
            **fallback,
            "tema_central_id": primary_id if primary_id in candidate_ids and taxonomy.is_active_selectable(primary_id) else fallback["tema_central_id"],
            "confianca": round(min(primary_conf, verifier_conf), 2),
            "motivo": "Divergência sobre a existência de tema compatível; revisão humana necessária.",
        }

    primary_valid = primary_id in candidate_ids and taxonomy.is_active_selectable(primary_id)
    verifier_valid = verifier_id in candidate_ids and taxonomy.is_active_selectable(verifier_id)
    if not primary_valid:
        fallback["motivo"] = "O modelo retornou tema inválido ou fora dos candidatos; revisão humana necessária."
        return fallback

    same_branch = verifier_valid and taxonomy.branch_related(primary_id, verifier_id)
    confidence = round(min(primary_conf, verifier_conf), 2)
    if (
        primary_decision == "publicar"
        and verifier_decision == "publicar"
        and verified_agreement
        and same_branch
        and primary_conf >= publish_threshold
        and verifier_conf >= verify_threshold
    ):
        extras: list[int] = []
        for raw in primary.get("extras_ids", []):
            extra_id = safe_int(raw)
            if extra_id in taxonomy.selectable_ids and extra_id != primary_id and extra_id in candidate_ids:
                extras.append(extra_id)
        return {
            "id": question_id,
            "decisao": "publicar",
            "tema_central_id": primary_id,
            "extras_ids": ";".join(str(item) for item in sorted(set(extras))),
            "confianca": confidence,
            "motivo": "",
        }

    if not same_branch:
        reason = "Classificador e verificador divergiram de ramo; validar a sugestão com especialista."
    elif not verified_agreement:
        reason = "Verificador não confirmou a classificação; encaminhada para revisão."
    elif primary_conf < publish_threshold or verifier_conf < verify_threshold:
        reason = "Confiança abaixo dos limiares conservadores de publicação."
    else:
        reason = str(primary.get("motivo") or verifier.get("motivo") or "Caso ambíguo; revisão humana necessária.")
    return {
        "id": question_id,
        "decisao": "revisar",
        "tema_central_id": primary_id,
        "extras_ids": "",
        "confianca": confidence,
        "motivo": reason,
    }
