"""Política determinística publicar / revisar / fora.

Princípio: um erro publicado é o custo mais alto. Publica-se quando o classificador forte tem
confiança suficiente E (a) algum verificador local independente aponta para o MESMO RAMO
(mesmo nó, pai ou filho; irmãos NÃO contam) ou (b) a confiança é alta e os verificadores não
vetam (veto = os dois concordam entre si em outro ramo). Nunca em nó-clone; nos ramos que têm
nó concorrente em outro lugar da árvore exige-se concordância de todos os verificadores.
Os limiares foram escolhidos pela calibração estimada (docs/estimativa_precisao.md).
Qualquer falha, resposta inválida, divergência ou dúvida vira 'revisar' com a melhor sugestão.
A confiança autodeclarada pelos modelos é só um filtro; o valor de `confianca` gravado no CSV
vem da estimativa por estrato (estimation.py), não do modelo.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .taxonomy import Taxonomy

# Estratos usados pela estimativa de precisão e pelo campo `confianca`.
PUB_EXATO = "publicar:concordancia_exata"
PUB_RAMO = "publicar:concordancia_de_ramo"
PUB_ALTA_CONF = "publicar:alta_confianca_sem_veto"
REV_VETO = "revisar:veto_dos_verificadores"
REV_POSTERIOR = "revisar:probabilidade_estimada_baixa"
REV_DIVERGENCIA = "revisar:divergencia"
REV_BAIXA_CONF = "revisar:baixa_confianca"
REV_RISCO = "revisar:zona_de_risco"
REV_CLONE = "revisar:no_clone"
REV_FALHA = "revisar:falha_ou_invalido"
REV_FORA_SEM_CONSENSO = "revisar:possivel_fora"
FORA = "fora:consenso"


@dataclass(frozen=True)
class PolicyConfig:
    versao: str = "politica-v3-calibrada"
    limiar_confianca_anotador_forte: float = 0.75
    limiar_publicacao_sem_concordancia: float = 0.9
    veto_por_consenso_local: bool = True
    limiar_posterior_publicacao: float = 0.0
    limiar_confianca_zona_de_risco: float = 0.9
    exigir_concordancia_de_todos_os_locais_na_zona_de_risco: bool = True
    limiar_confianca_fora: float = 0.9

    @classmethod
    def load(cls, path: Path) -> "PolicyConfig":
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        fields = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**fields)


GROUP_LABELS: dict[str, str] = {}


def load_ambiguity_groups(path: Path) -> dict[str, list[int]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    GROUP_LABELS.update(data.get("rotulos", {}))
    return {name: [int(i) for i in ids] for name, ids in data.get("grupos", {}).items()}


def risk_groups_for(node_id: int, taxonomy: Taxonomy, groups: dict[str, list[int]]) -> list[str]:
    """Grupos cujo algum nó está no mesmo ramo do nó publicado (nó concorrente em outro ramo)."""
    hits = []
    for name, members in groups.items():
        if any(taxonomy.branch_related(node_id, m) for m in members if m in taxonomy.by_id):
            hits.append(name)
    return hits


def _shallower(taxonomy: Taxonomy, left: int, right: int) -> int:
    """Entre dois nós do mesmo ramo, o mais geral: correto se a referência estiver em qualquer um."""
    return left if taxonomy.by_id[left].nivel <= taxonomy.by_id[right].nivel else right


def _row(qid: str, decision: str, central: int | None, extras: list[int], reason: str, stratum: str,
         **trace: Any) -> dict[str, Any]:
    return {
        "id": qid,
        "decisao": decision,
        "tema_central_id": "" if central is None else central,
        "extras_ids": ";".join(str(e) for e in extras),
        "confianca": None,  # preenchida pela estimativa por estrato
        "motivo": reason,
        "estrato": stratum,
        "trace": trace,
    }


def decide(
    qid: str,
    strong: dict[str, Any] | None,
    locals_: list[tuple[str, dict[str, Any] | None]],
    taxonomy: Taxonomy,
    groups: dict[str, list[int]],
    config: PolicyConfig,
    lexical_fallback: int | None,
) -> dict[str, Any]:
    """locals_: [(nome_do_modelo, voto)] dos verificadores locais independentes."""
    trace = {"forte": strong, "locais": {name: vote for name, vote in locals_}}

    def suggestion() -> int | None:
        for vote in [strong] + [v for _, v in locals_]:
            if vote and vote.get("valido") and vote.get("tema_central_id") is not None:
                tid = int(vote["tema_central_id"])
                return taxonomy.clones.get(tid, tid)
        return lexical_fallback

    if not strong or not strong.get("valido"):
        return _row(qid, "revisar", suggestion(), [],
                    "Classificador principal ausente ou com resposta inválida; revisão obrigatória.",
                    REV_FALHA, **trace)

    if strong["fora"]:
        local_fora = any(v and v.get("valido") and v["fora"] for _, v in locals_)
        if strong["confianca"] >= config.limiar_confianca_fora and local_fora:
            return _row(qid, "fora", None, [],
                        f"Nenhum tema da árvore cobre a questão: {strong['justificativa'] or 'conteúdo fora do recorte penal'}",
                        FORA, **trace)
        return _row(qid, "revisar", suggestion(), [],
                    "Possivelmente fora da árvore, sem consenso entre classificadores; confirmar ou criar tema.",
                    REV_FORA_SEM_CONSENSO, **trace)

    central = int(strong["tema_central_id"])
    if central in taxonomy.clones:
        original = taxonomy.clones[central]
        return _row(qid, "revisar", original, [],
                    f"Tema escolhido ({central}) é nó duplicado vazio; sugerido o original {original}.",
                    REV_CLONE, **trace)

    valid_locals = [(n, v) for n, v in locals_ if v and v.get("valido")]
    local_ids = [(n, None if v["fora"] else int(v["tema_central_id"])) for n, v in valid_locals]
    agreeing = [n for n, tid in local_ids if tid is not None and taxonomy.branch_related(central, tid)]
    trace["locais_concordantes"] = agreeing

    # Veto: dois verificadores independentes concordam entre si contra o classificador principal.
    if config.veto_por_consenso_local and len(local_ids) >= 2 and not agreeing:
        others_ids = [tid for _, tid in local_ids]
        if all(t is not None for t in others_ids) and all(
            taxonomy.branch_related(others_ids[0], t) for t in others_ids[1:]
        ):
            return _row(qid, "revisar", central, [],
                        f"Verificadores apontam outro ramo ({others_ids[0]}); confirmar entre {central} e {others_ids[0]}.",
                        REV_VETO, **trace)

    conf = strong["confianca"]
    if conf < config.limiar_confianca_anotador_forte:
        return _row(qid, "revisar", central, [],
                    f"Classificador principal inseguro ({conf:.2f}); confirmar a sugestão.",
                    REV_BAIXA_CONF, **trace)

    if agreeing:
        # Entre nós do mesmo ramo, publica o mais geral: correto se a referência estiver em qualquer um.
        first = dict(local_ids)[agreeing[0]]
        central_pub = _shallower(taxonomy, central, first)
        stratum = PUB_EXATO if first == central else PUB_RAMO
    elif conf >= config.limiar_publicacao_sem_concordancia and local_ids:
        central_pub = central
        stratum = PUB_ALTA_CONF
    elif not local_ids:
        return _row(qid, "revisar", central, [],
                    "Nenhum verificador independente respondeu de forma válida; sem verificação não se publica.",
                    REV_FALHA, **trace)
    else:
        detail = ", ".join(f"{n}={tid if tid is not None else 'fora'}" for n, tid in local_ids) or "sem resposta válida"
        return _row(qid, "revisar", central, [],
                    f"Sem concordância dos verificadores ({central} x {detail}).",
                    REV_DIVERGENCIA, **trace)

    risks = risk_groups_for(central_pub, taxonomy, groups)
    if risks:
        all_agree = len(agreeing) == len(locals_) and len(locals_) > 0
        if conf < config.limiar_confianca_zona_de_risco or (
            config.exigir_concordancia_de_todos_os_locais_na_zona_de_risco and not all_agree
        ):
            return _row(qid, "revisar", central, [],
                        "Assunto com nó equivalente em outro ramo ("
                        + "; ".join(GROUP_LABELS.get(r, r) for r in risks[:2]) + "); confirmar o nó.",
                        REV_RISCO, **trace)

    extras = [e for e in strong["extras_ids"]
              if e != central_pub and e not in taxonomy.clones and not taxonomy.branch_related(e, central_pub)]
    return _row(qid, "publicar", central_pub, extras, "", stratum, grupos_de_risco=risks, **trace)
