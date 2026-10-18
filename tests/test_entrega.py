"""Valida o publicacao.csv entregue na raiz contra o contrato oficial (LEIA-ME.md)."""
import csv
from pathlib import Path

import pytest

from vicio_case.data import PUBLICATION_COLUMNS, load_questions, load_topics, validate_publication_rows
from vicio_case.taxonomy import Taxonomy, load_clone_map

ROOT = Path(__file__).resolve().parents[1]
DELIVERY = ROOT / "publicacao.csv"


@pytest.mark.skipif(not DELIVERY.exists(), reason="publicacao.csv ainda não gerado")
def test_delivered_csv_matches_official_contract():
    with DELIVERY.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == PUBLICATION_COLUMNS
        rows = list(reader)
    questions = load_questions(ROOT / "data/input/questoes.jsonl")
    taxonomy = Taxonomy(load_topics(ROOT / "data/input/temas.csv"), load_clone_map(ROOT / "config/nos_duplicados.json"))
    validate_publication_rows(rows, {q["id"] for q in questions}, taxonomy.selectable_ids)
    for row in rows:
        if row["decisao"] == "publicar":
            assert int(row["tema_central_id"]) not in taxonomy.clones
        assert row["confianca"].count(".") == 1


@pytest.mark.skipif(not DELIVERY.exists(), reason="publicacao.csv ainda não gerado")
def test_delivered_copy_is_identical_to_artifacts():
    artifact = ROOT / "artifacts" / "publicacao.csv"
    assert artifact.read_bytes() == DELIVERY.read_bytes()
    assert (ROOT / "artifacts" / "previsao.txt").read_bytes() == (ROOT / "previsao.txt").read_bytes()
