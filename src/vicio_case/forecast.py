"""Geração do previsao.txt a partir da estimativa (estimation.py) e de ajustes declarados.

Os ajustes manuais (risco de divergência de critério do gabarito, auditoria de amostra) ficam em
config/previsao.json, versionados e citados no texto: nada fica escondido no código.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


def _undefined(coverage: float, mode: str, why: str) -> str:
    return (
        "precisao_prevista: 0.00\nprecisao_intervalo: 0.00-0.00\n"
        f"cobertura_prevista: {coverage:.2f}\ncobertura_intervalo: {coverage:.2f}-{coverage:.2f}\n\n"
        f"RASCUNHO ({mode}): {why} Os zeros acima só preservam o formato e NÃO são uma previsão.\n"
    )


def forecast_text(rows: list[dict[str, Any]], est: dict[str, Any], names: list[str], mode: str,
                  config_path: Path) -> str:
    total = len(rows)
    published = [row for row in rows if row["decisao"] == "publicar"]
    coverage = len(published) / total if total else 0.0
    if not published:
        return _undefined(coverage, mode, "nenhuma questão publicada; a precisão nas publicadas é INDEFINIDA.")
    model = est.get("precisao_modelo_publicadas") or {}
    if not model:
        return _undefined(coverage, mode, "estimativa indisponível (faltam três classificadores).")
    cfg = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    amb_low, amb_central, amb_high = cfg.get("risco_divergencia_de_criterio", [0.02, 0.04, 0.07])
    cov_margin = float(cfg.get("margem_cobertura", 0.02))
    point = model["pontual"] * (1 - amb_central)
    low = min(point, model["pessimista"] * (1 - amb_high))
    high = max(point, model["otimista"] * (1 - amb_low))
    strata = Counter(row["estrato"] for row in published)
    buckets = est.get("por_faixa_de_confianca", {})

    def fmt_acc(info: dict[str, Any]) -> str:
        acc = info.get("acuracias") or {}
        return ", ".join(f"{n}={acc[n]:.2f}" for n in names if n in acc) or "indisponível"

    lines = [
        f"precisao_prevista: {point:.2f}",
        f"precisao_intervalo: {low:.2f}-{high:.2f}",
        f"cobertura_prevista: {coverage:.2f}",
        f"cobertura_intervalo: {max(0, coverage - cov_margin):.2f}-{min(1, coverage + cov_margin):.2f}",
        "",
        "COMO CHEGUEI NESSES NÚMEROS",
        "(previsão feita antes de qualquer gabarito; o pacote do case não tem rótulos, então nada aqui é precisão medida)",
        "",
        f"1. Cobertura é conta direta: publiquei {len(published)} de {total} questões. Por estrato: "
        + "; ".join(f"{k}={v}" for k, v in sorted(strata.items()))
        + f". A margem de ±{cov_margin:.2f} só cobre a hipótese de a avaliação usar um subconjunto das questões.",
        "",
        "2. Três classificadores independentes votaram em todas as questões: " + ", ".join(names)
        + ". O primeiro (Claude Opus 5.5, rodando nesta sessão do Claude Code) é o classificador principal; os dois "
        "modelos locais (Ollama) são verificadores mais fracos e de outras famílias.",
        "",
        "3. Sem gabarito, estimei a acurácia de cada um pela concordância entre pares (modelo de acurácias latentes "
        "com três anotadores: concordância_ij ~ p_i * p_j; 'concordar' = mesmo nó, pai ou filho). Por faixa de "
        "confiança declarada pelo classificador principal: "
        + " | ".join(f"{b} (n={info.get('n')}): {fmt_acc(info)}" for b, info in buckets.items()) + ".",
        "",
        f"4. Para cada questão calculei a probabilidade de o tema estar certo (coluna confianca do CSV): parte da "
        f"acurácia do principal na faixa de confiança e é atualizada pelo voto de cada verificador (concordou / "
        f"discordou), usando a acurácia dele e r={est.get('r_usado', 0):.2f}, a chance de dois erros caírem no "
        f"mesmo ramo (medida: {est.get('r_empirico')}). A média nas publicadas é {model['pontual']:.3f}; variando "
        f"acurácias no IC90% do bootstrap e r entre metade e o dobro, fica entre {model['pessimista']:.3f} e "
        f"{model['otimista']:.3f}.",
        "",
        f"5. O modelo estatístico não enxerga a divergência de CRITÉRIO: o especialista pode ter escolhido outro nó "
        f"defensável (a árvore tem 20 nós-clone vazios e assuntos repetidos em ramos diferentes, ex.: 'Ação Penal' "
        f"em Penal e em Processo Penal; a política já manda esses casos para revisão, mas não todos). Descontei "
        f"{amb_central:.0%} (faixa {amb_low:.0%}-{amb_high:.0%}) por isso.",
    ]
    audit = cfg.get("auditoria_amostra")
    if audit:
        lines += ["", "6. Auditoria de amostra: " + audit]
    lines += [
        "",
        "7. Intervalo: pessimista = acurácias no limite inferior, r dobrado e desconto máximo; otimista = limite "
        "superior, r pela metade e desconto mínimo.",
        "",
        "Limitações: o modelo supõe que os erros dos classificadores são independentes dado o acerto; erros de LLMs "
        "são correlacionados (mesmas armadilhas da árvore), o que deixa a estimativa otimista. Por isso r foi medido, "
        "o desconto do item 5 existe e o intervalo é largo. O classificador principal é um LLM, não um especialista: "
        "suas escolhas não são gabarito e não foram usadas como tal.",
    ]
    return "\n".join(lines) + "\n"
