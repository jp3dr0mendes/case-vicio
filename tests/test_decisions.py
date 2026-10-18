from pathlib import Path

from vicio_case.data import load_topics
from vicio_case.decisions import decide
from vicio_case.taxonomy import Taxonomy

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    taxonomy = Taxonomy(load_topics(ROOT / "data/input/temas.csv"))
    candidates = [
        {"tema_id": 4370, "rank": 1, "titulo": "Modelos de Reação ao Delito"},
        {"tema_id": 4369, "rank": 2, "titulo": "Sistemas de Prevenção"},
        {"tema_id": 4368, "rank": 3, "titulo": "Criminologia no Estado Democrático de Direito"},
    ]
    return taxonomy, candidates


def test_publish_requires_two_high_confidence_publish_votes_same_branch():
    taxonomy, candidates = fixture()
    primary = {"decisao": "publicar", "tema_central_id": 4370, "extras_ids": [], "confianca": 0.98, "motivo": "", "justificativa_fora": ""}
    verifier = {"decisao": "publicar", "tema_central_id": 4368, "confianca": 0.96, "concorda": True, "motivo": ""}
    row = decide("Q0001", primary, verifier, candidates, taxonomy)
    assert row["decisao"] == "publicar"
    assert row["tema_central_id"] == 4370


def test_sibling_disagreement_routes_to_review():
    taxonomy, candidates = fixture()
    primary = {"decisao": "publicar", "tema_central_id": 4370, "extras_ids": [], "confianca": 0.99, "motivo": "", "justificativa_fora": ""}
    verifier = {"decisao": "publicar", "tema_central_id": 4369, "confianca": 0.99, "concorda": False, "motivo": "Outro subtema"}
    row = decide("Q0001", primary, verifier, candidates, taxonomy)
    assert row["decisao"] == "revisar"
    assert "divergiram" in row["motivo"]


def test_verifier_review_vote_prevents_autopublish():
    taxonomy, candidates = fixture()
    primary = {"decisao": "publicar", "tema_central_id": 4370, "extras_ids": [], "confianca": 0.99, "motivo": "", "justificativa_fora": ""}
    verifier = {"decisao": "revisar", "tema_central_id": 4368, "confianca": 0.99, "concorda": True, "motivo": "Ambíguo"}
    row = decide("Q0001", primary, verifier, candidates, taxonomy)
    assert row["decisao"] == "revisar"


def test_outside_requires_both_stages_to_agree():
    taxonomy, candidates = fixture()
    primary = {"decisao": "fora", "tema_central_id": None, "extras_ids": [], "confianca": 0.97, "motivo": "", "justificativa_fora": "Tema ausente"}
    verifier = {"decisao": "fora", "tema_central_id": None, "confianca": 0.95, "concorda": True, "motivo": "Nenhum tópico serve"}
    row = decide("Q0001", primary, verifier, candidates, taxonomy)
    assert row["decisao"] == "fora"
    assert row["tema_central_id"] == ""

    verifier["decisao"] = "revisar"
    row = decide("Q0001", primary, verifier, candidates, taxonomy)
    assert row["decisao"] == "revisar"
