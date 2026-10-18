from pathlib import Path

import pytest

from vicio_case.data import load_topics
from vicio_case.decisions import (
    PUB_ALTA_CONF, PUB_EXATO, PUB_RAMO, REV_BAIXA_CONF, REV_CLONE, REV_DIVERGENCIA, REV_FALHA,
    REV_RISCO, REV_VETO, FORA, REV_FORA_SEM_CONSENSO, PolicyConfig, decide, load_ambiguity_groups,
)
from vicio_case.taxonomy import Taxonomy, load_clone_map

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def ctx():
    taxonomy = Taxonomy(load_topics(ROOT / "data/input/temas.csv"), load_clone_map(ROOT / "config/nos_duplicados.json"))
    groups = load_ambiguity_groups(ROOT / "config/grupos_ambiguos.json")
    return taxonomy, groups, PolicyConfig()


def vote(tid, conf=0.95, fora=False):
    return {"tema_central_id": tid, "extras_ids": [], "fora": fora, "confianca": conf,
            "justificativa": "", "valido": True, "erro": None}


INVALID = {"tema_central_id": None, "extras_ids": [], "fora": False, "confianca": 0.0,
           "justificativa": "", "valido": False, "erro": "x"}


def run(ctx, strong, *locals_):
    taxonomy, groups, config = ctx
    return decide("Q", strong, [(f"m{i}", v) for i, v in enumerate(locals_)], taxonomy, groups, config, 5087)


def test_exact_agreement_publishes(ctx):
    row = run(ctx, vote(5092), vote(5092), vote(5150))
    assert (row["decisao"], row["tema_central_id"], row["estrato"]) == ("publicar", 5092, PUB_EXATO)


def test_parent_child_agreement_publishes_the_more_general_node(ctx):
    row = run(ctx, vote(5159, 0.8), vote(5157), vote(5150))
    assert (row["decisao"], row["tema_central_id"], row["estrato"]) == ("publicar", 5157, PUB_RAMO)


def test_sibling_is_not_agreement(ctx):
    row = run(ctx, vote(5092, 0.8), vote(5093), vote(5093))
    assert row["decisao"] == "revisar"
    assert row["tema_central_id"] == 5092  # sugestão preservada


def test_veto_when_both_verifiers_agree_elsewhere(ctx):
    row = run(ctx, vote(5092, 0.95), vote(5150), vote(5150))
    assert (row["decisao"], row["estrato"]) == ("revisar", REV_VETO)


def test_high_confidence_without_agreement_or_veto_publishes(ctx):
    row = run(ctx, vote(5092, 0.95), vote(5150), vote(5159))
    assert (row["decisao"], row["estrato"]) == ("publicar", PUB_ALTA_CONF)


def test_medium_confidence_without_agreement_goes_to_review(ctx):
    row = run(ctx, vote(5092, 0.8), vote(5150), vote(5159))
    assert (row["decisao"], row["estrato"]) == ("revisar", REV_DIVERGENCIA)


def test_low_confidence_never_publishes(ctx):
    row = run(ctx, vote(5092, 0.6), vote(5092), vote(5092))
    assert (row["decisao"], row["estrato"]) == ("revisar", REV_BAIXA_CONF)


def test_clone_node_is_never_published(ctx):
    row = run(ctx, vote(6724), vote(6724), vote(6724))
    assert (row["decisao"], row["tema_central_id"], row["estrato"]) == ("revisar", 4704, REV_CLONE)


def test_invalid_strong_answer_goes_to_review_with_suggestion(ctx):
    row = run(ctx, INVALID, vote(5092), INVALID)
    assert (row["decisao"], row["tema_central_id"], row["estrato"]) == ("revisar", 5092, REV_FALHA)


def test_risk_zone_requires_all_verifiers(ctx):
    # 'Ação Penal' (Penal) tem concorrente em Processo Penal
    row = run(ctx, vote(5063, 0.95), vote(5063), vote(5159))
    assert (row["decisao"], row["estrato"]) == ("revisar", REV_RISCO)
    row = run(ctx, vote(5063, 0.95), vote(5063), vote(5064))
    assert row["decisao"] == "publicar"


def test_fora_needs_consensus_otherwise_review(ctx):
    row = run(ctx, vote(None, 0.95, fora=True), vote(None, fora=True), vote(5159))
    assert (row["decisao"], row["tema_central_id"], row["estrato"]) == ("fora", "", FORA)
    row = run(ctx, vote(None, 0.95, fora=True), vote(5159), vote(5160))
    assert (row["decisao"], row["estrato"]) == ("revisar", REV_FORA_SEM_CONSENSO)
    assert row["tema_central_id"] == 5159


def test_no_valid_verifier_never_publishes_even_with_high_confidence(ctx):
    row = run(ctx, vote(5092, 0.95), INVALID, None)
    assert (row["decisao"], row["estrato"]) == ("revisar", REV_FALHA)
