"""Estimativa de precisão SEM gabarito.

Não há rótulos de referência no pacote do case, então a precisão é PREVISTA, não medida.
Método (documentado em docs/estimativa_precisao.md):

1. Três classificadores independentes (forte, verificador local primário, segundo local)
   votam em todas as questões. Medimos a taxa de concordância de RAMO entre cada par.
2. Modelo de acurácias latentes (triplet / Dawid-Skene simplificado, independência
   condicional): a_ij ~= p_i * p_j  =>  p_i = sqrt(a_ij * a_ik / a_jk).
   Intervalos por bootstrap sobre as questões.
3. Precisão das publicadas = P(forte certo | forte e verificador concordam)
   = p_F p_V / (p_F p_V + (1-p_F)(1-p_V) r), onde r é a chance de dois erros caírem no mesmo
   ramo (erros correlacionados). r não é identificável com 3 anotadores: usamos uma faixa
   declarada e a estimamos empiricamente pela concordância entre os dois locais quando ambos
   discordam do forte.
4. O modelo NÃO captura a ambiguidade do gabarito (especialista escolher outro nó defensável);
   esse risco entra separadamente na previsão final (previsao.txt).
"""
from __future__ import annotations

import math
import random
from typing import Any

from .taxonomy import Taxonomy


def _agrees(taxonomy: Taxonomy, left: dict[str, Any] | None, right: dict[str, Any] | None) -> bool | None:
    """None quando algum voto é inválido/fora (não entra na conta)."""
    if not left or not right or not left.get("valido") or not right.get("valido"):
        return None
    if left["fora"] or right["fora"]:
        return None
    return taxonomy.branch_related(int(left["tema_central_id"]), int(right["tema_central_id"]))


def pairwise_agreement(taxonomy: Taxonomy, votes: dict[str, dict[str, dict[str, Any]]], ids: list[str]) -> dict[str, Any]:
    names = list(votes)
    out: dict[str, Any] = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            flags = [_agrees(taxonomy, votes[a].get(q), votes[b].get(q)) for q in ids]
            valid = [f for f in flags if f is not None]
            out[f"{a}~{b}"] = {"n": len(valid), "taxa": (sum(valid) / len(valid)) if valid else None}
    return out


def triplet_accuracies(taxonomy: Taxonomy, votes: dict[str, dict[str, dict[str, Any]]], ids: list[str]) -> dict[str, float] | None:
    names = list(votes)
    if len(names) != 3:
        return None
    usable = [q for q in ids if all(_agrees(taxonomy, votes[n].get(q), votes[n].get(q)) is not None for n in names)]
    if len(usable) < 10:
        return None

    def rate(a: str, b: str) -> float:
        flags = [_agrees(taxonomy, votes[a][q], votes[b][q]) for q in usable]
        return max(1e-6, sum(bool(f) for f in flags) / len(flags))

    f, v, s = names
    a_fv, a_fs, a_vs = rate(f, v), rate(f, s), rate(v, s)
    return {
        f: min(1.0, math.sqrt(a_fv * a_fs / a_vs)),
        v: min(1.0, math.sqrt(a_fv * a_vs / a_fs)),
        s: min(1.0, math.sqrt(a_fs * a_vs / a_fv)),
        "_n": len(usable),
    }


def correlated_error_rate(taxonomy: Taxonomy, votes: dict[str, dict[str, dict[str, Any]]], ids: list[str]) -> float | None:
    """Proxy de r: quando os dois locais discordam do forte, com que frequência concordam entre si."""
    names = list(votes)
    if len(names) != 3:
        return None
    f, v, s = names
    both_disagree = [q for q in ids
                     if _agrees(taxonomy, votes[f].get(q), votes[v].get(q)) is False
                     and _agrees(taxonomy, votes[f].get(q), votes[s].get(q)) is False]
    flags = [_agrees(taxonomy, votes[v][q], votes[s][q]) for q in both_disagree]
    flags = [x for x in flags if x is not None]
    return (sum(flags) / len(flags)) if flags else None


def precision_given_agreement(p_f: float, p_v: float, r: float) -> float:
    num = p_f * p_v
    den = num + (1 - p_f) * (1 - p_v) * r
    return num / den if den else 0.0


def accuracy_given_disagreement(p_f: float, p_v: float, r: float) -> float:
    right = p_f * (1 - p_v)
    wrong = (1 - p_f) * p_v + (1 - p_f) * (1 - p_v) * (1 - r)
    return right / (right + wrong) if (right + wrong) else 0.0


def bootstrap_accuracies(taxonomy: Taxonomy, votes: dict[str, dict[str, dict[str, Any]]], ids: list[str],
                         rounds: int = 500, seed: int = 13) -> dict[str, tuple[float, float]] | None:
    rng = random.Random(seed)
    samples: dict[str, list[float]] = {n: [] for n in votes}
    for _ in range(rounds):
        resample = [rng.choice(ids) for _ in ids]
        # IDs repetidos: renomeia para manter o peso do bootstrap
        keyed = {f"{q}#{i}": q for i, q in enumerate(resample)}
        boot_votes = {n: {k: votes[n].get(q) for k, q in keyed.items()} for n in votes}
        est = triplet_accuracies(taxonomy, boot_votes, list(keyed))
        if est:
            for n in votes:
                samples[n].append(est[n])
    if not samples or not all(samples.values()):
        return None
    out = {}
    for n, values in samples.items():
        values.sort()
        out[n] = (values[int(0.05 * len(values))], values[int(0.95 * len(values)) - 1])
    return out


# ---------------------------------------------------------------------------
# Calibração por faixa de confiança e posterior por questão
# ---------------------------------------------------------------------------

BUCKETS = (("alta", 0.9, 1.01), ("media", 0.75, 0.9), ("baixa", 0.0, 0.75))


def bucket_of(confidence: float) -> str:
    for name, low, high in BUCKETS:
        if low <= confidence < high:
            return name
    return "baixa"


def posterior_correct(prior: float, pattern: list[tuple[bool | None, float]], r: float) -> float:
    """P(tema do classificador forte certo | padrão de concordância dos verificadores).

    pattern: [(concorda_no_ramo | None se voto inválido, acurácia_do_verificador)].
    Se o forte está certo, um verificador concorda ~ quando ele também acerta (p_i).
    Se o forte está errado, o verificador só concorda se errar no mesmo ramo ((1-p_i)*r)."""
    like_right, like_wrong = prior, 1 - prior
    for agrees, p_i in pattern:
        if agrees is None:
            continue
        like_right *= p_i if agrees else (1 - p_i)
        like_wrong *= (1 - p_i) * r if agrees else 1 - (1 - p_i) * r
    total = like_right + like_wrong
    return like_right / total if total else 0.0


def bucket_accuracies(taxonomy: Taxonomy, votes: dict[str, dict[str, dict[str, Any]]],
                      strong_name: str, ids: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, low, high in BUCKETS:
        subset = [q for q in ids if low <= (votes[strong_name].get(q) or {}).get("confianca", 0) < high]
        out[name] = {"n": len(subset), "acuracias": triplet_accuracies(taxonomy, votes, subset),
                     "ic90": bootstrap_accuracies(taxonomy, votes, subset, rounds=300)}
    return out
