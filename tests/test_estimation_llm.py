from pathlib import Path

from vicio_case.annotations import normalize_vote
from vicio_case.data import load_topics
from vicio_case.estimation import (
    posterior_correct,
    precision_given_agreement,
    triplet_accuracies,
)
from vicio_case.llm import match_option
from vicio_case.taxonomy import Taxonomy

ROOT = Path(__file__).resolve().parents[1]
TAX = Taxonomy(load_topics(ROOT / "data/input/temas.csv"))


def test_match_option_is_strict():
    options = ["Penal > Ação Penal", "Processo Penal > Ação Penal", "Penal > Prescrição"]
    assert match_option("Penal > Prescrição", options) == "Penal > Prescrição"
    assert match_option("prescrição", options) == "Penal > Prescrição"
    assert match_option("Ação Penal", options) is None          # ambíguo: não chuta
    assert match_option("B: I e III, apenas", options) is None  # respondeu a questão


def test_normalize_vote_rejects_inactive_root_and_unknown():
    assert not normalize_vote({"tema_central_id": 5078, "confianca": 0.9}, TAX)["valido"]  # inativo
    assert not normalize_vote({"tema_central_id": 5062, "confianca": 0.9}, TAX)["valido"]  # raiz
    assert not normalize_vote({"tema_central_id": 1, "confianca": 0.9}, TAX)["valido"]
    assert not normalize_vote({"tema_central_id": 5092, "confianca": 1.5}, TAX)["valido"]
    ok = normalize_vote({"tema_central_id": "5092", "extras_ids": "5093;5078;5092", "confianca": "0.9"}, TAX)
    assert ok["valido"] and ok["extras_ids"] == [5093]


def test_triplet_recovers_known_accuracies_on_synthetic_votes():
    import random
    rng = random.Random(1)
    truth = {f"Q{i}": rng.choice([5092, 5150, 5159, 5160, 5103]) for i in range(3000)}
    acc = {"a": 0.9, "b": 0.6, "c": 0.5}
    votes = {}
    for name, p in acc.items():
        votes[name] = {}
        for q, t in truth.items():
            tid = t if rng.random() < p else rng.choice([5226, 5227, 5225, 5224, 5223, 5212, 5213])
            votes[name][q] = {"tema_central_id": tid, "fora": False, "valido": True}
    est = triplet_accuracies(TAX, votes, list(truth))
    for name, p in acc.items():
        assert abs(est[name] - p) < 0.05


def test_posterior_increases_with_agreement_and_decreases_with_disagreement():
    prior = 0.85
    assert posterior_correct(prior, [(True, 0.5)], 0.15) > prior
    assert posterior_correct(prior, [(False, 0.5)], 0.15) < prior
    assert posterior_correct(prior, [(None, 0.5)], 0.15) == prior
    assert precision_given_agreement(0.9, 0.5, 0.1) > 0.98


def test_match_option_tolerates_only_small_typos():
    options = ["Processo Penal > Inquérito Policial > Conceito, Finalidade e Caractéristas do Inquérito Policial",
               "Processo Penal > Inquérito Policial > Juiz das Garantias"]
    assert match_option("Processo Penal > Inquérito Policial > Conceito, Finalidade e Características do Inquérito Policial",
                        options) == options[0]
    assert match_option("Processo Penal > Inquérito", options) is None


def test_match_option_handles_copied_suffix_and_theme_alias():
    options = ["Penal > Prescrição", "Penal > Punibilidade"]
    assert match_option("Penal > Prescrição  (subtemas: Outras Prescrições; Decadência)", options) == "Penal > Prescrição"
    sub = ["Furto", "Roubo", "(geral)"]
    assert match_option("Penal > Dos Crimes Contra o Patrimônio", sub,
                        {"Penal > Dos Crimes Contra o Patrimônio": "(geral)"}) == "(geral)"
